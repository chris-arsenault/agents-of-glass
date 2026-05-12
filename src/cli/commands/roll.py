"""Roll commands."""

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
from .character import auto_declare_skill_for_roll
from ..campaign import (
    active_campaign_id,
    active_campaign_root,
    lookup_player_character_id,
    pg_connection,
    resolve_active_campaign_workspace,
)
from ..character_projection import write_public_character_mirror
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
from ..errors import GlassError, agent_instruction
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
    state_path,
    state_summary,
    transcript_path,)
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


@click.command("roll")
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
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    campaign_id = active_campaign_id()

    with pg_connection() as conn:
        character = _db.character_get(conn, campaign_id, character_id)
        if character is None:
            raise GlassError(
                agent_instruction(
                    f"unknown character {character_id!r} in campaign {campaign_id!r}",
                    "Use the character id from TURN_START, `glass character list`, or the player's public character sheet.",
                )
            )
        if role.kind == "player" and character.get("player_id") != role.actor:
            raise GlassError(
                agent_instruction(
                    "players may roll only their own character",
                    f"This character belongs to `{character.get('player_id')}`; use your own character id.",
                    "If another character needs to roll, set them up in prose and let that player or the DM take the roll.",
                )
            )

        character, auto_declared = auto_declare_skill_for_roll(
            conn,
            campaign_id=campaign_id,
            character=character,
            skill=skill,
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
            session_id=state["campaign"],
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
        updated_character = _db.character_get(conn, campaign_id, character_id)
        if updated_character is None:
            raise GlassError(
                agent_instruction(
                    f"unknown character {character_id!r}",
                    "Retry with a character id that exists in this campaign.",
                )
            ) from None

    target_suffix = f" -> {target_id}" if target_id else ""
    summary = (
        f"roll {skill} ({attribute}) @ {risk}: {total} vs {target} -> "
        f"{outcome} ({momentum_in:+d} to {momentum_out:+d} momentum){target_suffix}"
    )
    queue_event(state, role.actor, summary)
    if auto_declared:
        cap = _db.skill_slot_cap(character["level"])
        used = len(character["skills"])
        queue_event(
            state,
            role.actor,
            f"{character_id} declared skill {skill} (fool, slot {used}/{cap})",
        )
    if skill_bumped_to:
        queue_event(
            state,
            role.actor,
            f"{character_id} skill {skill} -> {skill_bumped_to} (xp {skill_xp_after})",
        )
    roll_row["skill_xp_before"] = skill_xp_before
    roll_row["skill_xp_after"] = skill_xp_after
    roll_row["skill_bumped_to"] = skill_bumped_to
    roll_row["skill_auto_declared"] = auto_declared
    roll_row["character_mirror"] = write_public_character_mirror(
        paths,
        campaign_id,
        updated_character,
    )
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
