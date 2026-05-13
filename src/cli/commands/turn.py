"""Turn commands."""

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
from .. import embeddings as _embeddings
from .. import workspace as _workspace
from ..campaign import (
    active_campaign_id,
    active_campaign_root,
    lookup_player_character_id,
    pg_connection,
    resolve_active_campaign_workspace,
)
from ..config import REPO_ROOT, Paths, get_paths
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
from ..scene_beats import (
    ACTIVE_PLAY_TURN_KINDS,
    BEAT_MAX_AGE,
    BEAT_WARNING_AGE,
    beat_check_required_for_turn,
    scene_contract_failures,
    scene_contract_snapshot,
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


_TURN_END_NEXT_CHOICES = ("default", "dm", "tev", "sumi", "renno", "kit")
_TURN_END_SCENE_STATUS_CHOICES = (
    "active",
    "closing",
    "ending",
    "ended",
    "blocked",
)
_TURN_END_TURN_TYPE_CHOICES = ("act", "answer", "support", "pass")
_ACTIVE_PLAY_MODE_NAMES = {"scene-play", "action", "combat", "chase", "social-pressure"}
PASS_GUIDANCE_COMPLETED_BEATS = 8
_TURN_END_NEXT_SET = set(_TURN_END_NEXT_CHOICES)
_TURN_END_SCENE_STATUS_SET = set(_TURN_END_SCENE_STATUS_CHOICES)
_TURN_END_TURN_TYPE_SET = set(_TURN_END_TURN_TYPE_CHOICES)
_TURN_AUDIT_RECALL_EVENTS = {
    "beat.check",
    "clock.list",
    "clock.show",
    "msg.read",
    "scene.tracker.list",
    "search.semantic",
    "search.text",
    "summary.show",
    "table.current",
    "table.show",
    "turns.feed",
    "turns.find",
}
_TURN_AUDIT_RECALL_PREFIXES = ("entity.",)
_TURN_AUDIT_STATE_UPDATE_EVENTS = {
    "beat.close",
    "beat.convert",
    "beat.start",
    "clock.archive",
    "clock.resolve",
    "clock.set",
    "clock.tick",
    "lore.import",
    "lore.new",
    "lore.upsert",
    "msg.send",
    "note.propose",
    "note.ratify",
    "note.reject",
    "note.write",
    "quest.beat",
    "scene.clock.declare",
    "scene.pressure",
    "scene.tracker.set",
    "scene.tracker.tick",
    "summary.append",
    "summary.write",
    "table.append",
    "table.use",
    "table.write",
}
_TURN_AUDIT_STATE_UPDATE_PREFIXES = ("character.",)


@click.group()
def turn() -> None:
    """Turn lifecycle commands."""


@turn.command("begin")
@click.option("--turn-id", required=True)
@click.option("--actor", required=True)
@click.option("--role", "turn_role", required=True)
@click.option("--mode", "mode_name", required=True)
@click.option("--scene", "scene_id", required=True)
@click.option("--character", "character_id", default="")
@click.option("--kind", "turn_kind", required=True)
@click.option("--turn-type-required/--no-turn-type-required", default=False)
@click.option(
    "--allow-player-scene-close/--disallow-player-scene-close",
    default=False,
)
@click.pass_context
def turn_begin(
    ctx: click.Context,
    turn_id: str,
    actor: str,
    turn_role: str,
    mode_name: str,
    scene_id: str,
    character_id: str,
    turn_kind: str,
    turn_type_required: bool,
    allow_player_scene_close: bool,
) -> None:
    """Stage canonical active-turn context in Postgres before agent execution."""
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    turn_id_text = _required_text(turn_id, "--turn-id")
    actor_text = _required_text(actor, "--actor")
    role_text = _required_text(turn_role, "--role")
    mode_text = _required_text(mode_name, "--mode")
    scene_text = _required_text(scene_id, "--scene")
    kind_text = _required_text(turn_kind, "--kind")
    turn_number = _turn_number_from_turn_id(turn_id_text, campaign_id=campaign_id)

    state["active_turn_id"] = turn_id_text
    state["active_turn_number"] = turn_number
    state["active_turn_actor"] = actor_text
    state["active_turn_role"] = role_text
    state["active_turn_mode"] = mode_text
    state["active_turn_scene_id"] = scene_text
    state["active_turn_character_id"] = character_id.strip() or None
    state["active_turn_kind"] = kind_text
    state["active_turn_turn_type_required"] = bool(turn_type_required)
    state["active_turn_allow_player_scene_close"] = bool(allow_player_scene_close)
    state["active_turn_beat_checked_at"] = None
    state["active_turn_audit_ran_at"] = None
    _clear_staged_closeout(state)

    result = {
        "campaign_id": campaign_id,
        "turn_id": turn_id_text,
        "turn_number": turn_number,
        "actor": actor_text,
        "role": role_text,
        "mode": mode_text,
        "scene_id": scene_text,
        "character_id": state["active_turn_character_id"],
        "kind": kind_text,
        "turn_type_required": bool(turn_type_required),
        "allow_player_scene_close": bool(allow_player_scene_close),
    }
    commit(
        paths,
        state,
        ctx,
        "turn.begin",
        command_params(
            turn_id=turn_id_text,
            actor=actor_text,
            role=role_text,
            mode=mode_text,
            scene=scene_text,
            character=state["active_turn_character_id"],
            kind=kind_text,
            turn_type_required=bool(turn_type_required),
            allow_player_scene_close=bool(allow_player_scene_close),
        ),
        result,
    )


@turn.command("append")
@click.argument("markdown_file")
@click.option("--speaker")
@click.option("--role", "turn_role", type=click.Choice(["dm", "player", "operator"]))
@click.option("--mode", "mode_name")
@click.option("--scene", "scene_id")
@click.option("--character", "character_id")
@click.option("--end-file", "end_file")
@click.pass_context
def turn_append(
    ctx: click.Context,
    markdown_file: str,
    speaker: str | None,
    turn_role: str | None,
    mode_name: str | None,
    scene_id: str | None,
    character_id: str | None,
    end_file: str | None,
) -> None:
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    source = Path(markdown_file).expanduser()
    if not source.is_absolute():
        source = Path.cwd() / source
    if not source.exists():
        raise GlassError(
            agent_instruction(
                f"turn prose file does not exist: {markdown_file}",
                "Write the public turn prose file first, then let the orchestrator append it.",
                "During a normal agent turn, finish with `glass turn end ...` and exit; do not call `glass turn append` manually.",
            )
        )
    body = source.read_text(encoding="utf-8").strip()
    turn_context = _require_active_turn_context(state)
    turn_end = _require_valid_staged_closeout(state)
    role = current_role()
    speaker_id = str(turn_context.get("actor") or actor_for_turn(role, speaker))
    resolved_role = str(turn_context.get("role") or role_label_for_turn(role, turn_role))
    resolved_mode = str(turn_context.get("mode") or mode_name or "none")
    resolved_scene = str(turn_context.get("scene_id") or scene_id or "none")
    staged_character_id = turn_context.get("character_id")
    character_id = (
        str(staged_character_id)
        if isinstance(staged_character_id, str) and staged_character_id.strip()
        else character_id
    )
    if speaker and speaker != speaker_id:
        raise GlassError(
            agent_instruction(
                f"turn append speaker {speaker!r} does not match active turn actor {speaker_id!r}",
                "Use the actor recorded by `glass turn begin`, or rerun the turn lifecycle from the orchestrator.",
            )
        )
    if turn_role and turn_role != resolved_role:
        raise GlassError(
            agent_instruction(
                f"turn append role {turn_role!r} does not match active turn role {resolved_role!r}",
                "Use the role recorded by `glass turn begin`, or rerun the turn lifecycle from the orchestrator.",
            )
        )
    if mode_name and mode_name != resolved_mode:
        raise GlassError(
            agent_instruction(
                f"turn append mode {mode_name!r} does not match active turn mode {resolved_mode!r}",
                "Use the mode recorded by `glass turn begin`, or rerun the turn lifecycle from the orchestrator.",
            )
        )
    if scene_id and scene_id != resolved_scene:
        raise GlassError(
            agent_instruction(
                f"turn append scene {scene_id!r} does not match active turn scene {resolved_scene!r}",
                "Use the scene recorded by `glass turn begin`, or rerun the turn lifecycle from the orchestrator.",
            )
        )
    export_info = _turn_export_info(resolved_scene)
    arc_id = export_info.get("arc_id")
    scene_type = export_info.get("scene_type") or resolved_mode
    turn_id = _active_turn_number(turn_context)
    state["turn_counter"] = max(int(state.get("turn_counter", 0)), turn_id)

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
    ts = now_iso()
    turn_number_in_scene = _fallback_turn_number_in_scene(
        state, scene_id=resolved_scene
    )

    record = {
        "turn_id": turn_id,
        "campaign_id": state["campaign"],
        "session_id": state["campaign"],
        "scene_id": resolved_scene,
        "mode": resolved_mode,
        "speaker": speaker_id,
        "role": resolved_role,
        "character_id": character_id,
        "source_path": str(source),
        "prose": body,
        "event_summaries": [event["summary"] for event in flushed],
        "events": flushed,
        "markdown": turn_markdown,
        "created_at": ts,
        "ts": ts,
        "arc_id": arc_id,
        "scene_type": scene_type,
        "turn_number_in_scene": turn_number_in_scene,
        "visibility": "public",
        **_turn_end_record_fields(turn_end),
    }
    search_title = (
        f"Turn {turn_id} - {speaker_id} "
        f"({resolved_mode}, {resolved_scene})"
    )
    search_body = _turn_search_body(body, turn_end)
    embedded = _embeddings.embed_text(
        _embeddings.embedding_text(title=search_title, body=search_body),
        kind="document",
    )
    with pg_connection() as conn:
        turn_number_in_scene = (
            _db.turn_count(
                conn,
                campaign_id=state["campaign"],
                scene=resolved_scene,
            )
            + 1
        )
        record = _db.turn_insert(
            conn,
            campaign_id=state["campaign"],
            turn_id=turn_id,
            session_id=state["campaign"],
            scene_id=resolved_scene,
            mode=resolved_mode,
            speaker=speaker_id,
            role=resolved_role,
            character_id=character_id,
            source_path=str(source),
            prose=body,
            event_summaries=[event["summary"] for event in flushed],
            events=flushed,
            markdown=turn_markdown,
            created_at=ts,
            arc_id=arc_id,
            scene_type=scene_type,
            turn_number_in_scene=turn_number_in_scene,
            visibility="public",
            **_turn_end_db_fields(turn_end),
        )
        _db.event_insert_many(
            conn,
            campaign_id=state["campaign"],
            scene_id=resolved_scene,
            turn_id=turn_id,
            events=flushed,
        )
        _db.search_chunk_upsert(
            conn,
            chunk_id=f"{state['campaign']}:turn:{turn_id}",
            campaign_id=state["campaign"],
            source_type="turn",
            source_id=str(turn_id),
            visibility="public",
            owner_actor=None,
            path=str(source),
            title=search_title,
            body=search_body,
            metadata={
                "turn_id": turn_id,
                "speaker": speaker_id,
                "role": resolved_role,
                "mode": resolved_mode,
                "scene_id": resolved_scene,
                "arc_id": arc_id,
                "turn_type": record.get("turn_type"),
            },
            embedding=embedded.vectors[0],
            embedding_model=embedded.model,
            embedding_provider=embedded.provider,
        )
        beat_advance = _advance_scene_beats_after_append(
            conn,
            state=state,
            turn_context=turn_context,
            turn_end=turn_end,
        )
        conn.commit()

    # Derived compatibility export. The structured row above is the canonical
    # communication surface for queries and the future viewer UI.
    root_transcript = transcript_path(paths, state["campaign"])
    root_transcript.parent.mkdir(parents=True, exist_ok=True)
    with root_transcript.open("a", encoding="utf-8") as handle:
        handle.write(turn_markdown)
    scene_transcript_path = export_info.get("scene_transcript_path")
    if isinstance(scene_transcript_path, Path):
        with scene_transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(turn_markdown)

    next_speaker = str(turn_end.get("next") or "default")
    if next_speaker != "default":
        state["next_speakers"].append({"agent": next_speaker, "source": "turn.append"})
        queue_event(state, speaker_id, f"turn end handoff -> {next_speaker}")
    _clear_active_turn_state(state)
    state["turns"].append(record)
    result = {
        "turn": {key: value for key, value in record.items() if key != "markdown"},
        "events_flushed": flushed,
        "beat_advance": beat_advance,
        "transcript_export_path": display_path(root_transcript),
        "scene_transcript_export_path": (
            display_path(scene_transcript_path)
            if isinstance(scene_transcript_path, Path)
            else None
        ),
    }
    commit(
        paths,
        state,
        ctx,
        "turn.append",
        command_params(
            markdown_file=markdown_file,
            speaker=speaker_id,
            end_file=end_file,
            turn_id=turn_context.get("turn_id"),
        ),
        result,
    )


@turn.command("audit")
@click.pass_context
def turn_audit(ctx: click.Context) -> None:
    """Audit hard and soft turn requirements before closing the turn."""
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    turn_context = _require_active_turn_context(state)
    report = _turn_audit_report(paths=paths, state=state, turn_context=turn_context)
    state["active_turn_audit_ran_at"] = now_iso()
    result = {
        "turn_id": turn_context.get("turn_id"),
        "turn_number": turn_context.get("turn_number"),
        "actor": turn_context.get("actor"),
        "role": turn_context.get("role"),
        "kind": turn_context.get("kind"),
        "ready_for_turn_end": not report["hard_requirements"],
        "hard_requirements": report["hard_requirements"],
        "soft_considerations": report["soft_considerations"],
        "activity": report["activity"],
    }
    if report.get("scene_contract"):
        result["scene_contract"] = report["scene_contract"]
    commit(paths, state, ctx, "turn.audit", command_params(), result)


@turn.command("end")
@click.option("--summary", required=True, help="1-3 sentence compact continuity for the next actor.")
@click.option(
    "--next",
    "next_speaker",
    default="default",
    show_default=True,
    help="Next actor override. Use default to keep normal rotation/action order.",
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
@click.option("--open-question", "open_questions", multiple=True)
@click.option(
    "--scene-status",
    default="active",
    show_default=True,
)
@click.option("--turn-type", default="", help="Formal player turn type when applicable.")
@click.option("--position", default="", help="Position/leverage change, or unchanged.")
@click.option("--pressure", default="", help="Tracker/clock/HP/pressure change, or none.")
@click.option("--to", "end_file", default=None, hidden=True)
@click.pass_context
def turn_end(
    ctx: click.Context,
    summary: str,
    next_speaker: str,
    state_changes: tuple[str, ...],
    rolls: str,
    open_questions: tuple[str, ...],
    scene_status: str,
    turn_type: str,
    position: str,
    pressure: str,
    end_file: str | None,
) -> None:
    """Record the required end-of-turn closeout block.

    The orchestrator commits public prose separately with `glass turn append`.
    This command records the compact context block that future TURN_START files
    embed, and optionally queues a next-speaker override.
    """
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    turn_context = _require_active_turn_context(state)
    summary_text = _required_text(summary, "--summary")
    rolls_text = _required_text(rolls, "--rolls")
    state_items = [_required_text(item, "--state") for item in state_changes]
    open_items = [item.strip() for item in open_questions if item.strip()]
    turn_type_text = turn_type.strip()
    payload = {
        "summary": summary_text,
        "next": next_speaker.strip() or "default",
        "state": state_items,
        "rolls": rolls_text,
        "open_questions": open_items,
        "scene_status": scene_status.strip() or "active",
        "position": position.strip(),
        "pressure": pressure.strip(),
        "turn_type": turn_type_text or None,
        "campaign_id": campaign_id,
        "turn_id": turn_context.get("turn_id") or "",
        "actor": turn_context.get("actor"),
        "role": turn_context.get("role"),
        "mode": turn_context.get("mode"),
        "scene_id": turn_context.get("scene_id"),
        "created_at": now_iso(),
    }
    audit_report = _turn_audit_report(paths=paths, state=state, turn_context=turn_context)
    problems = _turn_end_validation_problems(
        turn_context,
        payload,
        state=state,
        audit_report=audit_report,
    )
    valid = not problems
    _stage_closeout(
        state,
        payload=payload,
        valid=valid,
        problems=problems,
    )
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
    }
    commit(
        paths,
        state,
        ctx,
        "turn.end",
        command_params(
            summary=summary_text,
            next=next_speaker,
            state=state_items,
            rolls=rolls_text,
            open_questions=open_items,
            scene_status=payload["scene_status"],
            turn_type=payload["turn_type"],
            position=position.strip(),
            pressure=pressure.strip(),
        ),
        result,
    )


def _require_active_turn_context(state: dict[str, Any]) -> dict[str, Any]:
    turn_id = str(state.get("active_turn_id") or "").strip()
    if not turn_id:
        raise GlassError(
            agent_instruction(
                "no active turn context is staged in Postgres",
                "Run this command from an orchestrated turn after the orchestrator has called `glass turn begin`.",
            )
        )
    return {
        "turn_id": turn_id,
        "turn_number": state.get("active_turn_number"),
        "actor": str(state.get("active_turn_actor") or "").strip(),
        "role": str(state.get("active_turn_role") or "").strip(),
        "mode": str(state.get("active_turn_mode") or "").strip(),
        "scene_id": str(state.get("active_turn_scene_id") or "").strip(),
        "character_id": str(state.get("active_turn_character_id") or "").strip() or None,
        "kind": str(state.get("active_turn_kind") or "").strip(),
        "turn_type_required": bool(state.get("active_turn_turn_type_required")),
        "allow_player_scene_close": bool(
            state.get("active_turn_allow_player_scene_close")
        ),
        "beat_checked_at": state.get("active_turn_beat_checked_at"),
        "audit_ran_at": state.get("active_turn_audit_ran_at"),
    }


def _active_turn_number(turn_context: dict[str, Any]) -> int:
    raw = turn_context.get("turn_number")
    if raw is not None:
        return int(raw)
    turn_id = str(turn_context.get("turn_id") or "")
    campaign_id = turn_id.split("-t", 1)[0] if "-t" in turn_id else ""
    return _turn_number_from_turn_id(turn_id, campaign_id=campaign_id)


def _require_valid_staged_closeout(state: dict[str, Any]) -> dict[str, Any]:
    summary = str(state.get("closeout_summary") or "").strip()
    if not summary:
        raise GlassError(
            agent_instruction(
                "no staged turn closeout exists for the active turn",
                "Run `glass turn end` after writing public prose, then retry the append.",
            )
        )
    valid = state.get("closeout_valid")
    problems = [str(item).strip() for item in state.get("closeout_problems", []) if str(item).strip()]
    if valid is not True:
        detail = "\n".join(f"- {problem}" for problem in problems) if problems else "- closeout is still invalid"
        raise GlassError(
            agent_instruction(
                "staged turn closeout is invalid",
                "Rerun `glass turn end` and fix the reported problems before the orchestrator appends the turn.",
            )
            + "\n\nProblems:\n"
            + detail
        )
    return {
        "summary": summary,
        "next": str(state.get("closeout_next_speaker") or "default").strip() or "default",
        "state": list(state.get("closeout_state_changes") or []),
        "rolls": str(state.get("closeout_rolls") or "").strip(),
        "open_questions": list(state.get("closeout_open_questions") or []),
        "scene_status": str(state.get("closeout_scene_status") or "active").strip() or "active",
        "position": str(state.get("closeout_position") or "").strip(),
        "pressure": str(state.get("closeout_pressure") or "").strip(),
        "turn_type": (
            str(state.get("closeout_turn_type") or "").strip() or None
        ),
        "campaign_id": str(state.get("campaign") or ""),
        "turn_id": str(state.get("active_turn_id") or ""),
        "actor": str(state.get("active_turn_actor") or ""),
        "role": str(state.get("active_turn_role") or ""),
        "mode": str(state.get("active_turn_mode") or ""),
        "scene_id": str(state.get("active_turn_scene_id") or ""),
        "created_at": str(state.get("closeout_updated_at") or now_iso()),
        "valid": True,
        "problems": [],
    }


def _turn_end_record_fields(turn_end: dict[str, Any]) -> dict[str, Any]:
    return {
        "turn_summary": str(turn_end.get("summary") or ""),
        "next_speaker": str(turn_end.get("next") or "default"),
        "scene_status": str(turn_end.get("scene_status") or "active"),
        "state_changes": list(turn_end.get("state") or []),
        "rolls": str(turn_end.get("rolls") or ""),
        "turn_type": (
            str(turn_end.get("turn_type") or "").strip() or None
        ),
        "open_questions": list(turn_end.get("open_questions") or []),
        "position": str(turn_end.get("position") or ""),
        "pressure": str(turn_end.get("pressure") or ""),
        "turn_end": dict(turn_end),
    }


def _turn_end_db_fields(turn_end: dict[str, Any]) -> dict[str, Any]:
    return _turn_end_record_fields(turn_end)


def _turn_search_body(body: str, turn_end: dict[str, Any]) -> str:
    parts = [body]
    summary = str(turn_end.get("summary") or "").strip()
    if summary:
        parts.append(summary)
    for key in ("state", "rolls", "turn_type", "open_questions", "position", "pressure"):
        value = turn_end.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value if str(item).strip())
        elif value:
            parts.append(str(value))
    return "\n\n".join(part for part in parts if part)


