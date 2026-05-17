"""Scene commands."""

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
from ..character_projection import write_public_character_mirror
from ..config import REPO_ROOT, Paths, get_paths
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
from ..outcomes import (
    append_clock_disposition_section,
    append_outcome_section,
    normalize_outcomes,
    outcome_section,
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


_campaign_workspace = resolve_active_campaign_workspace


@click.group()
def scene() -> None:
    """Scene lifecycle (DM-only): create, end, current, list."""


@scene.command("create")
@click.argument("scene_id")
@click.option(
    "--type",
    "scene_type",
    required=True,
    help="Scene protocol/toolkit label. Custom slugs are allowed.",
)
@click.option("--arc", "arc_id", default=None, help="Override active arc.")
@click.pass_context
def scene_create(
    ctx: click.Context, scene_id: str, scene_type: str, arc_id: str | None
) -> None:
    require_dm()
    workspace = _campaign_workspace()
    paths = get_paths()
    try:
        scene_dir = _workspace.create_scene(workspace, scene_id, scene_type, arc_id=arc_id)
    except FileExistsError as exc:
        raise GlassError(
            agent_instruction(
                str(exc),
                "Choose a new scene id, or activate/use the existing scene instead of creating it again.",
            )
        ) from exc
    except FileNotFoundError as exc:
        raise GlassError(
            agent_instruction(
                str(exc),
                "Create or activate the target arc first with "
                "`glass arc create <arc-id> --pull-source <source> "
                "--pull-utilization <note>` or `glass arc activate <arc-id>`.",
            )
        ) from exc
    except ValueError as exc:
        raise GlassError(
            agent_instruction(
                str(exc),
                "Use slug-like scene and type names, then retry the scene command.",
            )
        ) from exc
    state = load_state(paths, workspace.campaign_id)
    normalized_scene_type = _workspace.slugify(scene_type)
    normalized_scene_id = _workspace.slugify(scene_id)
    active_scene_arc = state.get("active_scene_arc")
    queue_event(
        state,
        "dm",
        f"scene create: {normalized_scene_id} ({normalized_scene_type})",
    )
    result = {
        "campaign_id": workspace.campaign_id,
        "scene_id": normalized_scene_id,
        "scene_type": normalized_scene_type,
        "arc_id": arc_id or active_scene_arc,
        "path": str(scene_dir),
        "files": ["prep.md", "context.md", "summary.md", "transcript.md", "audit.jsonl"],
        "table_path": str(workspace.table_dir),
        "table_files": ["scene.md", "handouts/", "<named-artifacts>.md"],
    }
    commit(
        paths,
        state,
        ctx,
        "scene.create",
        command_params(scene_id=scene_id, scene_type=scene_type, arc_id=arc_id),
        result,
    )


@scene.command("end")
@click.option("--summary", default=None,
              help="Scene summary written to arcs/<arc>/scenes/<scene>/summary.md.")
@click.option("--beats", default=None,
              help="Newline-separated bullets appended to shared/quest-log.md, "
                   "tagged with the scene + arc.")
@click.option("--outcome", "outcome_values", multiple=True, required=True,
              help="Repeat 1-2 times. In-universe scene outcome/consequence bullet.")
@click.option("--xp", "xp_spec", default=None,
              help="XP awards: 'tev=2,sumi=1,renno=3'. Calls character "
                   "award-xp per entry with reason=\"scene end: <scene_id>\".")
@click.option(
    "--carry-clock",
    "carry_clock_specs",
    multiple=True,
    help=(
        "Disposition for an active scene clock at scene close: "
        "`<clock-id>=<reason>`. Use when the clock's pressure continues "
        "beyond this scene and needs to surface in the next scene's prep."
    ),
)
@click.option(
    "--retire-clock",
    "retire_clock_specs",
    multiple=True,
    help=(
        "Disposition for an active scene clock at scene close: "
        "`<clock-id>=<reason>`. Use when the clock is obsolete, was "
        "resolved by fiction without a tick, or no longer matters."
    ),
)
@click.pass_context
def scene_end_cmd(
    ctx: click.Context,
    summary: str | None,
    beats: str | None,
    outcome_values: tuple[str, ...],
    xp_spec: str | None,
    carry_clock_specs: tuple[str, ...],
    retire_clock_specs: tuple[str, ...],
) -> None:
    """End the active scene + bundle wrap-up writes.

    Atomic: writes summary, appends beats, awards XP, then marks the scene
    as no-longer-active in the campaign workspace state. Also clears any
    scene_closing_turns countdown — the scene is over.
    """
    role = require_dm()
    workspace = _campaign_workspace()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    session_id = state["campaign"]

    current = _workspace.current_scene(workspace)
    if not current:
        raise GlassError(
            agent_instruction(
                "there is no active scene to end",
                "Do not call `glass scene end` until a scene has been created or activated.",
                "If you are transitioning scenes, create/start the next scene first only after the current active scene exists and is ready to close.",
            )
        )
    scene_id = current["scene_id"]
    arc_id = current["arc_id"]
    outcome_lines = normalize_outcomes(outcome_values)

    carry_dispositions = _parse_clock_disposition_specs(carry_clock_specs, "carry")
    retire_dispositions = _parse_clock_disposition_specs(retire_clock_specs, "retire")
    overlap = set(carry_dispositions) & set(retire_dispositions)
    if overlap:
        raise GlassError(
            agent_instruction(
                "the same clock cannot be both carried and retired: "
                + ", ".join(sorted(overlap)),
                "Pick one disposition per clock. Use `--carry-clock` when "
                "pressure continues beyond the scene; use `--retire-clock` "
                "when the clock is obsolete or resolved by fiction.",
            )
        )
    with pg_connection() as conn:
        active_scene_clocks = _db.scene_clock_list(
            conn,
            campaign_id=campaign_id,
            scene_id=scene_id,
        )
    active_clock_ids = {str(item["clock_id"]) for item in active_scene_clocks}
    declared_clock_ids = set(carry_dispositions) | set(retire_dispositions)
    missing_dispositions = sorted(active_clock_ids - declared_clock_ids)
    unknown_dispositions = sorted(declared_clock_ids - active_clock_ids)
    if missing_dispositions:
        raise GlassError(
            agent_instruction(
                "scene end refuses while active scene clocks have no disposition: "
                + ", ".join(missing_dispositions),
                "For each open scene clock, either resolve it during play with "
                "`glass scene clock tick`, then rerun `glass scene end`, or "
                "name an explicit disposition: `--carry-clock <id>=<reason>` "
                "if the pressure continues beyond this scene, or "
                "`--retire-clock <id>=<reason>` if the clock is obsolete or "
                "was resolved by fiction without a tick.",
            )
        )
    if unknown_dispositions:
        raise GlassError(
            agent_instruction(
                "disposition given for clocks that are not active in this scene: "
                + ", ".join(unknown_dispositions),
                "Use `glass scene clock list` or `glass check` to see the "
                "active scene clocks before dispositioning them.",
            )
        )
    clock_dispositions: list[dict[str, str]] = []
    for clock_record in active_scene_clocks:
        clock_id = str(clock_record["clock_id"])
        if clock_id in carry_dispositions:
            clock_dispositions.append(
                {
                    "clock_id": clock_id,
                    "label": str(clock_record.get("label") or clock_id),
                    "disposition": "carried",
                    "reason": carry_dispositions[clock_id],
                    "value": int(clock_record.get("value", 0) or 0),
                    "max": int(clock_record.get("max", 0) or 0),
                }
            )
        else:
            clock_dispositions.append(
                {
                    "clock_id": clock_id,
                    "label": str(clock_record.get("label") or clock_id),
                    "disposition": "retired",
                    "reason": retire_dispositions[clock_id],
                    "value": int(clock_record.get("value", 0) or 0),
                    "max": int(clock_record.get("max", 0) or 0),
                }
            )

    summary_path: str | None = None
    if summary and summary.strip():
        body = append_outcome_section(summary.strip(), outcome_lines)
        body = append_clock_disposition_section(body, clock_dispositions)
        summary_path = _write_scene_summary(workspace, arc_id, scene_id, body)
    else:
        summary_path = _append_scene_outcomes(
            workspace,
            arc_id,
            scene_id,
            outcome_lines,
        )
        if clock_dispositions and summary_path:
            existing = Path(summary_path).read_text(encoding="utf-8")
            Path(summary_path).write_text(
                append_clock_disposition_section(existing, clock_dispositions),
                encoding="utf-8",
            )

    beat_lines: list[str] = []
    if beats:
        for line in _split_quest_beat_lines(beats):
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
                        agent_instruction(
                            f"cannot award scene XP to {agent!r}",
                            "Use an agent id with exactly one character in this campaign.",
                            "If the player has no character or multiple rows, resolve the character sheet before awarding scene XP.",
                        )
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
                    raise GlassError(
                        agent_instruction(
                            f"unknown character {character_id!r}",
                            "Use the character id assigned to the target player in this campaign.",
                        )
                    ) from None
                xp_awards.append({
                    "player": agent,
                    "character_id": character_id,
                    "delta": delta,
                    "xp_before": before,
                    "xp_after": after,
                    "level": updated["level"],
                    "mirror": write_public_character_mirror(
                        paths,
                        campaign_id,
                        updated,
                    ),
                })

    table_archive_path: str | None = None
    try:
        table_archive_path = str(
            _workspace.archive_table(
                workspace,
                arc_id=arc_id,
                scene_id=scene_id,
                clear_live=True,
            )
        )
    except FileNotFoundError:
        table_archive_path = None

    try:
        ended = _workspace.end_scene(workspace)
    except ValueError as exc:
        raise GlassError(
            agent_instruction(
                str(exc),
                "Check the active scene with `glass scene current`, then end only that scene.",
            )
        ) from exc

    state["active_scene"] = None
    state["active_scene_arc"] = None
    state["active_scene_type"] = None
    state["scene_closing_turns"] = None
    state["action_order"] = None
    trackers = state.get("scene_trackers")
    if isinstance(trackers, dict):
        state["scene_trackers"] = {
            key: value
            for key, value in trackers.items()
            if not isinstance(value, dict) or value.get("scene_id") != scene_id
        }
    with pg_connection() as conn:
        _db.scene_tracker_delete_scene(
            conn,
            campaign_id=campaign_id,
            scene_id=scene_id,
        )
        _db.action_order_clear_scene(
            conn,
            campaign_id=campaign_id,
            scene_id=scene_id,
        )
        _db.scene_beat_drop_scene(
            conn,
            campaign_id=campaign_id,
            scene_id=scene_id,
            actor=role.actor,
            turn_id=str(state.get("active_turn_id") or "").strip() or None,
            outcome="scene ended",
        )
        _db.scene_clock_drop_scene(
            conn,
            campaign_id=campaign_id,
            scene_id=scene_id,
            actor=role.actor,
            turn_id=str(state.get("active_turn_id") or "").strip() or None,
            outcome="scene ended",
        )
    for item in clock_dispositions:
        queue_event(
            state,
            role.actor,
            f"scene clock {item['disposition']}: {item['label']} "
            f"({item['value']}/{item['max']}) — {item['reason']}",
        )
    queue_event(
        state, role.actor,
        f"scene end: {ended}"
        + (f" (+{len(xp_awards)} xp awards)" if xp_awards else ""),
    )
    result = {
        "campaign_id": workspace.campaign_id,
        "ended_scene": ended,
        "summary_path": summary_path,
        "outcomes": outcome_lines,
        "table_archive_path": table_archive_path,
        "beats_logged": beat_lines,
        "xp_awards": xp_awards,
        "clock_dispositions": clock_dispositions,
    }
    commit(
        paths, state, ctx, "scene.end",
        command_params(
            summary=summary,
            beats=beats,
            outcomes=outcome_lines,
            xp=xp_spec,
            carry_clock=list(carry_clock_specs),
            retire_clock=list(retire_clock_specs),
        ),
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
    instead. The DM closes with `glass scene end --outcome`.

    The countdown is informational pressure, not a hard cap — the DM is
    expected to actually call `glass scene end --outcome` when ready. The
    methodology says imperfect closure beats a forever-running scene.

    Use `--rounds N` for the typical case (1 round = ~5 agent turns).
    `--turns N` is an escape hatch for fine-grained control.
    """
    role = require_dm()
    if turn_budget is not None:
        if turn_budget <= 0:
            raise GlassError(
                agent_instruction(
                    "`--turns` must be positive",
                    "Pass a positive turn count, or omit `--turns` and use `--rounds <n>`.",
                )
            )
        commits = turn_budget
        unit_label = f"{turn_budget} turn(s)"
    else:
        if round_budget <= 0:
            raise GlassError(
                agent_instruction(
                    "`--rounds` must be positive",
                    "Pass a positive round count, or use `--turns <n>` for a raw turn countdown.",
                )
            )
        commits = round_budget * _AGENTS_PER_ROUND
        unit_label = f"~{round_budget} round(s)"
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
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


@scene.group("clock")
def scene_clock() -> None:
    """Scene-local required clocks for active play."""


@scene_clock.command("declare")
@click.argument("clock_id")
@click.option("--label", required=True)
@click.option("--goal", required=True)
@click.option("--value", type=int, default=0, show_default=True)
@click.option("--max", "max_value", type=int, required=True)
@click.option(
    "--direction",
    type=click.Choice(["progress", "countdown"]),
    required=True,
)
@click.option(
    "--polarity",
    type=click.Choice(["objective", "threat", "timer"]),
    default=None,
    help=(
        "Scene-clock meaning. Defaults to objective for progress clocks and "
        "timer for countdown clocks."
    ),
)
@click.option(
    "--visibility",
    type=click.Choice(["public", "dm"]),
    default="public",
    show_default=True,
)
@click.pass_context
def scene_clock_declare(
    ctx: click.Context,
    clock_id: str,
    label: str,
    goal: str,
    value: int,
    max_value: int,
    direction: str,
    polarity: str | None,
    visibility: str,
) -> None:
    """DM-only: declare or replace a scene-specific active-play clock."""
    role = require_dm()
    polarity_value = polarity or ("timer" if direction == "countdown" else "objective")
    if max_value <= 0:
        raise GlassError(
            agent_instruction(
                "`--max` must be greater than zero",
                "Choose the size of the scene clock, for example `--max 4`, `--max 6`, or `--max 10`.",
            )
        )
    if value < 0 or value > max_value:
        raise GlassError(
            agent_instruction(
                "`--value` must be between 0 and `--max`",
                "Set the current scene clock value within the clock bounds, or omit `--value` to start at 0.",
            )
        )
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    scene_id = _active_tracker_scene_id(state)
    clock_key = slugify(clock_id)
    turn_id = str(state.get("active_turn_id") or "").strip() or None
    with pg_connection() as conn:
        record = _db.scene_clock_upsert(
            conn,
            campaign_id=campaign_id,
            scene_id=scene_id,
            clock_id=clock_key,
            label=label.strip(),
            goal=goal.strip(),
            value=value,
            max_value=max_value,
            direction=direction,
            polarity=polarity_value,
            visibility=visibility,
            actor=role.actor,
            turn_id=turn_id,
        )
    queue_event(
        state,
        role.actor,
        (
            f"scene clock declare {record['label']}: "
            f"{record['value']}/{record['max']} ({polarity_value} {direction})"
        ),
    )
    commit(
        paths,
        state,
        ctx,
        "scene.clock.declare",
        command_params(
            clock_id=clock_key,
            label=label,
            goal=goal,
            value=value,
            max=max_value,
            direction=direction,
            polarity=polarity_value,
            visibility=visibility,
        ),
        {"clock": record},
    )


@scene_clock.command("tick")
@click.argument("clock_id")
@click.argument("delta", type=int, default=1, required=False)
@click.option("--outcome", required=True)
@click.pass_context
def scene_clock_tick(
    ctx: click.Context,
    clock_id: str,
    delta: int,
    outcome: str,
) -> None:
    """Move a scene clock directly when a turn creates a concrete consequence."""
    if delta == 0:
        raise GlassError(
            agent_instruction(
                "`delta` must not be 0",
                "Use a positive or negative integer that actually moves the scene clock.",
            )
        )
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    scene_id = _active_tracker_scene_id(state)
    clock_key = slugify(clock_id)
    turn_id = str(state.get("active_turn_id") or "").strip() or None
    outcome_text = outcome.strip()
    if not outcome_text:
        raise GlassError(
            agent_instruction(
                "`--outcome` cannot be empty",
                "Name the visible consequence or progress that moved this scene clock.",
            )
        )
    with pg_connection() as conn:
        existing = _db.scene_clock_get(
            conn,
            campaign_id=campaign_id,
            scene_id=scene_id,
            clock_id=clock_key,
        )
        if existing is None or existing.get("status") != "active":
            raise GlassError(
                agent_instruction(
                    f"unknown active scene clock {clock_key!r}",
                    "Use `glass check` to inspect the active scene contract, or have the DM declare the scene clock first.",
                )
            )
        if role.kind == "player" and existing.get("visibility") != "public":
            raise GlassError(
                agent_instruction(
                    f"scene clock {clock_key!r} is not player-visible",
                    "Players may tick only public scene clocks. End with `--next dm` if a hidden clock needs to move.",
                )
            )
        clock, before, after, resolved = _db.scene_clock_apply_delta(
            conn,
            campaign_id=campaign_id,
            scene_id=scene_id,
            clock_id=clock_key,
            delta=delta,
            actor=role.actor,
            turn_id=turn_id,
            outcome=outcome_text,
        )
    queue_event(
        state,
        role.actor,
        (
            f"scene clock tick {clock['label']}: {delta:+d} "
            f"({before}/{clock['max']} -> {after}/{clock['max']})"
        ),
    )
    if resolved:
        queue_event(state, role.actor, f"scene clock resolved {clock['label']}")
    commit(
        paths,
        state,
        ctx,
        "scene.clock.tick",
        command_params(clock_id=clock_key, delta=delta, outcome=outcome_text),
        {
            "clock": clock,
            "before": before,
            "after": after,
            "delta": delta,
            "resolved": resolved,
        },
    )


@scene.group("tracker")
def scene_tracker() -> None:
    """Scene-local generic counters/clocks."""


@scene_tracker.command("set")
@click.argument("tracker_id")
@click.option("--label", default=None, help="Player-facing label. Defaults to tracker id.")
@click.option("--value", type=int, default=0, show_default=True)
@click.option("--max", "max_value", type=int, required=True)
@click.option(
    "--resistance",
    type=int,
    default=0,
    show_default=True,
    help="Known to-hit resistance for scene pressure attempts.",
)
@click.option(
    "--impact-resistance",
    type=int,
    default=0,
    show_default=True,
    help="Rare reduction applied to successful pressure impact.",
)
@click.option(
    "--public/--hidden",
    "public",
    default=True,
    show_default=True,
    help="Whether the tracker appears in player turn context.",
)
@click.pass_context
def scene_tracker_set(
    ctx: click.Context,
    tracker_id: str,
    label: str | None,
    value: int,
    max_value: int,
    resistance: int,
    impact_resistance: int,
    public: bool,
) -> None:
    """DM-only: create or replace a scene-local generic tracker."""
    role = require_dm()
    if max_value <= 0:
        raise GlassError(
            agent_instruction(
                "`--max` must be greater than zero",
                "Choose the tracker size, for example `--max 4` for a short clock or `--max 10` for a larger pressure track.",
            )
        )
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    scene_id = _active_tracker_scene_id(state)
    tracker_key = slugify(tracker_id)
    tracker = {
        "tracker_id": tracker_key,
        "scene_id": scene_id,
        "label": label or tracker_key,
        "value": clamp(value, 0, max_value),
        "max": max_value,
        "resistance": resistance,
        "impact_resistance": impact_resistance,
        "public": public,
        "updated_at": now_iso(),
        "updated_by": role.actor,
    }
    with pg_connection() as conn:
        tracker = _db.scene_tracker_upsert(
            conn,
            campaign_id=campaign_id,
            tracker_id=tracker_key,
            scene_id=scene_id,
            label=label or tracker_key,
            value=tracker["value"],
            max_value=max_value,
            resistance=resistance,
            impact_resistance=impact_resistance,
            visibility="public" if public else "dm",
            actor=role.actor,
        )
    state.setdefault("scene_trackers", {})[tracker_key] = tracker
    queue_event(state, role.actor, _tracker_summary("tracker set", tracker))
    result = {"tracker": tracker}
    commit(
        paths,
        state,
        ctx,
        "scene.tracker.set",
        command_params(
            tracker_id=tracker_key,
            label=label,
            value=value,
            max=max_value,
            resistance=resistance,
            impact_resistance=impact_resistance,
            public=public,
        ),
        result,
    )


@scene_tracker.command("tick")
@click.argument("tracker_id")
@click.argument("delta", type=int, default=1, required=False)
@click.pass_context
def scene_tracker_tick(ctx: click.Context, tracker_id: str, delta: int) -> None:
    """DM-only: advance or reduce a scene tracker."""
    role = require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    tracker_key = slugify(tracker_id)
    trackers = state.setdefault("scene_trackers", {})
    with pg_connection() as conn:
        try:
            tracker, before, after = _db.scene_tracker_tick(
                conn,
                campaign_id=campaign_id,
                tracker_id=tracker_key,
                delta=delta,
                actor=role.actor,
            )
        except LookupError:
            raise GlassError(
                agent_instruction(
                    f"unknown scene tracker {tracker_key!r}",
                    "Create the tracker first with `glass scene tracker set <id> --max <n>`.",
                    "Use `glass scene tracker list` to see trackers for the active scene.",
                )
            ) from None
    max_value = int(tracker.get("max", 0))
    trackers[tracker_key] = tracker
    sign = f"{delta:+d}"
    queue_event(
        state,
        role.actor,
        (
            f"tracker {tracker.get('label', tracker_key)} {sign} "
            f"({before}/{max_value} -> {after}/{max_value})"
        ),
    )
    result = {
        "tracker": tracker,
        "delta": delta,
        "before": before,
        "after": after,
        "complete": after >= max_value,
    }
    commit(
        paths,
        state,
        ctx,
        "scene.tracker.tick",
        command_params(tracker_id=tracker_key, delta=delta),
        result,
    )


@scene_tracker.command("list")
@click.option(
    "--all-scenes",
    is_flag=True,
    help="Include trackers outside the active scene.",
)
@click.pass_context
def scene_tracker_list(ctx: click.Context, all_scenes: bool) -> None:
    """List scene trackers visible to the current role."""
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    active_scene_id = _active_tracker_scene_id(state, required=False)
    with pg_connection() as conn:
        trackers = _db.scene_tracker_list(
            conn,
            campaign_id=campaign_id,
            scene_id=None if all_scenes else active_scene_id,
            visibility="public" if role.kind == "player" else None,
        )
    result = {"trackers": trackers, "count": len(trackers)}
    append_audit(
        paths,
        state,
        ctx,
        "scene.tracker.list",
        command_params(all_scenes=all_scenes),
        result,
    )
    emit(result)


@scene.command("pressure")
@click.argument("target_id")
@click.argument("skill")
@click.argument("attribute")
@click.option("--risk", required=True, type=click.Choice(sorted(RISK_THRESHOLDS)))
@click.option("--character", "character_id", required=True)
@click.option("--impact", "impact_die", required=True, type=click.Choice(["d6", "d8", "d10"]))
@click.option("--bonus", type=int, default=0, show_default=True)
@click.option(
    "--save-skill",
    is_flag=True,
    help="Declare this skill before rolling if it is not already on the sheet.",
)
@click.option("--because", default=None, help="Short explanation for bonuses, leverage, or item use.")
@click.option("--note", default=None, help="Free-text fictional effect note. Not mechanically interpreted.")
@click.pass_context
def scene_pressure(
    ctx: click.Context,
    target_id: str,
    skill: str,
    attribute: str,
    risk: str,
    character_id: str,
    impact_die: str,
    bonus: int,
    save_skill: bool,
    because: str | None,
    note: str | None,
) -> None:
    """Apply roll-mediated pressure to a scene tracker.

    This is intentionally generic: HP, morale, resistance, distance, alert, and
    similar values all use the same numeric reduction shape. Any nonnumeric
    effect stays in prose via --note and the turn narration.
    """
    assert_attribute_name(attribute)
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    scene_id = _active_tracker_scene_id(state)
    target_key = slugify(target_id)
    trackers = state.setdefault("scene_trackers", {})
    with pg_connection() as conn:
        tracker = _db.scene_tracker_get(
            conn,
            campaign_id=campaign_id,
            tracker_id=target_key,
        )
    if tracker is None:
        raise GlassError(
            agent_instruction(
                f"unknown scene tracker {target_key!r}",
                "Use `glass scene tracker list` to find active tracker ids.",
                "The DM can create a pressure target with `glass scene tracker set <id> --max <n>`.",
            )
        )
    if tracker.get("scene_id") != scene_id:
        raise GlassError(
            agent_instruction(
                f"scene tracker {target_key!r} belongs to scene {tracker.get('scene_id')!r}",
                "Pressure only trackers in the active scene.",
                "Use `glass scene tracker list` for the active scene, or have the DM create a new tracker for the current scene.",
            )
        )
    if role.kind == "player" and not bool(tracker.get("public", True)):
        raise GlassError(
            agent_instruction(
                "players cannot pressure hidden trackers",
                "Choose a public tracker from `glass scene tracker list`, or ask the DM to handle the hidden pressure.",
            )
        )

    resistance = int(tracker.get("resistance", 0))
    impact_resistance = int(tracker.get("impact_resistance", 0))
    base_target = RISK_THRESHOLDS[risk]
    adjusted_target = base_target + resistance
    rng = random.SystemRandom()

    with pg_connection() as conn:
        character = _db.character_get(conn, campaign_id, character_id)
        if character is None:
            raise GlassError(
                agent_instruction(
                    f"unknown character {character_id!r} in campaign {campaign_id!r}",
                    "Use the character id from your TURN_START character context or public character sheet.",
                )
            )
        if role.kind == "player" and character.get("player_id") != role.actor:
            raise GlassError(
                agent_instruction(
                    "players may pressure only with their own character",
                    f"This character belongs to `{character.get('player_id')}`; use your own character id.",
                    "If another character should act, use prose to set them up and let that player or the DM take the action.",
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
        dice = [rng.randint(1, CHECK_DIE_SIDES) for _ in range(CHECK_DICE_COUNT)]
        total = sum(dice) + skill_modifier + attribute_modifier + bonus
        margin = total - adjusted_target
        outcome, momentum_delta = outcome_for_margin(margin)
        momentum_out = clamp(momentum_in + momentum_delta, floor, ceiling)
        momentum_effect, momentum_guidance = momentum_narrative_effect(momentum_out)

        impact_roll: int | None = None
        base_reduction = 0
        if outcome in {"breakthrough", "advance"}:
            impact_roll = rng.randint(1, int(impact_die[1:]))
            base_reduction = _impact_reduction(impact_roll)
        elif outcome == "stall":
            base_reduction = 1
        reduction = max(0, base_reduction - impact_resistance)
        before = int(tracker.get("value", 0))
        max_value = int(tracker.get("max", 0))
        after = clamp(before - reduction, 0, max_value)

        metadata = {
            "command": "scene.pressure",
            "pressure_target_id": target_key,
            "base_target": base_target,
            "resistance": resistance,
            "bonus": bonus,
            "because": because,
            "impact_die": impact_die,
            "impact_resistance": impact_resistance,
            "impact_roll": impact_roll,
            "base_reduction": base_reduction,
            "reduction": reduction,
            "pressure_before": before,
            "pressure_after": after,
            "note": note,
            "momentum_applied_to_total": False,
            "momentum_effect": momentum_effect,
            "momentum_guidance": momentum_guidance,
            "skill_declared": skill_declared,
            "skill_saved": skill_saved,
            "skill_xp_eligible": skill_declared,
        }
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
            target=adjusted_target,
            margin=margin,
            outcome=outcome,
            momentum_delta=momentum_delta,
            momentum_out=momentum_out,
            target_id=target_key,
            metadata=metadata,
        )
        _db.character_set_momentum_internal(
            conn,
            campaign_id=campaign_id,
            character_id=character_id,
            value=momentum_out,
        )
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
        conn.commit()
        updated_character = _db.character_get(conn, campaign_id, character_id)
        if updated_character is None:
            raise GlassError(
                agent_instruction(
                    f"unknown character {character_id!r}",
                    "Retry with a character id that exists in this campaign.",
                )
            ) from None

    tracker["value"] = after
    tracker["updated_at"] = now_iso()
    tracker["updated_by"] = role.actor
    with pg_connection() as conn:
        tracker = _db.scene_tracker_set_value(
            conn,
            campaign_id=campaign_id,
            tracker_id=target_key,
            value=after,
            actor=role.actor,
        )
    trackers[target_key] = tracker

    label = tracker.get("label", target_key)
    impact_text = (
        f"{impact_die}={impact_roll} -> {base_reduction}"
        if impact_roll is not None
        else f"glancing -> {base_reduction}" if outcome == "stall" else "none"
    )
    resistance_text = (
        f", impact resistance {impact_resistance}" if impact_resistance else ""
    )
    queue_event(
        state,
        role.actor,
        (
            f"pressure {label}: {outcome}, impact {impact_text}"
            f"{resistance_text}, -{reduction} ({before}/{max_value} -> {after}/{max_value})"
            + {
                "additional_good": "; momentum rider: extra good",
                "additional_complication": "; momentum rider: complication",
            }.get(momentum_effect, "")
        ),
    )
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
    roll_row["character_mirror"] = write_public_character_mirror(
        paths,
        campaign_id,
        updated_character,
    )
    result = {
        "target": tracker,
        "before": before,
        "after": after,
        "reduction": reduction,
        "complete": after <= 0,
        "hit": {
            "roll": roll_row,
            "base_target": base_target,
            "resistance": resistance,
            "bonus": bonus,
            "adjusted_target": adjusted_target,
            "because": because,
        },
        "impact": {
            "die": impact_die,
            "roll": impact_roll,
            "base_reduction": base_reduction,
            "impact_resistance": impact_resistance,
            "reduction": reduction,
        },
        "note": note,
    }
    commit(
        paths,
        state,
        ctx,
        "scene.pressure",
        command_params(
            target_id=target_key,
            skill=skill,
            attribute=attribute,
            risk=risk,
            character_id=character_id,
            impact=impact_die,
            bonus=bonus,
            save_skill=save_skill,
            because=because,
            note=note,
        ),
        result,
    )


def _impact_reduction(impact_roll: int) -> int:
    if impact_roll <= 3:
        return 1
    if impact_roll <= 6:
        return 2
    return 3


def _active_tracker_scene_id(
    state: dict[str, Any], *, required: bool = True
) -> str | None:
    current = current_mode_record(state)
    if current and current.get("scene_id") and current["scene_id"] != "none":
        return str(current["scene_id"])
    if required:
        raise GlassError(
            agent_instruction(
                "scene trackers require an active mode and scene",
                "The DM should start or activate the scene and mode before using tracker or pressure commands.",
                "Use `glass scene current` and `glass mode start <mode> <scene-id>` to establish the active context.",
            )
        )
    return None


def _tracker_summary(prefix: str, tracker: dict[str, Any]) -> str:
    return (
        f"{prefix} {tracker.get('label', tracker.get('tracker_id'))}: "
        f"{tracker.get('value')}/{tracker.get('max')}"
    )


def _parse_clock_disposition_specs(
    specs: tuple[str, ...],
    disposition: str,
) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in specs:
        text = entry.strip()
        if not text:
            continue
        if "=" not in text:
            raise GlassError(
                agent_instruction(
                    f"invalid --{disposition}-clock {entry!r}",
                    f"Use `<clock-id>=<reason>`, for example "
                    f"`--{disposition}-clock cinder-cascade=\"Pressure carries "
                    f"into the next dock scene\"`.",
                )
            )
        clock_id, reason = text.split("=", 1)
        clock_id = slugify(clock_id)
        reason = reason.strip()
        if not clock_id:
            raise GlassError(
                agent_instruction(
                    f"--{disposition}-clock entry {entry!r} is missing a clock id",
                    f"Use `<clock-id>=<reason>` with the scene clock id from "
                    "`glass scene clock list` or `glass check`.",
                )
            )
        if not reason:
            raise GlassError(
                agent_instruction(
                    f"--{disposition}-clock {clock_id!r} is missing a reason",
                    "Name why this clock is being "
                    f"{'carried beyond the scene' if disposition == 'carry' else 'retired'}.",
                )
            )
        if clock_id in out:
            raise GlassError(
                agent_instruction(
                    f"clock {clock_id!r} appears more than once in --{disposition}-clock",
                    "Each clock can only carry one disposition.",
                )
            )
        out[clock_id] = reason
    return out


def _parse_xp_spec(spec: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for entry in spec.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "=" not in entry:
            raise GlassError(
                agent_instruction(
                    f"invalid XP award {entry!r}",
                    "Use `agent=delta` entries separated by commas, for example `tev=2,sumi=1`.",
                )
            )
        agent, delta_text = entry.split("=", 1)
        agent = agent.strip()
        try:
            delta = int(delta_text.strip())
        except ValueError:
            raise GlassError(
                agent_instruction(
                    f"invalid XP delta {delta_text!r}",
                    "Use an integer XP delta, for example `tev=2`.",
                )
            ) from None
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
    header = f"# {scene_id} - summary\n\n"
    path.write_text(header + body.rstrip() + "\n", encoding="utf-8")
    return display_path(path)


def _append_scene_outcomes(
    workspace: _workspace.CampaignWorkspace,
    arc_id: str | None,
    scene_id: str,
    outcomes: list[str],
) -> str | None:
    if not arc_id:
        return None
    scene_dir = workspace.scene_dir(arc_id, scene_id)
    scene_dir.mkdir(parents=True, exist_ok=True)
    path = scene_dir / "summary.md"
    if path.exists():
        existing = path.read_text(encoding="utf-8").rstrip()
        body = append_outcome_section(existing, outcomes)
    else:
        body = f"# {scene_id} - summary\n\n{outcome_section(outcomes)}"
    path.write_text(body.rstrip() + "\n", encoding="utf-8")
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


def _split_quest_beat_lines(text: str) -> list[str]:
    normalized = (
        text.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
    )
    return normalized.splitlines()


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
