"""Mode commands."""

from __future__ import annotations

import click

from .. import db as _db
from ..campaign import active_campaign_id, pg_connection
from ..config import get_paths
from ..errors import GlassError, agent_instruction
from ..facts import fact_pack
from ..ids import now_iso, slugify
from ..role import require_dm
from ..state import (
    append_audit,
    commit,
    current_mode_record,
    load_state,
    queue_event,
)
from ..yaml_io import command_params, emit


@click.group()
def mode() -> None:
    """Mode stack commands."""


_DEPRECATED_PLAY_MODE_LABELS = {
    "combat",
    "chase",
    "social-pressure",
    "travel",
    "travel-montage",
    "montage",
}


@mode.command("start")
@click.argument("mode_name")
@click.argument("scene_id")
@click.pass_context
def mode_start(ctx: click.Context, mode_name: str, scene_id: str) -> None:
    start_mode_service(
        command_path=ctx,
        emit_output=True,
        mode_name=mode_name,
        scene_id=scene_id,
    )


def start_mode_service(
    *,
    command_path: click.Context | str = "glass_mode_start",
    emit_output: bool = False,
    mode_name: str,
    scene_id: str,
) -> dict[str, object]:
    """Push a mode frame onto the stack."""

    role = require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    normalized_mode = slugify(mode_name)
    normalized_scene = slugify(scene_id)
    if normalized_mode in _DEPRECATED_PLAY_MODE_LABELS:
        raise GlassError(
            agent_instruction(
                f"`{normalized_mode}` is a scene type, not a mode",
                "Use `glass mode start action <scene-id>` for quickfire play or `glass mode start scene-play <scene-id>` for open scene play.",
                "Keep labels like combat, chase, social-pressure, travel, and montage in the scene `--type` or scene notes.",
            )
        )
    for existing in state["mode_stack"]:
        if (
            existing.get("mode") == normalized_mode
            and existing.get("scene_id") == normalized_scene
        ):
            raise GlassError(
                agent_instruction(
                    f"mode `{normalized_mode}` on scene `{normalized_scene}` is "
                    "already on the mode stack; refusing to push a duplicate frame",
                    "If the frame is the active top of the stack, you are already "
                    "in this mode/scene — continue play normally.",
                    "If the frame is buried (a parent of the current scene), pop "
                    "frames back to it with `glass mode end` instead of pushing a "
                    "second copy.",
                    "If you intended to begin a different scene, use a unique "
                    "`scene_id` (and create it with `glass scene create` first).",
                )
            )
    record = {
        "mode": normalized_mode,
        "scene_id": normalized_scene,
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
        command_path,
        "mode.start",
        command_params(mode_name=mode_name, scene_id=scene_id),
        result,
        emit_output=emit_output,
    )
    return result


@mode.command("end")
@click.pass_context
def mode_end(ctx: click.Context) -> None:
    end_mode_service(command_path=ctx, emit_output=True)


def end_mode_service(
    *,
    command_path: click.Context | str = "glass_mode_end",
    emit_output: bool = False,
) -> dict[str, object]:
    """Pop the active mode frame."""

    role = require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    if not state["mode_stack"]:
        raise GlassError(
            agent_instruction(
                "cannot end mode: there is no active mode on the stack",
                "Do not call `glass mode end` until the DM has started a mode with `glass mode start <mode> <scene>`.",
                "If the scene is already inactive, stop trying to close it and continue the current turn normally.",
            )
        )
    ending = state["mode_stack"][-1]
    if ending.get("mode") == "character-creation":
        failures = _character_creation_mode_end_failures()
        if failures:
            detail = "\n".join(f"- {failure}" for failure in failures)
            raise GlassError(
                agent_instruction(
                    "cannot end character-creation: relationship round is incomplete",
                    "Do not retry `glass mode end` in this turn.",
                    "Continue character creation instead: use `glass done --summary <what remains> --state <relationship facts still needed> --rolls none --next default`.",
                    "Each character must have at least one neutral graph fact with predicate `relationship`; after all are present, the final DM ratification turn may end the mode.",
                )
                + "\n\nStill needed:\n"
                + detail
            )
    ended = state["mode_stack"].pop()
    ended["ended_at"] = now_iso()
    action_order = state.get("action_order")
    if (
        isinstance(action_order, dict)
        and action_order.get("mode") == ended.get("mode")
        and action_order.get("scene_id") == ended.get("scene_id")
    ):
        state["action_order"] = None
    trackers = state.get("scene_trackers")
    if isinstance(trackers, dict):
        state["scene_trackers"] = {
            key: value
            for key, value in trackers.items()
            if not isinstance(value, dict)
            or value.get("scene_id") != ended.get("scene_id")
        }
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
    commit(paths, state, command_path, "mode.end", {}, result, emit_output=emit_output)
    return result


def _character_creation_mode_end_failures() -> list[str]:
    failures: list[str] = []
    campaign_id = active_campaign_id()
    with pg_connection() as conn:
        characters = _db.character_list(conn, campaign_id)
    if not characters:
        return []
    try:
        pack = fact_pack(campaign_id=campaign_id, audience="continuity", limit=500)
    except Exception as exc:
        return [f"continuity facts unavailable for relationship validation: {exc}"]
    subjects_with_relationships = {
        str(fact.get("subject_id") or "").strip()
        for fact in pack.get("facts") or []
        if str(fact.get("predicate") or "").strip() == "relationship"
    }
    for character in characters:
        character_id = str(character.get("character_id") or "").strip()
        player_id = str(character.get("player_id") or character_id or "<unknown>").strip()
        if character_id and character_id not in subjects_with_relationships:
            failures.append(f"{player_id}: missing relationship fact for {character_id}")
    return failures


@mode.command("current")
@click.pass_context
def mode_current(ctx: click.Context) -> None:
    emit(current_mode_service(command_path=ctx))


def current_mode_service(
    *,
    command_path: click.Context | str = "glass_mode_current",
) -> dict[str, object]:
    """Read the active mode stack."""

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    current = current_mode_record(state)
    result = {
        "current_mode": current["mode"] if current else None,
        "current_scene": current["scene_id"] if current else None,
        "mode_stack": state["mode_stack"],
    }
    append_audit(paths, state, command_path, "mode.current", {}, result)
    return result