def _required_text(value: str, label: str) -> str:
    text = value.strip()
    if not text:
        raise GlassError(
            agent_instruction(
                f"{label} cannot be empty",
                "Provide a real value for every required `glass turn end` field.",
                "Use `--rolls none` when no roll happened and `--state \"no state change\"` only when nothing durable changed.",
            )
        )
    return text


def _turn_end_target_path(*, end_file: str | None) -> Path | None:
    raw = end_file or os.environ.get("AOG_TURN_CLOSEOUT")
    if raw:
        path = Path(raw).expanduser()
        return path if path.is_absolute() else Path.cwd() / path
    return None


def _turn_number_from_turn_id(turn_id: str, *, campaign_id: str) -> int:
    prefix = f"{campaign_id}-t"
    if not turn_id.startswith(prefix):
        raise GlassError(
            agent_instruction(
                f"turn id {turn_id!r} does not match active campaign {campaign_id!r}",
                "Use the orchestrator-generated turn id, for example `campaign-t0001`.",
            )
        )
    suffix = turn_id[len(prefix):]
    if not suffix.isdigit():
        raise GlassError(
            agent_instruction(
                f"turn id {turn_id!r} is not in `<campaign>-tNNNN` format",
                "Use the orchestrator-generated turn id, for example `campaign-t0001`.",
            )
        )
    return int(suffix)


