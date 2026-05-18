"""Mode commands."""

from __future__ import annotations

import click

from ..campaign import active_campaign_id, active_campaign_root
from ..config import get_paths
from ..errors import GlassError, agent_instruction
from ..ids import now_iso, slugify
from ..role import require_dm
from ..state import (
    commit,
    current_mode_record,
    load_state,
    queue_event,
)
from ..yaml_io import command_params


@click.group()
def mode() -> None:
    """Mode stack commands."""


@mode.command("start")
@click.argument("mode_name")
@click.argument("scene_id")
@click.pass_context
def mode_start(ctx: click.Context, mode_name: str, scene_id: str) -> None:
    role = require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    normalized_mode = slugify(mode_name)
    normalized_scene = slugify(scene_id)
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
                    "Continue character creation instead: use `glass done --summary <what remains> --state <relationship files still needed> --rolls none --next default`.",
                    "Each listed player must create a non-empty `players/<id>/public/relationships.md`; after all are present, the final DM ratification turn may end the mode.",
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
    commit(paths, state, ctx, "mode.end", {}, result)


def _character_creation_mode_end_failures() -> list[str]:
    campaign_root = active_campaign_root()
    players_root = campaign_root / "players"
    if not players_root.exists():
        return []
    failures: list[str] = []
    for player_dir in sorted(path for path in players_root.iterdir() if path.is_dir()):
        player_id = player_dir.name
        path = player_dir / "public" / "relationships.md"
        try:
            has_text = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            failures.append(
                f"{player_id}: missing players/{player_id}/public/relationships.md"
            )
            continue
        except PermissionError as exc:
            failures.append(
                f"{player_id}: cannot read players/{player_id}/public/relationships.md: "
                f"{exc.strerror or exc}"
            )
            continue
        except OSError:
            failures.append(
                f"{player_id}: cannot read players/{player_id}/public/relationships.md"
            )
            continue
        if not has_text:
            failures.append(
                f"{player_id}: empty players/{player_id}/public/relationships.md"
            )
    return failures


@mode.command("current")
@click.pass_context
def mode_current(ctx: click.Context) -> None:
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    current = current_mode_record(state)
    result = {
        "current_mode": current["mode"] if current else None,
        "current_scene": current["scene_id"] if current else None,
        "mode_stack": state["mode_stack"],
    }
    append_audit(paths, state, ctx, "mode.current", {}, result)
    emit(result)
