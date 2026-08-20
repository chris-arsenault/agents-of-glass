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
from .character import resolve_skill_for_roll
from ..campaign import (
    active_campaign_id,
    active_campaign_root,
    lookup_player_character_id,
    pg_connection,
    resolve_active_campaign_workspace,
)
from ..character_display import write_public_character_mirror
from ..config import REPO_ROOT, Paths, get_paths, load_config
from ..constants import (
    CHECK_DICE_COUNT,
    CHECK_DIE_SIDES,
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
from ..scene_beats import BEAT_FAILURE_LIMIT
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
    state_path,
    state_summary,
    transcript_path,)
from ..validation import (
    assert_attribute_name,
    clamp,
    momentum_narrative_effect,
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


_FAILED_ROLL_OUTCOMES = {"stall", "regress", "collapse"}


@click.command("roll")
@click.argument("skill")
@click.argument("attribute")
@click.option("--risk", required=True, type=click.Choice(sorted(RISK_THRESHOLDS)))
@click.option("--character", "character_id", required=True)
@click.option("--target", "target_id")
@click.option(
    "--save-skill",
    is_flag=True,
    help="Declare this skill before rolling if it is not already on the sheet.",
)
@click.pass_context
def roll(
    ctx: click.Context,
    skill: str,
    attribute: str,
    risk: str,
    character_id: str,
    target_id: str | None,
    save_skill: bool,
) -> None:
    roll_service(
        command_path=ctx,
        emit_output=True,
        skill=skill,
        attribute=attribute,
        risk=risk,
        character_id=character_id,
        target_id=target_id,
        save_skill=save_skill,
    )


def roll_service(
    *,
    command_path: click.Context | str = "glass_roll",
    emit_output: bool = False,
    skill: str,
    attribute: str,
    risk: str,
    character_id: str,
    target_id: str | None = None,
    save_skill: bool = False,
) -> dict[str, Any]:
    """Resolve and persist one character roll from typed runtime inputs."""

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
                    "Use the character id from the injected prompt, `glass character list`, or `glass character bulk-get --all`.",
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

        character, skill, skill_declared, skill_saved = resolve_skill_for_roll(
            conn,
            campaign_id=campaign_id,
            character=character,
            skill=skill,
            save_skill=save_skill,
        )

        skill_tier = character["skills"].get(skill, "fool")
        attribute_tier = character["attributes"].get(attribute, "standard")
        skill_modifier = SKILL_TIERS[skill_tier]
        attribute_modifier = ATTRIBUTE_TIERS[attribute_tier]
        momentum_in = int(character["momentum"]["current"])
        floor = int(character["momentum"]["floor"])
        ceiling = int(character["momentum"]["ceiling"])

        rng = random.SystemRandom()
        dice = [rng.randint(1, CHECK_DIE_SIDES) for _ in range(CHECK_DICE_COUNT)]
        target = RISK_THRESHOLDS[risk]
        total = sum(dice) + skill_modifier + attribute_modifier
        margin = total - target
        outcome, momentum_delta = outcome_for_margin(margin)
        momentum_out = clamp(momentum_in + momentum_delta, floor, ceiling)
        momentum_effect, momentum_guidance = momentum_narrative_effect(momentum_out)

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
            metadata={
                "momentum_applied_to_total": False,
                "momentum_effect": momentum_effect,
                "momentum_guidance": momentum_guidance,
                "skill_declared": skill_declared,
                "skill_saved": skill_saved,
                "skill_xp_eligible": skill_declared,
            },
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
        skill_xp_before: int | None = None
        skill_xp_after: int | None = None
        skill_bumped_to: str | None = None
        if skill_declared:
            existing_xp = int(character["skill_xp"].get(skill, 0))
            skill_xp_before = existing_xp
            skill_xp_after = existing_xp
        if skill_declared and skill_xp_delta:
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
        beat_failure = _apply_beat_failure_pressure(
            conn,
            state=state,
            campaign_id=campaign_id,
            scene_id=scene_id,
            target_id=target_id,
            outcome=outcome,
            actor=role.actor,
            turn_id=str(state.get("active_turn_id") or "").strip() or None,
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
    rider_suffix = {
        "additional_good": "; momentum rider: extra good",
        "additional_complication": "; momentum rider: complication",
    }.get(momentum_effect, "")
    summary = (
        f"roll {skill} ({attribute}) @ {risk}: {total} vs {target} -> "
        f"{outcome} ({momentum_in:+d} to {momentum_out:+d} momentum"
        f"{rider_suffix}){target_suffix}"
    )
    queue_event(state, role.actor, summary)
    if skill_saved:
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
    roll_row["skill_declared"] = skill_declared
    roll_row["skill_saved"] = skill_saved
    roll_row["skill_xp_eligible"] = skill_declared
    roll_row["momentum_effect"] = momentum_effect
    roll_row["momentum_guidance"] = momentum_guidance
    if beat_failure is not None:
        roll_row["beat_failure"] = beat_failure
    roll_row["instructions"] = _roll_result_instructions(
        outcome=outcome,
        scene_id=scene_id,
        target_id=target_id,
        beat_failure=beat_failure,
    )
    roll_row["character_mirror"] = write_public_character_mirror(
        paths,
        campaign_id,
        updated_character,
    )
    commit(
        paths,
        state,
        command_path,
        "roll",
        command_params(
            skill=skill,
            attribute=attribute,
            risk=risk,
            character_id=character_id,
            target_id=target_id,
            save_skill=save_skill,
        ),
        roll_row,
        emit_output=emit_output,
    )
    return roll_row


def _roll_result_instructions(
    *,
    outcome: str,
    scene_id: str | None,
    target_id: str | None,
    beat_failure: dict[str, Any] | None,
) -> list[str]:
    instructions = [
        "This roll is resolved. Carry this exact outcome forward; do not reroll the same action under a new skill or angle.",
    ]
    if outcome in _FAILED_ROLL_OUTCOMES:
        instructions.append(
            _failed_roll_instruction(
                scene_id=scene_id,
                target_id=target_id,
                beat_failure=beat_failure,
            )
        )
    elif scene_id:
        instructions.append(
            "If this resolves the live beat, close or convert the beat, tick the relevant scene clock/tracker, or commit any durable state change before glass_done; otherwise carry the success into the next action instead of drilling deeper."
        )
    else:
        instructions.append(
            "Use the result in public prose and record any durable state change with the matching MCP tool before glass_done."
        )
    return instructions


def _failed_roll_instruction(
    *,
    scene_id: str | None,
    target_id: str | None,
    beat_failure: dict[str, Any] | None,
) -> str:
    if isinstance(beat_failure, dict):
        status = str(beat_failure.get("status") or "")
        reason = str(beat_failure.get("reason") or "")
        beat = beat_failure.get("beat")
        beat_id = ""
        if isinstance(beat, dict):
            beat_id = str(beat.get("beat_id") or "")
        beat_id = beat_id or str(target_id or "").strip()
        after = beat_failure.get("after")
        limit = beat_failure.get("limit") or BEAT_FAILURE_LIMIT
        if status == "closed":
            return (
                f"Failed-roll pressure on beat `{beat_id}` reached {after}/{limit}; "
                "the beat is closed and the DM is queued to reframe the route. Do not retry or reopen it; finish the turn with the visible setback."
            )
        if status == "ticked":
            return (
                f"Failed-roll pressure on beat `{beat_id}` is {after}/{limit}. "
                "Finish this turn with a visible setback or cost. A later actor may make the second attempt before the beat closes, but it should be a concrete action that changes table position rather than more diagnosis."
            )
        if reason == "multiple_active_beats_require_target_id":
            return (
                "No beat failure pressure ticked because multiple active beats require target_id. Apply a visible consequence this turn; future ordinary active-play rolls must target one active beat from glass_check()."
            )
        if reason == "target_is_not_active_beat":
            return (
                "No beat failure pressure ticked because target_id is not an active beat. Apply a visible consequence this turn; future ordinary active-play rolls must target one active beat from glass_check()."
            )
        if reason == "no_active_beat":
            return (
                "No beat failure pressure ticked because there is no active beat. Apply a visible consequence this turn and ask the DM to open or reframe a beat if play needs one."
            )
    if scene_id:
        return (
            "This failed outcome needs a visible cost, consequence, or changed position before glass_done; do not retry the same obstacle unless the DM reframes it."
        )
    return (
        "This failed outcome needs a visible cost, consequence, or changed position before glass_done."
    )


def _apply_beat_failure_pressure(
    conn: Any,
    *,
    state: dict[str, Any],
    campaign_id: str,
    scene_id: str | None,
    target_id: str | None,
    outcome: str,
    actor: str,
    turn_id: str | None,
) -> dict[str, Any] | None:
    if outcome not in _FAILED_ROLL_OUTCOMES or not scene_id:
        return None

    active_beats = _db.scene_beat_list(
        conn,
        campaign_id=campaign_id,
        scene_id=scene_id,
        include_inactive=False,
    )
    if not active_beats:
        return {
            "status": "not_applied",
            "reason": "no_active_beat",
            "limit": BEAT_FAILURE_LIMIT,
        }

    target_key = slugify(target_id or "")
    beat_id: str | None = None
    if target_key:
        for beat in active_beats:
            if str(beat.get("beat_id") or "") == target_key:
                beat_id = target_key
                break
        if beat_id is None:
            return {
                "status": "not_applied",
                "reason": "target_is_not_active_beat",
                "target_id": target_key,
                "active_beat_ids": [str(beat.get("beat_id") or "") for beat in active_beats],
                "limit": BEAT_FAILURE_LIMIT,
            }
    elif len(active_beats) == 1:
        beat_id = str(active_beats[0].get("beat_id") or "")
    else:
        return {
            "status": "not_applied",
            "reason": "multiple_active_beats_require_target_id",
            "active_beat_ids": [str(beat.get("beat_id") or "") for beat in active_beats],
            "limit": BEAT_FAILURE_LIMIT,
        }

    tick = _db.scene_beat_failure_tick(
        conn,
        campaign_id=campaign_id,
        scene_id=scene_id,
        beat_id=beat_id,
        actor=actor,
        turn_id=turn_id,
        limit=BEAT_FAILURE_LIMIT,
        outcome=(
            "failed-roll limit reached: two failed rolls against this beat; "
            "DM must route the party toward the scene goal through a fresh offer "
            "or angle."
        ),
    )
    beat = tick["beat"]
    queue_event(
        state,
        actor,
        f"beat failure {beat['label']}: {tick['after']}/{tick['limit']}",
    )
    status = "ticked"
    if tick["closed"]:
        status = "closed"
        queue_event(
            state,
            actor,
            f"beat close {beat['label']} (failed twice; DM reframe)",
        )
        tick["handoff"] = _queue_dm_reframe_after_current_turn(state, beat_id=beat_id)
    tick["status"] = status
    return tick


def _queue_dm_reframe_after_current_turn(
    state: dict[str, Any], *, beat_id: str
) -> dict[str, Any]:
    entry = {
        "agent": "dm",
        "source": "beat.failure-limit",
        "beat_id": beat_id,
    }
    queue = state.setdefault("next_speakers", [])
    for existing in queue:
        if not isinstance(existing, dict):
            continue
        if (
            existing.get("agent") == "dm"
            and existing.get("source") == "beat.failure-limit"
            and existing.get("beat_id") == beat_id
        ):
            return existing

    current_actor = str(state.get("active_turn_actor") or "").strip()
    insert_at = len(queue)
    if queue:
        head = queue[0] if isinstance(queue[0], dict) else {"agent": queue[0]}
        if head.get("agent") == current_actor:
            insert_at = 1
    queue.insert(insert_at, entry)
    return entry
