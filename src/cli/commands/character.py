"""Character commands."""

from __future__ import annotations

import json
import random
from collections import Counter
from typing import Any

import click

from .. import db as _db
from ..campaign import active_campaign_id, pg_connection
from ..character_display import write_public_character_mirror as _write_public_character_mirror
from ..config import get_paths
from ..constants import ATTRIBUTE_TIERS, ATTRIBUTES, SKILL_TIERS
from ..errors import GlassError, agent_instruction
from ..facts import FactSpec, set_fact_specs
from ..role import assert_character_writable, current_role, require_dm
from ..state import append_audit, commit, current_mode_record, load_state, queue_event
from ..validation import assert_attribute_name, assert_valid_item_id, validate_key_values
from ..yaml_io import command_params, emit, read_body


@click.group()
def character() -> None:
    """Character sheet and hard-state commands."""


@character.command("new")
@click.argument("character_id")
@click.option("--player", "player_id", required=True)
@click.option("--name", required=True)
@click.option("--species", "--race", "species", required=True)
@click.option("--culture", required=True)
@click.option("--archetype", required=True)
@click.option("--org-role", "organization_role", required=True)
@click.option("--pronouns", default="")
@click.option("--bio", required=True)
@click.option("--goal", "goals", multiple=True, help="Repeat 2-3 times.")
@click.option(
    "--primary-drive",
    required=True,
    help="Free-text primary drive; must differ from other existing PCs.",
)
@click.option(
    "--positive-trait",
    required=True,
    help="Visible fun/warm/playful trait, not a work habit or competence signal.",
)
@click.option(
    "--table-presence",
    required=True,
    help="A recurring social bit or personality behavior other players can use.",
)
@click.option(
    "--non-work-want",
    required=True,
    help="A want not about the job, mission, profit, safety, or competence.",
)
@click.option(
    "--opening-social-action",
    required=True,
    help="A direct social action toward another PC for the public intro.",
)
@click.option(
    "--life-prompt",
    "life_prompts",
    multiple=True,
    help="Repeat 2-3 times as 'prompt=concrete answer'.",
)
@click.option(
    "--pull-utilization",
    required=True,
    help="Non-adjacent source and identity thesis.",
)
@click.option("--hp", "hp_max", type=int, default=10)
@click.option(
    "--attribute",
    "attribute_values",
    multiple=True,
    help="Repeatable name=tier.",
)
@click.option(
    "--skill",
    "skill_values",
    multiple=True,
    help="Repeatable name=tier.",
)
@click.option("--tag", "tags", multiple=True)
@click.pass_context
def character_new(
    ctx: click.Context,
    character_id: str,
    player_id: str,
    name: str,
    species: str,
    culture: str,
    archetype: str,
    organization_role: str,
    pronouns: str,
    bio: str,
    goals: tuple[str, ...],
    primary_drive: str,
    positive_trait: str,
    table_presence: str,
    non_work_want: str,
    opening_social_action: str,
    life_prompts: tuple[str, ...],
    pull_utilization: str,
    hp_max: int,
    attribute_values: tuple[str, ...],
    skill_values: tuple[str, ...],
    tags: tuple[str, ...],
) -> None:
    create_character_service(
        command_path=ctx,
        emit_output=True,
        character_id=character_id,
        player_id=player_id,
        name=name,
        species=species,
        culture=culture,
        archetype=archetype,
        organization_role=organization_role,
        pronouns=pronouns,
        bio=bio,
        goals=goals,
        primary_drive=primary_drive,
        positive_trait=positive_trait,
        table_presence=table_presence,
        non_work_want=non_work_want,
        opening_social_action=opening_social_action,
        life_prompts=life_prompts,
        pull_utilization=pull_utilization,
        hp_max=hp_max,
        attribute_values=attribute_values,
        skill_values=skill_values,
        tags=tags,
    )


