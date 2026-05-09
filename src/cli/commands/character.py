"""Character commands."""

from __future__ import annotations

import json
import os
import random
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

from .. import db as _db
from .. import workspace as _workspace
from ..campaign import (
    active_campaign_id,
    active_campaign_root,
    lookup_player_character_id,
    pg_connection,
    resolve_active_campaign_workspace,
)
from ..config import REPO_ROOT, Paths, get_paths, load_config
from ..constants import (
    ATTRIBUTE_TIERS,
    ATTRIBUTES,
    RISK_THRESHOLDS,
    SKILL_TIERS,
    STARTER_MESSAGE_TYPES,
)
from ..entities import (
    markdown_title,
    parse_frontmatter,
    parse_sections,
    upsert_entity_from_path,
)
from ..errors import GlassError
from ..ids import new_id, now_iso, slugify
from ..messages import (
    infer_player_from_path,
    load_message_types,
    message_visible_to,
    player_dirs,
    require_message_type,
    require_recipient,
    roster,
)
from ..paths_resolve import (
    clean_relative_path,
    display_path,
    ensure_under,
    ensure_under_any,
    resolve_content_path,
    resolve_note_write_path,
)
from ..role import (
    Role,
    actor_for_turn,
    assert_character_writable,
    current_role,
    require_dm,
    require_player,
    role_label_for_turn,
)
from ..state import (
    active_session_file,
    active_session_id,
    append_audit,
    audit_path,
    commit,
    current_mode_record,
    default_state,
    inline_event_lines,
    load_state,
    normalize_state,
    queue_event,
    save_state,
    session_dir,
    state_path,
    state_summary,
    transcript_path,
    write_active_session,
)
from ..validation import (
    assert_attribute_name,
    clamp,
    outcome_for_margin,
    validate_key_values,
)
from ..yaml_io import (
    command_params,
    emit,
    make_jsonable,
    read_body,
    to_yaml,
    yaml_scalar,
)


@click.group()
def character() -> None:
    """Character sheet and hard-state commands."""


@character.command("new")
@click.argument("character_id")
@click.option("--player", "player_id", required=True)
@click.option("--name")
@click.option("--archetype", default="")
@click.option("--pronouns", default="")
@click.option("--hp", "hp_max", type=int, default=10)
@click.option("--attribute", "attribute_values", multiple=True, help="Repeatable name=tier.")
@click.option("--skill", "skill_values", multiple=True, help="Repeatable name=tier.")
@click.option("--tag", "tags", multiple=True)
@click.pass_context
def character_new(
    ctx: click.Context,
    character_id: str,
    player_id: str,
    name: str | None,
    archetype: str,
    pronouns: str,
    hp_max: int,
    attribute_values: tuple[str, ...],
    skill_values: tuple[str, ...],
    tags: tuple[str, ...],
) -> None:
    role = current_role()
    if role.kind == "player" and player_id != role.actor:
        raise GlassError("permission denied: players may create only their own character")
    if hp_max <= 0:
        raise GlassError("--hp must be greater than zero")
    paths = get_paths()
    state = load_state(paths)
    campaign_id = active_campaign_id()

    attributes = {attribute: "standard" for attribute in ATTRIBUTES}
    attributes.update(validate_key_values(attribute_values, ATTRIBUTE_TIERS, "attribute"))
    for attribute_name in attributes:
        assert_attribute_name(attribute_name)
    skills = validate_key_values(skill_values, SKILL_TIERS, "skill")

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
            name=name or character_id,
            archetype=archetype,
            pronouns=pronouns,
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
    state = load_state(paths)
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
    state = load_state(paths)
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
                "archetype": c["archetype"],
                "hp": c["hp"],
                "momentum": c["momentum"],
            }
            for c in characters
        ],
    }
    append_audit(paths, state, ctx, "character.list", {}, result)
    emit(result)


@character.command("set-hp", context_settings={"ignore_unknown_options": True})
@click.argument("character_id")
@click.argument("delta", type=int)
@click.pass_context
def character_set_hp(ctx: click.Context, character_id: str, delta: int) -> None:
    paths = get_paths()
    state = load_state(paths)
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
    state = load_state(paths)
    campaign_id = active_campaign_id()
    session_id = state["session"]["id"]
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
    state = load_state(paths)
    campaign_id = active_campaign_id()
    session_id = state["session"]["id"]
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
    state = load_state(paths)
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
@click.pass_context
def character_inventory_add(
    ctx: click.Context, character_id: str, item_id: str, qty: int
) -> None:
    if qty <= 0:
        raise GlassError("--qty must be greater than zero")
    paths = get_paths()
    state = load_state(paths)
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
        else:
            inventory.append({"id": item_id, "qty": qty})
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
        "inventory": updated["inventory"],
    }
    commit(
        paths,
        state,
        ctx,
        "character.inventory-add",
        command_params(character_id=character_id, item_id=item_id, qty=qty),
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
    state = load_state(paths)
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


