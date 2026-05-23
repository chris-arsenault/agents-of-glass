"""Scene beat commands."""

from __future__ import annotations

from typing import Any

import click

from .. import db as _db
from ..campaign import active_campaign_id, pg_connection
from ..errors import GlassError, agent_instruction
from ..ids import now_iso, slugify
from ..role import current_role
from ..scene_beats import (
    BEAT_MAX_ACTIVE,
    beat_check_required_for_turn,
    scene_contract_failures,
    scene_contract_snapshot,
)
from ..state import append_audit, commit, current_mode_record, load_state, queue_event
from ..config import get_paths
from ..yaml_io import command_params, emit

_ACTIVE_PLAY_MODE_NAMES = {"scene-play", "action"}


@click.group()
def beat() -> None:
    """Scene-local dramatic beat tracking."""


@beat.command("check")
@click.pass_context
def beat_check(ctx: click.Context) -> None:
    """Show the active scene's beat contract and mark the check as completed."""
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    turn_context = _active_turn_context(state)
    scene_id = _current_scene_id(state)
    role = current_role()
    if not scene_id:
        result = {
            "required": False,
            "scene_id": None,
            "note": "No active scene is available for beat tracking.",
        }
        append_audit(paths, state, ctx, "beat.check", command_params(), result)
        emit(result)
        return

    reference_turn = (
        int(state.get("active_turn_number"))
        if state.get("active_turn_number") is not None
        else int(state.get("turn_counter", 0)) + 1
    )
    with pg_connection() as conn:
        snapshot = scene_contract_snapshot(
            conn,
            campaign_id=campaign_id,
            scene_id=scene_id,
            role_kind=role.kind,
            reference_turn_number=reference_turn,
        )
    required = beat_check_required_for_turn(turn_context)
    failures = scene_contract_failures(snapshot)
    continuation_gap = bool(snapshot.get("recent_beats")) or int(
        snapshot.get("completed_beats", 0) or 0
    ) > 0
    continuation_failures = {
        "this active scene has 0 scene clocks",
        "this active scene has 0 active beats",
    }
    if required and failures:
        continuation_only = continuation_gap and all(
            failure in continuation_failures for failure in failures
        )
        if not continuation_only:
            detail = "\n".join(f"- {failure}" for failure in failures)
            raise GlassError(
                agent_instruction(
                    "active play cannot proceed until the scene clock/beat contract is live",
                    "The DM must declare at least one scene clock and start at least one beat for this scene before continuing active play.",
                    'Use `glass_scene_clock_declare(clock_id="<clock-id>", label="...", goal="...", max_value=<n>, direction="progress|countdown", polarity="objective|threat|timer", visibility="public|dm")` and `glass_beat_start(beat_id="<beat-id>", clock_id="<clock-id>", label="...", question="...")`.',
                )
                + "\n\nCurrent problems:\n"
                + detail
            )

    if turn_context:
        state["active_turn_beat_checked_at"] = now_iso()
    result = {
        "required": required,
        "scene_id": scene_id,
        "clock_count": snapshot["active_clock_count"],
        "hidden_clock_count": snapshot["hidden_clock_count"],
        "scene_clocks": snapshot["clocks"],
        "clock_groups": snapshot["clock_groups"],
        "clock_warnings": snapshot["clock_warnings"],
        "active_beats": snapshot["active_beats"],
        "recent_beats": snapshot["recent_beats"],
        "completed_beats": snapshot["completed_beats"],
        "scene_note": snapshot["scene_note"],
        "warning_beats": [beat["beat_id"] for beat in snapshot["warning_beats"]],
        "expired_beats": [beat["beat_id"] for beat in snapshot["expired_beats"]],
    }
    commit(paths, state, ctx, "beat.check", command_params(), result)


@beat.command("start")
@click.argument("beat_id")
@click.option("--clock", "clock_id", required=True)
@click.option("--label", required=True)
@click.option("--question", required=True)
@click.pass_context
def beat_start(
    ctx: click.Context,
    beat_id: str,
    clock_id: str,
    label: str,
    question: str,
) -> None:
    """Start a new dramatic beat in the active scene."""
    start_beat_service(
        command_path=ctx,
        emit_output=True,
        beat_id=beat_id,
        clock_id=clock_id,
        label=label,
        question=question,
    )