def create_character_service(
    *,
    command_path: click.Context | str = "glass_character_new",
    emit_output: bool = False,
    character_id: str,
    player_id: str,
    name: str,
    species: str,
    culture: str,
    archetype: str,
    organization_role: str,
    pronouns: str = "",
    bio: str,
    goals: tuple[str, ...],
    primary_drive: str,
    positive_trait: str,
    table_presence: str,
    non_work_want: str,
    opening_social_action: str,
    life_prompts: tuple[str, ...],
    pull_utilization: str,
    hp_max: int = 10,
    attribute_values: tuple[str, ...] = (),
    skill_values: tuple[str, ...] = (),
    starting_items: tuple[dict[str, Any], ...] = (),
    fact_specs: tuple[FactSpec, ...] = (),
    tags: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Create one character from already-shaped runtime inputs."""

    role = current_role()
    if role.kind == "player" and player_id != role.actor:
        raise GlassError(
            agent_instruction(
                "players may create only their own character",
                f"Use `--player {role.actor}` from this player turn, or ask the DM to create a character for another player.",
            )
        )
    name = _require_nonempty(name, "--name")
    species = _require_nonempty(species, "--species")
    culture = _require_nonempty(culture, "--culture")
    archetype = _require_nonempty(archetype, "--archetype")
    organization_role = _require_nonempty(organization_role, "--org-role")
    bio = _require_nonempty(bio, "--bio")
    normalized_goals = _normalize_goals(goals)
    normalized_primary_drive = _normalize_primary_drive(primary_drive)
    positive_trait = _require_concrete_note(
        positive_trait,
        "--positive-trait",
        "Name a visible fun, warm, playful, or quirky behavior that is not just work competence.",
    )
    table_presence = _require_concrete_note(
        table_presence,
        "--table-presence",
        "Name a recurring social bit or personality behavior another player can recognize and respond to.",
    )
    non_work_want = _require_concrete_note(
        non_work_want,
        "--non-work-want",
        "Name something the character wants that is not profit, safety, the mission, or doing the job correctly.",
    )
    opening_social_action = _require_concrete_note(
        opening_social_action,
        "--opening-social-action",
        "Name one direct social action toward another PC that belongs in the public intro.",
    )
    normalized_life_prompts = _normalize_life_prompt_answers(life_prompts)
    pull_utilization_note = _require_pull_utilization_note(
        pull_utilization,
        "--pull-utilization",
    )
    if hp_max <= 0:
        raise GlassError(
            agent_instruction(
                "`--hp` must be greater than zero",
                "Use a positive maximum HP value for the character.",
            )
        )
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    campaign_id = active_campaign_id()

    attributes = {attribute: "standard" for attribute in ATTRIBUTES}
    attributes.update(validate_key_values(attribute_values, ATTRIBUTE_TIERS, "attribute"))
    for attribute_name in attributes:
        assert_attribute_name(attribute_name)
    skills = validate_key_values(skill_values, SKILL_TIERS, "skill")
    _validate_starting_skill_budget(skills)
    inventory = _normalize_starting_inventory(starting_items)
    mode = current_mode_record(state) or {}
    active_scene = str(mode.get("scene_id") or "").strip() or None

    with pg_connection() as conn:
        if _db.character_exists(conn, campaign_id, character_id):
            raise GlassError(
                agent_instruction(
                    f"character already exists in campaign {campaign_id!r}: {character_id}",
                    "Use a different character id, or update the existing character instead of creating it again.",
                )
            )
        _validate_primary_drive_available(conn, campaign_id, normalized_primary_drive)
    fact_result = set_fact_specs(
        campaign_id=campaign_id,
        specs=list(fact_specs),
        actor=role.actor,
        turn_id=str(state.get("active_turn_id") or "") or None,
        mode=str(mode.get("mode") or "") or None,
        scene_id=active_scene,
        require_available=bool(fact_specs),
    )
    with pg_connection() as conn:
        record = _db.character_create(
            conn,
            campaign_id=campaign_id,
            character_id=character_id,
            player_id=player_id,
            name=name,
            archetype=archetype,
            species=species,
            culture=culture,
            organization_role=organization_role,
            pronouns=pronouns,
            bio=bio,
            goals=normalized_goals,
            primary_drive=normalized_primary_drive,
            positive_trait=positive_trait,
            table_presence=table_presence,
            non_work_want=non_work_want,
            opening_social_action=opening_social_action,
            life_prompt_answers=normalized_life_prompts,
            pull_utilization_note=pull_utilization_note,
            attributes=attributes,
            skills=skills,
            hp_max=hp_max,
            inventory=inventory,
            tags=list(tags),
        )
    mirror_result = _write_public_character_mirror(paths, campaign_id, record)

    queue_event(
        state,
        role.actor,
        f"character new {character_id} ({record['name']}, {player_id})",
    )
    commit(
        paths,
        state,
        command_path,
        "character.new",
        command_params(character_id=character_id, player_id=player_id),
        {"character": record, "facts": fact_result, "mirror": mirror_result},
        emit_output=emit_output,
    )
    return {"character": record, "facts": fact_result, "mirror": mirror_result}


@character.command("get")
@click.argument("character_id")
@click.pass_context
def character_get(ctx: click.Context, character_id: str) -> None:
    emit(get_character_service(command_path=ctx, character_id=character_id))


def get_character_service(
    *,
    command_path: click.Context | str = "glass_character_get",
    character_id: str,
    agent_projection: bool = False,
) -> dict[str, Any]:
    """Read one character record visible to the current role."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    campaign_id = active_campaign_id()
    with pg_connection() as conn:
        character = _db.character_get(conn, campaign_id, character_id)
        role = current_role()
        signature_moves = _db.character_signature_moves_list(
            conn,
            campaign_id=campaign_id,
            character_id=character_id,
            visibility=None if role.kind in {"dm", "operator"} else "public",
        )
    if character is None:
        raise GlassError(_unknown_character_message(character_id, campaign_id))
    character = {**character, "signature_moves": signature_moves}
    if agent_projection:
        character = character_agent_view(character, role=role)
    result = {"character": character}
    append_audit(
        paths,
        state,
        command_path,
        "character.get",
        command_params(character_id=character_id),
        result,
    )
    return result


@character.command("list")
@click.pass_context
def character_list(ctx: click.Context) -> None:
    emit(list_characters_service(command_path=ctx))


def list_characters_service(
    *,
    command_path: click.Context | str = "glass_character_list",
) -> dict[str, Any]:
    """List compact character records for the current campaign."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    campaign_id = active_campaign_id()
    with pg_connection() as conn:
        characters = _db.character_list(conn, campaign_id)
    result = {
        "campaign_id": campaign_id,
        "characters": [
            {
                "character_id": c["character_id"],
                "player_id": c["player_id"],
                "name": c["name"],
                "species": c["species"],
                "culture": c["culture"],
                "archetype": c["archetype"],
                "organization_role": c["organization_role"],
                "primary_drive": c["primary_drive"],
                "hp": c["hp"],
                "momentum": c["momentum"],
            }
            for c in characters
        ],
    }
    append_audit(paths, state, command_path, "character.list", {}, result)
    return result


@character.command("bulk-get")
@click.argument("character_ids", nargs=-1)
@click.option("--all", "include_all", is_flag=True, help="Return every character.")
@click.pass_context
def character_bulk_get(
    ctx: click.Context,
    character_ids: tuple[str, ...],
    include_all: bool,
) -> None:
    """Read multiple full character records with one tool call."""

    emit(
        bulk_get_characters_service(
            command_path=ctx,
            character_ids=character_ids,
            include_all=include_all,
        )
    )


def bulk_get_characters_service(
    *,
    command_path: click.Context | str = "glass_character_bulk_get",
    character_ids: tuple[str, ...] = (),
    include_all: bool = False,
    agent_projection: bool = False,
) -> dict[str, Any]:
    """Read multiple full character records visible to the current role."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    ids = _unique_nonempty(character_ids)
    missing: list[str] = []
    if include_all and ids:
        raise GlassError(
            agent_instruction(
                "use either character ids or `--all`, not both",
                "Run `glass character bulk-get --all` for every character, or list the specific character ids without `--all`.",
            )
        )
    if not include_all and not ids:
        raise GlassError(
            agent_instruction(
                "character bulk-get needs a target",
                "Pass one or more character ids, or use `glass character bulk-get --all`.",
            )
        )

    role = current_role()
    with pg_connection() as conn:
        if include_all:
            characters = _db.character_list(conn, campaign_id)
        else:
            characters = []
            for character_id in ids:
                character = _db.character_get(conn, campaign_id, character_id)
                if character is None:
                    missing.append(character_id)
                else:
                    characters.append(character)
        moves = _db.character_signature_moves_list(
            conn,
            campaign_id=campaign_id,
            visibility=None if role.kind in {"dm", "operator"} else "public",
        )
    if missing:
        raise GlassError(
            agent_instruction(
                f"unknown character(s) in campaign {campaign_id!r}: {', '.join(missing)}",
                "Use character ids returned by `glass character list`, `glass character bulk-get --all`, or visible in the injected prompt.",
            )
        )

    moves_by_character: dict[str, list[dict[str, Any]]] = {}
    for move in moves:
        moves_by_character.setdefault(str(move["character_id"]), []).append(move)
    characters = [
        {
            **character,
            "signature_moves": moves_by_character.get(
                str(character["character_id"]),
                [],
            ),
        }
        for character in characters
    ]
    if agent_projection:
        characters = [character_agent_view(character, role=role) for character in characters]

    result: dict[str, Any] = {
        "campaign_id": campaign_id,
        "count": len(characters),
        "characters": characters,
    }

    append_audit(
        paths,
        state,
        command_path,
        "character.bulk-get",
        command_params(character_ids=ids, all=include_all),
        result,
    )
    return result


def character_agent_view(
    character: dict[str, Any],
    *,
    role: Any,
) -> dict[str, Any]:
    """Return the MCP-facing character view for the current turn actor."""

    view: dict[str, Any] = {
        "character_id": character.get("character_id"),
        "player_id": character.get("player_id"),
        "name": character.get("name"),
        "species": character.get("species"),
        "culture": character.get("culture"),
        "archetype": character.get("archetype"),
        "organization_role": character.get("organization_role"),
        "pronouns": character.get("pronouns"),
        "bio": character.get("bio"),
        "goals": character.get("goals") or [],
        "primary_drive": character.get("primary_drive"),
        "attributes": character.get("attributes") or {},
        "skills": character.get("skills") or {},
        "skill_meta": character.get("skill_meta") or {},
        "hp": character.get("hp"),
        "momentum": character.get("momentum"),
        "inventory": character.get("inventory") or [],
        "signature_moves": character.get("signature_moves") or [],
        "tags": character.get("tags") or [],
        "xp": character.get("xp"),
        "level": character.get("level"),
    }
    if role.kind == "player" and str(character.get("player_id") or "") == role.actor:
        view["profile"] = {
            "positive_trait": character.get("positive_trait"),
            "table_presence": character.get("table_presence"),
            "non_work_want": character.get("non_work_want"),
            "opening_social_action": character.get("opening_social_action"),
            "life_prompt_answers": character.get("life_prompt_answers") or [],
            "pull": character.get("pull_utilization_note"),
        }
    return view


@character.command("mirror")
@click.argument("character_id")
@click.pass_context
def character_mirror(ctx: click.Context, character_id: str) -> None:
    """Retired: character rows are read through Glass commands."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    campaign_id = active_campaign_id()
    with pg_connection() as conn:
        character = _db.character_get(conn, campaign_id, character_id)
    if character is None:
        raise GlassError(_unknown_character_message(character_id, campaign_id))
    assert_character_writable(character)
    result = {
        "character_id": character_id,
        "status": "retired",
        "detail": "character markdown mirrors are not written; use character commands",
    }
    commit(
        paths,
        state,
        ctx,
        "character.mirror",
        command_params(character_id=character_id),
        result,
        save=False,
    )


@character.command("bulk-update")
@click.option("--json", "payload_text", help="JSON payload for one or more updates.")
@click.option("--from", "from_file", help="Read JSON payload from this file, or '-' for stdin.")
@click.option(
    "--mirror/--no-mirror",
    "mirror_override",
    default=None,
    help="Override per-update mirror behavior for every updated character.",
)
@click.pass_context
def character_bulk_update(
    ctx: click.Context,
    payload_text: str | None,
    from_file: str | None,
    mirror_override: bool | None,
) -> None:
    """Apply multiple character mutations from one JSON payload."""

    role = current_role()
    if payload_text is not None and from_file is not None:
        raise GlassError(
            agent_instruction(
                "use either `--json` or `--from`, not both",
                "Pass inline JSON with `--json <payload>`, or read JSON from a file/stdin with `--from <path-or-->`.",
            )
        )
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    payload = _read_json_payload(read_body(payload_text, from_file), "character bulk update")
    updates = _normalize_bulk_update_payload(payload, mirror_override=mirror_override)

    results: list[dict[str, Any]] = []
    with pg_connection() as conn:
        for update in updates:
            character_id = update["character_id"]
            character = _db.character_get(conn, campaign_id, character_id)
            if character is None:
                raise GlassError(_unknown_character_message(character_id, campaign_id))
            assert_character_writable(character)

            operations: list[str] = []
            updated = character
            set_fields = _normalize_character_set_fields(update["set"], updated)
            if "skills" in set_fields and _is_character_creation_mode(state):
                _validate_starting_skill_budget(set_fields["skills"])
            elif "skills" in set_fields:
                cap = _db.skill_slot_cap(character["level"])
                if len(set_fields["skills"]) > cap:
                    raise GlassError(
                        agent_instruction(
                            f"skill update would exceed slot cap for {character_id}: {len(set_fields['skills'])} > {cap} at level {character['level']}",
                            "Drop a skill from the payload, or wait until level-up (each level adds one slot).",
                            "Use `glass character skill-declare` for single-skill additions; the cap is enforced consistently across paths.",
                        )
                    )
            if "primary_drive" in set_fields:
                _validate_primary_drive_available(
                    conn,
                    campaign_id,
                    set_fields["primary_drive"],
                    exclude_character_id=character_id,
                )
            if set_fields:
                updated = _db.character_update_fields(
                    conn,
                    campaign_id=campaign_id,
                    character_id=character_id,
                    fields=set_fields,
                )
                operations.append("set")

            hp_delta = update.get("hp_delta")
            if hp_delta is not None:
                updated, before, after = _db.character_update_hp(
                    conn,
                    campaign_id=campaign_id,
                    character_id=character_id,
                    delta=hp_delta,
                )
                operations.append(f"hp {before}->{after}")

            momentum = update.get("momentum")
            if momentum is not None:
                updated, before, after = _db.character_update_momentum(
                    conn,
                    campaign_id=campaign_id,
                    character_id=character_id,
                    value=momentum,
                )
                operations.append(f"momentum {before}->{after}")

            inventory_ops = update["inventory_add"] or update["inventory_rm"]
            if inventory_ops:
                inventory = [dict(item) for item in updated["inventory"]]
                inventory_changes: list[dict[str, Any]] = []
                for item in update["inventory_add"]:
                    inventory_changes.append(_inventory_add(inventory, item))
                for item in update["inventory_rm"]:
                    inventory_changes.append(_inventory_rm(inventory, item))
                updated = _db.character_set_inventory(
                    conn,
                    campaign_id=campaign_id,
                    character_id=character_id,
                    inventory=inventory,
                )
                operations.append("inventory")
            else:
                inventory_changes = []

            signature_result = None
            if update["signature_moves"]:
                signature_result = _add_signature_moves_bulk(
                    conn,
                    campaign_id,
                    updated,
                    update["signature_moves"],
                    actor=role.actor,
                )
                operations.append("signature_moves")

            mirror_result = None
            should_mirror = bool(
                update["mirror"]
                or set_fields
                or hp_delta is not None
                or momentum is not None
                or inventory_ops
            )
            if should_mirror:
                mirror_result = _write_public_character_mirror(paths, campaign_id, updated)
                operations.append("mirror")

            results.append(
                {
                    "character_id": character_id,
                    "operations": operations,
                    "character": updated,
                    "inventory_changes": inventory_changes,
                    "signature_moves": signature_result,
                    "mirror": mirror_result,
                }
            )

    queue_event(
        state,
        role.actor,
        f"character bulk-update {len(results)} character(s)",
    )
    result = {
        "campaign_id": campaign_id,
        "updated_count": len(results),
        "updates": results,
    }
    commit(
        paths,
        state,
        ctx,
        "character.bulk-update",
        command_params(count=len(results)),
        result,
    )


@character.command("signature-status")
@click.argument("character_id")
@click.pass_context
def character_signature_status(ctx: click.Context, character_id: str) -> None:
    """Show signature move slots and current typed entries."""

    emit(signature_status_service(command_path=ctx, character_id=character_id))


def signature_status_service(
    *,
    command_path: click.Context | str = "glass_character_signature_status",
    character_id: str,
) -> dict[str, Any]:
    """Show signature move slots and current typed entries."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    with pg_connection() as conn:
        character = _db.character_get(conn, campaign_id, character_id)
        moves = _db.character_signature_moves_list(
            conn,
            campaign_id=campaign_id,
            character_id=character_id,
            visibility=None if role.kind in {"dm", "operator"} else "public",
        )
    if character is None:
        raise GlassError(_unknown_character_message(character_id, campaign_id))

    result = _signature_status(character, moves)
    append_audit(
        paths,
        state,
        command_path,
        "character.signature-status",
        command_params(character_id=character_id),
        result,
    )
    return result


@character.command("signature-add")
@click.argument("character_id")
@click.argument("name")
@click.option(
    "--descriptor",
    required=True,
    help=(
        "Required. Generic noun phrase reached for in ordinary turn prose. "
        "The positional `<name>` is the prose name (used only when the "
        "character names the move aloud); the descriptor is what narration "
        "should reach for instead. Example: positional name "
        "'Ride The Line Down', --descriptor 'the fall-line ride'. "
        "Example: positional name 'Quiet Door', "
        "--descriptor 'her old lockpick trick'."
    ),
)
@click.option("--body", default="", help="Freeform prose body for the move.")
@click.option("--look", default="", help="What the move looks/sounds/feels like.")
@click.option("--use", "usual_use", default="", help="When the character reaches for it.")
@click.option("--tell", default="", help="Trace, cost, risk, or who might recognize it.")
@click.pass_context
def character_signature_add(
    ctx: click.Context,
    character_id: str,
    name: str,
    descriptor: str,
    body: str,
    look: str,
    usual_use: str,
    tell: str,
) -> None:
    """Append one signature move if the character has an open slot."""

    add_signature_move_service(
        command_path=ctx,
        emit_output=True,
        character_id=character_id,
        name=name,
        descriptor=descriptor,
        body=body,
        look=look,
        usual_use=usual_use,
        tell=tell,
    )


def add_signature_move_service(
    *,
    command_path: click.Context | str = "glass_character_signature_add",
    emit_output: bool = False,
    character_id: str,
    name: str,
    descriptor: str,
    body: str = "",
    look: str = "",
    usual_use: str = "",
    tell: str = "",
) -> dict[str, Any]:
    """Append one signature move if the character has an open slot."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    with pg_connection() as conn:
        character = _db.character_get(conn, campaign_id, character_id)
    if character is None:
        raise GlassError(_unknown_character_message(character_id, campaign_id))
    role = assert_character_writable(character)

    name = _require_nonempty(name, "name")
    descriptor = _require_nonempty(descriptor, "--descriptor")
    move_body = _signature_move_body(
        body=body,
        look=look,
        usual_use=usual_use,
        tell=tell,
        descriptor=descriptor,
    )
    with pg_connection() as conn:
        try:
            move = _db.character_signature_move_add(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                name=name,
                descriptor=descriptor,
                body=move_body,
                actor=role.actor,
            )
            moves = _db.character_signature_moves_list(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                visibility="public",
            )
        except ValueError as exc:
            raise _signature_move_db_error(character, name, str(exc)) from exc

    queue_event(state, role.actor, f"signature move added for {character_id}: {name}")
    slots = _signature_move_slots(character["level"])
    result = {
        "character_id": character_id,
        "player_id": character["player_id"],
        "level": character["level"],
        "slots": slots,
        "used": len(moves),
        "available": max(0, slots - len(moves)),
        "move": move,
    }
    commit(
        paths,
        state,
        command_path,
        "character.signature-add",
        command_params(character_id=character_id, name=name),
        result,
        emit_output=emit_output,
    )
    return result


@character.command("skill-declare")
@click.argument("character_id")
@click.argument("skill")
@click.option(
    "--name",
    "prose_name",
    required=True,
    help=(
        "Required. Prose name of the skill, used only when the character "
        "names the craft aloud. Example for the slug "
        "`read-parallel-resonance-bands`: --name 'Read Parallel "
        "Resonance Bands'. Example for `talk-down-crowds`: "
        "--name 'Talk Down Crowds'."
    ),
)
@click.option(
    "--descriptor",
    required=True,
    help=(
        "Required. Generic verb or short phrase reached for in ordinary "
        "turn prose. Example for `read-parallel-resonance-bands`: "
        "--descriptor 'reading the bands'. Example for "
        "`talk-down-crowds`: --descriptor 'talking the crowd down'."
    ),
)
@click.pass_context
def character_skill_declare(
    ctx: click.Context,
    character_id: str,
    skill: str,
    prose_name: str,
    descriptor: str,
) -> None:
    """Declare a new skill at `fool` tier if the character has a free slot.

    Cap is `3 + level`: 4 at level 1, 5 at level 2, etc. The skill starts at
    `fool` with 0 skill xp and advances by use through normal rolls (5 xp ->
    apprentice, 15 -> artisan, 30 -> virtuoso).

    Use this command when adding a skill outside the roll command. During a
    roll, `--save-skill` declares a new skill before resolving the check.
    """
    declare_skill_service(
        command_path=ctx,
        emit_output=True,
        character_id=character_id,
        skill=skill,
        prose_name=prose_name,
        descriptor=descriptor,
    )


def declare_skill_service(
    *,
    command_path: click.Context | str = "glass_character_skill_declare",
    emit_output: bool = False,
    character_id: str,
    skill: str,
    prose_name: str,
    descriptor: str,
) -> dict[str, Any]:
    """Declare a new skill at `fool` tier if the character has a free slot."""

    skill_name = (skill or "").strip()
    if not skill_name:
        raise GlassError(
            agent_instruction(
                "skill slug is required",
                "Pass a non-empty skill slug as the second positional argument.",
            )
        )
    prose_name = _require_nonempty(prose_name, "--name")
    descriptor = _require_nonempty(descriptor, "--descriptor")
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)

    with pg_connection() as conn:
        existing = _db.character_get(conn, campaign_id, character_id)
        if existing is None:
            raise GlassError(_unknown_character_message(character_id, campaign_id))
        role = assert_character_writable(existing)
        try:
            updated, was_new = _db.character_declare_skill(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                skill=skill_name,
                prose_name=prose_name,
                descriptor=descriptor,
            )
        except _db.SkillSlotCapFull as exc:
            raise GlassError(
                _skill_slot_cap_full_message(character_id, exc)
            ) from None
        except LookupError:
            raise GlassError(_unknown_character_message(character_id)) from None

    if not was_new:
        existing_tier = updated["skills"].get(skill_name, "fool")
        raise GlassError(
            agent_instruction(
                f"skill {skill_name!r} already declared for {character_id} at {existing_tier}",
                "Roll the existing skill instead of redeclaring it.",
                "Use `glass character get <id>` to see all declared skills and their tiers.",
            )
        )

    cap = _db.skill_slot_cap(updated["level"])
    used = len(updated["skills"])
    queue_event(
        state,
        role.actor,
        f"{character_id} declared skill {skill_name} (fool, slot {used}/{cap})",
    )
    mirror_result = _write_public_character_mirror(paths, campaign_id, updated)
    result = {
        "character_id": character_id,
        "skill": skill_name,
        "name": prose_name,
        "descriptor": descriptor,
        "starting_tier": "fool",
        "level": updated["level"],
        "slots_used": used,
        "slots_cap": cap,
        "slots_available": cap - used,
        "mirror": mirror_result,
    }
    commit(
        paths,
        state,
        command_path,
        "character.skill-declare",
        command_params(
            character_id=character_id,
            skill=skill_name,
            name=prose_name,
            descriptor=descriptor,
        ),
        result,
        emit_output=emit_output,
    )
    return result


def _skill_slot_cap_full_message(
    character_id: str, exc: "_db.SkillSlotCapFull"
) -> str:
    return agent_instruction(
        f"no free skill slots for {character_id}: {exc.used}/{exc.cap} declared at level {exc.level}",
        "Do not declare a new skill now.",
        "Roll an existing skill that fits the action, or wait for the next level (each level adds one slot).",
        "Use `glass character get <id>` to see declared skills.",
    )


def resolve_skill_for_roll(
    conn: "_db.psycopg.Connection[Any]",  # type: ignore[name-defined]
    *,
    campaign_id: str,
    character: dict[str, Any],
    skill: str,
    save_skill: bool = False,
) -> tuple[dict[str, Any], str, bool, bool]:
    """Resolve a roll skill.

    Returns `(character, skill_name, declared, saved_now)`. Undeclared skills
    can be rolled at `fool`, but they do not accrue skill XP unless saved.
    """
    skill_key = (skill or "").strip()
    character_id = str(character.get("character_id") or "<unknown>")
    if not skill_key:
        raise GlassError(
            agent_instruction(
                "skill name is required",
                "Roll one of the character's declared skills.",
                f"Use `glass character get {character_id}` to see declared skills.",
            )
        )
    skills = character.get("skills") or {}
    if skill_key in skills:
        return character, skill_key, True, False
    if not save_skill:
        return character, skill_key, False, False
    try:
        refreshed, added = _db.character_declare_skill(
            conn,
            campaign_id=campaign_id,
            character_id=character_id,
            skill=skill_key,
        )
    except _db.SkillSlotCapFull as exc:
        raise GlassError(_skill_slot_cap_full_message(character_id, exc)) from None
    if not added:
        return refreshed, skill_key, True, False
    return refreshed, skill_key, True, True


@character.command("set-hp", context_settings={"ignore_unknown_options": True})
@click.argument("character_id")
@click.argument("delta", type=int)
@click.pass_context
def character_set_hp(ctx: click.Context, character_id: str, delta: int) -> None:
    set_hp_service(
        command_path=ctx,
        emit_output=True,
        character_id=character_id,
        delta=delta,
    )


def set_hp_service(
    *,
    command_path: click.Context | str = "glass_character_set_hp",
    emit_output: bool = False,
    character_id: str,
    delta: int,
) -> dict[str, Any]:
    """Adjust a character's HP by a signed delta."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    campaign_id = active_campaign_id()

    with pg_connection() as conn:
        existing = _db.character_get(conn, campaign_id, character_id)
        if existing is None:
            raise GlassError(_unknown_character_message(character_id, campaign_id))
        role = assert_character_writable(existing)
        try:
            updated, before, after = _db.character_update_hp(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                delta=delta,
            )
        except LookupError:
            raise GlassError(_unknown_character_message(character_id)) from None

    sign = f"{delta:+d}"
    summary = f"{character_id} hp {sign} ({before} -> {after})"
    queue_event(state, role.actor, summary)
    mirror_result = _write_public_character_mirror(paths, campaign_id, updated)
    result = {
        "character_id": character_id,
        "hp_before": before,
        "delta": delta,
        "applied_delta": after - before,
        "hp_after": after,
        "hp_max": updated["hp"]["max"],
        "mirror": mirror_result,
    }
    commit(
        paths,
        state,
        command_path,
        "character.set-hp",
        command_params(character_id=character_id, delta=delta),
        result,
        emit_output=emit_output,
    )
    return result


@character.command("award-xp", context_settings={"ignore_unknown_options": True})
@click.argument("character_id")
@click.argument("delta", type=int)
@click.option("--reason", default=None, help="Free-form note logged with the award.")
@click.pass_context
def character_award_xp(
    ctx: click.Context, character_id: str, delta: int, reason: str | None
) -> None:
    """DM-only: award (or revoke) XP. Bumps `xp`; `level` is unchanged.

    Resolution of crossed level thresholds happens via `glass character level-up`.
    """
    award_xp_service(
        command_path=ctx,
        emit_output=True,
        character_id=character_id,
        delta=delta,
        reason=reason,
    )


def award_xp_service(
    *,
    command_path: click.Context | str = "glass_character_award_xp",
    emit_output: bool = False,
    character_id: str,
    delta: int,
    reason: str | None = None,
) -> dict[str, Any]:
    """DM-only: award or revoke XP."""

    role = require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    campaign_id = active_campaign_id()
    session_id = state["campaign"]
    scene_id = None
    current = current_mode_record(state)
    if current and current.get("scene_id") and current["scene_id"] != "none":
        scene_id = current["scene_id"]

    with pg_connection() as conn:
        existing = _db.character_get(conn, campaign_id, character_id)
        if existing is None:
            raise GlassError(_unknown_character_message(character_id, campaign_id))
        try:
            updated, before, after = _db.character_award_xp(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                delta=delta,
                actor=role.actor,
                reason=reason,
                session_id=session_id,
                scene_id=scene_id,
            )
        except LookupError:
            raise GlassError(_unknown_character_message(character_id)) from None

    sign = f"{delta:+d}"
    summary = f"{character_id} xp {sign} ({before} -> {after}, level {updated['level']})"
    queue_event(state, role.actor, summary)
    pending_levels = max(0, (after // 10) + 1 - int(updated["level"]))
    mirror_result = _write_public_character_mirror(paths, campaign_id, updated)
    result = {
        "character_id": character_id,
        "xp_before": before,
        "delta": delta,
        "xp_after": after,
        "level": updated["level"],
        "pending_level_ups": pending_levels,
        "reason": reason,
        "mirror": mirror_result,
    }
    commit(
        paths,
        state,
        command_path,
        "character.award-xp",
        command_params(character_id=character_id, delta=delta, reason=reason),
        result,
        emit_output=emit_output,
    )
    return result


@character.command("level-up")
@click.argument("character_id")
@click.option("--attribute", "attribute_name", default=None,
              help="Required when crossing a level that's a multiple of 4. "
                   "Bumps that attribute one tier (cap at superior).")
@click.pass_context
def character_level_up(
    ctx: click.Context, character_id: str, attribute_name: str | None
) -> None:
    """Resolve one pending level. Each call bumps level by 1.

    Mechanical effects:
      - hp_max += d6 (hp_current grows by the same amount, capped at new max)
      - new_level % 4 == 0: --attribute required; that attribute bumps one tier
      - new_level % 5 == 0: momentum_ceiling += 1 (automatic)
    """
    level_up_service(
        command_path=ctx,
        emit_output=True,
        character_id=character_id,
        attribute_name=attribute_name,
    )


def level_up_service(
    *,
    command_path: click.Context | str = "glass_character_level_up",
    emit_output: bool = False,
    character_id: str,
    attribute_name: str | None = None,
) -> dict[str, Any]:
    """Resolve one pending character level."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    campaign_id = active_campaign_id()
    session_id = state["campaign"]
    scene_id = None
    current = current_mode_record(state)
    if current and current.get("scene_id") and current["scene_id"] != "none":
        scene_id = current["scene_id"]

    with pg_connection() as conn:
        existing = _db.character_get(conn, campaign_id, character_id)
        if existing is None:
            raise GlassError(_unknown_character_message(character_id, campaign_id))
        role = assert_character_writable(existing)

        from_level = int(existing["level"])
        xp = int(existing["xp"])
        if (xp // 10) + 1 <= from_level:
            raise GlassError(
                agent_instruction(
                    f"{character_id} has no pending level-ups (xp {xp}, level {from_level})",
                    "Do not run `glass character level-up` until XP crosses the next 10-point threshold.",
                )
            )

        to_level = from_level + 1
        attribute_to_tier: str | None = None
        if to_level % 4 == 0:
            if not attribute_name:
                raise GlassError(
                    agent_instruction(
                        f"reaching level {to_level} requires an attribute bump",
                        "Pass `--attribute <name>` with one valid attribute to bump.",
                    )
                )
            assert_attribute_name(attribute_name)
            current_tier = existing["attributes"].get(attribute_name, "standard")
            ladder = _db.ATTRIBUTE_TIER_LADDER
            try:
                idx = ladder.index(current_tier)
            except ValueError:
                raise GlassError(
                    agent_instruction(
                        f"attribute {attribute_name!r} is at non-bumpable tier {current_tier!r}",
                        "Choose another attribute or ask the DM to repair the character sheet.",
                    )
                ) from None
            if idx >= len(ladder) - 1:
                raise GlassError(
                    agent_instruction(
                        f"attribute {attribute_name!r} is already at {current_tier!r}",
                        "Choose a different attribute; transcendent is plot-only and cannot be reached by level-up.",
                    )
                )
            attribute_to_tier = ladder[idx + 1]
        elif attribute_name:
            raise GlassError(
                agent_instruction(
                    f"`--attribute` is only valid when crossing a multiple of 4; this is level {to_level}",
                    "Retry without `--attribute` for this level-up.",
                )
            )

        hp_roll = random.SystemRandom().randint(1, 6)
        momentum_ceiling_bumps = 1 if to_level % 5 == 0 else 0

        try:
            updated = _db.character_level_up(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                actor=role.actor,
                hp_roll=hp_roll,
                attribute_bumped=attribute_name if attribute_to_tier else None,
                attribute_to_tier=attribute_to_tier,
                momentum_ceiling_bumps=momentum_ceiling_bumps,
                session_id=session_id,
                scene_id=scene_id,
        )
        except LookupError:
            raise GlassError(_unknown_character_message(character_id)) from None

    parts = [f"{character_id} level {from_level} -> {to_level}", f"hp_max +{hp_roll}"]
    if attribute_to_tier:
        parts.append(f"{attribute_name} -> {attribute_to_tier}")
    if momentum_ceiling_bumps:
        parts.append(
            f"momentum_ceiling -> {existing['momentum']['ceiling'] + momentum_ceiling_bumps}"
        )
    summary = ", ".join(parts)
    queue_event(state, role.actor, summary)
    mirror_result = _write_public_character_mirror(paths, campaign_id, updated)
    result = {
        "character_id": character_id,
        "from_level": from_level,
        "to_level": to_level,
        "hp_roll": hp_roll,
        "hp_max_before": existing["hp"]["max"],
        "hp_max_after": updated["hp"]["max"],
        "attribute_bumped": attribute_name if attribute_to_tier else None,
        "attribute_to_tier": attribute_to_tier,
        "momentum_ceiling_before": existing["momentum"]["ceiling"],
        "momentum_ceiling_after": updated["momentum"]["ceiling"],
        "pending_level_ups": max(0, (updated["xp"] // 10) + 1 - updated["level"]),
        "mirror": mirror_result,
    }
    commit(
        paths,
        state,
        command_path,
        "character.level-up",
        command_params(character_id=character_id, attribute=attribute_name),
        result,
        emit_output=emit_output,
    )
    return result


@character.command("set-momentum", context_settings={"ignore_unknown_options": True})
@click.argument("character_id")
@click.argument("value", type=int)
@click.pass_context
def character_set_momentum(ctx: click.Context, character_id: str, value: int) -> None:
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    campaign_id = active_campaign_id()

    with pg_connection() as conn:
        existing = _db.character_get(conn, campaign_id, character_id)
        if existing is None:
            raise GlassError(_unknown_character_message(character_id, campaign_id))
        role = assert_character_writable(existing)
        try:
            updated, before, after = _db.character_update_momentum(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                value=value,
        )
        except LookupError:
            raise GlassError(_unknown_character_message(character_id)) from None

    summary = f"{character_id} momentum {before:+d} -> {after:+d}"
    queue_event(state, role.actor, summary)
    mirror_result = _write_public_character_mirror(paths, campaign_id, updated)
    result = {
        "character_id": character_id,
        "momentum_before": before,
        "requested": value,
        "momentum_after": after,
        "floor": updated["momentum"]["floor"],
        "ceiling": updated["momentum"]["ceiling"],
        "mirror": mirror_result,
    }
    commit(
        paths,
        state,
        ctx,
        "character.set-momentum",
        command_params(character_id=character_id, value=value),
        result,
    )


@character.command("inventory-add")
@click.argument("character_id")
@click.argument("item_id")
@click.option("--qty", type=int, default=1)
@click.option(
    "--name",
    "prose_name",
    required=True,
    help=(
        "Required. Prose name of the item, used only when the character "
        "names it aloud. Example for the slug `mirror-baton`: "
        "--name 'Mirror Baton'."
    ),
)
@click.option(
    "--descriptor",
    required=True,
    help=(
        "Required. Generic noun reached for in ordinary turn prose. "
        "Example for the slug `mirror-baton`: --descriptor 'baton'. "
        "Example for the slug `forged-route-seal`: "
        "--descriptor 'a forged dock pass'."
    ),
)
@click.option(
    "--effect-tag",
    "effect_tags",
    multiple=True,
    help="Repeatable free-text narrative tag for how this item can matter.",
)
@click.pass_context
def character_inventory_add(
    ctx: click.Context,
    character_id: str,
    item_id: str,
    qty: int,
    prose_name: str,
    descriptor: str,
    effect_tags: tuple[str, ...],
) -> None:
    inventory_add_service(
        command_path=ctx,
        emit_output=True,
        character_id=character_id,
        item_id=item_id,
        qty=qty,
        prose_name=prose_name,
        descriptor=descriptor,
        effect_tags=effect_tags,
    )


def inventory_add_service(
    *,
    command_path: click.Context | str = "glass_character_inventory_add",
    emit_output: bool = False,
    character_id: str,
    item_id: str,
    qty: int = 1,
    prose_name: str,
    descriptor: str,
    effect_tags: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Add an inventory item or increase its quantity."""

    if qty <= 0:
        raise GlassError(
            agent_instruction(
                "`--qty` must be greater than zero",
                "Use a positive quantity when adding inventory.",
            )
        )
    assert_valid_item_id(item_id)
    normalized_effect_tags = _normalize_effect_tags(effect_tags)
    prose_name = _require_nonempty(prose_name, "--name")
    descriptor = _require_nonempty(descriptor, "--descriptor")
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    campaign_id = active_campaign_id()

    with pg_connection() as conn:
        existing = _db.character_get(conn, campaign_id, character_id)
        if existing is None:
            raise GlassError(_unknown_character_message(character_id, campaign_id))
        role = assert_character_writable(existing)
        inventory = list(existing["inventory"])
        item = next((entry for entry in inventory if entry.get("id") == item_id), None)
        before = int(item["qty"]) if item else 0
        if item:
            item["qty"] = before + qty
            if normalized_effect_tags:
                item["effect_tags"] = _merge_effect_tags(
                    item.get("effect_tags"),
                    normalized_effect_tags,
                )
            if prose_name:
                item["name"] = prose_name
            if descriptor:
                item["descriptor"] = descriptor
        else:
            entry: dict[str, Any] = {"id": item_id, "qty": qty}
            if prose_name:
                entry["name"] = prose_name
            if descriptor:
                entry["descriptor"] = descriptor
            if normalized_effect_tags:
                entry["effect_tags"] = normalized_effect_tags
            inventory.append(entry)
        after = before + qty
        updated = _db.character_set_inventory(
            conn,
            campaign_id=campaign_id,
            character_id=character_id,
            inventory=inventory,
        )

    queue_event(
        state,
        role.actor,
        f"{character_id} inventory +{qty} {item_id} ({before} -> {after})",
    )
    mirror_result = _write_public_character_mirror(paths, campaign_id, updated)
    result = {
        "character_id": character_id,
        "item_id": item_id,
        "qty_before": before,
        "delta": qty,
        "qty_after": after,
        "name": prose_name,
        "descriptor": descriptor,
        "effect_tags": normalized_effect_tags,
        "inventory": updated["inventory"],
        "mirror": mirror_result,
    }
    commit(
        paths,
        state,
        command_path,
        "character.inventory-add",
        command_params(
            character_id=character_id,
            item_id=item_id,
            qty=qty,
            name=prose_name,
            descriptor=descriptor,
            effect_tags=normalized_effect_tags,
        ),
        result,
        emit_output=emit_output,
    )
    return result


@character.command("inventory-rm")
@click.argument("character_id")
@click.argument("item_id")
@click.option("--qty", type=int, default=1)
@click.pass_context
def character_inventory_rm(
    ctx: click.Context, character_id: str, item_id: str, qty: int
) -> None:
    inventory_remove_service(
        command_path=ctx,
        emit_output=True,
        character_id=character_id,
        item_id=item_id,
        qty=qty,
    )


def inventory_remove_service(
    *,
    command_path: click.Context | str = "glass_character_inventory_remove",
    emit_output: bool = False,
    character_id: str,
    item_id: str,
    qty: int = 1,
) -> dict[str, Any]:
    """Remove an inventory quantity."""

    if qty <= 0:
        raise GlassError(
            agent_instruction(
                "`--qty` must be greater than zero",
                "Use a positive quantity when removing inventory.",
            )
        )
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    campaign_id = active_campaign_id()

    with pg_connection() as conn:
        existing = _db.character_get(conn, campaign_id, character_id)
        if existing is None:
            raise GlassError(_unknown_character_message(character_id, campaign_id))
        role = assert_character_writable(existing)
        inventory = list(existing["inventory"])
        item = next((entry for entry in inventory if entry.get("id") == item_id), None)
        before = int(item["qty"]) if item else 0
        after = max(0, before - qty)
        if item:
            item["qty"] = after
        inventory = [entry for entry in inventory if int(entry.get("qty", 0)) > 0]
        updated = _db.character_set_inventory(
            conn,
            campaign_id=campaign_id,
            character_id=character_id,
            inventory=inventory,
        )

    queue_event(
        state,
        role.actor,
        f"{character_id} inventory -{qty} {item_id} ({before} -> {after})",
    )
    mirror_result = _write_public_character_mirror(paths, campaign_id, updated)
    result = {
        "character_id": character_id,
        "item_id": item_id,
        "qty_before": before,
        "delta": -qty,
        "applied_delta": after - before,
        "qty_after": after,
        "inventory": updated["inventory"],
        "mirror": mirror_result,
    }
    commit(
        paths,
        state,
        command_path,
        "character.inventory-rm",
        command_params(character_id=character_id, item_id=item_id, qty=qty),
        result,
        emit_output=emit_output,
    )
    return result


@character.command("consequence-add")
@click.argument("character_id")
@click.argument("label")
@click.option("--description", default="", help="Freeform consequence description.")
@click.option(
    "--severity",
    type=click.Choice(["minor", "serious", "critical"]),
    default="minor",
    show_default=True,
)
@click.option(
    "--scope",
    type=click.Choice(["scene", "arc", "campaign"]),
    default="scene",
    show_default=True,
)
@click.option(
    "--public/--hidden",
    "public",
    default=True,
    show_default=True,
    help="Whether players can see this consequence.",
)
@click.pass_context
def character_consequence_add(
    ctx: click.Context,
    character_id: str,
    label: str,
    description: str,
    severity: str,
    scope: str,
    public: bool,
) -> None:
    """Add a lasting character consequence.

    Consequences are prose-backed state, not a condition engine. Use them for
    injuries, capture, obligations, disgrace, gear strain, or other effects
    that need to persist beyond the current line of narration.
    """
    add_consequence_service(
        command_path=ctx,
        emit_output=True,
        character_id=character_id,
        label=label,
        description=description,
        severity=severity,
        scope=scope,
        public=public,
    )


def add_consequence_service(
    *,
    command_path: click.Context | str = "glass_character_consequence_add",
    emit_output: bool = False,
    character_id: str,
    label: str,
    description: str = "",
    severity: str = "minor",
    scope: str = "scene",
    public: bool = True,
) -> dict[str, Any]:
    """Add a lasting character consequence.

    DM/operator may add any consequence. Players may add public consequences to
    their own character, matching the player-owned turn model for HP and other
    character state.
    """

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    visibility = "public" if public else "dm"
    with pg_connection() as conn:
        existing = _db.character_get(conn, campaign_id, character_id)
        if existing is None:
            raise GlassError(_unknown_character_message(character_id, campaign_id))
        role = assert_character_writable(existing)
        if role.kind == "player" and not public:
            raise GlassError(
                agent_instruction(
                    "players may add only public consequences to their own character",
                    "Use `public=True` for player-authored consequences; ask the DM to record hidden fallout.",
                )
            )
        try:
            consequence = _db.character_consequence_add(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                label=label,
                description=description,
                severity=severity,
                scope=scope,
                visibility=visibility,
                actor=role.actor,
            )
        except LookupError:
            raise GlassError(_unknown_character_message(character_id)) from None
    queue_event(
        state,
        role.actor,
        f"{character_id} consequence {severity}: {label} ({scope}, {visibility})",
    )
    commit(
        paths,
        state,
        command_path,
        "character.consequence-add",
        command_params(
            character_id=character_id,
            label=label,
            severity=severity,
            scope=scope,
            visibility=visibility,
        ),
        {"consequence": consequence},
        emit_output=emit_output,
    )
    return {"consequence": consequence}


@character.command("consequence-list")
@click.argument("character_id")
@click.option("--all", "include_resolved", is_flag=True, help="Include resolved consequences.")
@click.option("--hidden", "include_hidden", is_flag=True, help="DM-only: include hidden consequences.")
@click.pass_context
def character_consequence_list(
    ctx: click.Context,
    character_id: str,
    include_resolved: bool,
    include_hidden: bool,
) -> None:
    """List consequences for a character."""
    emit(
        list_consequences_service(
            command_path=ctx,
            character_id=character_id,
            include_resolved=include_resolved,
            include_hidden=include_hidden,
        )
    )


def list_consequences_service(
    *,
    command_path: click.Context | str = "glass_character_consequence_list",
    character_id: str,
    include_resolved: bool = False,
    include_hidden: bool = False,
) -> dict[str, Any]:
    """List consequences for a character."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    if role.kind == "player" and include_hidden:
        raise GlassError(
            agent_instruction(
                "players cannot read hidden consequences",
                "Run consequence list without `--hidden`, or ask the DM to review hidden consequences.",
            )
        )
    with pg_connection() as conn:
        character = _db.character_get(conn, campaign_id, character_id)
        if character is None:
            raise GlassError(_unknown_character_message(character_id, campaign_id))
        if role.kind == "player" and character.get("player_id") != role.actor:
            include_hidden = False
        consequences = _db.character_consequence_list(
            conn,
            campaign_id=campaign_id,
            character_id=character_id,
            include_hidden=include_hidden and role.kind != "player",
            include_resolved=include_resolved,
        )
    result = {
        "character_id": character_id,
        "consequences": consequences,
        "count": len(consequences),
    }
    append_audit(
        paths,
        state,
        command_path,
        "character.consequence-list",
        command_params(
            character_id=character_id,
            all=include_resolved,
            hidden=include_hidden,
        ),
        result,
    )
    return result


@character.command("consequence-resolve")
@click.argument("character_id")
@click.argument("consequence_id")
@click.option("--note", default="", help="How this consequence was resolved.")
@click.pass_context
def character_consequence_resolve(
    ctx: click.Context,
    character_id: str,
    consequence_id: str,
    note: str,
) -> None:
    """Resolve a lasting character consequence."""
    resolve_consequence_service(
        command_path=ctx,
        emit_output=True,
        character_id=character_id,
        consequence_id=consequence_id,
        note=note,
    )


def resolve_consequence_service(
    *,
    command_path: click.Context | str = "glass_character_consequence_resolve",
    emit_output: bool = False,
    character_id: str,
    consequence_id: str,
    note: str = "",
) -> dict[str, Any]:
    """Resolve a lasting character consequence.

    DM/operator may resolve any consequence. Players may resolve public
    consequences on their own character.
    """

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    with pg_connection() as conn:
        existing = _db.character_get(conn, campaign_id, character_id)
        if existing is None:
            raise GlassError(_unknown_character_message(character_id, campaign_id))
        role = assert_character_writable(existing)
        if role.kind == "player":
            visible = _db.character_consequence_list(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                include_hidden=False,
                include_resolved=True,
            )
            if consequence_id not in {
                str(item.get("consequence_id") or "") for item in visible
            }:
                raise GlassError(
                    agent_instruction(
                        f"unknown public consequence {consequence_id!r}",
                        "Players may resolve only public consequences on their own character.",
                    )
                )
        try:
            consequence = _db.character_consequence_resolve(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                consequence_id=consequence_id,
                actor=role.actor,
                note=note,
            )
        except LookupError:
            raise GlassError(
                agent_instruction(
                    f"unknown consequence {consequence_id!r}",
                    "Use `glass character consequence-list <character-id>` to find consequence ids before resolving one.",
                )
            ) from None
    queue_event(
        state,
        role.actor,
        f"{character_id} consequence resolved: {consequence['label']}",
    )
    commit(
        paths,
        state,
        command_path,
        "character.consequence-resolve",
        command_params(
            character_id=character_id,
            consequence_id=consequence_id,
            note=note,
        ),
        {"consequence": consequence},
        emit_output=emit_output,
    )
    return {"consequence": consequence}


def _unknown_character_message(character_id: str, campaign_id: str | None = None) -> str:
    scope = f" in campaign {campaign_id!r}" if campaign_id else ""
    return agent_instruction(
        f"unknown character {character_id!r}{scope}",
        "Use the character id from the injected prompt, `glass character list`, or `glass character bulk-get --all`.",
        "Do not invent character ids when calling character commands.",
    )


def _require_nonempty(value: str, option_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise GlassError(
            agent_instruction(
                f"{option_name} is required",
                f"Provide a non-empty value for `{option_name}`.",
            )
        )
    return cleaned


def _unique_nonempty(values: tuple[str, ...]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized


def _normalize_goals(goals: tuple[str, ...]) -> list[str]:
    normalized: list[str] = []
    for goal in goals:
        value = goal.strip()
        if value:
            normalized.append(value)
    if not (2 <= len(normalized) <= 3):
        raise GlassError(
            agent_instruction(
                "character creation requires 2-3 `--goal` values",
                "Create two or three concrete character goals and pass each as a separate `--goal` option.",
            )
        )
    return normalized


def _normalize_primary_drive(value: str) -> str:
    return _require_nonempty(value, "--primary-drive")


def _validate_primary_drive_available(
    conn: Any,
    campaign_id: str,
    primary_drive: str,
    *,
    exclude_character_id: str | None = None,
) -> None:
    existing = [
        character
        for character in _db.character_list(conn, campaign_id)
        if str(character.get("primary_drive") or "").casefold()
        == primary_drive.casefold()
        and character.get("character_id") != exclude_character_id
    ]
    if not existing:
        return
    owners = ", ".join(
        f"{character['character_id']} ({character['name']})" for character in existing
    )
    raise GlassError(
        agent_instruction(
            f"primary drive already claimed: {primary_drive}",
            f"Existing character(s): {owners}.",
            "Choose a different primary drive for this character.",
        )
    )


def _normalize_life_prompt_answers(prompts: tuple[str, ...]) -> list[dict[str, str]]:
    answers = [
        _parse_life_prompt_answer(prompt, index)
        for index, prompt in enumerate(prompts, 1)
    ]
    answers = [answer for answer in answers if answer is not None]
    if not (2 <= len(answers) <= 3):
        raise GlassError(
            agent_instruction(
                "character creation requires 2-3 `--life-prompt` answers",
                "Pass each answer as `--life-prompt \"<prompt>=<concrete behavior>\"`.",
            )
        )
    return answers


def _normalize_life_prompt_answers_value(value: Any) -> list[dict[str, str]]:
    if isinstance(value, list):
        raw_answers = value
    else:
        raw_answers = [value]
    answers: list[dict[str, str]] = []
    for index, raw_answer in enumerate(raw_answers, start=1):
        if isinstance(raw_answer, str):
            parsed = _parse_life_prompt_answer(raw_answer, index)
            if parsed is not None:
                answers.append(parsed)
            continue
        if isinstance(raw_answer, dict):
            prompt = _require_nonempty(
                str(raw_answer.get("prompt") or ""),
                "life_prompt prompt",
            )
            answer = _require_concrete_note(
                str(raw_answer.get("answer") or ""),
                "life_prompt answer",
                "Answer with a concrete behavior, not a mood label.",
            )
            answers.append({"prompt": prompt, "answer": answer})
            continue
        raise GlassError(
            agent_instruction(
                f"life prompt answer #{index} must be a string or object",
                "Use `prompt=answer` strings or objects with `prompt` and `answer`.",
            )
        )
    if not (2 <= len(answers) <= 3):
        raise GlassError(
            agent_instruction(
                "`life_prompt_answers` requires 2-3 answers",
                "Store two or three concrete life-prompt answers.",
            )
        )
    return answers


def _parse_life_prompt_answer(raw_value: str, index: int) -> dict[str, str] | None:
    value = raw_value.strip()
    if not value:
        return None
    separator = "=" if "=" in value else ":"
    if separator not in value:
        raise GlassError(
            agent_instruction(
                f"life prompt answer #{index} is missing a prompt/answer separator",
                "Use `--life-prompt \"what they do when praised=They change the subject by handing over tea.\"`.",
            )
        )
    prompt, answer = value.split(separator, 1)
    return {
        "prompt": _require_nonempty(prompt, f"life prompt #{index} prompt"),
        "answer": _require_concrete_note(
            answer,
            f"life prompt #{index} answer",
            "Answer with a concrete behavior, not a mood label.",
        ),
    }


def _require_concrete_note(value: str, option_name: str, _instruction: str) -> str:
    cleaned = _require_nonempty(value, option_name)
    return cleaned


def _normalize_starting_inventory(items: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw_item in enumerate(items, start=1):
        item_id = str(raw_item.get("id") or raw_item.get("item_id") or "").strip()
        assert_valid_item_id(item_id)
        if item_id in seen:
            raise GlassError(
                agent_instruction(
                    f"duplicate starting item id: {item_id}",
                    "Each starting inventory item needs a unique item_id.",
                )
            )
        seen.add(item_id)
        qty = int(raw_item.get("qty", 0) or 0)
        if qty <= 0:
            raise GlassError(
                agent_instruction(
                    f"starting item #{index} qty must be greater than zero",
                    "Set a positive quantity for each starting inventory item.",
                )
            )
        name = _require_nonempty(str(raw_item.get("name") or ""), f"starting item #{index} name")
        descriptor = _require_nonempty(
            str(raw_item.get("descriptor") or ""),
            f"starting item #{index} descriptor",
        )
        effect_tags = _normalize_effect_tags(tuple(raw_item.get("effect_tags") or ()))
        entry: dict[str, Any] = {
            "id": item_id,
            "qty": qty,
            "name": name,
            "descriptor": descriptor,
        }
        if effect_tags:
            entry["effect_tags"] = effect_tags
        inventory.append(entry)
    return inventory


def _require_pull_utilization_note(value: str, option_name: str) -> str:
    cleaned = _require_concrete_note(
        value,
        option_name,
        "Name the non-adjacent source and the identity thesis it creates.",
    )
    normalized = cleaned.casefold()
    if "source" not in normalized or "thesis" not in normalized:
        raise GlassError(
            agent_instruction(
                f"{option_name} is missing source or thesis",
                "Use a short note with `Source:` and `Thesis:`. Do not enumerate every surface.",
            )
        )
    if "used in:" in normalized or "surfaces" in normalized:
        raise GlassError(
            agent_instruction(
                f"{option_name} is too detailed",
                "Keep pull utilization to `Source:` and `Thesis:` only. Put concrete character details in the typed character fields.",
            )
        )
    return cleaned


def _validate_starting_skill_budget(skills: dict[str, str]) -> None:
    counts = Counter(skills.values())
    expected = Counter({"apprentice": 2, "artisan": 1})
    if counts == expected:
        return
    raise GlassError(
        agent_instruction(
            "character creation requires exactly 3 trained skills",
            "Pass exactly two skills at `apprentice` and one skill at `artisan`.",
            "Do not list `fool`, `virtuoso`, or `legend` skills at level 1; additional skills must be declared later with `glass character skill-declare`.",
        )
    )


def _is_character_creation_mode(state: dict[str, Any]) -> bool:
    current = current_mode_record(state)
    return bool(current and current.get("mode") == "character-creation")


def _read_json_payload(text: str, label: str) -> Any:
    if not text.strip():
        raise GlassError(
            agent_instruction(
                f"{label} JSON payload is empty",
                "Provide a JSON object/list payload, or use the specific character command for the mutation you need.",
            )
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise GlassError(
            agent_instruction(
                f"invalid {label} JSON",
                "Fix the JSON payload and retry.",
                f"JSON parser detail: {exc.msg} at line {exc.lineno}",
            )
        ) from exc


def _normalize_bulk_update_payload(
    payload: Any,
    *,
    mirror_override: bool | None,
) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        raw_updates = payload
        default_mirror = False
    elif isinstance(payload, dict):
        has_characters = "characters" in payload
        has_updates = "updates" in payload
        if has_characters and has_updates:
            raise GlassError(
                agent_instruction(
                    "bulk update payload must use either `characters` or `updates`, not both",
                    "Choose one array key for the update list.",
                )
            )
        if has_characters or has_updates:
            raw_updates = payload["characters"] if has_characters else payload["updates"]
            if not isinstance(raw_updates, list):
                raise GlassError(
                    agent_instruction(
                        "bulk update `characters`/`updates` must be a list",
                        "Wrap character updates in an array, even when sending one update.",
                    )
                )
            default_mirror = _optional_bool(payload.get("mirror"), default=False)
        else:
            raw_updates = [payload]
            default_mirror = _optional_bool(payload.get("mirror"), default=False)
    else:
        raise GlassError(
            agent_instruction(
                "bulk update payload must be an object or list",
                "Use a single update object, an array of updates, or an object with `updates`/`characters` array.",
            )
        )

    if not raw_updates:
        raise GlassError(
            agent_instruction(
                "bulk update payload has no character updates",
                "Add at least one update object, or skip the command if there is nothing to change.",
            )
        )

    updates: list[dict[str, Any]] = []
    for index, raw_update in enumerate(raw_updates, start=1):
        if not isinstance(raw_update, dict):
            raise GlassError(
                agent_instruction(
                    f"bulk update #{index} must be an object",
                    "Each update must name `character_id` or `id` and at least one mutation.",
                )
            )
        allowed = {
            "id",
            "character_id",
            "set",
            "hp_delta",
            "momentum",
            "inventory_add",
            "add_inventory",
            "inventory_rm",
            "inventory_remove",
            "remove_inventory",
            "signature_moves",
            "signature_add",
            "signatures",
            "mirror",
        }
        unknown = sorted(set(raw_update) - allowed)
        if unknown:
            raise GlassError(
                agent_instruction(
                    f"bulk update #{index} has unsupported field(s): {', '.join(unknown)}",
                    f"Use only these fields: {', '.join(sorted(allowed))}.",
                )
            )
        character_id = str(
            raw_update.get("character_id") or raw_update.get("id") or ""
        ).strip()
        if not character_id:
            raise GlassError(
                agent_instruction(
                    f"bulk update #{index} is missing `character_id`",
                    "Set `character_id` or `id` to the character being mutated.",
                )
            )
        set_fields = raw_update.get("set") or {}
        if not isinstance(set_fields, dict):
            raise GlassError(
                agent_instruction(
                    f"bulk update {character_id}: `set` must be an object",
                    "Put sheet field replacements under `set`, for example `{\"set\": {\"bio\": \"...\"}}`.",
                )
            )

        signature_value = _first_present(
            raw_update,
            ("signature_moves", "signature_add", "signatures"),
        )
        inventory_add_value = _first_present(
            raw_update,
            ("inventory_add", "add_inventory"),
        )
        inventory_rm_value = _first_present(
            raw_update,
            ("inventory_rm", "inventory_remove", "remove_inventory"),
        )
        mirror = (
            mirror_override
            if mirror_override is not None
            else _optional_bool(raw_update.get("mirror"), default=default_mirror)
        )
        update = {
            "character_id": character_id,
            "set": set_fields,
            "hp_delta": _optional_int(raw_update.get("hp_delta"), "hp_delta"),
            "momentum": _optional_int(raw_update.get("momentum"), "momentum"),
            "inventory_add": _normalize_inventory_items(
                inventory_add_value,
                "inventory_add",
                require_labels=True,
            ),
            "inventory_rm": _normalize_inventory_items(
                inventory_rm_value,
                "inventory_rm",
                require_labels=False,
            ),
            "signature_moves": _normalize_signature_move_updates(signature_value),
            "mirror": mirror,
        }
        if not any(
            [
                update["set"],
                update["hp_delta"] is not None,
                update["momentum"] is not None,
                update["inventory_add"],
                update["inventory_rm"],
                update["signature_moves"],
                update["mirror"],
            ]
        ):
            raise GlassError(
                agent_instruction(
                    f"bulk update {character_id}: no mutations requested",
                    "Include at least one of `set`, `hp_delta`, `momentum`, `inventory_add`, `inventory_rm`, `signature_moves`, or `mirror`.",
                )
            )
        updates.append(update)
    return updates


def _first_present(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _optional_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise GlassError(
        agent_instruction(
            "`mirror` must be true or false",
            "Set `mirror` to a JSON boolean, not a string.",
        )
    )


def _optional_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise GlassError(
            agent_instruction(
                f"`{field_name}` must be an integer",
                "Use a JSON number such as `1`, `-1`, or `0`, not a string.",
            )
        )
    return value


def _normalize_inventory_items(
    value: Any,
    field_name: str,
    *,
    require_labels: bool = True,
) -> list[dict[str, Any]]:
    """Normalize a list of inventory item dicts.

    Each item must carry a slug `id`, a prose `name`, and a generic
    `descriptor` (used by ordinary turn prose). Set `require_labels=False`
    for removal flows where only `id`/`qty` matter.

    Example payload entry:

        {"id": "mirror-baton", "name": "Mirror Baton",
         "descriptor": "baton", "qty": 1,
         "effect_tags": ["weapon:strike"]}
    """
    if value is None:
        return []
    raw_items = value if isinstance(value, list) else [value]
    items: list[dict[str, Any]] = []
    for index, raw_item in enumerate(raw_items, start=1):
        prose_name = ""
        descriptor = ""
        if isinstance(raw_item, str):
            item_id = raw_item.strip()
            qty = 1
            effect_tags: list[str] = []
        elif isinstance(raw_item, dict):
            item_id = str(raw_item.get("id") or raw_item.get("item_id") or "").strip()
            qty = raw_item.get("qty", 1)
            if isinstance(qty, bool) or not isinstance(qty, int):
                raise GlassError(
                    agent_instruction(
                        f"{field_name} item #{index}: `qty` must be an integer",
                        "Use a JSON number quantity, or omit `qty` for 1.",
                    )
                )
            effect_tags = _normalize_effect_tags(
                tuple(_string_list(raw_item.get("effect_tags") or raw_item.get("effect_tag")))
            )
            prose_name = str(raw_item.get("name") or "").strip()
            descriptor = str(raw_item.get("descriptor") or "").strip()
        else:
            raise GlassError(
                agent_instruction(
                    f"{field_name} item #{index} must be a string or object",
                    "Use an object like "
                    "`{\"id\": \"mirror-baton\", \"name\": \"Mirror Baton\", "
                    "\"descriptor\": \"baton\", \"qty\": 1, "
                    "\"effect_tags\": [\"weapon:strike\"]}`.",
                )
            )
        if not item_id:
            raise GlassError(
                agent_instruction(
                    f"{field_name} item #{index} is missing `id`",
                    "Set `id` or `item_id` to the inventory item slug.",
                )
            )
        if qty <= 0:
            raise GlassError(
                agent_instruction(
                    f"{field_name} item #{index}: `qty` must be greater than zero",
                    "Use a positive quantity.",
                )
            )
        assert_valid_item_id(item_id)
        if require_labels and not prose_name:
            raise GlassError(
                agent_instruction(
                    f"{field_name} item #{index} ({item_id}) is missing `name`",
                    "Every item must have a prose `name` for the moment a "
                    "character names it aloud. Example: "
                    "`\"name\": \"Mirror Baton\"`.",
                )
            )
        if require_labels and not descriptor:
            raise GlassError(
                agent_instruction(
                    f"{field_name} item #{index} ({item_id}) is missing `descriptor`",
                    "Every item must have a generic `descriptor` reached for "
                    "in ordinary turn prose. Example for `mirror-baton`: "
                    "`\"descriptor\": \"baton\"`. Example for "
                    "`forged-route-seal`: `\"descriptor\": \"a forged dock "
                    "pass\"`.",
                )
            )
        entry: dict[str, Any] = {"id": item_id, "qty": qty, "effect_tags": effect_tags}
        if prose_name:
            entry["name"] = prose_name
        if descriptor:
            entry["descriptor"] = descriptor
        items.append(entry)
    return items


def _normalize_signature_move_updates(value: Any) -> list[dict[str, str]]:
    """Normalize signature-move dicts. Each move must carry `name` (the
    prose name spoken aloud), `descriptor` (the generic noun phrase reached
    for in ordinary turn prose), and either a freeform `body` or the
    structured `look`/`use`/`tell` trio.

    Example payload entry:

        {"name": "Ride The Line Down",
         "descriptor": "the fall-line ride",
         "look": "Mox plants her feet on the fall line and lets the wreck "
                 "carry her into its own backstop.",
         "use": "When a beam is going to come down anyway and someone is "
                "in the fall pocket.",
         "tell": "One chance to read the line right."}
    """
    if value is None:
        return []
    raw_moves = value if isinstance(value, list) else [value]
    moves: list[dict[str, str]] = []
    for index, raw_move in enumerate(raw_moves, start=1):
        if not isinstance(raw_move, dict):
            raise GlassError(
                agent_instruction(
                    f"signature move #{index} must be an object",
                    "Use an object with `name`, `descriptor`, and either "
                    "`body` or the structured `look`, `use`, and `tell` fields.",
                )
            )
        name = _require_nonempty(str(raw_move.get("name") or ""), "signature move name")
        descriptor = str(raw_move.get("descriptor") or "").strip()
        if not descriptor:
            raise GlassError(
                agent_instruction(
                    f"signature move {name!r} is missing `descriptor`",
                    "Every signature move must have a generic `descriptor` "
                    "phrase reached for in ordinary turn prose. The `name` "
                    "is the prose name (used only when a character names "
                    "the move aloud). Example: "
                    "`\"name\": \"Ride The Line Down\", "
                    "\"descriptor\": \"the fall-line ride\"`. Example: "
                    "`\"name\": \"Quiet Door\", "
                    "\"descriptor\": \"her old lockpick trick\"`.",
                )
            )
        body = _signature_move_body(
            body=str(raw_move.get("body") or ""),
            look=str(raw_move.get("look") or ""),
            usual_use=str(raw_move.get("use") or raw_move.get("usual_use") or ""),
            tell=str(
                raw_move.get("tell")
                or raw_move.get("tells")
                or raw_move.get("tells_costs")
                or ""
            ),
            descriptor=descriptor,
        )
        moves.append({"name": name, "descriptor": descriptor, "body": body})
    return moves


def _normalize_character_set_fields(
    raw_fields: dict[str, Any],
    existing: dict[str, Any],
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    aliases = {
        "race": "species",
        "org_role": "organization_role",
        "pull_utilization": "pull_utilization_note",
    }
    allowed = {
        "name",
        "species",
        "culture",
        "archetype",
        "organization_role",
        "pronouns",
        "bio",
        "goals",
        "primary_drive",
        "positive_trait",
        "table_presence",
        "non_work_want",
        "opening_social_action",
        "life_prompt_answers",
        "pull_utilization_note",
        "attributes",
        "skills",
        "skill_meta",
        "tags",
    }
    for raw_name, value in raw_fields.items():
        name = aliases.get(raw_name, raw_name)
        if name not in allowed:
            raise GlassError(
                agent_instruction(
                    f"unsupported character set field: {raw_name}",
                    f"Use only these fields under `set`: {', '.join(sorted(allowed | set(aliases)))}.",
                )
            )
        if name in {
            "name",
            "species",
            "culture",
            "archetype",
            "organization_role",
            "bio",
            "positive_trait",
            "table_presence",
            "non_work_want",
            "opening_social_action",
        }:
            if name in {
                "positive_trait",
                "table_presence",
                "non_work_want",
                "opening_social_action",
            }:
                fields[name] = _require_concrete_note(
                    str(value),
                    name,
                    "Use a concrete table-facing behavior or want, not a one-word label.",
                )
            else:
                fields[name] = _require_nonempty(str(value), name)
        elif name == "pronouns":
            fields[name] = str(value).strip()
        elif name == "goals":
            fields[name] = _normalize_goals(tuple(_string_list(value)))
        elif name == "primary_drive":
            fields[name] = _normalize_primary_drive(str(value))
        elif name == "life_prompt_answers":
            fields[name] = _normalize_life_prompt_answers_value(value)
        elif name == "pull_utilization_note":
            fields[name] = _require_pull_utilization_note(
                str(value),
                "pull_utilization_note",
            )
        elif name == "attributes":
            merged = dict(existing.get("attributes") or {})
            merged.update(_normalize_attribute_map(value))
            fields[name] = merged
        elif name == "skills":
            skills_only, meta_extracted = _normalize_skill_map(value)
            merged_skills = dict(existing.get("skills") or {})
            merged_skills.update(skills_only)
            fields[name] = merged_skills
            if meta_extracted:
                merged_meta = dict(existing.get("skill_meta") or {})
                if "skill_meta" in fields:
                    merged_meta.update(fields["skill_meta"])
                merged_meta.update(meta_extracted)
                fields["skill_meta"] = merged_meta
        elif name == "skill_meta":
            merged_meta = dict(existing.get("skill_meta") or {})
            if "skill_meta" in fields:
                merged_meta.update(fields["skill_meta"])
            merged_meta.update(_normalize_skill_meta_map(value))
            fields["skill_meta"] = merged_meta
        elif name == "tags":
            fields[name] = _string_list(value)
    return fields


def _normalize_attribute_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise GlassError(
            agent_instruction(
                "`attributes` must be an object",
                "Use a map like `{\"resolve\": \"strong\"}`.",
            )
        )
    normalized: dict[str, str] = {}
    for name, tier in value.items():
        attribute = str(name).strip()
        assert_attribute_name(attribute)
        tier_name = str(tier).strip()
        if tier_name not in ATTRIBUTE_TIERS:
            raise GlassError(
                agent_instruction(
                    f"invalid attribute tier for {attribute}: {tier_name}",
                    f"Use one of: {', '.join(sorted(ATTRIBUTE_TIERS))}.",
                )
            )
        normalized[attribute] = tier_name
    return normalized


def _normalize_skill_map(
    value: Any,
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """Normalize a skills map.

    Every entry must be a dict with `tier`, `name` (prose name spoken aloud),
    and `descriptor` (generic verb phrase reached for in ordinary turn
    prose). The simple `{slug: tier}` shape is still accepted for legacy
    payloads that only adjust an existing skill's tier without adding a new
    one; in that case the existing `skill_meta` entry is preserved.

    Example:

        {"read-parallel-resonance-bands": {
            "tier": "artisan",
            "name": "Read Parallel Resonance Bands",
            "descriptor": "reading the bands"
        },
         "talk-down-crowds": {
            "tier": "apprentice",
            "name": "Talk Down Crowds",
            "descriptor": "talking the crowd down"
        }}

    Returns `(skills, skill_meta)`.
    """
    if not isinstance(value, dict):
        raise GlassError(
            agent_instruction(
                "`skills` must be an object",
                "Use a map like "
                "`{\"read-parallel-resonance-bands\": "
                "{\"tier\": \"artisan\", "
                "\"name\": \"Read Parallel Resonance Bands\", "
                "\"descriptor\": \"reading the bands\"}}`.",
            )
        )
    skills: dict[str, str] = {}
    meta: dict[str, dict[str, str]] = {}
    for raw_name, raw_value in value.items():
        skill = str(raw_name).strip()
        if not skill:
            raise GlassError(
                agent_instruction(
                    "skill slugs must be non-empty",
                    "Use a real skill slug as the object key.",
                )
            )
        if isinstance(raw_value, dict):
            tier_name = str(raw_value.get("tier") or "").strip()
            prose_name = str(raw_value.get("name") or "").strip()
            descriptor = str(raw_value.get("descriptor") or "").strip()
            if not prose_name:
                raise GlassError(
                    agent_instruction(
                        f"skill {skill!r} is missing `name`",
                        "Every skill must have a prose `name` for the moment "
                        "a character names the craft aloud. Example: "
                        "`\"name\": \"Read Parallel Resonance Bands\"`.",
                    )
                )
            if not descriptor:
                raise GlassError(
                    agent_instruction(
                        f"skill {skill!r} is missing `descriptor`",
                        "Every skill must have a generic `descriptor` "
                        "phrase reached for in ordinary turn prose. Example "
                        "for `read-parallel-resonance-bands`: "
                        "`\"descriptor\": \"reading the bands\"`. Example "
                        "for `talk-down-crowds`: "
                        "`\"descriptor\": \"talking the crowd down\"`.",
                    )
                )
        else:
            tier_name = str(raw_value).strip()
            prose_name = ""
            descriptor = ""
        if tier_name not in SKILL_TIERS:
            raise GlassError(
                agent_instruction(
                    f"invalid skill tier for {skill}: {tier_name}",
                    f"Use one of: {', '.join(sorted(SKILL_TIERS))}.",
                )
            )
        skills[skill] = tier_name
        if prose_name or descriptor:
            entry: dict[str, str] = {}
            if prose_name:
                entry["name"] = prose_name
            if descriptor:
                entry["descriptor"] = descriptor
            meta[skill] = entry
    return skills, meta


def _normalize_skill_meta_map(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        raise GlassError(
            agent_instruction(
                "`skill_meta` must be an object",
                "Use `{\"slug\": {\"name\": ..., \"descriptor\": ...}}`.",
            )
        )
    normalized: dict[str, dict[str, str]] = {}
    for raw_name, raw_value in value.items():
        slug = str(raw_name).strip()
        if not slug:
            continue
        if not isinstance(raw_value, dict):
            raise GlassError(
                agent_instruction(
                    f"`skill_meta.{slug}` must be an object",
                    "Use `{\"name\": ..., \"descriptor\": ...}`.",
                )
            )
        prose_name = str(raw_value.get("name") or "").strip()
        descriptor = str(raw_value.get("descriptor") or "").strip()
        entry: dict[str, str] = {}
        if prose_name:
            entry["name"] = prose_name
        if descriptor:
            entry["descriptor"] = descriptor
        if entry:
            normalized[slug] = entry
    return normalized


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    raw_values = value if isinstance(value, list) else [value]
    strings: list[str] = []
    for raw in raw_values:
        text = str(raw).strip()
        if text:
            strings.append(text)
    return strings


def _signature_move_slots(level: int) -> int:
    return _db.signature_move_slots(level)


def _next_signature_move_unlock(level: int) -> int | None:
    return _db.next_signature_move_unlock(level)


def _signature_status(
    character: dict[str, Any],
    moves: list[dict[str, Any]],
) -> dict[str, Any]:
    slots = _signature_move_slots(character["level"])
    return {
        "character_id": character["character_id"],
        "player_id": character["player_id"],
        "level": character["level"],
        "slots": slots,
        "used": len(moves),
        "available": max(0, slots - len(moves)),
        "over_slots": len(moves) > slots,
        "next_unlock_level": _next_signature_move_unlock(character["level"]),
        "moves": moves,
    }


def _signature_move_body(
    *,
    body: str,
    look: str,
    usual_use: str,
    tell: str,
    descriptor: str = "",
) -> str:
    descriptor = (descriptor or "").strip()
    if body.strip():
        return _prepend_descriptor(body.strip(), descriptor)

    look = _require_nonempty(look, "--look")
    usual_use = _require_nonempty(usual_use, "--use")
    tell = _require_nonempty(tell, "--tell")
    bullets: list[str] = []
    if descriptor:
        bullets.append(
            f"- **Descriptor (prefer in prose):** {descriptor}"
        )
    bullets.extend(
        [
            f"- **Look:** {look}",
            f"- **Usual use:** {usual_use}",
            f"- **Tells/costs:** {tell}",
        ]
    )
    return "\n".join(bullets)


def _prepend_descriptor(existing_body: str, descriptor: str) -> str:
    if not descriptor:
        return existing_body
    if "**Descriptor" in existing_body:
        return existing_body
    return f"- **Descriptor (prefer in prose):** {descriptor}\n{existing_body}"


def _signature_move_db_error(
    character: dict[str, Any],
    name: str,
    reason: str,
) -> GlassError:
    if reason == "signature_move_exists":
        return GlassError(
            agent_instruction(
                f"signature move already exists for {character['character_id']}: {name}",
                "Choose a distinct move name.",
            )
        )
    if reason == "signature_move_slots_full":
        slots = _signature_move_slots(character["level"])
        next_level = _next_signature_move_unlock(character["level"])
        suffix = (
            f"; next slot unlocks at level {next_level}"
            if next_level is not None
            else "; no more slots are available from level progression"
        )
        return GlassError(
            agent_instruction(
                f"no signature move slots available for {character['character_id']}: {slots}/{slots} used at level {character['level']}{suffix}",
                "Do not add another signature move now.",
                "Use `glass character signature-status <character-id>` to check slots before trying again.",
            )
        )
    return GlassError(str(reason))


def _add_signature_moves_bulk(
    conn,
    campaign_id: str,
    character: dict[str, Any],
    moves: list[dict[str, str]],
    *,
    actor: str,
) -> dict[str, Any]:
    existing_moves = _db.character_signature_moves_list(
        conn,
        campaign_id=campaign_id,
        character_id=character["character_id"],
        visibility=None,
    )
    slots = _signature_move_slots(character["level"])
    if len(existing_moves) + len(moves) > slots:
        next_level = _next_signature_move_unlock(character["level"])
        suffix = (
            f"; next slot unlocks at level {next_level}"
            if next_level is not None
            else "; no more slots are available from level progression"
        )
        raise GlassError(
            agent_instruction(
                f"no signature move slots available for {character['character_id']}: {len(existing_moves)}/{slots} used at level {character['level']} and {len(moves)} requested{suffix}",
                "Do not add these signature moves now.",
                "Use `glass character signature-status <character-id>` to see slot availability.",
            )
        )
    seen = {str(move["name"]).casefold() for move in existing_moves}
    for move in moves:
        key = move["name"].casefold()
        if key in seen:
            raise _signature_move_db_error(character, move["name"], "signature_move_exists")
        seen.add(key)

    added: list[dict[str, Any]] = []
    for move in moves:
        name = move["name"]
        try:
            added.append(
                _db.character_signature_move_add(
                    conn,
                    campaign_id=campaign_id,
                    character_id=character["character_id"],
                    name=name,
                    descriptor=move["descriptor"],
                    body=move["body"],
                    actor=actor,
                )
            )
        except ValueError as exc:
            raise _signature_move_db_error(character, name, str(exc)) from exc
    all_moves = _db.character_signature_moves_list(
        conn,
        campaign_id=campaign_id,
        character_id=character["character_id"],
        visibility="public",
    )
    return {
        "added": added,
        "slots": slots,
        "used": len(all_moves),
        "available": max(0, slots - len(all_moves)),
    }


def _inventory_add(inventory: list[dict[str, Any]], item: dict[str, Any]) -> dict[str, Any]:
    item_id = item["id"]
    qty = int(item["qty"])
    effect_tags = list(item.get("effect_tags") or [])
    prose_name = str(item.get("name") or "").strip()
    descriptor = str(item.get("descriptor") or "").strip()
    entry = next((existing for existing in inventory if existing.get("id") == item_id), None)
    before = int(entry["qty"]) if entry else 0
    if entry:
        entry["qty"] = before + qty
        if effect_tags:
            entry["effect_tags"] = _merge_effect_tags(entry.get("effect_tags"), effect_tags)
        if prose_name:
            entry["name"] = prose_name
        if descriptor:
            entry["descriptor"] = descriptor
    else:
        entry = {"id": item_id, "qty": qty}
        if prose_name:
            entry["name"] = prose_name
        if descriptor:
            entry["descriptor"] = descriptor
        if effect_tags:
            entry["effect_tags"] = effect_tags
        inventory.append(entry)
    after = before + qty
    return {
        "item_id": item_id,
        "qty_before": before,
        "delta": qty,
        "qty_after": after,
        "name": prose_name,
        "descriptor": descriptor,
        "effect_tags": effect_tags,
    }


def _inventory_rm(inventory: list[dict[str, Any]], item: dict[str, Any]) -> dict[str, Any]:
    item_id = item["id"]
    qty = int(item["qty"])
    entry = next((existing for existing in inventory if existing.get("id") == item_id), None)
    before = int(entry["qty"]) if entry else 0
    after = max(0, before - qty)
    if entry:
        entry["qty"] = after
    inventory[:] = [existing for existing in inventory if int(existing.get("qty", 0)) > 0]
    return {
        "item_id": item_id,
        "qty_before": before,
        "delta": -qty,
        "applied_delta": after - before,
        "qty_after": after,
    }


def _normalize_effect_tags(effect_tags: tuple[str, ...]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in effect_tags:
        value = tag.strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(value)
    return normalized


def _merge_effect_tags(existing: Any, additions: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    if isinstance(existing, list):
        for tag in existing:
            if not isinstance(tag, str):
                continue
            value = tag.strip()
            if not value:
                continue
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            merged.append(value)
    for tag in additions:
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(tag)
    return merged