def _clear_staged_closeout(state: dict[str, Any]) -> None:
    state["closeout_summary"] = None
    state["closeout_next_speaker"] = None
    state["closeout_scene_status"] = None
    state["closeout_state_changes"] = []
    state["closeout_rolls"] = None
    state["closeout_open_questions"] = []
    state["closeout_position"] = None
    state["closeout_pressure"] = None
    state["closeout_turn_type"] = None
    state["closeout_valid"] = None
    state["closeout_problems"] = []
    state["closeout_updated_at"] = None


def _clear_active_turn_state(state: dict[str, Any]) -> None:
    state["active_turn_id"] = None
    state["active_turn_number"] = None
    state["active_turn_actor"] = None
    state["active_turn_role"] = None
    state["active_turn_mode"] = None
    state["active_turn_scene_id"] = None
    state["active_turn_character_id"] = None
    state["active_turn_kind"] = None
    state["active_turn_turn_type_required"] = False
    state["active_turn_allow_player_scene_close"] = False
    state["active_turn_beat_checked_at"] = None
    state["active_turn_audit_ran_at"] = None
    _clear_staged_closeout(state)


def _stage_closeout(
    state: dict[str, Any],
    *,
    payload: dict[str, Any],
    valid: bool,
    problems: list[str],
) -> None:
    state["closeout_summary"] = str(payload.get("summary") or "").strip() or None
    state["closeout_next_speaker"] = str(payload.get("next") or "default").strip() or "default"
    state["closeout_scene_status"] = str(payload.get("scene_status") or "active").strip() or "active"
    state["closeout_state_changes"] = list(payload.get("state") or [])
    state["closeout_rolls"] = str(payload.get("rolls") or "").strip() or None
    state["closeout_open_questions"] = list(payload.get("open_questions") or [])
    state["closeout_position"] = str(payload.get("position") or "").strip() or None
    state["closeout_pressure"] = str(payload.get("pressure") or "").strip() or None
    turn_type = str(payload.get("turn_type") or "").strip()
    state["closeout_turn_type"] = turn_type or None
    state["closeout_valid"] = bool(valid)
    state["closeout_problems"] = list(problems)
    state["closeout_updated_at"] = now_iso()


