"""Entry point for the `glass` CLI.

The CLI is the in-session tool surface for Agents of Glass. It intentionally
keeps prose in markdown and records only coherence-critical state: sessions,
mode labels, dice, character numbers, messages, note ratification state, and
turn metadata.

Helpers live in sibling modules (errors, constants, ids, yaml_io, config,
role, paths_resolve, validation, state, campaign, messages, entities). This
file holds only the click command tree; per-group extraction to `commands/`
is the next refactor step.
"""

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

from . import db as _db
from . import workspace as _workspace
from .campaign import (
    active_campaign_id,
    active_campaign_root,
    lookup_player_character_id,
    pg_connection,
    resolve_active_campaign_workspace,
)
from .config import REPO_ROOT, Paths, get_paths, load_config
from .constants import (
    ATTRIBUTE_TIERS,
    ATTRIBUTES,
    RISK_THRESHOLDS,
    SKILL_TIERS,
    STARTER_MESSAGE_TYPES,
)
from .entities import (
    markdown_title,
    parse_frontmatter,
    parse_sections,
    upsert_entity_from_path,
)
from .errors import GlassError
from .ids import new_id, now_iso, slugify
from .messages import (
    infer_player_from_path,
    load_message_types,
    message_visible_to,
    player_dirs,
    require_message_type,
    require_recipient,
    roster,
)
from .paths_resolve import (
    clean_relative_path,
    display_path,
    ensure_under,
    ensure_under_any,
    resolve_content_path,
    resolve_note_write_path,
)
from .role import (
    Role,
    actor_for_turn,
    assert_character_writable,
    current_role,
    require_dm,
    require_player,
    role_label_for_turn,
)
from .state import (
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
from .validation import (
    assert_attribute_name,
    clamp,
    outcome_for_margin,
    validate_key_values,
)
from .yaml_io import (
    command_params,
    emit,
    make_jsonable,
    read_body,
    to_yaml,
    yaml_scalar,
)


@click.group()
def main() -> None:
    """In-session state CLI for Agents of Glass."""


@main.group()
def session() -> None:
    """Session lifecycle commands."""


@session.command("new")
@click.option("--campaign", required=True, help="Human-readable campaign name.")
@click.option("--session-id", help="Explicit session id. Defaults to campaign slug + timestamp.")
@click.pass_context
def session_new(ctx: click.Context, campaign: str, session_id: str | None) -> None:
    paths = get_paths()
    paths.sessions.mkdir(parents=True, exist_ok=True)
    if not session_id:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        session_id = f"{slugify(campaign)}-{stamp}"
    session_id = slugify(session_id)
    directory = session_dir(paths, session_id)
    if directory.exists():
        raise GlassError(f"session already exists: {session_id}")

    state = default_state(session_id, campaign)
    directory.mkdir(parents=True, exist_ok=False)
    transcript_path(paths, session_id).write_text(
        f"# {campaign}\n\nSession: `{session_id}`\n\n", encoding="utf-8"
    )
    (directory / "scene-framing.md").write_text("# Scene Framing\n\n", encoding="utf-8")
    save_state(paths, state)
    write_active_session(paths, session_id)
    result = {
        "session_id": session_id,
        "campaign": campaign,
        "status": "active",
        "path": display_path(directory),
        "active": True,
    }
    append_audit(paths, state, ctx, "session.new", command_params(campaign=campaign), result)
    emit(result)


@session.command("show")
@click.option("--session-id", help="Session id to show. Defaults to GLASS_SESSION_ID or active.")
@click.pass_context
def session_show(ctx: click.Context, session_id: str | None) -> None:
    paths = get_paths()
    state = load_state(paths, session_id)
    result = state_summary(state)
    append_audit(paths, state, ctx, "session.show", command_params(session_id=session_id), result)
    emit(result)


@session.command("list")
@click.pass_context
def session_list(ctx: click.Context) -> None:
    paths = get_paths()
    paths.sessions.mkdir(parents=True, exist_ok=True)
    active = active_session_id(paths, required=False)
    records = []
    for path in sorted(paths.sessions.iterdir()):
        if not path.is_dir():
            continue
        state_file = path / "state.json"
        if not state_file.exists():
            continue
        state = normalize_state(json.loads(state_file.read_text(encoding="utf-8")))
        records.append(
            {
                "session_id": state["session"]["id"],
                "campaign": state["session"]["campaign"],
                "status": state["session"]["status"],
                "updated_at": state["session"]["updated_at"],
                "active": state["session"]["id"] == active,
            }
        )
    result = {"sessions": records}
    if active:
        state = load_state(paths, active)
        append_audit(paths, state, ctx, "session.list", {}, result)
    emit(result)


@session.command("wrap")
@click.option("--summary", help="Session summary text.")
@click.option("--from", "from_file", help="Read summary from this file, or '-' for stdin.")
@click.pass_context
def session_wrap(ctx: click.Context, summary: str | None, from_file: str | None) -> None:
    require_dm()
    paths = get_paths()
    state = load_state(paths)
    body = read_body(summary, from_file).strip()
    state["session"]["status"] = "wrapped"
    state["session"]["wrapped_at"] = now_iso()
    state["session"]["summary"] = body
    result = {
        "session_id": state["session"]["id"],
        "status": "wrapped",
        "wrapped_at": state["session"]["wrapped_at"],
        "summary": body,
    }
    commit(paths, state, ctx, "session.wrap", command_params(summary=body), result)


@main.group()
def mode() -> None:
    """Mode stack commands."""


@mode.command("start")
@click.argument("mode_name")
@click.argument("scene_id")
@click.pass_context
def mode_start(ctx: click.Context, mode_name: str, scene_id: str) -> None:
    role = require_dm()
    paths = get_paths()
    state = load_state(paths)
    record = {
        "mode": slugify(mode_name),
        "scene_id": slugify(scene_id),
        "started_at": now_iso(),
        "started_by": role.actor,
    }
    state["mode_stack"].append(record)
    queue_event(
        state,
        role.actor,
        f"mode start {record['mode']} @ {record['scene_id']}",
    )
    result = {
        "current_mode": record["mode"],
        "current_scene": record["scene_id"],
        "mode_stack": state["mode_stack"],
    }
    commit(
        paths,
        state,
        ctx,
        "mode.start",
        command_params(mode_name=mode_name, scene_id=scene_id),
        result,
    )


@mode.command("end")
@click.pass_context
def mode_end(ctx: click.Context) -> None:
    role = require_dm()
    paths = get_paths()
    state = load_state(paths)
    if not state["mode_stack"]:
        raise GlassError("cannot end mode: mode stack is empty")
    ended = state["mode_stack"].pop()
    ended["ended_at"] = now_iso()
    current = current_mode_record(state)
    queue_event(
        state,
        role.actor,
        f"mode end {ended['mode']} @ {ended['scene_id']}",
    )
    result = {
        "ended": ended,
        "current_mode": current["mode"] if current else None,
        "current_scene": current["scene_id"] if current else None,
        "mode_stack": state["mode_stack"],
    }
    commit(paths, state, ctx, "mode.end", {}, result)


@mode.command("current")
@click.pass_context
def mode_current(ctx: click.Context) -> None:
    paths = get_paths()
    state = load_state(paths)
    current = current_mode_record(state)
    result = {
        "current_mode": current["mode"] if current else None,
        "current_scene": current["scene_id"] if current else None,
        "mode_stack": state["mode_stack"],
    }
    append_audit(paths, state, ctx, "mode.current", {}, result)
    emit(result)


@main.command("roll")
@click.argument("skill")
@click.argument("attribute")
@click.option("--risk", required=True, type=click.Choice(sorted(RISK_THRESHOLDS)))
@click.option("--character", "character_id", required=True)
@click.option("--target", "target_id")
@click.pass_context
def roll(
    ctx: click.Context,
    skill: str,
    attribute: str,
    risk: str,
    character_id: str,
    target_id: str | None,
) -> None:
    assert_attribute_name(attribute)
    paths = get_paths()
    state = load_state(paths)
    role = current_role()
    campaign_id = active_campaign_id()

    with pg_connection() as conn:
        character = _db.character_get(conn, campaign_id, character_id)
        if character is None:
            raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
        if role.kind == "player" and character.get("player_id") != role.actor:
            raise GlassError(
                "permission denied: players may roll only their own character "
                f"(owner: {character.get('player_id')})"
            )

        skill_tier = character["skills"].get(skill, "fool")
        attribute_tier = character["attributes"].get(attribute, "standard")
        skill_modifier = SKILL_TIERS[skill_tier]
        attribute_modifier = ATTRIBUTE_TIERS[attribute_tier]
        momentum_in = int(character["momentum"]["current"])
        floor = int(character["momentum"]["floor"])
        ceiling = int(character["momentum"]["ceiling"])

        dice = [random.SystemRandom().randint(1, 6), random.SystemRandom().randint(1, 6)]
        target = RISK_THRESHOLDS[risk]
        total = sum(dice) + skill_modifier + attribute_modifier + momentum_in
        margin = total - target
        outcome, momentum_delta = outcome_for_margin(margin)
        momentum_out = clamp(momentum_in + momentum_delta, floor, ceiling)

        scene_id: str | None = None
        current = current_mode_record(state)
        if current and current.get("scene_id") and current["scene_id"] != "none":
            scene_id = current["scene_id"]

        roll_row = _db.roll_record(
            conn,
            campaign_id=campaign_id,
            session_id=state["session"]["id"],
            scene_id=scene_id,
            character_id=character_id,
            actor=role.actor,
            skill=skill,
            attribute=attribute,
            risk=risk,
            dice=dice,
            skill_tier=skill_tier,
            skill_modifier=skill_modifier,
            attribute_tier=attribute_tier,
            attribute_modifier=attribute_modifier,
            momentum_in=momentum_in,
            total=total,
            target=target,
            margin=margin,
            outcome=outcome,
            momentum_delta=momentum_delta,
            momentum_out=momentum_out,
            target_id=target_id,
        )
        # Persist new momentum back to the character row.
        _db.character_set_momentum_internal(
            conn,
            campaign_id=campaign_id,
            character_id=character_id,
            value=momentum_out,
        )
        # Skill-by-use: advance grants 1 skill_xp, breakthrough grants 2.
        # Failures do not award skill_xp.
        skill_xp_delta = 0
        if outcome == "advance":
            skill_xp_delta = 1
        elif outcome == "breakthrough":
            skill_xp_delta = 2
        existing_xp = int(character["skill_xp"].get(skill, 0))
        skill_xp_before = existing_xp
        skill_xp_after = existing_xp
        skill_bumped_to: str | None = None
        if skill_xp_delta:
            (
                skill_xp_before,
                skill_xp_after,
                skill_bumped_to,
            ) = _db.character_apply_skill_xp(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                skill=skill,
                delta=skill_xp_delta,
            )
        conn.commit()

    target_suffix = f" -> {target_id}" if target_id else ""
    summary = (
        f"roll {skill} ({attribute}) @ {risk}: {total} vs {target} -> "
        f"{outcome} ({momentum_in:+d} to {momentum_out:+d} momentum){target_suffix}"
    )
    queue_event(state, role.actor, summary)
    if skill_bumped_to:
        queue_event(
            state,
            role.actor,
            f"{character_id} skill {skill} -> {skill_bumped_to} (xp {skill_xp_after})",
        )
    roll_row["skill_xp_before"] = skill_xp_before
    roll_row["skill_xp_after"] = skill_xp_after
    roll_row["skill_bumped_to"] = skill_bumped_to
    commit(
        paths,
        state,
        ctx,
        "roll",
        command_params(
            skill=skill,
            attribute=attribute,
            risk=risk,
            character_id=character_id,
            target_id=target_id,
        ),
        roll_row,
    )


@main.group()
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


@main.group()
def note() -> None:
    """Lore draft and journal commands."""


@note.command("write")
@click.argument("path_text")
@click.option("--body", help="Markdown body to write.")
@click.option("--from", "from_file", help="Read body from this file, or '-' for stdin.")
@click.pass_context
def note_write(
    ctx: click.Context, path_text: str, body: str | None, from_file: str | None
) -> None:
    paths = get_paths()
    state = load_state(paths)
    destination = resolve_note_write_path(paths, path_text)
    text = read_body(body, from_file)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    result = {
        "path": display_path(destination),
        "bytes": len(text.encode("utf-8")),
    }
    commit(
        paths,
        state,
        ctx,
        "note.write",
        command_params(path=path_text, bytes=result["bytes"]),
        result,
    )


@note.command("propose")
@click.argument("path_text")
@click.pass_context
def note_propose(ctx: click.Context, path_text: str) -> None:
    role = require_player()
    paths = get_paths()
    state = load_state(paths)
    source = resolve_content_path(paths, path_text)
    workspace_root = active_campaign_root()

    def _player_drafts_root(workspace: Path, player: str) -> Path:
        return (workspace / "players" / player / "drafts").resolve()

    if role.kind == "player":
        # Source must be under <campaign or templates>/players/<actor>/drafts/
        candidates = [_player_drafts_root(workspace_root, role.actor)]
        if workspace_root != paths.content:
            candidates.append(_player_drafts_root(paths.content, role.actor))
        if not any(
            str(source.resolve()).startswith(str(root) + os.sep) or source.resolve() == root
            for root in candidates
        ):
            raise GlassError(
                "permission denied: players can propose only their own drafts/"
            )
        player_id = role.actor
    else:
        player_id = infer_player_from_path(paths, source)
        if not player_id and workspace_root != paths.content:
            try:
                rel = source.resolve().relative_to(workspace_root.resolve())
                if len(rel.parts) >= 3 and rel.parts[0] == "players" and rel.parts[2] == "drafts":
                    player_id = rel.parts[1]
            except ValueError:
                pass
        if not player_id:
            raise GlassError(
                "operator note propose needs a path under players/<id>/drafts/"
            )
    if not source.exists():
        raise GlassError(f"draft not found: {display_path(source)}")
    intake_id = new_id("intake")
    destination_name = f"{intake_id}--{player_id}--{source.name}"
    destination = workspace_root / "dm" / "intake" / destination_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    record = {
        "intake_id": intake_id,
        "player_id": player_id,
        "source_path": display_path(source),
        "intake_path": display_path(destination),
        "status": "pending",
        "created_at": now_iso(),
        "resolved_at": None,
        "ratified_path": None,
    }
    state["note_intake"].append(record)
    result = {"intake": record}
    commit(
        paths,
        state,
        ctx,
        "note.propose",
        command_params(path=path_text),
        result,
    )


def require_intake(state: dict[str, Any], intake_id: str) -> dict[str, Any]:
    for item in state.get("note_intake", []):
        if item["intake_id"] == intake_id:
            return item
    pending = ", ".join(item["intake_id"] for item in state.get("note_intake", [])) or "none"
    raise GlassError(f"unknown intake id {intake_id!r}; known intake ids: {pending}")


@note.command("ratify")
@click.argument("intake_id")
@click.option("--to", "target_path",
              help="Target path relative to shared/lore/. Defaults to "
                   "shared/lore/<original-filename>.")
@click.pass_context
def note_ratify(
    ctx: click.Context,
    intake_id: str,
    target_path: str | None,
) -> None:
    """DM-only: ratify an intake (e.g. a public journal entry) into shared lore.

    propose/ratify is intended for public journal entries — text the player
    wants to publish to the party. Character sheets, intros, and relationships
    are written by the player directly into their own dirs without going
    through this loop.
    """
    require_dm()
    paths = get_paths()
    state = load_state(paths)
    item = require_intake(state, intake_id)
    if item["status"] != "pending":
        raise GlassError(f"intake {intake_id} is already {item['status']}")
    source = REPO_ROOT / item["intake_path"]
    workspace_root = active_campaign_root()
    lore_root = workspace_root / "shared" / "lore"

    if target_path:
        rel = clean_relative_path(target_path)
        while rel.parts and rel.parts[0] in {"content", "shared", "lore"}:
            rel = Path(*rel.parts[1:])
        destination = lore_root / rel
    else:
        # Strip the "<intake_id>--<player_id>--" prefix off the intake filename.
        original_name = source.name.split("--", 2)[-1]
        destination = lore_root / original_name

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    item["status"] = "ratified"
    item["resolved_at"] = now_iso()
    item["ratified_path"] = display_path(destination)
    entity = upsert_entity_from_path(paths, state, destination)
    result = {"intake": item, "entity": entity}
    commit(
        paths,
        state,
        ctx,
        "note.ratify",
        command_params(intake_id=intake_id, target_path=target_path),
        result,
    )


@note.command("reject")
@click.argument("intake_id")
@click.option("--reason", default="")
@click.pass_context
def note_reject(ctx: click.Context, intake_id: str, reason: str) -> None:
    require_dm()
    paths = get_paths()
    state = load_state(paths)
    item = require_intake(state, intake_id)
    if item["status"] != "pending":
        raise GlassError(f"intake {intake_id} is already {item['status']}")
    item["status"] = "rejected"
    item["resolved_at"] = now_iso()
    item["reason"] = reason
    result = {"intake": item}
    commit(
        paths,
        state,
        ctx,
        "note.reject",
        command_params(intake_id=intake_id, reason=reason),
        result,
    )


@main.group()
def entity() -> None:
    """Campaign-lore graph mirror commands."""


@entity.command("upsert")
@click.argument("path_text")
@click.option("--campaign-id", default=None, help="Override campaign id (default: GLASS_CAMPAIGN_ID).")
@click.pass_context
def entity_upsert(ctx: click.Context, path_text: str, campaign_id: str | None) -> None:
    require_dm()
    paths = get_paths()
    state = load_state(paths)
    path = resolve_content_path(paths, path_text)
    record = upsert_entity_from_path(paths, state, path)

    # Mirror the entity into FalkorDB. Best-effort: if the graph is
    # unreachable, the JSON state still has the data and the operation
    # remains useful — but we surface the error so the operator knows.
    graph_status = _mirror_entity_to_graph(record, path, campaign_id)

    result = {"entity": record, "graph": graph_status}
    commit(
        paths,
        state,
        ctx,
        "entity.upsert",
        command_params(path=path_text),
        result,
    )


def _mirror_entity_to_graph(
    record: dict[str, Any], path: Path, campaign_id_override: str | None
) -> dict[str, Any]:
    """Push an entity to FalkorDB. Returns a status dict describing the result."""
    from . import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        return {"status": "unavailable", "target": config.describe()}

    text = path.read_text(encoding="utf-8")
    mentions = _graph.extract_mentions(text)
    fm = record.get("frontmatter", {}) or {}
    campaign_id = (
        campaign_id_override
        or os.environ.get("GLASS_CAMPAIGN_ID")
        or fm.get("campaign_id")
        or "<unknown>"
    )
    entity_type = fm.get("type") or "entity"
    tags_raw = fm.get("tags")
    if isinstance(tags_raw, str):
        tags = [t.strip() for t in tags_raw.strip("[]").split(",") if t.strip()]
    elif isinstance(tags_raw, list):
        tags = [str(t) for t in tags_raw]
    else:
        tags = []

    try:
        with _graph.connect(config) as g:
            _graph.upsert_entity(
                g,
                entity_id=record["entity_id"],
                campaign_id=campaign_id,
                title=record.get("title", record["entity_id"]),
                entity_type=entity_type,
                file_path=record.get("path", str(path)),
                tags=tags,
                prominence=fm.get("prominence"),
                status=fm.get("status"),
                source=fm.get("source"),
                sections=record.get("sections", []),
                mentions=mentions,
            )
    except Exception as exc:
        return {"status": "error", "target": config.describe(), "message": str(exc)}
    return {
        "status": "upserted",
        "target": config.describe(),
        "campaign_id": campaign_id,
        "mentions": mentions,
    }


@entity.command("neighborhood")
@click.argument("entity_id")
@click.pass_context
def entity_neighborhood(ctx: click.Context, entity_id: str) -> None:
    """Show an entity's outgoing edges, incoming edges, and sections.

    Prefers FalkorDB; falls back to JSON state if the graph is unreachable.
    """
    from . import graph as _graph

    paths = get_paths()
    state = load_state(paths)

    config = _graph.load_falkor_config(load_config())
    if _graph.is_available(config):
        try:
            with _graph.connect(config) as g:
                payload = _graph.neighborhood(g, entity_id)
        except Exception as exc:
            payload = {"found": False, "error": str(exc)}
        if payload.get("found"):
            result = {**payload, "source": "falkordb", "target": config.describe()}
            append_audit(
                paths, state, ctx, "entity.neighborhood",
                command_params(entity_id=entity_id), result,
            )
            emit(result)
            return

    # Fallback: JSON state.
    entity_record = state.get("entities", {}).get(entity_id)
    if not entity_record:
        known = ", ".join(sorted(state.get("entities", {}))) or "none"
        raise GlassError(f"unknown entity {entity_id!r}; known entities: {known}")
    result = {
        "entity_id": entity_id,
        "entity": entity_record,
        "outgoing": entity_record.get("edges", []),
        "incoming": [],
        "source": "json-fallback",
    }
    append_audit(
        paths, state, ctx, "entity.neighborhood",
        command_params(entity_id=entity_id), result,
    )
    emit(result)


@entity.command("similar")
@click.argument("section_id")
@click.option("--limit", type=int, default=5)
@click.pass_context
def entity_similar(ctx: click.Context, section_id: str, limit: int) -> None:
    paths = get_paths()
    state = load_state(paths)
    sections = []
    target: dict[str, Any] | None = None
    for entity_record in state.get("entities", {}).values():
        for section in entity_record.get("sections", []):
            merged = {**section, "entity_id": entity_record["entity_id"]}
            sections.append(merged)
            if section["section_id"] == section_id:
                target = merged
    if target is None:
        known = ", ".join(section["section_id"] for section in sections) or "none"
        raise GlassError(f"unknown section {section_id!r}; known sections: {known}")
    target_words = set(re.findall(r"[a-z0-9]+", target["text"].lower()))
    scored = []
    for section in sections:
        if section["section_id"] == section_id:
            continue
        words = set(re.findall(r"[a-z0-9]+", section["text"].lower()))
        score = len(target_words & words)
        if score:
            scored.append({**section, "score": score})
    scored.sort(key=lambda item: item["score"], reverse=True)
    result = {"section_id": section_id, "matches": scored[:limit]}
    append_audit(
        paths,
        state,
        ctx,
        "entity.similar",
        command_params(section_id=section_id, limit=limit),
        result,
    )
    emit(result)


@entity.command("find")
@click.option("--query", "-q", default=None, help="Substring search on id/title.")
@click.option("--type", "type_filter", default=None, help="Filter by entity type.")
@click.option("--campaign-id", default=None, help="Filter by campaign.")
@click.option("--limit", type=int, default=25, show_default=True)
@click.pass_context
def entity_find(
    ctx: click.Context,
    query: str | None,
    type_filter: str | None,
    campaign_id: str | None,
    limit: int,
) -> None:
    """Search entities in the graph by substring + filters."""
    from . import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(f"falkordb is not reachable at {config.describe()}")

    campaign = campaign_id or os.environ.get("GLASS_CAMPAIGN_ID")
    try:
        with _graph.connect(config) as g:
            matches = _graph.find_entities(
                g,
                query=query,
                type_filter=type_filter,
                campaign_id=campaign,
                limit=limit,
            )
    except Exception as exc:
        raise GlassError(f"falkordb find failed: {exc}") from exc

    emit({
        "target": config.describe(),
        "query": query,
        "type": type_filter,
        "campaign_id": campaign,
        "matches": matches,
        "count": len(matches),
    })


@entity.command("link")
@click.argument("src_id")
@click.argument("edge_type")
@click.argument("dst_id")
@click.option("--prop", "props", multiple=True, help="key=value edge property; repeatable.")
@click.pass_context
def entity_link(
    ctx: click.Context,
    src_id: str,
    edge_type: str,
    dst_id: str,
    props: tuple[str, ...],
) -> None:
    """Add a typed edge between two entities (DM-only).

    Edge types are UPPERCASE_SNAKE_CASE — e.g. LOCATED_IN, MEMBER_OF,
    ADVANCES_BEAT. Creates either entity as a `shell` if it does not yet
    exist (so you can link to entities that haven't been ratified yet).
    """
    require_dm()
    from . import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(f"falkordb is not reachable at {config.describe()}")

    properties: dict[str, Any] = {}
    for raw in props:
        if "=" not in raw:
            raise GlassError(f"--prop must be key=value: {raw!r}")
        k, v = raw.split("=", 1)
        properties[k.strip()] = v.strip()

    try:
        with _graph.connect(config) as g:
            _graph.link_entities(
                g, src_id=src_id, edge_type=edge_type, dst_id=dst_id, properties=properties
            )
    except (ValueError, Exception) as exc:
        raise GlassError(f"falkordb link failed: {exc}") from exc

    emit({
        "target": config.describe(),
        "src": src_id,
        "edge_type": edge_type,
        "dst": dst_id,
        "properties": properties,
        "status": "linked",
    })


@entity.command("unlink")
@click.argument("src_id")
@click.argument("edge_type")
@click.argument("dst_id")
@click.pass_context
def entity_unlink(ctx: click.Context, src_id: str, edge_type: str, dst_id: str) -> None:
    """Remove a typed edge between two entities (DM-only)."""
    require_dm()
    from . import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(f"falkordb is not reachable at {config.describe()}")
    try:
        with _graph.connect(config) as g:
            removed = _graph.unlink_entities(g, src_id=src_id, edge_type=edge_type, dst_id=dst_id)
    except Exception as exc:
        raise GlassError(f"falkordb unlink failed: {exc}") from exc
    emit({"src": src_id, "edge_type": edge_type, "dst": dst_id, "removed": removed})


@entity.command("query")
@click.argument("cypher")
@click.option("--param", "params", multiple=True, help="key=value query param; repeatable.")
@click.pass_context
def entity_query(ctx: click.Context, cypher: str, params: tuple[str, ...]) -> None:
    """Run an arbitrary Cypher query against the campaign graph (DM-only).

    Use for ad-hoc analysis the other commands don't cover. Examples:

        glass entity query "MATCH (e:Entity {type: 'faction'}) RETURN e.id, e.title"
        glass entity query "MATCH (a:Entity)-[:GOVERNS]->(b) RETURN a.id, b.id"

    Properties are returned as plain dicts; nodes get a `_kind` of 'node',
    edges get `_kind: 'edge'` and a `_relation` field.
    """
    require_dm()
    from . import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(f"falkordb is not reachable at {config.describe()}")

    parameters: dict[str, Any] = {}
    for raw in params:
        if "=" not in raw:
            raise GlassError(f"--param must be key=value: {raw!r}")
        k, v = raw.split("=", 1)
        parameters[k.strip()] = v.strip()

    try:
        with _graph.connect(config) as g:
            payload = _graph.run_query(g, cypher, parameters)
    except Exception as exc:
        raise GlassError(f"falkordb query failed: {exc}") from exc

    emit({"target": config.describe(), "cypher": cypher, "params": parameters, **payload})


@entity.command("stats")
@click.pass_context
def entity_stats(ctx: click.Context) -> None:
    """Show graph counts: entities, sections, edges, top edge types, top entity types."""
    from . import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(f"falkordb is not reachable at {config.describe()}")
    try:
        with _graph.connect(config) as g:
            stats = _graph.graph_stats(g)
    except Exception as exc:
        raise GlassError(f"falkordb stats failed: {exc}") from exc
    emit({"target": config.describe(), **stats})


@main.group()
def thread() -> None:
    """DM scaffolding thread commands."""


@thread.command("current")
@click.pass_context
def thread_current(ctx: click.Context) -> None:
    paths = get_paths()
    state = load_state(paths)
    result = {"threads": state.get("threads", {})}
    append_audit(paths, state, ctx, "thread.current", {}, result)
    emit(result)


@thread.command("beat")
@click.argument("thread_id")
@click.pass_context
def thread_beat(ctx: click.Context, thread_id: str) -> None:
    paths = get_paths()
    state = load_state(paths)
    record = state.get("threads", {}).get(thread_id)
    if not record:
        known = ", ".join(state["threads"]) or "none"
        raise GlassError(f"unknown thread {thread_id!r}; known threads: {known}")
    result = {"thread": record}
    append_audit(
        paths,
        state,
        ctx,
        "thread.beat",
        command_params(thread_id=thread_id),
        result,
    )
    emit(result)


@thread.command("advance")
@click.argument("thread_id")
@click.option("--note", default="")
@click.pass_context
def thread_advance(ctx: click.Context, thread_id: str, note: str) -> None:
    require_dm()
    paths = get_paths()
    state = load_state(paths)
    record = state.setdefault("threads", {}).setdefault(
        thread_id,
        {"thread_id": thread_id, "current_beat": 0, "history": []},
    )
    before = int(record.get("current_beat", 0))
    after = before + 1
    record["current_beat"] = after
    record.setdefault("history", []).append({"beat": after, "note": note, "ts": now_iso()})
    result = {"thread": record, "beat_before": before, "beat_after": after}
    commit(
        paths,
        state,
        ctx,
        "thread.advance",
        command_params(thread_id=thread_id, note=note),
        result,
    )


class MessageGroup(click.Group):
    """Allow both `glass msg read` and spec-shaped `glass msg <type> <to> <body>`."""

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        if args and args[0] in self.commands:
            return super().resolve_command(ctx, args)
        return super().resolve_command(ctx, ["send", *args])


@main.group(cls=MessageGroup, name="msg")
def msg_group() -> None:
    """Typed inter-agent message bus.

    Send with: glass msg <type> <recipient> <body>
    Read with: glass msg read [--since-checkpoint]
    """


@msg_group.command("send", hidden=True)
@click.argument("message_type")
@click.argument("recipient")
@click.argument("body_parts", nargs=-1, required=True)
@click.pass_context
def msg_send(
    ctx: click.Context, message_type: str, recipient: str, body_parts: tuple[str, ...]
) -> None:
    paths = get_paths()
    state = load_state(paths)
    require_message_type(paths, message_type)
    require_recipient(paths, state, recipient)
    role = current_role()
    body = " ".join(body_parts)
    campaign_id = active_campaign_id()
    with pg_connection() as conn:
        message = _db.message_send(
            conn,
            campaign_id=campaign_id,
            session_id=state["session"]["id"],
            sender=role.actor,
            recipient=recipient,
            type_=message_type,
            body=body,
        )
    result = {"message": message}
    commit(
        paths,
        state,
        ctx,
        "msg.send",
        command_params(message_type=message_type, recipient=recipient),
        result,
    )


@msg_group.command("read")
@click.option("--since-checkpoint", is_flag=True,
              help="Show only messages this agent hasn't read yet (recommended at turn start).")
@click.option("--from", "sender")
@click.option("--type", "message_type")
@click.option("--no-mark", is_flag=True,
              help="Do not write read-checkpoints. Useful for spot-checking the bus.")
@click.pass_context
def msg_read(
    ctx: click.Context,
    since_checkpoint: bool,
    sender: str | None,
    message_type: str | None,
    no_mark: bool,
) -> None:
    paths = get_paths()
    state = load_state(paths)
    if message_type:
        require_message_type(paths, message_type)
    role = current_role()
    campaign_id = active_campaign_id()
    with pg_connection() as conn:
        rows = _db.message_list(
            conn,
            campaign_id=campaign_id,
            agent_id=role.actor,
            only_unread=since_checkpoint,
            sender=sender,
            type_=message_type,
            limit=500,
        )
        # Visibility filter at the app layer (DM sees all; players see
        # party broadcasts, addressed-to-them, and self-sent).
        visible = [m for m in rows if message_visible_to(m, role)]
        if not no_mark and visible:
            _db.message_mark_read(
                conn,
                agent_id=role.actor,
                message_ids=[m["id"] for m in visible],
            )
    result = {"messages": visible, "count": len(visible)}
    commit(
        paths,
        state,
        ctx,
        "msg.read",
        command_params(
            since_checkpoint=since_checkpoint,
            sender=sender,
            message_type=message_type,
            no_mark=no_mark,
        ),
        result,
    )


@main.group()
def turn() -> None:
    """Turn append command."""


@turn.command("append")
@click.argument("markdown_file")
@click.option("--speaker")
@click.option("--role", "turn_role", type=click.Choice(["dm", "player", "operator"]))
@click.option("--mode", "mode_name")
@click.option("--scene", "scene_id")
@click.option("--character", "character_id")
@click.pass_context
def turn_append(
    ctx: click.Context,
    markdown_file: str,
    speaker: str | None,
    turn_role: str | None,
    mode_name: str | None,
    scene_id: str | None,
    character_id: str | None,
) -> None:
    paths = get_paths()
    state = load_state(paths)
    source = Path(markdown_file).expanduser()
    if not source.is_absolute():
        source = Path.cwd() / source
    if not source.exists():
        raise GlassError(f"turn markdown not found: {markdown_file}")
    body = source.read_text(encoding="utf-8").strip()
    role = current_role()
    speaker_id = actor_for_turn(role, speaker)
    resolved_role = role_label_for_turn(role, turn_role)
    current = current_mode_record(state)
    resolved_mode = mode_name or (current["mode"] if current else "none")
    resolved_scene = scene_id or (current["scene_id"] if current else "none")
    state["session"]["turn_counter"] = int(state["session"].get("turn_counter", 0)) + 1
    turn_id = state["session"]["turn_counter"]

    flushed: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for event in state.get("pending_events", []):
        if event.get("actor") == speaker_id or role.can_do_anything:
            flushed.append(event)
        else:
            remaining.append(event)
    state["pending_events"] = remaining

    header = (
        f"## Turn {turn_id} - {speaker_id} ({resolved_role}) - "
        f"{resolved_mode}, {resolved_scene}"
    )
    parts = [header, "", body]
    event_lines = inline_event_lines(flushed)
    if event_lines:
        parts.extend(["", *event_lines])
    turn_markdown = "\n".join(parts).rstrip() + "\n\n"
    with transcript_path(paths, state["session"]["id"]).open("a", encoding="utf-8") as handle:
        handle.write(turn_markdown)

    record = {
        "turn_id": turn_id,
        "session_id": state["session"]["id"],
        "scene_id": resolved_scene,
        "mode": resolved_mode,
        "speaker": speaker_id,
        "role": resolved_role,
        "character_id": character_id,
        "ts": now_iso(),
        "source_path": str(source),
        "event_summaries": [event["summary"] for event in flushed],
        "markdown": turn_markdown,
    }
    state["turns"].append(record)
    result = {
        "turn": {key: value for key, value in record.items() if key != "markdown"},
        "events_flushed": flushed,
        "transcript_path": display_path(transcript_path(paths, state["session"]["id"])),
    }
    commit(
        paths,
        state,
        ctx,
        "turn.append",
        command_params(markdown_file=markdown_file, speaker=speaker_id),
        result,
    )


_HANDOFF_AGENT_IDS = ("dm", "tev", "sumi", "renno", "kit")
_PLAYER_AGENT_IDS = ("tev", "sumi", "renno", "kit")


@turn.command("handoff")
@click.argument("agent_id")
@click.pass_context
def turn_handoff(ctx: click.Context, agent_id: str) -> None:
    """Append a one-off override to the next-speaker queue.

    Each call appends; multiple calls in a single turn queue up multiple
    redirects in the order called. The orchestrator pops one off per
    turn. After the queue is drained, round-robin resumes from the last
    redirected agent.

    Example: a DM in their turn calls `glass turn handoff sumi` then
    `glass turn handoff dm`. Sumi runs next, then the DM, then rotation
    continues from the DM (dm -> next-in-rotation).
    """
    if agent_id not in _HANDOFF_AGENT_IDS:
        raise GlassError(
            f"unknown agent id {agent_id!r}; valid: {', '.join(_HANDOFF_AGENT_IDS)}"
        )
    paths = get_paths()
    state = load_state(paths)
    role = current_role()
    state["next_speakers"].append({"agent": agent_id})
    queue_event(state, role.actor, f"handoff -> {agent_id}")
    result = {"queue": list(state["next_speakers"])}
    commit(
        paths, state, ctx, "turn.handoff",
        command_params(agent_id=agent_id), result,
    )


@turn.command("rapid-round")
@click.argument("prompt_parts", nargs=-1, required=True)
@click.option("--players", "players_csv", default=None,
              help="Comma-separated player ids (subset of tev,sumi,renno,kit). "
                   "Order matters. Defaults to all four in declaration order.")
@click.pass_context
def turn_rapid_round(
    ctx: click.Context, prompt_parts: tuple[str, ...], players_csv: str | None,
) -> None:
    """DM-only: queue a single-shot rapid response from each player.

    Each queued turn sees the prompt in TURN_START.md and is told to give
    a brief reactive narration only — no rolls, no full menu, no handoff.
    Use this when the DM needs each player's character to react to the
    same stimulus quickly without spending a full per-player turn.
    """
    require_dm()
    if players_csv:
        targets = [p.strip() for p in players_csv.split(",") if p.strip()]
    else:
        targets = list(_PLAYER_AGENT_IDS)
    for player in targets:
        if player not in _PLAYER_AGENT_IDS:
            raise GlassError(
                f"unknown player {player!r}; valid: {', '.join(_PLAYER_AGENT_IDS)}"
            )
    paths = get_paths()
    state = load_state(paths)
    role = current_role()
    prompt = " ".join(prompt_parts).strip()
    if not prompt:
        raise GlassError("rapid-round prompt cannot be empty")
    for player in targets:
        state["next_speakers"].append({
            "agent": player,
            "rapid_prompt": prompt,
        })
    queue_event(
        state, role.actor,
        f"rapid-round queued for {','.join(targets)}: {prompt[:60]}",
    )
    result = {"queue": list(state["next_speakers"]), "prompt": prompt}
    commit(
        paths, state, ctx, "turn.rapid-round",
        command_params(prompt=prompt, players=targets), result,
    )


@turn.command("restart-order")
@click.argument("agent_id")
@click.pass_context
def turn_restart_order(ctx: click.Context, agent_id: str) -> None:
    """DM-only: clear any pending handoff queue + redirect to AGENT_ID.

    Use this when the rotation needs a hard reset — e.g., a player went
    out of order and you want to restart from a specific PC. Round-robin
    resumes from the new agent on subsequent turns.
    """
    require_dm()
    if agent_id not in _HANDOFF_AGENT_IDS:
        raise GlassError(
            f"unknown agent id {agent_id!r}; valid: {', '.join(_HANDOFF_AGENT_IDS)}"
        )
    paths = get_paths()
    state = load_state(paths)
    role = current_role()
    cleared = list(state["next_speakers"])
    state["next_speakers"] = [{"agent": agent_id}]
    queue_event(state, role.actor, f"restart turn order -> {agent_id}")
    result = {"cleared": cleared, "queue": list(state["next_speakers"])}
    commit(
        paths, state, ctx, "turn.restart-order",
        command_params(agent_id=agent_id), result,
    )


@turn.command("clear-handoff")
@click.pass_context
def turn_clear_handoff(ctx: click.Context) -> None:
    """DM-only: wipe any pending handoff queue (rare — usually the
    orchestrator consumes entries automatically on each turn)."""
    require_dm()
    paths = get_paths()
    state = load_state(paths)
    previous = list(state.get("next_speakers", []))
    state["next_speakers"] = []
    result = {"cleared": previous}
    commit(paths, state, ctx, "turn.clear-handoff", {}, result)


@main.group()
def turns() -> None:
    """Corpus query commands."""


@turns.command("find")
@click.option("--scene")
@click.option("--speaker")
@click.option("--mode", "mode_name")
@click.option("--turn-id", type=int)
@click.option("--limit", type=int, default=20)
@click.pass_context
def turns_find(
    ctx: click.Context,
    scene: str | None,
    speaker: str | None,
    mode_name: str | None,
    turn_id: int | None,
    limit: int,
) -> None:
    paths = get_paths()
    state = load_state(paths)
    records = list(state.get("turns", []))
    if scene:
        records = [record for record in records if record["scene_id"] == scene]
    if speaker:
        records = [record for record in records if record["speaker"] == speaker]
    if mode_name:
        records = [record for record in records if record["mode"] == mode_name]
    if turn_id is not None:
        records = [record for record in records if record["turn_id"] == turn_id]
    records = records[-limit:]
    result = {"turns": records, "count": len(records)}
    append_audit(
        paths,
        state,
        ctx,
        "turns.find",
        command_params(
            scene=scene,
            speaker=speaker,
            mode=mode_name,
            turn_id=turn_id,
            limit=limit,
        ),
        result,
    )
    emit(result)


# ============================================================================
# Postgres / migrations
# ============================================================================


@main.group()
def db() -> None:
    """Postgres connection + migration runner."""


@db.command("migrate")
@click.pass_context
def db_migrate(ctx: click.Context) -> None:
    """Apply pending SQL migrations from the repo's migrations/ directory."""
    config = load_config()
    pg_config = _db.load_pg_config(config)
    try:
        with _db.connect(pg_config) as conn:
            actions = _db.migrate(conn)
    except Exception as exc:
        raise GlassError(f"db migrate failed against {pg_config.describe()}: {exc}") from exc

    result = {"target": pg_config.describe(), "actions": actions}
    # Best-effort audit: skip if no active session, or if the active-session
    # pointer is stale (points to a cleared/deleted session).
    paths = get_paths()
    if active_session_file(paths).exists():
        try:
            state = load_state(paths)
        except GlassError:
            state = None
        if state is not None:
            append_audit(paths, state, ctx, "db.migrate", command_params(), result)
    emit(result)


@db.command("status")
@click.pass_context
def db_status(ctx: click.Context) -> None:
    """Show applied + pending migrations and any checksum mismatches."""
    config = load_config()
    pg_config = _db.load_pg_config(config)
    try:
        with _db.connect(pg_config) as conn:
            report = _db.status(conn)
    except Exception as exc:
        raise GlassError(f"db status failed against {pg_config.describe()}: {exc}") from exc
    report["target"] = pg_config.describe()
    emit(report)


# ============================================================================
# Campaign workspace: arc / scene / lore
# ============================================================================


def _campaign_workspace() -> _workspace.CampaignWorkspace:
    paths = get_paths()
    if paths.campaigns is None:
        raise GlassError("paths.campaigns is not configured")
    env_id = os.environ.get("GLASS_CAMPAIGN_ID")
    try:
        return _workspace.resolve_active_campaign(paths.campaigns, env_id=env_id)
    except FileNotFoundError as exc:
        raise GlassError(str(exc)) from exc


@main.group()
def arc() -> None:
    """Arc lifecycle (DM-only): create, list, current."""


@arc.command("create")
@click.argument("arc_id")
@click.pass_context
def arc_create(ctx: click.Context, arc_id: str) -> None:
    require_dm()
    workspace = _campaign_workspace()
    try:
        arc_dir = _workspace.create_arc(workspace, arc_id)
    except (FileExistsError, ValueError) as exc:
        raise GlassError(str(exc)) from exc
    result = {
        "campaign_id": workspace.campaign_id,
        "arc_id": arc_id,
        "path": str(arc_dir),
        "files": ["plan.md", "context.md", "scenes/"],
    }
    emit(result)


@arc.command("list")
@click.pass_context
def arc_list(ctx: click.Context) -> None:
    workspace = _campaign_workspace()
    arcs = _workspace.list_arcs(workspace)
    emit({"campaign_id": workspace.campaign_id, "arcs": arcs})


@arc.command("current")
@click.pass_context
def arc_current(ctx: click.Context) -> None:
    workspace = _campaign_workspace()
    current = _workspace.current_arc(workspace)
    emit({"campaign_id": workspace.campaign_id, "active_arc": current})


@main.group()
def scene() -> None:
    """Scene lifecycle (DM-only): create, end, current, list."""


@scene.command("create")
@click.argument("scene_id")
@click.option(
    "--type",
    "scene_type",
    required=True,
    help="Scene type / mode: town, social, exploration, investigation, combat, travel, montage, wrap.",
)
@click.option("--arc", "arc_id", default=None, help="Override active arc.")
@click.pass_context
def scene_create(
    ctx: click.Context, scene_id: str, scene_type: str, arc_id: str | None
) -> None:
    require_dm()
    workspace = _campaign_workspace()
    try:
        scene_dir = _workspace.create_scene(workspace, scene_id, scene_type, arc_id=arc_id)
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        raise GlassError(str(exc)) from exc
    result = {
        "campaign_id": workspace.campaign_id,
        "scene_id": scene_id,
        "scene_type": scene_type,
        "arc_id": arc_id or _workspace.load_campaign_state(workspace).get("active_scene_arc"),
        "path": str(scene_dir),
        "files": ["prep.md", "context.md", "transcript.md", "audit.jsonl"],
    }
    emit(result)


@scene.command("end")
@click.option("--summary", default=None,
              help="Scene summary written to arcs/<arc>/scenes/<scene>/summary.md.")
@click.option("--beats", default=None,
              help="Newline-separated bullets appended to shared/quest-log.md, "
                   "tagged with the scene + arc.")
@click.option("--xp", "xp_spec", default=None,
              help="XP awards: 'tev=2,sumi=1,renno=3'. Calls character "
                   "award-xp per entry with reason=\"scene end: <scene_id>\".")
@click.pass_context
def scene_end_cmd(
    ctx: click.Context,
    summary: str | None,
    beats: str | None,
    xp_spec: str | None,
) -> None:
    """End the active scene + bundle wrap-up writes.

    Atomic: writes summary, appends beats, awards XP, then marks the scene
    as no-longer-active in the campaign workspace state. Also clears any
    scene_closing_turns countdown — the scene is over.
    """
    role = require_dm()
    workspace = _campaign_workspace()
    state = load_state(get_paths())
    paths = get_paths()
    campaign_id = active_campaign_id()
    session_id = state["session"]["id"]

    current = _workspace.current_scene(workspace)
    if not current:
        raise GlassError("no active scene to end")
    scene_id = current["scene_id"]
    arc_id = current["arc_id"]

    summary_path: str | None = None
    if summary and summary.strip():
        summary_path = _write_scene_summary(workspace, arc_id, scene_id, summary.strip())

    beat_lines: list[str] = []
    if beats:
        for line in beats.splitlines():
            text = line.strip().lstrip("-*").strip()
            if text:
                _append_quest_beat(workspace, text, scene_id=scene_id, arc_id=arc_id)
                beat_lines.append(text)

    xp_awards: list[dict[str, Any]] = []
    if xp_spec:
        with pg_connection() as conn:
            for agent, delta in _parse_xp_spec(xp_spec):
                character_id = lookup_player_character_id(campaign_id, agent)
                if not character_id:
                    raise GlassError(
                        f"can't award xp to {agent!r}: no character row "
                        f"or multiple characters in campaign"
                    )
                try:
                    updated, before, after = _db.character_award_xp(
                        conn,
                        campaign_id=campaign_id,
                        character_id=character_id,
                        delta=delta,
                        actor=role.actor,
                        reason=f"scene end: {scene_id}",
                        session_id=session_id,
                        scene_id=scene_id,
                    )
                except LookupError:
                    raise GlassError(f"unknown character {character_id!r}") from None
                xp_awards.append({
                    "player": agent,
                    "character_id": character_id,
                    "delta": delta,
                    "xp_before": before,
                    "xp_after": after,
                    "level": updated["level"],
                })

    try:
        ended = _workspace.end_scene(workspace)
    except ValueError as exc:
        raise GlassError(str(exc)) from exc

    state["scene_closing_turns"] = None
    queue_event(
        state, role.actor,
        f"scene end: {ended}"
        + (f" (+{len(xp_awards)} xp awards)" if xp_awards else ""),
    )
    result = {
        "campaign_id": workspace.campaign_id,
        "ended_scene": ended,
        "summary_path": summary_path,
        "beats_logged": beat_lines,
        "xp_awards": xp_awards,
    }
    commit(
        paths, state, ctx, "scene.end",
        command_params(summary=summary, beats=beats, xp=xp_spec),
        result,
    )


# A "round" is one full cycle through the speaker order. For all current
# modes (character-creation, scene-play) the rotation is 5 agents long
# (4 players + DM). Action modes will customize this when they exist.
_AGENTS_PER_ROUND = 5


@scene.command("closing-down")
@click.option("--rounds", "round_budget", type=int, default=4, show_default=True,
              help="How many rounds (full cycles through the table) of soft "
                   "closing pressure.")
@click.option("--turns", "turn_budget", type=int, default=None,
              help="Escape hatch: raw agent-commit count (overrides --rounds).")
@click.pass_context
def scene_closing_down(
    ctx: click.Context, round_budget: int, turn_budget: int | None,
) -> None:
    """DM-only: declare the scene is closing down.

    Sets a countdown that surfaces in every subsequent TURN_START.md as
    "Scene closing — N rounds left" so players know to converge their
    threads. When the counter hits 0, agents see a "Final round" section
    instead. The DM closes with `glass scene end`.

    The countdown is informational pressure, not a hard cap — the DM is
    expected to actually call `glass scene end` when ready. The
    methodology says imperfect closure beats a forever-running scene.

    Use `--rounds N` for the typical case (1 round = ~5 agent turns).
    `--turns N` is an escape hatch for fine-grained control.
    """
    role = require_dm()
    if turn_budget is not None:
        if turn_budget <= 0:
            raise GlassError("--turns must be positive")
        commits = turn_budget
        unit_label = f"{turn_budget} turn(s)"
    else:
        if round_budget <= 0:
            raise GlassError("--rounds must be positive")
        commits = round_budget * _AGENTS_PER_ROUND
        unit_label = f"~{round_budget} round(s)"
    paths = get_paths()
    state = load_state(paths)
    # Stored as commits+1 because the orchestrator decrements once on the
    # commit of the DM's setting turn. The first non-DM turn that follows
    # sees the user-friendly value in TURN_START.
    state["scene_closing_turns"] = commits + 1
    queue_event(state, role.actor, f"scene closing down ({unit_label} left)")
    result = {
        "scene_closing_turns": commits,
        "rounds": round_budget if turn_budget is None else None,
    }
    commit(
        paths, state, ctx, "scene.closing-down",
        command_params(rounds=round_budget, turns=turn_budget), result,
    )


def _parse_xp_spec(spec: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for entry in spec.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "=" not in entry:
            raise GlassError(f"invalid xp award {entry!r}; expected agent=delta")
        agent, delta_text = entry.split("=", 1)
        agent = agent.strip()
        try:
            delta = int(delta_text.strip())
        except ValueError:
            raise GlassError(f"invalid xp delta {delta_text!r} (must be int)") from None
        out.append((agent, delta))
    return out


def _write_scene_summary(
    workspace: _workspace.CampaignWorkspace,
    arc_id: str | None,
    scene_id: str,
    body: str,
) -> str | None:
    if not arc_id:
        return None
    scene_dir = workspace.scene_dir(arc_id, scene_id)
    if not scene_dir.exists():
        scene_dir.mkdir(parents=True, exist_ok=True)
    path = scene_dir / "summary.md"
    header = f"# {scene_id} — summary\n\n"
    path.write_text(header + body.rstrip() + "\n", encoding="utf-8")
    return display_path(path)


def _append_quest_beat(
    workspace: _workspace.CampaignWorkspace,
    text: str,
    *,
    scene_id: str | None = None,
    arc_id: str | None = None,
) -> Path:
    log_path = workspace.root / "shared" / "quest-log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not log_path.exists():
        log_path.write_text(
            "---\ntitle: Quest Log\n---\n\n"
            "# Quest Log\n\n"
            "Party-visible log of story-shifting beats. Appended to via "
            "`glass quest beat` and `glass scene end --beats`.\n\n",
            encoding="utf-8",
        )
    tag_parts = []
    if arc_id:
        tag_parts.append(arc_id)
    if scene_id:
        tag_parts.append(scene_id)
    prefix = f"[{':'.join(tag_parts)}] " if tag_parts else ""
    line = f"- {prefix}{text}\n"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line)
    return log_path


@scene.command("current")
@click.pass_context
def scene_current(ctx: click.Context) -> None:
    workspace = _campaign_workspace()
    emit({
        "campaign_id": workspace.campaign_id,
        "active_scene": _workspace.current_scene(workspace),
    })


@scene.command("list")
@click.option("--arc", "arc_id", default=None, help="List scenes in a specific arc (default: active).")
@click.pass_context
def scene_list(ctx: click.Context, arc_id: str | None) -> None:
    workspace = _campaign_workspace()
    scenes = _workspace.list_scenes(workspace, arc_id=arc_id)
    emit({"campaign_id": workspace.campaign_id, "arc_id": arc_id, "scenes": scenes})


@main.group()
def quest() -> None:
    """Party-visible story log: beats."""


@quest.command("beat")
@click.argument("text_parts", nargs=-1, required=True)
@click.option("--scene", "scene_id", default=None, help="Scene id tag (defaults to active).")
@click.option("--arc", "arc_id", default=None, help="Arc id tag (defaults to active).")
@click.pass_context
def quest_beat(
    ctx: click.Context,
    text_parts: tuple[str, ...],
    scene_id: str | None,
    arc_id: str | None,
) -> None:
    """DM-only: append a story-shifting beat to shared/quest-log.md.

    A beat is a real campaign-shifting moment — an NPC's allegiance flips,
    a clock lands, a faction makes a move, a character commits. Not
    bookkeeping. Beats are party-visible canon for what happened in the
    campaign; the corpus consumes them.

    Bundled into `glass scene end --beats` for end-of-scene logging.
    """
    role = require_dm()
    text = " ".join(text_parts).strip()
    if not text:
        raise GlassError("beat text cannot be empty")
    workspace = _campaign_workspace()
    current = _workspace.current_scene(workspace) or {}
    scene = scene_id or current.get("scene_id")
    arc = arc_id or current.get("arc_id")
    log_path = _append_quest_beat(workspace, text, scene_id=scene, arc_id=arc)
    paths = get_paths()
    state = load_state(paths)
    queue_event(state, role.actor, f"beat: {text[:60]}")
    result = {
        "log_path": display_path(log_path),
        "scene_id": scene,
        "arc_id": arc,
        "text": text,
    }
    commit(
        paths, state, ctx, "quest.beat",
        command_params(scene=scene, arc=arc, text=text), result,
    )


@main.group()
def lore() -> None:
    """Lore curation: import / list / search."""


@lore.command("import")
@click.argument("source_path")
@click.option("--as", "alias", default=None, help="Override destination filename.")
@click.pass_context
def lore_import(ctx: click.Context, source_path: str, alias: str | None) -> None:
    """Import an entry from the world bible into the campaign's curated lore.

    SOURCE_PATH is interpreted relative to the lore root (`lore.path` in config),
    or as an absolute path. Examples:
      glass lore import player/concepts/ringglass.md
      glass lore import dm/themes/builders-gone.md
    """
    require_dm()
    workspace = _campaign_workspace()
    paths = get_paths()
    if paths.lore is None:
        raise GlassError("lore.path is not configured")

    source = Path(source_path)
    if not source.is_absolute():
        source = (paths.lore / source).resolve()
    try:
        dest = _workspace.import_lore(workspace, source, paths.lore, alias=alias)
    except (FileExistsError, FileNotFoundError) as exc:
        raise GlassError(str(exc)) from exc

    # Mirror the imported entry into the graph (best-effort).
    state = load_state(paths) if active_session_file(paths).exists() else {"entities": {}}
    record = upsert_entity_from_path(paths, state, dest) if False else _record_for_lore_import(dest)
    graph_status = _mirror_entity_to_graph(record, dest, workspace.campaign_id)

    result = {
        "campaign_id": workspace.campaign_id,
        "source": str(source),
        "destination": str(dest),
        "graph": graph_status,
    }
    emit(result)


def _record_for_lore_import(path: Path) -> dict[str, Any]:
    """Build the same record shape as upsert_entity_from_path, but without the
    paths-must-be-under-content guard (lore lands in campaigns/<id>/shared/lore/).
    """
    text = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    entity_id = fm.get("id") or slugify(path.stem)
    return {
        "entity_id": entity_id,
        "title": fm.get("title") or markdown_title(text, path.stem),
        "path": str(path),
        "updated_at": now_iso(),
        "sections": parse_sections(text, entity_id),
        "frontmatter": fm,
        "edges": [],
    }


@lore.command("list")
@click.pass_context
def lore_list(ctx: click.Context) -> None:
    workspace = _campaign_workspace()
    entries = _workspace.list_lore(workspace)
    emit({"campaign_id": workspace.campaign_id, "lore": entries, "count": len(entries)})


@lore.command("search")
@click.argument("query")
@click.option("--limit", type=int, default=20, show_default=True)
@click.pass_context
def lore_search(ctx: click.Context, query: str, limit: int) -> None:
    """Search the world bible (DM only) — for finding candidates to import."""
    require_dm()
    paths = get_paths()
    if paths.lore is None:
        raise GlassError("lore.path is not configured")
    matches = _workspace.search_lore(paths.lore, query, limit=limit)
    emit({"query": query, "lore_root": str(paths.lore), "matches": matches, "count": len(matches)})


@lore.command("new")
@click.argument("entity_type")
@click.argument("slug")
@click.option("--title", default=None, help="Entry title (defaults to slug, title-cased).")
@click.option("--tags", default="", help="Comma-separated tag list.")
@click.option(
    "--prominence",
    type=click.Choice(["forgotten", "marginal", "recognized", "renowned", "mythic"]),
    default=None,
)
@click.option(
    "--category",
    default=None,
    help="Subdirectory under shared/lore/ (e.g. 'npcs', 'factions', 'locales'). "
    "Defaults to the plural of <entity_type> when sensible.",
)
@click.pass_context
def lore_new(
    ctx: click.Context,
    entity_type: str,
    slug: str,
    title: str | None,
    tags: str,
    prominence: str | None,
    category: str | None,
) -> None:
    """Scaffold a new lore entry under campaigns/<id>/shared/lore/.

    Creates a file with valid frontmatter, ready for the DM to fill in. Does
    NOT upsert to the graph — the DM edits the body, then runs `glass lore
    upsert <path>` once the entry is real. Run with empty body, fill in
    afterward.

    Example:
      glass lore new npc patrol-leader-verra --title "Patrol Leader Verra" \\
                     --tags "patrol,accord" --prominence marginal
    """
    require_dm()
    workspace = _campaign_workspace()
    slug_clean = _workspace.slugify(slug)
    cat = category or _default_category_for(entity_type)
    dest_dir = workspace.lore_dir / cat
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{slug_clean}.md"
    if dest.exists():
        raise GlassError(f"lore entry already exists: {dest}")

    title_value = title or slug_clean.replace("-", " ").title()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    fm_lines = [
        "---",
        f"title: {title_value}",
        f"type: {entity_type}",
        f"id: {slug_clean}",
    ]
    if tag_list:
        fm_lines.append("tags: [" + ", ".join(tag_list) + "]")
    if prominence:
        fm_lines.append(f"prominence: {prominence}")
    fm_lines.extend(["status: draft", "---", "", f"# {title_value}", "", "_Body to be authored._", ""])
    dest.write_text("\n".join(fm_lines), encoding="utf-8")

    emit({
        "campaign_id": workspace.campaign_id,
        "id": slug_clean,
        "type": entity_type,
        "title": title_value,
        "path": str(dest),
        "next": [
            f"edit {dest} to fill in the body",
            f"glass lore upsert {dest.relative_to(workspace.root)} to register in the graph",
        ],
    })


def _default_category_for(entity_type: str) -> str:
    plurals = {
        "npc": "npcs",
        "faction": "factions",
        "location": "locales",
        "locale": "locales",
        "creature": "creatures",
        "artifact": "artifacts",
        "ship": "ships",
        "transport": "ships",
        "event": "events",
        "occurrence": "events",
        "concept": "concepts",
        "thread": "threads",
        "loop": "loops",
        "theme": "themes",
        "hook": "hooks",
        "secret": "secrets",
    }
    return plurals.get(entity_type.lower(), entity_type.lower() + "s")


@lore.command("upsert")
@click.argument("path_text")
@click.pass_context
def lore_upsert(ctx: click.Context, path_text: str) -> None:
    """Register an authored lore entry in the FalkorDB graph.

    Use this after writing a lore file (either with `glass lore new` then
    your editor, or directly with the agent's Write tool). The path can be
    relative to the campaign workspace or absolute.

    Example:
      glass lore upsert shared/lore/npcs/patrol-leader-verra.md
    """
    require_dm()
    paths = get_paths()
    state = load_state(paths)

    raw = Path(path_text).expanduser()
    if not raw.is_absolute():
        # Resolve relative to cwd (typically the campaign workspace).
        raw = (Path.cwd() / raw).resolve()

    if not raw.exists():
        raise GlassError(f"file not found: {raw}")

    record = upsert_entity_from_path(paths, state, raw)
    graph_status = _mirror_entity_to_graph(
        record, raw, os.environ.get("GLASS_CAMPAIGN_ID")
    )
    result = {"entity": record, "graph": graph_status}
    commit(paths, state, ctx, "lore.upsert", command_params(path=path_text), result)


if __name__ == "__main__":
    main()
