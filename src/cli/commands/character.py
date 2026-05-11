"""Character commands."""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

import click

from .. import db as _db
from ..campaign import active_campaign_id, pg_connection
from ..config import Paths, get_paths
from ..constants import ATTRIBUTE_TIERS, ATTRIBUTES, SKILL_TIERS
from ..errors import GlassError
from ..paths_resolve import display_path
from ..role import assert_character_writable, current_role, require_dm
from ..state import append_audit, commit, current_mode_record, load_state, queue_event
from ..validation import assert_attribute_name, validate_key_values
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
@click.option("--hp", "hp_max", type=int, default=10)
@click.option("--attribute", "attribute_values", multiple=True, help="Repeatable name=tier.")
@click.option("--skill", "skill_values", multiple=True, help="Repeatable name=tier.")
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
    hp_max: int,
    attribute_values: tuple[str, ...],
    skill_values: tuple[str, ...],
    tags: tuple[str, ...],
) -> None:
    role = current_role()
    if role.kind == "player" and player_id != role.actor:
        raise GlassError("permission denied: players may create only their own character")
    name = _require_nonempty(name, "--name")
    species = _require_nonempty(species, "--species")
    culture = _require_nonempty(culture, "--culture")
    archetype = _require_nonempty(archetype, "--archetype")
    organization_role = _require_nonempty(organization_role, "--org-role")
    bio = _require_nonempty(bio, "--bio")
    normalized_goals = _normalize_goals(goals)
    if hp_max <= 0:
        raise GlassError("--hp must be greater than zero")
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

    with pg_connection() as conn:
        if _db.character_exists(conn, campaign_id, character_id):
            raise GlassError(
                f"character already exists in campaign {campaign_id!r}: {character_id}"
            )
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
            attributes=attributes,
            skills=skills,
            hp_max=hp_max,
            tags=list(tags),
        )

    queue_event(
        state,
        role.actor,
        f"character new {character_id} ({record['name']}, {player_id})",
    )
    commit(
        paths,
        state,
        ctx,
        "character.new",
        command_params(character_id=character_id, player_id=player_id),
        {"character": record},
    )


@character.command("get")
@click.argument("character_id")
@click.pass_context
def character_get(ctx: click.Context, character_id: str) -> None:
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    campaign_id = active_campaign_id()
    with pg_connection() as conn:
        character = _db.character_get(conn, campaign_id, character_id)
    if character is None:
        raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
    result = {"character": character}
    append_audit(
        paths,
        state,
        ctx,
        "character.get",
        command_params(character_id=character_id),
        result,
    )
    emit(result)


@character.command("list")
@click.pass_context
def character_list(ctx: click.Context) -> None:
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
                "hp": c["hp"],
                "momentum": c["momentum"],
            }
            for c in characters
        ],
    }
    append_audit(paths, state, ctx, "character.list", {}, result)
    emit(result)