def _turn_audit_records(
    paths: Paths,
    *,
    campaign_id: str,
    turn_id: str,
    actor: str,
) -> list[dict[str, Any]]:
    path = audit_path(paths, campaign_id)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    records: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(raw, dict):
            continue
        records.append(raw)
    begin_index: int | None = None
    for idx, record in enumerate(records):
        if str(record.get("event") or "") != "turn.begin":
            continue
        params = record.get("params")
        result = record.get("result")
        record_turn_id = ""
        if isinstance(params, dict):
            record_turn_id = str(params.get("turn_id") or "")
        if not record_turn_id and isinstance(result, dict):
            record_turn_id = str(result.get("turn_id") or "")
        if record_turn_id == turn_id:
            begin_index = idx
    if begin_index is None:
        return []
    scoped = records[begin_index + 1:]
    return [
        record
        for record in scoped
        if str(record.get("actor") or "") == actor
    ]


def _turn_audit_activity(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "commands_run": 0,
        "beat_checks": 0,
        "messages_sent": 0,
        "recall_actions": 0,
        "state_updates": 0,
    }
    for record in records:
        event = str(record.get("event") or "").strip()
        if not event:
            continue
        counts["commands_run"] += 1
        if event == "beat.check":
            counts["beat_checks"] += 1
        if event == "msg.send":
            counts["messages_sent"] += 1
        if event in _TURN_AUDIT_RECALL_EVENTS or event.startswith(_TURN_AUDIT_RECALL_PREFIXES):
            counts["recall_actions"] += 1
        if event in _TURN_AUDIT_STATE_UPDATE_EVENTS or event.startswith(_TURN_AUDIT_STATE_UPDATE_PREFIXES):
            counts["state_updates"] += 1
    return counts


