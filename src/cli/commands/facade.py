"""Small agent-facing command facade.

The lower-level command groups remain available for explicit methodology steps
and operator work. These commands are the default surface agents should reach
for during normal turns.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from .. import db as _db
from ..campaign import (
    active_campaign_id,
    pg_connection,
    resolve_active_campaign_workspace,
)
from ..errors import GlassError, agent_instruction
from ..ids import now_iso
from ..messages import message_visible_to, render_message_identities
from ..paths_resolve import display_path
from ..role import current_role, require_dm
from ..scene_beats import (
    beat_check_required_for_turn,
    scene_contract_failures,
    scene_contract_snapshot,
)
from ..config import get_paths
from ..state import append_audit, commit, current_mode_record, load_state, queue_event
from ..yaml_io import command_params, emit
from .search import _run_search
from .turn import (
    _HANDOFF_AGENT_IDS,
    _PLAYER_AGENT_IDS,
    _TURN_END_NEXT_CHOICES,
    _TURN_END_SCENE_STATUS_CHOICES,
    _TURN_END_TURN_TYPE_CHOICES,
    _active_turn_number,
    _require_active_turn_context,
    _stage_closeout,
    _turn_audit_report,
    _turn_end_fix_suggestions,
    _turn_end_validation_problems,
    _write_turn_closeout_artifact,
)


@click.command("check")
@click.option(
    "--no-mark",
    is_flag=True,
    help="Do not mark unread messages as read.",
)
@click.pass_context
def check(ctx: click.Context, no_mark: bool) -> None:
    """One turn-start check: messages, scene contract, table, clocks, upkeep."""
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    turn_context = _optional_active_turn_context(state)
    scene_id = _active_scene_id(state, turn_context)
    reference_turn = (
        _active_turn_number(turn_context)
        if turn_context is not None
        else int(state.get("turn_counter", 0) or 0) + 1
    )

    with pg_connection() as conn:
        message_rows = _db.message_list(
            conn,
            campaign_id=campaign_id,
            agent_id=role.actor,
            only_unread=True,
            limit=500,
        )
        visible_messages = [
            message for message in message_rows if message_visible_to(message, role)
        ]
        if not no_mark and visible_messages:
            _db.message_mark_read(
                conn,
                agent_id=role.actor,
                message_ids=[message["id"] for message in visible_messages],
            )
        durable_clocks = _db.clock_list(
            conn,
            campaign_id=campaign_id,
            visibility="public" if role.kind == "player" else None,
        )
        characters = _db.character_list(conn, campaign_id)
        snapshot = (
            scene_contract_snapshot(
                conn,
                campaign_id=campaign_id,
                scene_id=scene_id,
                role_kind=role.kind,
                reference_turn_number=reference_turn,
            )
            if scene_id
            else None
        )

    hard_requirements: list[str] = []
    required = beat_check_required_for_turn(turn_context)
    marked_beat_check = False
    scene_contract: dict[str, Any] | None = None
    if snapshot is not None:
        failures = scene_contract_failures(snapshot)
        continuation_failures = {
            "this active scene has 0 scene clocks",
            "this active scene has 0 active beats",
        }
        continuation_gap = (
            bool(snapshot.get("recent_beats")) or int(snapshot.get("completed_beats", 0) or 0) > 0
        )
        continuation_only = continuation_gap and all(
            failure in continuation_failures for failure in failures
        )
        if required and failures and not continuation_only:
            hard_requirements.extend(failures)
        elif required and turn_context is not None:
            state["active_turn_beat_checked_at"] = now_iso()
            marked_beat_check = True
        scene_contract = {
            "scene_id": scene_id,
            "required": required,
            "clock_count": snapshot["active_clock_count"],
            "hidden_clock_count": snapshot["hidden_clock_count"],
            "scene_clocks": snapshot["clocks"],
            "clock_groups": snapshot["clock_groups"],
            "clock_warnings": snapshot["clock_warnings"],
            "active_beats": snapshot["active_beats"],
            "beat_warnings": snapshot["beat_warnings"],
            "recent_beats": snapshot["recent_beats"],
            "completed_beats": snapshot["completed_beats"],
            "scene_note": snapshot["scene_note"],
            "warning_beats": [beat["beat_id"] for beat in snapshot["warning_beats"]],
            "expired_beats": [beat["beat_id"] for beat in snapshot["expired_beats"]],
            "continuation_gap": continuation_gap,
        }
    elif required:
        hard_requirements.append("no active scene is staged for beat tracking")

    result = {
        "campaign_id": campaign_id,
        "actor": role.actor,
        "role": role.kind,
        "turn": turn_context,
        "mode": current_mode_record(state),
        "unread_messages": [
            render_message_identities(paths, state, message) for message in visible_messages
        ],
        "unread_message_count": len(visible_messages),
        "messages_marked_read": bool(visible_messages and not no_mark),
        "table": _table_overview(),
        "durable_clocks": durable_clocks,
        "scene_contract": scene_contract,
        "pending_level_ups": _pending_level_ups(characters),
        "beat_check_marked": marked_beat_check,
        "ready_for_done": not hard_requirements,
        "hard_requirements": hard_requirements,
    }
    commit(paths, state, ctx, "check", command_params(no_mark=no_mark), result)


@click.command("done")
@click.option(
    "--summary",
    required=True,
    help="1-3 sentence compact continuity for the next actor.",
)
@click.option(
    "--state",
    "state_changes",
    multiple=True,
    required=True,
    help="Durable state/table/lore/message update, or 'no state change'. Repeat as needed.",
)
@click.option(
    "--rolls",
    required=True,
    help="Rolls/checks/pressure commands used, or 'none'.",
)
@click.option(
    "--turn-type",
    "--type",
    "turn_type",
    type=click.Choice(_TURN_END_TURN_TYPE_CHOICES),
    default=None,
    help="Formal player turn type: act, answer, support, or pass.",
)
@click.option(
    "--next",
    "next_speaker",
    type=click.Choice(_TURN_END_NEXT_CHOICES),
    default="default",
    show_default=True,
)
@click.option(
    "--scene-status",
    type=click.Choice(_TURN_END_SCENE_STATUS_CHOICES),
    default="active",
    show_default=True,
)
@click.option("--open-question", "open_questions", multiple=True)
@click.option("--position", default="", help="Position/leverage change, or unchanged.")
@click.option("--pressure", default="", help="Tracker/clock/HP/pressure change, or none.")
@click.option("--to", "end_file", default=None, hidden=True)
@click.pass_context
def done(
    ctx: click.Context,
    summary: str,
    state_changes: tuple[str, ...],
    rolls: str,
    turn_type: str | None,
    next_speaker: str,
    scene_status: str,
    open_questions: tuple[str, ...],
    position: str,
    pressure: str,
    end_file: str | None,
) -> None:
    """Run turn audit and stage the closeout in one command."""
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    turn_context = _require_active_turn_context(state)
    summary_text = _required_text(summary, "--summary")
    rolls_text = _required_text(rolls, "--rolls")
    state_items = [_required_text(item, "--state") for item in state_changes]
    open_items = [item.strip() for item in open_questions if item.strip()]
    payload = {
        "summary": summary_text,
        "next": next_speaker.strip() or "default",
        "state": state_items,
        "rolls": rolls_text,
        "open_questions": open_items,
        "scene_status": scene_status.strip() or "active",
        "position": position.strip(),
        "pressure": pressure.strip(),
        "turn_type": (turn_type or "").strip() or None,
        "campaign_id": campaign_id,
        "turn_id": turn_context.get("turn_id") or "",
        "actor": turn_context.get("actor"),
        "role": turn_context.get("role"),
        "mode": turn_context.get("mode"),
        "scene_id": turn_context.get("scene_id"),
        "created_at": now_iso(),
    }
    state["active_turn_audit_ran_at"] = now_iso()
    audit_report = _turn_audit_report(paths=paths, state=state, turn_context=turn_context)
    problems = _turn_end_validation_problems(
        turn_context,
        payload,
        state=state,
        audit_report=audit_report,
    )
    valid = not problems
    _stage_closeout(state, payload=payload, valid=valid, problems=problems)
    _write_turn_closeout_artifact(payload, valid=valid, problems=problems, end_file=end_file)

    result = {
        "turn_id": turn_context.get("turn_id"),
        "turn_number": turn_context.get("turn_number"),
        "actor": turn_context.get("actor"),
        "role": turn_context.get("role"),
        "kind": turn_context.get("kind"),
        "summary": summary_text,
        "next": payload["next"],
        "state": state_items,
        "rolls": rolls_text,
        "turn_type": payload["turn_type"],
        "open_questions": open_items,
        "scene_status": payload["scene_status"],
        "valid": valid,
        "problems": problems,
        "fixes": _turn_end_fix_suggestions(problems),
        "audit": {
            "hard_requirements": audit_report["hard_requirements"],
            "soft_considerations": audit_report["soft_considerations"],
            "activity": audit_report["activity"],
        },
    }
    if audit_report.get("scene_contract"):
        result["audit"]["scene_contract"] = audit_report["scene_contract"]
    if (audit_report.get("roll_consequence") or {}).get("requires_consequence"):
        result["audit"]["roll_consequence"] = audit_report["roll_consequence"]
    commit(
        paths,
        state,
        ctx,
        "done",
        command_params(
            summary=summary_text,
            state=state_items,
            rolls=rolls_text,
            turn_type=payload["turn_type"],
            next=payload["next"],
            scene_status=payload["scene_status"],
            open_questions=open_items,
            position=position.strip(),
            pressure=pressure.strip(),
        ),
        result,
    )


@click.command("find")
@click.argument("query", required=False, default="")
@click.option(
    "--mode",
    "find_mode",
    type=click.Choice(["text", "semantic", "turns"]),
    default="text",
    show_default=True,
)
@click.option("--type", "source_type", default=None, help="Search source type filter.")
@click.option("--scene", default=None, help="Turn-search scene filter.")
@click.option("--speaker", default=None, help="Turn-search speaker filter.")
@click.option("--limit", type=int, default=10, show_default=True)
@click.pass_context
def find(
    ctx: click.Context,
    query: str,
    find_mode: str,
    source_type: str | None,
    scene: str | None,
    speaker: str | None,
    limit: int,
) -> None:
    """Search with one memorable command."""
    if find_mode in {"text", "semantic"}:
        if not query.strip():
            raise GlassError(
                agent_instruction(
                    "search query cannot be empty",
                    'Run `glass find "<query>"`, or use `--mode turns --scene <scene-id>` for a filtered turn list.',
                )
            )
        _run_search(
            ctx,
            query,
            source_type=source_type,
            limit=limit,
            semantic=find_mode == "semantic",
        )
        return

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    with pg_connection() as conn:
        records = _db.turn_list(
            conn,
            campaign_id=campaign_id,
            scene=scene,
            speaker=speaker,
            text=query.strip() or None,
            limit=limit,
            latest=True,
        )
    result = {
        "campaign_id": campaign_id,
        "mode": "turns",
        "query": query.strip() or None,
        "scene": scene,
        "speaker": speaker,
        "turns": records,
        "count": len(records),
    }
    append_audit(
        paths,
        state,
        ctx,
        "find",
        command_params(query=query, mode=find_mode, scene=scene, speaker=speaker, limit=limit),
        result,
    )
    emit(result)


@click.command(
    "next",
    context_settings={"ignore_unknown_options": True},
)
@click.argument(
    "action",
    type=click.Choice(
        ["handoff", "rapid-round", "housekeeping-round", "restart-order", "clear", "clear-handoff"]
    ),
)
@click.argument("args", nargs=-1)
@click.option(
    "--players",
    "players_csv",
    default=None,
    help="Comma-separated player ids for rapid/housekeeping rounds.",
)
@click.option("--previous-scene", default="")
@click.option("--next-scene", default="")
@click.option(
    "--next",
    "next_actor",
    type=click.Choice(_TURN_END_NEXT_CHOICES),
    default="default",
    show_default=True,
    help="Actor queued after housekeeping.",
)
@click.pass_context
def next_command(
    ctx: click.Context,
    action: str,
    args: tuple[str, ...],
    players_csv: str | None,
    previous_scene: str,
    next_scene: str,
    next_actor: str,
) -> None:
    """Queue the next actor(s): handoff, rounds, restart, or clear."""
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()

    if action == "handoff":
        agent_id = _single_arg(args, "handoff target")
        if agent_id not in _HANDOFF_AGENT_IDS:
            raise GlassError(_unknown_agent(agent_id, _HANDOFF_AGENT_IDS, "handoff target"))
        state["next_speakers"].append({"agent": agent_id, "source": "next.handoff"})
        queue_event(state, role.actor, f"handoff -> {agent_id}")
        result = {"queue": list(state["next_speakers"])}
        commit(paths, state, ctx, "next.handoff", command_params(agent_id=agent_id), result)
        return

    require_dm()
    if action == "rapid-round":
        prompt = " ".join(args).strip()
        if not prompt:
            raise GlassError(
                agent_instruction(
                    "rapid-round prompt cannot be empty",
                    'Run `glass next rapid-round "<short shared stimulus>"`.',
                )
            )
        targets = _players_from_csv(players_csv)
        for player in targets:
            state["next_speakers"].append({"agent": player, "rapid_prompt": prompt})
        queue_event(
            state,
            role.actor,
            f"rapid-round queued for {','.join(targets)}: {prompt[:60]}",
        )
        result = {"queue": list(state["next_speakers"]), "prompt": prompt, "players": targets}
        commit(
            paths,
            state,
            ctx,
            "next.rapid-round",
            command_params(prompt=prompt, players=targets),
            result,
        )
        return

    if action == "housekeeping-round":
        targets = _players_from_csv(players_csv)
        previous = previous_scene.strip()
        upcoming = next_scene.strip()
        for player in targets:
            state["next_speakers"].append(
                {
                    "agent": player,
                    "housekeeping": True,
                    "previous_scene": previous,
                    "next_scene": upcoming,
                    "source": "next.housekeeping-round",
                }
            )
        if next_actor != "default":
            state["next_speakers"].append(
                {
                    "agent": next_actor,
                    "after_housekeeping": True,
                    "previous_scene": previous,
                    "next_scene": upcoming,
                    "source": "next.housekeeping-round",
                }
            )
        queue_event(
            state,
            role.actor,
            f"housekeeping-round queued for {','.join(targets)}; next scene actor: {next_actor}",
        )
        result = {
            "queue": list(state["next_speakers"]),
            "players": targets,
            "previous_scene": previous,
            "next_scene": upcoming,
            "next": next_actor,
        }
        commit(
            paths,
            state,
            ctx,
            "next.housekeeping-round",
            command_params(
                players=targets, previous_scene=previous, next_scene=upcoming, next=next_actor
            ),
            result,
        )
        return

    if action == "restart-order":
        agent_id = _single_arg(args, "restart target")
        if agent_id not in _HANDOFF_AGENT_IDS:
            raise GlassError(_unknown_agent(agent_id, _HANDOFF_AGENT_IDS, "restart target"))
        previous = list(state.get("next_speakers", []))
        state["next_speakers"] = [{"agent": agent_id, "source": "next.restart-order"}]
        queue_event(state, role.actor, f"restart turn order -> {agent_id}")
        result = {"cleared": previous, "queue": list(state["next_speakers"])}
        commit(paths, state, ctx, "next.restart-order", command_params(agent_id=agent_id), result)
        return

    previous = list(state.get("next_speakers", []))
    state["next_speakers"] = []
    result = {"cleared": previous}
    commit(paths, state, ctx, "next.clear", command_params(action=action), result)


def _optional_active_turn_context(state: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return _require_active_turn_context(state)
    except GlassError:
        return None


def _active_scene_id(
    state: dict[str, Any],
    turn_context: dict[str, Any] | None,
) -> str:
    if turn_context is not None:
        scene = str(turn_context.get("scene_id") or "").strip()
        if scene and scene != "none":
            return scene
    current = current_mode_record(state)
    if not current:
        return ""
    scene = str(current.get("scene_id") or "").strip()
    return "" if scene == "none" else scene


def _table_overview() -> dict[str, Any]:
    try:
        workspace = resolve_active_campaign_workspace()
    except GlassError:
        return {"available": False, "files": []}
    root = workspace.table_dir
    return {
        "available": root.exists(),
        "path": display_path(root),
        "files": _markdown_files(root),
    }


def _markdown_files(root: Path) -> list[str]:
    if not root.exists():
        return []
    files = [display_path(path) for path in root.rglob("*.md") if path.is_file()]
    return sorted(files)


def _pending_level_ups(characters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pending: list[dict[str, Any]] = []
    for character in characters:
        xp = int(character.get("xp", 0) or 0)
        level = int(character.get("level", 1) or 1)
        target_level = (xp // 10) + 1
        pending_count = max(target_level - level, 0)
        if pending_count <= 0:
            continue
        pending.append(
            {
                "character_id": character.get("character_id"),
                "name": character.get("name"),
                "level": level,
                "xp": xp,
                "target_level": target_level,
                "pending_count": pending_count,
            }
        )
    return pending


def _required_text(value: str, label: str) -> str:
    text = value.strip()
    if not text:
        raise GlassError(
            agent_instruction(
                f"{label} cannot be empty",
                "Provide a real value, or use `none` / `no state change` where appropriate.",
            )
        )
    return text


def _single_arg(args: tuple[str, ...], label: str) -> str:
    if len(args) != 1 or not args[0].strip():
        raise GlassError(
            agent_instruction(
                f"{label} is required",
                "Provide exactly one agent id.",
            )
        )
    return args[0].strip()


def _players_from_csv(players_csv: str | None) -> list[str]:
    if players_csv:
        targets = [item.strip() for item in players_csv.split(",") if item.strip()]
    else:
        targets = list(_PLAYER_AGENT_IDS)
    seen: set[str] = set()
    for player in targets:
        if player not in _PLAYER_AGENT_IDS:
            raise GlassError(_unknown_agent(player, _PLAYER_AGENT_IDS, "player"))
        if player in seen:
            raise GlassError(
                agent_instruction(
                    f"duplicate player {player!r}",
                    "List each player at most once.",
                )
            )
        seen.add(player)
    return targets


def _unknown_agent(agent_id: str, choices: tuple[str, ...], label: str) -> str:
    return agent_instruction(
        f"unknown {label} {agent_id!r}",
        f"Use one of: {', '.join(choices)}.",
    )