def start_beat_service(
    *,
    command_path: click.Context | str = "glass_beat_start",
    emit_output: bool = False,
    beat_id: str,
    clock_id: str,
    label: str,
    question: str,
) -> dict[str, Any]:
    """Start a new dramatic beat in the active scene."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    scene_id = _require_active_play_scene_id(state, tool_name="glass_beat_start")
    beat_key = slugify(beat_id)
    clock_key = slugify(clock_id)
    turn_id = str(state.get("active_turn_id") or "").strip() or None
    with pg_connection() as conn:
        try:
            record = _db.scene_beat_start(
                conn,
                campaign_id=campaign_id,
                scene_id=scene_id,
                beat_id=beat_key,
                clock_id=clock_key,
                label=label.strip(),
                question=question.strip(),
                actor=role.actor,
                turn_id=turn_id,
            )
        except LookupError:
            raise GlassError(
                agent_instruction(
                    f"unknown active scene clock {clock_key!r}",
                    "Use `glass_check()` to inspect the active scene contract, or have the DM declare the scene clock first.",
                )
            ) from None
        except ValueError as exc:
            if str(exc) == "too_many_active_beats":
                raise GlassError(
                    agent_instruction(
                        f"cannot start beat: this scene already has {BEAT_MAX_ACTIVE} active beats",
                        "Close or resolve an existing beat first with `glass_beat_close(beat_id=\"<beat-id>\", outcome=\"...\", clock_delta=<n>)`.",
                    )
                ) from None
            if str(exc) == "expired_active_beats":
                raise GlassError(
                    agent_instruction(
                        "cannot start a new beat while an active beat is already at 10/10",
                        "Close or convert the expired beat before opening another beat.",
                        "Use `glass_check()` to see which beat must be resolved.",
                    )
                ) from None
            if str(exc) == "beat_exists":
                raise GlassError(
                    agent_instruction(
                        f"beat {beat_key!r} already exists in this scene",
                        "Choose a new beat id, or close/convert the existing beat instead of starting it again.",
                    )
                ) from None
            raise
    queue_event(state, role.actor, f"beat start {record['label']}")
    commit(
        paths,
        state,
        command_path,
        "beat.start",
        command_params(beat_id=beat_key, clock=clock_key, label=label, question=question),
        {"beat": record},
        emit_output=emit_output,
    )
    return {"beat": record}


@beat.command("close")
@click.argument("beat_id")
@click.option("--outcome", required=True)
@click.option(
    "--clock-delta",
    type=int,
    required=True,
    help=(
        "Movement applied to this beat's scene clock as the beat closes. "
        "0 is valid (the beat resolved without moving the clock) but must be "
        "stated explicitly. Use a positive integer when the beat advanced the "
        "clock toward its goal/threat, or a negative integer when it walked "
        "the clock back."
    ),
)
@click.pass_context
def beat_close(
    ctx: click.Context,
    beat_id: str,
    outcome: str,
    clock_delta: int,
) -> None:
    """Close an active beat and record its scene-clock movement."""
    close_beat_service(
        command_path=ctx,
        emit_output=True,
        beat_id=beat_id,
        outcome=outcome,
        clock_delta=clock_delta,
    )


def close_beat_service(
    *,
    command_path: click.Context | str = "glass_beat_close",
    emit_output: bool = False,
    beat_id: str,
    outcome: str,
    clock_delta: int,
) -> dict[str, Any]:
    """Close an active beat and record its scene-clock movement."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    scene_id = _require_scene_id(state)
    beat_key = slugify(beat_id)
    turn_id = str(state.get("active_turn_id") or "").strip() or None
    with pg_connection() as conn:
        beat = _db.scene_beat_get(
            conn,
            campaign_id=campaign_id,
            scene_id=scene_id,
            beat_id=beat_key,
        )
        if beat is None or beat.get("status") != "active":
            raise GlassError(
                agent_instruction(
                    f"unknown active beat {beat_key!r}",
                    "Use `glass_check()` to inspect active beats for this scene.",
                )
            )
        closed = _db.scene_beat_close(
            conn,
            campaign_id=campaign_id,
            scene_id=scene_id,
            beat_id=beat_key,
            actor=role.actor,
            turn_id=turn_id,
            outcome=outcome.strip(),
        )
        clock_result: dict[str, Any] | None = None
        if clock_delta:
            clock, before, after, resolved = _db.scene_clock_apply_delta(
                conn,
                campaign_id=campaign_id,
                scene_id=scene_id,
                clock_id=str(beat.get("clock_id") or ""),
                delta=clock_delta,
                actor=role.actor,
                turn_id=turn_id,
                outcome=outcome.strip(),
            )
            clock_result = {
                "clock": clock,
                "before": before,
                "after": after,
                "delta": clock_delta,
                "resolved": resolved,
            }
    queue_event(state, role.actor, f"beat close {closed['label']}")
    if clock_result and clock_result.get("resolved"):
        queue_event(
            state,
            role.actor,
            f"scene clock resolved {clock_result['clock']['label']}",
        )
    commit(
        paths,
        state,
        command_path,
        "beat.close",
        command_params(beat_id=beat_key, outcome=outcome, clock_delta=clock_delta),
        {"beat": closed, "clock": clock_result},
        emit_output=emit_output,
    )
    return {"beat": closed, "clock": clock_result}