def _scene_contract_target_for_audit(
    state: dict[str, Any],
    turn_context: dict[str, Any],
) -> dict[str, str] | None:
    if beat_check_required_for_turn(turn_context):
        scene_id = str(turn_context.get("scene_id") or "").strip()
        if not scene_id or scene_id == "none":
            return {"scene_id": "", "mode": str(turn_context.get("mode") or "").strip()}
        return {
            "scene_id": scene_id,
            "mode": str(turn_context.get("mode") or "").strip(),
        }
    role = str(turn_context.get("role") or "").strip()
    mode_name = str(turn_context.get("mode") or "").strip()
    if role != "dm" or mode_name not in {"prelude", "scene-prep"}:
        return None
    current = current_mode_record(state)
    if not current:
        return None
    current_mode = str(current.get("mode") or "").strip()
    current_scene = str(current.get("scene_id") or "").strip()
    if current_mode not in _ACTIVE_PLAY_MODE_NAMES:
        return None
    if not current_scene or current_scene == "none":
        return {"scene_id": "", "mode": current_mode}
    return {"scene_id": current_scene, "mode": current_mode}


def _scene_contract_gap_is_continuation(snapshot: dict[str, Any]) -> bool:
    completed = int(snapshot.get("completed_beats", 0) or 0)
    recent = snapshot.get("recent_beats") or []
    return completed > 0 or bool(recent)


def _scene_contract_gap_message(
    *,
    failure: str,
    completed_beats: int,
    role_kind: str,
) -> str:
    if failure == "this active scene has 0 scene clocks":
        if completed_beats > PASS_GUIDANCE_COMPLETED_BEATS:
            return (
                f"This scene has 0 active scene clocks after {completed_beats} "
                "completed beats. Treat this as a closure gap: end with "
                "`--next dm` so the DM can close or transition, unless the DM "
                "deliberately opens a genuinely new scene question."
            )
        return (
            "This scene has 0 active scene clocks. If the scene continues, "
            "the DM should declare the next one with `glass scene clock declare ...`."
        )
    if role_kind == "player":
        if completed_beats > PASS_GUIDANCE_COMPLETED_BEATS:
            return (
                f"This scene has 0 active beats after {completed_beats} "
                "completed beats. Do not open a replacement beat by default. "
                "If your character has no decisive blockbuster-scale "
                "contribution, use a short visible pass and `--next dm` so "
                "the DM can close or transition."
            )
        return (
            "This scene has 0 active beats. If the scene continues, end with "
            "`--next dm` so the DM can start the next beat or close the scene; "
            "do not open a replacement beat from a player turn unless the DM "
            "explicitly instructed it."
        )
    if completed_beats > PASS_GUIDANCE_COMPLETED_BEATS:
        return (
            f"This scene has 0 active beats after {completed_beats} completed "
            "beats. Prefer closing or transitioning; start another beat only "
            "for a genuinely new scene question."
        )
    return (
        "This scene has 0 active beats. If the scene continues, start the next "
        "beat with `glass beat start <beat-id> --clock <clock-id> --label ... "
        "--question ...`."
    )


def _completed_beat_pass_guidance(completed_beats: int, *, role_kind: str) -> str | None:
    if completed_beats <= PASS_GUIDANCE_COMPLETED_BEATS:
        return None
    if role_kind == "player":
        return (
            f"This scene already has {completed_beats} completed beats. If you "
            "do not have a decisive blockbuster-scale contribution, use "
            "`--turn-type pass` with one visible cue and `--next dm` rather "
            "than adding procedure or opening another beat."
        )
    return (
        f"This scene already has {completed_beats} completed beats. Prefer "
        "closing or transitioning over another beat unless a genuinely new "
        "scene question belongs here."
    )