@character.command("bulk-get")
@click.argument("character_ids", nargs=-1)
@click.option("--all", "include_all", is_flag=True, help="Return every character.")
@click.option(
    "--signatures/--no-signatures",
    default=True,
    show_default=True,
    help="Include signature move slot status from markdown.",
)
@click.pass_context
def character_bulk_get(
    ctx: click.Context,
    character_ids: tuple[str, ...],
    include_all: bool,
    signatures: bool,
) -> None:
    """Read multiple full character records with one tool call."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    ids = _unique_nonempty(character_ids)
    if include_all and ids:
        raise GlassError("use either character ids or --all, not both")
    if not include_all and not ids:
        raise GlassError("provide one or more character ids, or pass --all")

    with pg_connection() as conn:
        if include_all:
            characters = _db.character_list(conn, campaign_id)
        else:
            characters = []
            missing: list[str] = []
            for character_id in ids:
                character = _db.character_get(conn, campaign_id, character_id)
                if character is None:
                    missing.append(character_id)
                else:
                    characters.append(character)
    if missing:
        raise GlassError(
            f"unknown character(s) in campaign {campaign_id!r}: {', '.join(missing)}"
        )

    result: dict[str, Any] = {
        "campaign_id": campaign_id,
        "count": len(characters),
        "characters": characters,
    }
    if signatures:
        result["signature_moves"] = {
            character["character_id"]: _signature_status(paths, campaign_id, character)
            for character in characters
        }

    append_audit(
        paths,
        state,
        ctx,
        "character.bulk-get",
        command_params(character_ids=ids, all=include_all, signatures=signatures),
        result,
    )
    emit(result)


@character.command("mirror")
@click.argument("character_id")
@click.pass_context
def character_mirror(ctx: click.Context, character_id: str) -> None:
    """Write the canonical public character display from Postgres."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    campaign_id = active_campaign_id()
    with pg_connection() as conn:
        character = _db.character_get(conn, campaign_id, character_id)
    if character is None:
        raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
    role = assert_character_writable(character)
    path = _public_character_mirror_path(paths, campaign_id, character)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = _render_public_character_mirror(character)
    path.write_text(body, encoding="utf-8")
    queue_event(state, role.actor, f"character mirror {character_id}")
    result = {
        "character_id": character_id,
        "path": display_path(path),
        "bytes": len(body.encode("utf-8")),
    }
    commit(
        paths,
        state,
        ctx,
        "character.mirror",
        command_params(character_id=character_id, path=result["path"]),
        result,
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
        raise GlassError("use either --json or --from, not both")
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
                raise GlassError(
                    f"unknown character {character_id!r} in campaign {campaign_id!r}"
                )
            assert_character_writable(character)

            operations: list[str] = []
            updated = character
            set_fields = _normalize_character_set_fields(update["set"], updated)
            if "skills" in set_fields and _is_character_creation_mode(state):
                _validate_starting_skill_budget(set_fields["skills"])
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
                    paths,
                    campaign_id,
                    updated,
                    update["signature_moves"],
                )
                operations.append("signature_moves")

            mirror_result = None
            if update["mirror"]:
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
    """Show signature move slots and current markdown entries."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    with pg_connection() as conn:
        character = _db.character_get(conn, campaign_id, character_id)
    if character is None:
        raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")

    result = _signature_status(paths, campaign_id, character)
    append_audit(
        paths,
        state,
        ctx,
        "character.signature-status",
        command_params(character_id=character_id),
        result,
    )
    emit(result)


@character.command("signature-add")
@click.argument("character_id")
@click.argument("name")
@click.option("--body", default="", help="Freeform markdown body for the move.")
@click.option(
    "--from",
    "source_path",
    type=click.Path(path_type=Path),
    help="Read freeform move markdown from this draft file.",
)
@click.option("--look", default="", help="What the move looks/sounds/feels like.")
@click.option("--use", "usual_use", default="", help="When the character reaches for it.")
@click.option("--tell", default="", help="Trace, cost, risk, or who might recognize it.")
@click.pass_context
def character_signature_add(
    ctx: click.Context,
    character_id: str,
    name: str,
    body: str,
    source_path: Path | None,
    look: str,
    usual_use: str,
    tell: str,
) -> None:
    """Append one signature move if the character has an open slot."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    with pg_connection() as conn:
        character = _db.character_get(conn, campaign_id, character_id)
    if character is None:
        raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
    role = assert_character_writable(character)

    name = _require_nonempty(name, "name")
    path = _signature_moves_path(paths, campaign_id, character)
    existing_body = path.read_text(encoding="utf-8") if path.exists() else ""
    move_names = _signature_move_names(existing_body)
    duplicate = name.casefold()
    if duplicate in {move.casefold() for move in move_names}:
        raise GlassError(f"signature move already exists for {character_id}: {name}")

    slots = _signature_move_slots(character["level"])
    if len(move_names) >= slots:
        next_level = _next_signature_move_unlock(character["level"])
        suffix = (
            f"; next slot unlocks at level {next_level}"
            if next_level is not None
            else "; no more slots are available from level progression"
        )
        raise GlassError(
            f"no signature move slots available for {character_id}: "
            f"{len(move_names)}/{slots} used at level {character['level']}{suffix}"
        )

    move_body = _signature_move_body(
        body=body,
        source_path=source_path,
        look=look,
        usual_use=usual_use,
        tell=tell,
    )
    updated = _append_signature_move(existing_body, character, name, move_body)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding="utf-8")

    queue_event(state, role.actor, f"signature move added for {character_id}: {name}")
    result = {
        "character_id": character_id,
        "player_id": character["player_id"],
        "level": character["level"],
        "slots": slots,
        "used": len(move_names) + 1,
        "available": slots - len(move_names) - 1,
        "path": display_path(path),
        "move": name,
    }
    commit(
        paths,
        state,
        ctx,
        "character.signature-add",
        command_params(character_id=character_id, name=name),
        result,
    )