@beat.command("convert")
@click.argument("beat_id")
@click.option("--to-clock", "to_clock_id", required=True)
@click.option("--reason", required=True)
@click.pass_context
def beat_convert(
    ctx: click.Context,
    beat_id: str,
    to_clock_id: str,
    reason: str,
) -> None:
    """Convert an active beat into longer-running clock pressure."""
    convert_beat_service(
        command_path=ctx,
        emit_output=True,
        beat_id=beat_id,
        to_clock_id=to_clock_id,
        reason=reason,
    )


def convert_beat_service(
    *,
    command_path: click.Context | str = "glass_beat_convert",
    emit_output: bool = False,
    beat_id: str,
    to_clock_id: str,
    reason: str,
) -> dict[str, Any]:
    """Convert an active beat into longer-running clock pressure."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    scene_id = _require_scene_id(state)
    beat_key = slugify(beat_id)
    clock_key = slugify(to_clock_id)
    turn_id = str(state.get("active_turn_id") or "").strip() or None
    with pg_connection() as conn:
        try:
            record = _db.scene_beat_convert(
                conn,
                campaign_id=campaign_id,
                scene_id=scene_id,
                beat_id=beat_key,
                to_clock_id=clock_key,
                actor=role.actor,
                turn_id=turn_id,
                reason=reason.strip(),
            )
        except LookupError:
            raise GlassError(
                agent_instruction(
                    f"cannot convert beat {beat_key!r} to clock {clock_key!r}",
                    "Use `glass_check()` to inspect the active beats and scene clocks for this scene.",
                )
            ) from None
    queue_event(state, role.actor, f"beat convert {record['label']}")
    commit(
        paths,
        state,
        command_path,
        "beat.convert",
        command_params(beat_id=beat_key, to_clock=clock_key, reason=reason),
        {"beat": record},
        emit_output=emit_output,
    )
    return {"beat": record}


def _active_turn_context(state: dict[str, Any]) -> dict[str, Any] | None:
    turn_id = str(state.get("active_turn_id") or "").strip()
    if not turn_id:
        return None
    return {
        "turn_id": turn_id,
        "kind": str(state.get("active_turn_kind") or "").strip(),
    }


def _current_scene_id(state: dict[str, Any]) -> str | None:
    current = current_mode_record(state)
    if current and current.get("scene_id") and current["scene_id"] != "none":
        return str(current["scene_id"])
    active_turn_scene = str(state.get("active_turn_scene_id") or "").strip()
    if active_turn_scene:
        return active_turn_scene
    return None


def _require_scene_id(state: dict[str, Any]) -> str:
    scene_id = _current_scene_id(state)
    if scene_id:
        return scene_id
    raise GlassError(
        agent_instruction(
            "scene beats require an active scene",
            "Start or activate the scene and mode before using scene beat MCP tools.",
            'Use `glass_scene_current()` and `glass_mode_start(mode_name="<mode>", scene_id="<scene-id>")` to establish the active context.',
        )
    )


def _require_active_play_scene_id(state: dict[str, Any], *, tool_name: str) -> str:
    current = current_mode_record(state)
    if current and current.get("scene_id") and current["scene_id"] != "none":
        mode = str(current.get("mode") or "").strip()
        if mode in _ACTIVE_PLAY_MODE_NAMES:
            return str(current["scene_id"])
        raise GlassError(
            agent_instruction(
                f"{tool_name} requires the target scene to be the active play mode",
                "Scene beats are scene-play/action state. Do not start beats while the active mode is scene-prep, campaign-planning, character-creation, or another setup frame.",
                'After `glass_scene_create(...)`, call `glass_mode_end()` if needed, then `glass_mode_start(mode_name="scene-play", scene_id="<scene-id>")` or `glass_mode_start(mode_name="action", scene_id="<scene-id>")` before using beat tools.',
            )
        )
    raise GlassError(
        agent_instruction(
            f"{tool_name} requires an active play scene",
            'Start the target scene first with `glass_mode_start(mode_name="scene-play", scene_id="<scene-id>")` or `glass_mode_start(mode_name="action", scene_id="<scene-id>")`.',
            "Beat tools take the scene id from the active mode; they do not infer it from the last created scene.",
        )
    )