def _turn_audit_report(
    *,
    paths: Paths,
    state: dict[str, Any],
    turn_context: dict[str, Any],
) -> dict[str, Any]:
    actor = str(turn_context.get("actor") or "")
    turn_id = str(turn_context.get("turn_id") or "")
    records = _turn_audit_records(
        paths,
        campaign_id=str(state.get("campaign") or ""),
        turn_id=turn_id,
        actor=actor,
    )
    activity = _turn_audit_activity(records)
    hard_requirements: list[str] = []
    soft_considerations: list[str] = []
    scene_contract: dict[str, Any] | None = None

    contract_target = _scene_contract_target_for_audit(state, turn_context)
    if contract_target is not None:
        scene_id = str(contract_target.get("scene_id") or "").strip()
        if not scene_id or scene_id == "none":
            hard_requirements.append("No active scene is staged for beat tracking.")
        else:
            role = current_role()
            reference_turn = _active_turn_number(turn_context)
            with pg_connection() as conn:
                snapshot = scene_contract_snapshot(
                    conn,
                    campaign_id=str(state.get("campaign") or ""),
                    scene_id=scene_id,
                    role_kind=role.kind,
                    reference_turn_number=reference_turn,
                )
            scene_contract = {
                "scene_id": scene_id,
                "mode": str(contract_target.get("mode") or "").strip() or None,
                "scene_clocks": snapshot["clocks"],
                "active_beats": snapshot["active_beats"],
                "recent_beats": snapshot["recent_beats"],
                "completed_beats": snapshot["completed_beats"],
                "scene_note": snapshot["scene_note"],
            }
            if not state.get("active_turn_beat_checked_at"):
                hard_requirements.append("You MUST still run glass beat check.")
            continuation_gap = _scene_contract_gap_is_continuation(snapshot)
            completed_beats = int(snapshot.get("completed_beats", 0) or 0)
            for failure in scene_contract_failures(snapshot):
                if failure == "this active scene has 0 scene clocks":
                    if continuation_gap:
                        soft_considerations.append(
                            _scene_contract_gap_message(
                                failure=failure,
                                completed_beats=completed_beats,
                                role_kind=role.kind,
                            )
                        )
                    else:
                        hard_requirements.append(
                            "This active scene has 0 scene clocks. The DM MUST declare at least one with `glass scene clock declare ...`."
                        )
                elif failure == "this active scene has 0 active beats":
                    if continuation_gap:
                        soft_considerations.append(
                            _scene_contract_gap_message(
                                failure=failure,
                                completed_beats=completed_beats,
                                role_kind=role.kind,
                            )
                        )
                    else:
                        hard_requirements.append(
                            "This active scene has 0 active beats. Start one with `glass beat start <beat-id> --clock <clock-id> --label ... --question ...`."
                        )
                elif "more than" in failure:
                    hard_requirements.append(
                        "This active scene already exceeds the 3-beat cap. Close or convert an existing beat first."
                    )
                else:
                    hard_requirements.append(
                        f"{failure}. Resolve, convert, or end the scene before continuing active play."
                    )
            for beat in snapshot.get("expired_beats", []):
                hard_requirements.append(
                    f"Beat `{beat.get('beat_id')}` is already at {beat.get('age_text')}. Resolve or convert it before another non-pass turn."
                )
            pass_guidance = _completed_beat_pass_guidance(
                completed_beats,
                role_kind=role.kind,
            )
            if pass_guidance:
                soft_considerations.append(pass_guidance)

    if activity["messages_sent"] <= 0:
        soft_considerations.append(
            "You sent 0 messages this turn; consider sending something."
        )
    if activity["recall_actions"] <= 0:
        soft_considerations.append(
            "You ran 0 recall/search checks this turn; consider checking the available surfaces if you are uncertain."
        )
    if activity["state_updates"] <= 0:
        soft_considerations.append(
            "You recorded 0 durable state updates this turn; if the turn changed canon or table state, commit it before closing."
        )

    return {
        "activity": activity,
        "hard_requirements": hard_requirements,
        "soft_considerations": soft_considerations,
        "scene_contract": scene_contract,
    }


def _turn_end_validation_problems(
    turn_context: dict[str, Any],
    payload: dict[str, Any],
    *,
    state: dict[str, Any],
    audit_report: dict[str, Any],
) -> list[str]:
    problems: list[str] = []
    next_speaker = str(payload.get("next") or "default").strip() or "default"
    if next_speaker not in _TURN_END_NEXT_SET:
        problems.append(
            f"`--next {next_speaker}` is invalid; use one of: {', '.join(_TURN_END_NEXT_CHOICES)}."
        )
    scene_status = str(payload.get("scene_status") or "active").strip() or "active"
    if scene_status not in _TURN_END_SCENE_STATUS_SET:
        problems.append(
            f"`--scene-status {scene_status}` is invalid; use one of: {', '.join(_TURN_END_SCENE_STATUS_CHOICES)}."
        )
    turn_type = str(payload.get("turn_type") or "").strip()
    if turn_type and turn_type not in _TURN_END_TURN_TYPE_SET:
        problems.append(
            f"`--turn-type {turn_type}` is invalid; use one of: {', '.join(_TURN_END_TURN_TYPE_CHOICES)}."
        )
    if not state.get("active_turn_audit_ran_at"):
        problems.append("run `glass turn audit` before `glass turn end`.")
    if turn_context.get("turn_type_required") and not turn_type:
        problems.append(
            f"`--turn-type` is required for `{turn_context.get('kind') or 'this'}` player turns."
        )
    for requirement in audit_report.get("hard_requirements", []):
        if requirement == "You MUST still run glass beat check.":
            problems.append("You MUST still run glass beat check.")
        elif requirement.startswith("This active scene has 0 scene clocks"):
            problems.append(
                "the active scene has 0 scene clocks; the DM must declare one before active play can continue."
            )
        elif requirement.startswith("This active scene has 0 active beats"):
            problems.append(
                "the active scene has 0 active beats; start one before active play can continue."
            )
        elif "already exceeds" in requirement:
            problems.append(
                "the active scene already exceeds the 3-beat cap; close or convert an active beat first."
            )
        elif requirement.startswith("Beat `"):
            problems.append(requirement)
        elif requirement not in problems:
            problems.append(requirement)
    state_changes = [str(item).strip() for item in payload.get("state", []) if str(item).strip()]
    rolls = str(payload.get("rolls") or "").strip()
    if turn_type == "pass":
        if state_changes != ["no state change"]:
            problems.append(
                "`pass` requires exactly `--state \"no state change\"`."
            )
        if rolls.lower() != "none":
            problems.append("`pass` requires `--rolls none`.")
        if (
            str(turn_context.get("role") or "") == "player"
            and scene_status != "active"
            and not bool(turn_context.get("allow_player_scene_close"))
        ):
            problems.append(
                "`pass` must keep `--scene-status active` for this player turn."
            )
    elif beat_check_required_for_turn(turn_context):
        scene_contract = audit_report.get("scene_contract") or {}
        for beat in scene_contract.get("active_beats", []):
            age = int(beat.get("non_pass_turns", 0) or 0)
            if age >= BEAT_MAX_AGE:
                problems.append(
                    f"Beat `{beat.get('beat_id')}` is already at {age}/{BEAT_MAX_AGE}. Resolve or convert it before another non-pass turn."
                )
    deduped: list[str] = []
    seen: set[str] = set()
    for problem in problems:
        if problem in seen:
            continue
        deduped.append(problem)
        seen.add(problem)
    return deduped