@character.command("set-hp", context_settings={"ignore_unknown_options": True})
@click.argument("character_id")
@click.argument("delta", type=int)
@click.pass_context
def character_set_hp(ctx: click.Context, character_id: str, delta: int) -> None:
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    campaign_id = active_campaign_id()

    with pg_connection() as conn:
        existing = _db.character_get(conn, campaign_id, character_id)
        if existing is None:
            raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
        role = assert_character_writable(existing)
        try:
            updated, before, after = _db.character_update_hp(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                delta=delta,
            )
        except LookupError:
            raise GlassError(f"unknown character {character_id!r}") from None

    sign = f"{delta:+d}"
    summary = f"{character_id} hp {sign} ({before} -> {after})"
    queue_event(state, role.actor, summary)
    result = {
        "character_id": character_id,
        "hp_before": before,
        "delta": delta,
        "applied_delta": after - before,
        "hp_after": after,
        "hp_max": updated["hp"]["max"],
    }
    commit(
        paths,
        state,
        ctx,
        "character.set-hp",
        command_params(character_id=character_id, delta=delta),
        result,
    )


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
            raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
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
            raise GlassError(f"unknown character {character_id!r}") from None

    sign = f"{delta:+d}"
    summary = f"{character_id} xp {sign} ({before} -> {after}, level {updated['level']})"
    queue_event(state, role.actor, summary)
    pending_levels = max(0, (after // 10) + 1 - int(updated["level"]))
    result = {
        "character_id": character_id,
        "xp_before": before,
        "delta": delta,
        "xp_after": after,
        "level": updated["level"],
        "pending_level_ups": pending_levels,
        "reason": reason,
    }
    commit(
        paths,
        state,
        ctx,
        "character.award-xp",
        command_params(character_id=character_id, delta=delta, reason=reason),
        result,
    )


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
            raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
        role = assert_character_writable(existing)

        from_level = int(existing["level"])
        xp = int(existing["xp"])
        if (xp // 10) + 1 <= from_level:
            raise GlassError(
                f"{character_id} has no pending level-ups (xp {xp}, level {from_level})"
            )

        to_level = from_level + 1
        attribute_to_tier: str | None = None
        if to_level % 4 == 0:
            if not attribute_name:
                raise GlassError(
                    f"reaching level {to_level} requires an attribute bump; "
                    f"pass --attribute <name>"
                )
            assert_attribute_name(attribute_name)
            current_tier = existing["attributes"].get(attribute_name, "standard")
            ladder = _db.ATTRIBUTE_TIER_LADDER
            try:
                idx = ladder.index(current_tier)
            except ValueError:
                raise GlassError(
                    f"attribute {attribute_name!r} is at non-bumpable tier {current_tier!r}"
                ) from None
            if idx >= len(ladder) - 1:
                raise GlassError(
                    f"attribute {attribute_name!r} is already at {current_tier!r}; "
                    f"cannot bump further (transcendent is plot-only)"
                )
            attribute_to_tier = ladder[idx + 1]
        elif attribute_name:
            raise GlassError(
                f"--attribute is only valid when crossing a multiple of 4 "
                f"(this is level {to_level})"
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
            raise GlassError(f"unknown character {character_id!r}") from None

    parts = [f"{character_id} level {from_level} -> {to_level}", f"hp_max +{hp_roll}"]
    if attribute_to_tier:
        parts.append(f"{attribute_name} -> {attribute_to_tier}")
    if momentum_ceiling_bumps:
        parts.append(
            f"momentum_ceiling -> {existing['momentum']['ceiling'] + momentum_ceiling_bumps}"
        )
    summary = ", ".join(parts)
    queue_event(state, role.actor, summary)
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
    }
    commit(
        paths,
        state,
        ctx,
        "character.level-up",
        command_params(character_id=character_id, attribute=attribute_name),
        result,
    )


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
            raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
        role = assert_character_writable(existing)
        try:
            updated, before, after = _db.character_update_momentum(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                value=value,
            )
        except LookupError:
            raise GlassError(f"unknown character {character_id!r}") from None

    summary = f"{character_id} momentum {before:+d} -> {after:+d}"
    queue_event(state, role.actor, summary)
    result = {
        "character_id": character_id,
        "momentum_before": before,
        "requested": value,
        "momentum_after": after,
        "floor": updated["momentum"]["floor"],
        "ceiling": updated["momentum"]["ceiling"],
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
    effect_tags: tuple[str, ...],
) -> None:
    if qty <= 0:
        raise GlassError("--qty must be greater than zero")
    normalized_effect_tags = _normalize_effect_tags(effect_tags)
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    campaign_id = active_campaign_id()

    with pg_connection() as conn:
        existing = _db.character_get(conn, campaign_id, character_id)
        if existing is None:
            raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
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
        else:
            entry: dict[str, Any] = {"id": item_id, "qty": qty}
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
    result = {
        "character_id": character_id,
        "item_id": item_id,
        "qty_before": before,
        "delta": qty,
        "qty_after": after,
        "effect_tags": normalized_effect_tags,
        "inventory": updated["inventory"],
    }
    commit(
        paths,
        state,
        ctx,
        "character.inventory-add",
        command_params(
            character_id=character_id,
            item_id=item_id,
            qty=qty,
            effect_tags=normalized_effect_tags,
        ),
        result,
    )


@character.command("inventory-rm")
@click.argument("character_id")
@click.argument("item_id")
@click.option("--qty", type=int, default=1)
@click.pass_context
def character_inventory_rm(
    ctx: click.Context, character_id: str, item_id: str, qty: int
) -> None:
    if qty <= 0:
        raise GlassError("--qty must be greater than zero")
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    campaign_id = active_campaign_id()

    with pg_connection() as conn:
        existing = _db.character_get(conn, campaign_id, character_id)
        if existing is None:
            raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
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
    result = {
        "character_id": character_id,
        "item_id": item_id,
        "qty_before": before,
        "delta": -qty,
        "applied_delta": after - before,
        "qty_after": after,
        "inventory": updated["inventory"],
    }
    commit(
        paths,
        state,
        ctx,
        "character.inventory-rm",
        command_params(character_id=character_id, item_id=item_id, qty=qty),
        result,
    )


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
    """DM-only: add a lasting character consequence.

    Consequences are prose-backed state, not a condition engine. Use them for
    injuries, capture, obligations, disgrace, gear strain, or other effects
    that need to persist beyond the current line of narration.
    """
    role = require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    visibility = "public" if public else "dm"
    with pg_connection() as conn:
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
            raise GlassError(f"unknown character {character_id!r}") from None
    queue_event(
        state,
        role.actor,
        f"{character_id} consequence {severity}: {label} ({scope}, {visibility})",
    )
    commit(
        paths,
        state,
        ctx,
        "character.consequence-add",
        command_params(
            character_id=character_id,
            label=label,
            severity=severity,
            scope=scope,
            visibility=visibility,
        ),
        {"consequence": consequence},
    )


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
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    if role.kind == "player" and include_hidden:
        raise GlassError("permission denied: players cannot read hidden consequences")
    with pg_connection() as conn:
        character = _db.character_get(conn, campaign_id, character_id)
        if character is None:
            raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
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
        ctx,
        "character.consequence-list",
        command_params(
            character_id=character_id,
            all=include_resolved,
            hidden=include_hidden,
        ),
        result,
    )
    emit(result)


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
    """DM-only: resolve a lasting character consequence."""
    role = require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    with pg_connection() as conn:
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
            raise GlassError(f"unknown consequence {consequence_id!r}") from None
    queue_event(
        state,
        role.actor,
        f"{character_id} consequence resolved: {consequence['label']}",
    )
    commit(
        paths,
        state,
        ctx,
        "character.consequence-resolve",
        command_params(
            character_id=character_id,
            consequence_id=consequence_id,
            note=note,
        ),
        {"consequence": consequence},
    )


def _require_nonempty(value: str, option_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise GlassError(f"{option_name} is required")
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
        raise GlassError("character creation requires 2-3 --goal values")
    return normalized


def _validate_starting_skill_budget(skills: dict[str, str]) -> None:
    counts = Counter(skills.values())
    expected = Counter({"apprentice": 2, "artisan": 1})
    if counts == expected:
        return
    raise GlassError(
        "character creation requires exactly 3 trained skills: "
        "2 apprentice and 1 artisan. Do not list fool, virtuoso, or legend "
        "skills at level 1; unlisted skills default to fool."
    )


def _is_character_creation_mode(state: dict[str, Any]) -> bool:
    current = current_mode_record(state)
    return bool(current and current.get("mode") == "character-creation")


def _read_json_payload(text: str, label: str) -> Any:
    if not text.strip():
        raise GlassError(f"{label} JSON payload is empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise GlassError(f"invalid {label} JSON: {exc.msg} at line {exc.lineno}") from exc


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
            raise GlassError("bulk update payload must use either characters or updates, not both")
        if has_characters or has_updates:
            raw_updates = payload["characters"] if has_characters else payload["updates"]
            if not isinstance(raw_updates, list):
                raise GlassError("bulk update characters/updates must be a list")
            default_mirror = _optional_bool(payload.get("mirror"), default=False)
        else:
            raw_updates = [payload]
            default_mirror = _optional_bool(payload.get("mirror"), default=False)
    else:
        raise GlassError("bulk update payload must be an object or list")

    if not raw_updates:
        raise GlassError("bulk update payload has no character updates")

    updates: list[dict[str, Any]] = []
    for index, raw_update in enumerate(raw_updates, start=1):
        if not isinstance(raw_update, dict):
            raise GlassError(f"bulk update #{index} must be an object")
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
                f"bulk update #{index} has unsupported field(s): {', '.join(unknown)}"
            )
        character_id = str(
            raw_update.get("character_id") or raw_update.get("id") or ""
        ).strip()
        if not character_id:
            raise GlassError(f"bulk update #{index} is missing character_id")
        set_fields = raw_update.get("set") or {}
        if not isinstance(set_fields, dict):
            raise GlassError(f"bulk update {character_id}: set must be an object")

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
            ),
            "inventory_rm": _normalize_inventory_items(
                inventory_rm_value,
                "inventory_rm",
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
            raise GlassError(f"bulk update {character_id}: no mutations requested")
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
    raise GlassError("mirror must be true or false")


def _optional_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise GlassError(f"{field_name} must be an integer")
    return value


def _normalize_inventory_items(value: Any, field_name: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    raw_items = value if isinstance(value, list) else [value]
    items: list[dict[str, Any]] = []
    for index, raw_item in enumerate(raw_items, start=1):
        if isinstance(raw_item, str):
            item_id = raw_item.strip()
            qty = 1
            effect_tags: list[str] = []
        elif isinstance(raw_item, dict):
            item_id = str(raw_item.get("id") or raw_item.get("item_id") or "").strip()
            qty = raw_item.get("qty", 1)
            if isinstance(qty, bool) or not isinstance(qty, int):
                raise GlassError(f"{field_name} item #{index}: qty must be an integer")
            effect_tags = _normalize_effect_tags(
                tuple(_string_list(raw_item.get("effect_tags") or raw_item.get("effect_tag")))
            )
        else:
            raise GlassError(f"{field_name} item #{index} must be a string or object")
        if not item_id:
            raise GlassError(f"{field_name} item #{index} is missing id")
        if qty <= 0:
            raise GlassError(f"{field_name} item #{index}: qty must be greater than zero")
        items.append({"id": item_id, "qty": qty, "effect_tags": effect_tags})
    return items


def _normalize_signature_move_updates(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    raw_moves = value if isinstance(value, list) else [value]
    moves: list[dict[str, str]] = []
    for index, raw_move in enumerate(raw_moves, start=1):
        if not isinstance(raw_move, dict):
            raise GlassError(f"signature move #{index} must be an object")
        name = _require_nonempty(str(raw_move.get("name") or ""), "signature move name")
        body = _signature_move_body(
            body=str(raw_move.get("body") or ""),
            source_path=None,
            look=str(raw_move.get("look") or ""),
            usual_use=str(raw_move.get("use") or raw_move.get("usual_use") or ""),
            tell=str(
                raw_move.get("tell")
                or raw_move.get("tells")
                or raw_move.get("tells_costs")
                or ""
            ),
        )
        moves.append({"name": name, "body": body})
    return moves


def _normalize_character_set_fields(
    raw_fields: dict[str, Any],
    existing: dict[str, Any],
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    aliases = {
        "race": "species",
        "org_role": "organization_role",
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
        "attributes",
        "skills",
        "tags",
    }
    for raw_name, value in raw_fields.items():
        name = aliases.get(raw_name, raw_name)
        if name not in allowed:
            raise GlassError(f"unsupported character set field: {raw_name}")
        if name in {"name", "species", "culture", "archetype", "organization_role", "bio"}:
            fields[name] = _require_nonempty(str(value), name)
        elif name == "pronouns":
            fields[name] = str(value).strip()
        elif name == "goals":
            fields[name] = _normalize_goals(tuple(_string_list(value)))
        elif name == "attributes":
            merged = dict(existing.get("attributes") or {})
            merged.update(_normalize_attribute_map(value))
            fields[name] = merged
        elif name == "skills":
            merged = dict(existing.get("skills") or {})
            merged.update(_normalize_skill_map(value))
            fields[name] = merged
        elif name == "tags":
            fields[name] = _string_list(value)
    return fields


def _normalize_attribute_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise GlassError("attributes must be an object")
    normalized: dict[str, str] = {}
    for name, tier in value.items():
        attribute = str(name).strip()
        assert_attribute_name(attribute)
        tier_name = str(tier).strip()
        if tier_name not in ATTRIBUTE_TIERS:
            raise GlassError(f"invalid attribute tier for {attribute}: {tier_name}")
        normalized[attribute] = tier_name
    return normalized


def _normalize_skill_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise GlassError("skills must be an object")
    normalized: dict[str, str] = {}
    for name, tier in value.items():
        skill = str(name).strip()
        if not skill:
            raise GlassError("skill names must be non-empty")
        tier_name = str(tier).strip()
        if tier_name not in SKILL_TIERS:
            raise GlassError(f"invalid skill tier for {skill}: {tier_name}")
        normalized[skill] = tier_name
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


def _public_character_mirror_path(
    paths: Paths,
    campaign_id: str,
    character: dict[str, Any],
) -> Path:
    return (
        paths.campaigns
        / campaign_id
        / "players"
        / str(character["player_id"])
        / "public"
        / "character.md"
    )


def _write_public_character_mirror(
    paths: Paths,
    campaign_id: str,
    character: dict[str, Any],
) -> dict[str, Any]:
    path = _public_character_mirror_path(paths, campaign_id, character)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = _render_public_character_mirror(character)
    path.write_text(body, encoding="utf-8")
    return {
        "path": display_path(path),
        "bytes": len(body.encode("utf-8")),
    }


def _render_public_character_mirror(character: dict[str, Any]) -> str:
    lines = [
        "---",
        f"title: {character['name']}",
        "type: character-display",
        f"character_id: {character['character_id']}",
        f"player_id: {character['player_id']}",
        "---",
        "",
        f"# {character['name']}",
        "",
        f"- **Player:** {character['player_id']}",
        f"- **Species:** {character['species']}",
        f"- **Culture:** {character['culture']}",
        f"- **Archetype:** {character['archetype']}",
        f"- **Organization role:** {character['organization_role']}",
        f"- **Pronouns:** {character.get('pronouns') or 'unspecified'}",
        f"- **Level:** {character['level']} ({character['xp']} XP)",
        f"- **HP:** {character['hp']['current']}/{character['hp']['max']}",
        (
            f"- **Momentum:** {character['momentum']['current']} "
            f"({character['momentum']['floor']} to {character['momentum']['ceiling']})"
        ),
        "",
        "## Bio",
        "",
        str(character["bio"]).strip(),
        "",
        "## Goals",
        "",
    ]
    lines.extend(f"- {goal}" for goal in character.get("goals", []))
    lines.extend(["", "## Attributes", ""])
    for attribute in ATTRIBUTES:
        lines.append(f"- **{attribute}:** {character['attributes'].get(attribute, 'standard')}")
    lines.extend(["", "## Skills", ""])
    for skill, tier in sorted(character.get("skills", {}).items()):
        lines.append(f"- **{skill}:** {tier}")
    lines.extend(["", "## Inventory", ""])
    inventory = list(character.get("inventory") or [])
    if inventory:
        for item in inventory:
            item_line = f"- **{item.get('id', 'item')}:** x{int(item.get('qty', 1))}"
            effect_tags = item.get("effect_tags")
            if isinstance(effect_tags, list) and effect_tags:
                item_line += " — " + "; ".join(str(tag) for tag in effect_tags)
            lines.append(item_line)
    else:
        lines.append("- None recorded.")
    tags = list(character.get("tags") or [])
    if tags:
        lines.extend(["", "## Tags", ""])
        lines.append(", ".join(tags))
    return "\n".join(lines).rstrip() + "\n"


SIGNATURE_MOVE_UNLOCK_LEVELS = (1, 3, 5, 7, 9)


def _signature_move_slots(level: int) -> int:
    return sum(1 for unlock in SIGNATURE_MOVE_UNLOCK_LEVELS if level >= unlock)


def _next_signature_move_unlock(level: int) -> int | None:
    for unlock in SIGNATURE_MOVE_UNLOCK_LEVELS:
        if level < unlock:
            return unlock
    return None


def _signature_moves_path(
    paths: Paths,
    campaign_id: str,
    character: dict[str, Any],
) -> Path:
    return (
        paths.campaigns
        / campaign_id
        / "players"
        / str(character["player_id"])
        / "signature-moves.md"
    )


def _signature_status(
    paths: Paths,
    campaign_id: str,
    character: dict[str, Any],
) -> dict[str, Any]:
    path = _signature_moves_path(paths, campaign_id, character)
    body = path.read_text(encoding="utf-8") if path.exists() else ""
    move_names = _signature_move_names(body)
    slots = _signature_move_slots(character["level"])
    return {
        "character_id": character["character_id"],
        "player_id": character["player_id"],
        "level": character["level"],
        "slots": slots,
        "used": len(move_names),
        "available": max(0, slots - len(move_names)),
        "over_slots": len(move_names) > slots,
        "next_unlock_level": _next_signature_move_unlock(character["level"]),
        "path": display_path(path),
        "moves": move_names,
    }


def _signature_move_names(body: str) -> list[str]:
    names: list[str] = []
    in_moves = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_moves = stripped.casefold() == "## moves"
            continue
        if not in_moves:
            continue
        if stripped.startswith("### "):
            name = stripped.removeprefix("### ").strip()
            if name and name.casefold() != "move name":
                names.append(name)
    return names


def _signature_move_body(
    *,
    body: str,
    source_path: Path | None,
    look: str,
    usual_use: str,
    tell: str,
) -> str:
    if body.strip() and source_path is not None:
        raise GlassError("use either --body or --from, not both")
    if source_path is not None:
        try:
            source_body = source_path.expanduser().read_text(encoding="utf-8")
        except OSError as exc:
            raise GlassError(f"cannot read signature move draft: {source_path}") from exc
        cleaned = source_body.strip()
        if not cleaned:
            raise GlassError("signature move draft is empty")
        return cleaned
    if body.strip():
        return body.strip()

    look = _require_nonempty(look, "--look")
    usual_use = _require_nonempty(usual_use, "--use")
    tell = _require_nonempty(tell, "--tell")
    return "\n".join(
        [
            f"- **Look:** {look}",
            f"- **Usual use:** {usual_use}",
            f"- **Tells/costs:** {tell}",
        ]
    )


def _append_signature_move(
    existing_body: str,
    character: dict[str, Any],
    name: str,
    move_body: str,
) -> str:
    body = existing_body.strip()
    if not body:
        body = _render_signature_moves_header(character).strip()
    if "## Moves" not in body:
        body = body.rstrip() + "\n\n## Moves"
    body = _strip_signature_move_placeholder(body)
    entry = f"### {name}\n\n{move_body.strip()}"
    return body.rstrip() + "\n\n" + entry + "\n"


def _render_signature_moves_header(character: dict[str, Any]) -> str:
    return (
        "---\n"
        f"title: {character['name']}'s Signature Moves\n"
        "status: player-maintained\n"
        "---\n\n"
        "# Signature Moves\n\n"
        "Start with one simple move at level 1. Add another slot at levels 3, "
        "5, 7, and 9, for five total slots by level 9. These are narrative "
        "consistency tools, not powers with guaranteed mechanics. A move "
        "should be something active you can do under pressure, not just a tic, "
        "trait, or possession. Spell-like resonance techniques are valid "
        "signature moves.\n\n"
        "Use `glass character signature-status <character-id>` before adding "
        "a move, and `glass character signature-add <character-id> <name>` "
        "when repetition makes a move identity-defining.\n\n"
        "## Moves\n"
    )


def _strip_signature_move_placeholder(body: str) -> str:
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if line.strip().casefold() == "### move name":
            return "\n".join(lines[:index]).rstrip()
    return body


def _add_signature_moves_bulk(
    paths: Paths,
    campaign_id: str,
    character: dict[str, Any],
    moves: list[dict[str, str]],
) -> dict[str, Any]:
    path = _signature_moves_path(paths, campaign_id, character)
    body = path.read_text(encoding="utf-8") if path.exists() else ""
    move_names = _signature_move_names(body)
    slots = _signature_move_slots(character["level"])
    if len(move_names) + len(moves) > slots:
        next_level = _next_signature_move_unlock(character["level"])
        suffix = (
            f"; next slot unlocks at level {next_level}"
            if next_level is not None
            else "; no more slots are available from level progression"
        )
        raise GlassError(
            f"no signature move slots available for {character['character_id']}: "
            f"{len(move_names)}/{slots} used at level {character['level']} "
            f"and {len(moves)} requested{suffix}"
        )
    seen = {move.casefold() for move in move_names}
    added: list[str] = []
    for move in moves:
        name = move["name"]
        key = name.casefold()
        if key in seen:
            raise GlassError(
                f"signature move already exists for {character['character_id']}: {name}"
            )
        seen.add(key)
        body = _append_signature_move(body, character, name, move["body"])
        added.append(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return {
        "path": display_path(path),
        "added": added,
        "slots": slots,
        "used": len(move_names) + len(added),
        "available": slots - len(move_names) - len(added),
    }


def _inventory_add(inventory: list[dict[str, Any]], item: dict[str, Any]) -> dict[str, Any]:
    item_id = item["id"]
    qty = int(item["qty"])
    effect_tags = list(item.get("effect_tags") or [])
    entry = next((existing for existing in inventory if existing.get("id") == item_id), None)
    before = int(entry["qty"]) if entry else 0
    if entry:
        entry["qty"] = before + qty
        if effect_tags:
            entry["effect_tags"] = _merge_effect_tags(entry.get("effect_tags"), effect_tags)
    else:
        entry = {"id": item_id, "qty": qty}
        if effect_tags:
            entry["effect_tags"] = effect_tags
        inventory.append(entry)
    after = before + qty
    return {
        "item_id": item_id,
        "qty_before": before,
        "delta": qty,
        "qty_after": after,
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