def _turn_end_fix_suggestions(problems: list[str]) -> list[str]:
    fixes: list[str] = []
    seen: set[str] = set()
    for problem in problems:
        if "--turn-type" in problem:
            fix = "Rerun `glass turn end` with `--turn-type act|answer|support|pass`."
        elif "run `glass turn audit` before `glass turn end`" in problem:
            fix = "Run `glass turn audit`, address any hard requirements it prints, then rerun `glass turn end`."
        elif "You MUST still run glass beat check" in problem:
            fix = "Run `glass beat check`, then rerun `glass turn end`."
        elif "0 scene clocks" in problem:
            fix = "Have the DM declare a scene clock with `glass scene clock declare ...`, then rerun `glass beat check` and `glass turn end`."
        elif "0 active beats" in problem:
            fix = "Start a beat with `glass beat start <beat-id> --clock <clock-id> --label ... --question ...`, then rerun `glass beat check` and `glass turn end`."
        elif "3-beat cap" in problem:
            fix = "Close or convert an active beat, then rerun `glass beat check` and `glass turn end`."
        elif "Resolve or convert it before another non-pass turn" in problem:
            fix = "Resolve the beat with `glass beat close`, convert it with `glass beat convert`, or pass instead of taking another non-pass turn."
        elif "requires exactly `--state \"no state change\"`" in problem:
            fix = "Rerun with `--state \"no state change\"` and no other `--state` values."
        elif "`pass` requires `--rolls none`" in problem:
            fix = "Rerun with `--rolls none`."
        elif "`--scene-status" in problem or "must keep `--scene-status active`" in problem:
            fix = "Rerun with a valid `--scene-status`, usually `active`."
        elif "`--next" in problem:
            fix = "Rerun with `--next default|dm|tev|sumi|renno|kit`."
        else:
            fix = "Rerun `glass turn end` after correcting the reported field."
        if fix not in seen:
            fixes.append(fix)
            seen.add(fix)
    return fixes


def _write_turn_closeout_artifact(
    payload: dict[str, Any],
    *,
    valid: bool,
    problems: list[str],
    end_file: str | None,
) -> None:
    target = _turn_end_target_path(end_file=end_file)
    if target is None:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    artifact = dict(payload)
    artifact["valid"] = bool(valid)
    artifact["problems"] = list(problems)
    target.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _turn_export_info(scene_id: str) -> dict[str, Any]:
    try:
        workspace = resolve_active_campaign_workspace()
        current = _workspace.current_scene(workspace)
    except GlassError:
        return {}
    if not current or current.get("scene_id") != scene_id:
        return {}
    arc_id = current.get("arc_id")
    transcript: Path | None = None
    if arc_id:
        transcript = workspace.scene_dir(str(arc_id), scene_id) / "transcript.md"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        if not transcript.exists():
            transcript.write_text(f"# Scene: {scene_id}\n\n", encoding="utf-8")
    return {
        "arc_id": arc_id,
        "scene_type": current.get("scene_type"),
        "scene_transcript_path": transcript,
    }


def _advance_scene_beats_after_append(
    conn: "Any",
    *,
    state: dict[str, Any],
    turn_context: dict[str, Any],
    turn_end: dict[str, Any],
) -> dict[str, Any] | None:
    if not beat_check_required_for_turn(turn_context):
        return None
    scene_id = str(turn_context.get("scene_id") or "").strip()
    if not scene_id or scene_id == "none":
        return None
    turn_type = str(turn_end.get("turn_type") or "").strip()
    if turn_type == "pass":
        return {"skipped": "pass", "aged_beats": [], "warning_beats": [], "expired_beats": []}
    updated = _db.scene_beat_increment_active(
        conn,
        campaign_id=str(state.get("campaign") or ""),
        scene_id=scene_id,
        skip_created_turn_id=str(turn_context.get("turn_id") or "").strip() or None,
    )
    warning_beats: list[str] = []
    expired_beats: list[str] = []
    for beat in updated:
        age = int(beat.get("non_pass_turns", 0) or 0)
        beat_id = str(beat.get("beat_id") or "")
        if age == BEAT_WARNING_AGE:
            warning_beats.append(beat_id)
            queue_event(
                state,
                str(turn_context.get("actor") or ""),
                f"beat warning {beat.get('label')}: {age}/{BEAT_MAX_AGE}",
            )
        if age >= BEAT_MAX_AGE:
            expired_beats.append(beat_id)
            queue_event(
                state,
                str(turn_context.get("actor") or ""),
                f"beat expiry {beat.get('label')}: {age}/{BEAT_MAX_AGE}; resolve or convert before another non-pass turn",
            )
    return {
        "skipped": None,
        "aged_beats": [str(beat.get("beat_id") or "") for beat in updated],
        "warning_beats": warning_beats,
        "expired_beats": expired_beats,
    }


def _fallback_turn_number_in_scene(state: dict[str, Any], *, scene_id: str) -> int:
    return (
        sum(1 for turn in state.get("turns", []) if turn.get("scene_id") == scene_id)
        + 1
    )


_HANDOFF_AGENT_IDS = ("dm", "tev", "sumi", "renno", "kit")
_PLAYER_AGENT_IDS = ("tev", "sumi", "renno", "kit")
_ACTION_PARTICIPANT_IDS = ("dm", "tev", "sumi", "renno", "kit")


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
            agent_instruction(
                f"unknown handoff target {agent_id!r}",
                f"Use one of: {', '.join(_HANDOFF_AGENT_IDS)}.",
                "Use `glass turn end --next default` for normal rotation, or `--next dm` only when the DM specifically needs the next turn.",
            )
        )
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    state["next_speakers"].append({"agent": agent_id})
    queue_event(state, role.actor, f"handoff -> {agent_id}")
    result = {"queue": list(state["next_speakers"])}
    commit(
        paths, state, ctx, "turn.handoff",
        command_params(agent_id=agent_id), result,
    )


@turn.command("initiative")
@click.option(
    "--participants",
    "participants_csv",
    default=None,
    help="Comma-separated agent ids. The DM is always included in the roll.",
)
@click.option("--label", default="initiative", show_default=True)
@click.pass_context
def turn_initiative(
    ctx: click.Context, participants_csv: str | None, label: str
) -> None:
    """DM-only: roll and persist action-scene turn order.

    Use this after the DM's opening layout for quickfire action scenes.
    The DM is always a participant, so their next turn after the
    opening layout can land wherever the initiative roll puts it.
    """
    role = require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    current = current_mode_record(state)
    if not current or current.get("mode") == "none":
        raise GlassError(
            agent_instruction(
                "initiative requires an active mode and scene",
                "The DM should start action play first with `glass mode start action <scene-id>` or the scene's action mode.",
                "Then run `glass turn initiative` once, from the DM turn that opens action play.",
            )
        )

    if participants_csv:
        participants = [
            entry.strip() for entry in participants_csv.split(",") if entry.strip()
        ]
    else:
        participants = list(_ACTION_PARTICIPANT_IDS)
    if "dm" not in participants:
        participants.append("dm")
    if not participants:
        raise GlassError(
            agent_instruction(
                "initiative needs at least one participant",
                f"Pass `--participants` with one or more of: {', '.join(_ACTION_PARTICIPANT_IDS)}.",
            )
        )

    seen: set[str] = set()
    for participant in participants:
        if participant not in _ACTION_PARTICIPANT_IDS:
            raise GlassError(
                agent_instruction(
                    f"unknown initiative participant {participant!r}",
                    f"Use only these agent ids: {', '.join(_ACTION_PARTICIPANT_IDS)}.",
                )
            )
        if participant in seen:
            raise GlassError(
                agent_instruction(
                    f"duplicate initiative participant {participant!r}",
                    "List each participant at most once in `--participants`.",
                )
            )
        seen.add(participant)

    rng = random.SystemRandom()
    rolls: list[dict[str, Any]] = []
    for participant in participants:
        dice = [rng.randint(1, 6), rng.randint(1, 6)]
        rolls.append(
            {
                "agent": participant,
                "dice": dice,
                "total": sum(dice),
                "tiebreaker": rng.randint(1, 1_000_000),
            }
        )
    ordered_rolls = sorted(
        rolls,
        key=lambda item: (int(item["total"]), int(item["tiebreaker"])),
        reverse=True,
    )
    order = [str(item["agent"]) for item in ordered_rolls]
    public_rolls = [
        {
            "agent": item["agent"],
            "dice": item["dice"],
            "total": item["total"],
        }
        for item in ordered_rolls
    ]
    state["action_order"] = {
        "mode": current["mode"],
        "scene_id": current["scene_id"],
        "label": label,
        "round": 1,
        "cursor": 0,
        "order": order,
        "rolls": public_rolls,
        "created_at": now_iso(),
        "created_by": role.actor,
    }
    with pg_connection() as conn:
        persisted = _db.action_order_upsert(
            conn,
            campaign_id=campaign_id,
            mode=str(current["mode"]),
            scene_id=str(current["scene_id"]),
            label=label,
            order=order,
            rolls=public_rolls,
            actor=role.actor,
        )
    state["action_order"] = {
        key: persisted[key]
        for key in ("mode", "scene_id", "label", "round", "cursor", "order", "rolls")
    } | {"created_at": persisted["created_at"], "created_by": role.actor}

    order_summary = ", ".join(
        f"{item['agent']}({item['total']})" for item in public_rolls
    )
    queue_event(
        state,
        role.actor,
        f"{label} order @ {current['scene_id']}: {order_summary}",
    )
    result = {
        "action_order": state["action_order"],
    }
    commit(
        paths,
        state,
        ctx,
        "turn.initiative",
        command_params(participants=participants, label=label),
        result,
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
                agent_instruction(
                    f"unknown rapid-round player {player!r}",
                    f"Use one or more of: {', '.join(_PLAYER_AGENT_IDS)}.",
                )
            )
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    prompt = " ".join(prompt_parts).strip()
    if not prompt:
        raise GlassError(
            agent_instruction(
                "rapid-round prompt cannot be empty",
                "Call `glass turn rapid-round <short shared stimulus>` so each queued player sees what to react to.",
            )
        )
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


@turn.command("housekeeping-round")
@click.option(
    "--players",
    "players_csv",
    default=None,
    help="Comma-separated player ids. Defaults to tev,sumi,renno,kit.",
)
@click.option(
    "--previous-scene",
    default="",
    help="Scene that just closed. Used only for TURN_START context.",
)
@click.option(
    "--next-scene",
    default="",
    help="Scene being staged next. Used only for TURN_START context.",
)
@click.option(
    "--next",
    "next_actor",
    type=click.Choice(_TURN_END_NEXT_CHOICES),
    default="tev",
    show_default=True,
    help="Actor queued after housekeeping. Use default to leave rotation alone.",
)
@click.pass_context
def turn_housekeeping_round(
    ctx: click.Context,
    players_csv: str | None,
    previous_scene: str,
    next_scene: str,
    next_actor: str,
) -> None:
    """DM-only: queue one non-plot housekeeping turn for each player.

    Use this at a scene boundary after the DM has wrapped the old scene,
    staged the next scene, and started the next scene's play mode. The queued
    player turns are for notes, journals, sheet cleanup, and private requests;
    they must not introduce new in-fiction action or mid/long-term plot design.
    """
    require_dm()
    if players_csv:
        targets = [p.strip() for p in players_csv.split(",") if p.strip()]
    else:
        targets = list(_PLAYER_AGENT_IDS)
    seen: set[str] = set()
    for player in targets:
        if player not in _PLAYER_AGENT_IDS:
            raise GlassError(
                agent_instruction(
                    f"unknown housekeeping player {player!r}",
                    f"Use one or more of: {', '.join(_PLAYER_AGENT_IDS)}.",
                )
            )
        if player in seen:
            raise GlassError(
                agent_instruction(
                    f"duplicate housekeeping player {player!r}",
                    "List each player at most once in `--players`.",
                )
            )
        seen.add(player)

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    previous = previous_scene.strip()
    upcoming = next_scene.strip()

    for player in targets:
        state["next_speakers"].append(
            {
                "agent": player,
                "housekeeping": True,
                "previous_scene": previous,
                "next_scene": upcoming,
                "source": "turn.housekeeping-round",
            }
        )
    if next_actor != "default":
        state["next_speakers"].append(
            {
                "agent": next_actor,
                "after_housekeeping": True,
                "previous_scene": previous,
                "next_scene": upcoming,
                "source": "turn.housekeeping-round",
            }
        )
    queue_event(
        state,
        role.actor,
        (
            f"housekeeping-round queued for {','.join(targets)}"
            f"; next scene actor: {next_actor}"
        ),
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
        "turn.housekeeping-round",
        command_params(
            players=targets,
            previous_scene=previous,
            next_scene=upcoming,
            next=next_actor,
        ),
        result,
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
            agent_instruction(
                f"unknown restart target {agent_id!r}",
                f"Use one of: {', '.join(_HANDOFF_AGENT_IDS)}.",
                "Use this only when the DM needs to reset the turn queue; otherwise leave normal rotation alone.",
            )
        )
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
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
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    previous = list(state.get("next_speakers", []))
    state["next_speakers"] = []
    result = {"cleared": previous}
    commit(paths, state, ctx, "turn.clear-handoff", {}, result)
