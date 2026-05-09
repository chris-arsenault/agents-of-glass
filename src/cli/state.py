"""Session state IO + audit + events.

Layout under sessions/<id>/:
  state.json       — persisted session JSON (this module owns it)
  audit.jsonl      — append-only command audit log
  transcript.md    — public transcript (managed by glass turn append)
  turns/<NNNN>/    — per-turn artifacts (managed by orchestrator)

Session JSON schema (v3):
  schema_version: 3
  session: {id, campaign, status, created_at, updated_at, wrapped_at,
            summary, turn_counter}
  mode_stack: list[ModeFrame]
  pending_events: list[{event_id, actor, ts, summary}] — flushed into
    next transcript turn as `> {summary}` lines
  note_intake: list — DM intake queue (propose/ratify)
  entities: dict — graph mirror cache (graph is canonical)
  threads: dict — DM thread tracker
  turns: list — turn metadata
  next_speakers: list[{agent, rapid_prompt?}] — handoff queue
  scene_closing_turns: int | None — closing-down countdown
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import click

from .config import Paths
from .errors import GlassError
from .ids import new_id, now_iso
from .role import current_role
from .yaml_io import emit, make_jsonable


# --- session paths ---


def active_session_file(paths: Paths) -> Path:
    return paths.sessions / ".active-session"


def write_active_session(paths: Paths, session_id: str) -> None:
    paths.sessions.mkdir(parents=True, exist_ok=True)
    active_session_file(paths).write_text(f"{session_id}\n", encoding="utf-8")


def active_session_id(paths: Paths, required: bool = True) -> str | None:
    env_session = os.environ.get("GLASS_SESSION_ID")
    if env_session:
        return env_session
    active = active_session_file(paths)
    if active.exists():
        value = active.read_text(encoding="utf-8").strip()
        if value:
            return value
    if required:
        raise GlassError("no active session: set GLASS_SESSION_ID or run 'glass session new'")
    return None


def session_dir(paths: Paths, session_id: str) -> Path:
    return paths.sessions / session_id


def state_path(paths: Paths, session_id: str) -> Path:
    return session_dir(paths, session_id) / "state.json"


def audit_path(paths: Paths, session_id: str) -> Path:
    return session_dir(paths, session_id) / "audit.jsonl"


def transcript_path(paths: Paths, session_id: str) -> Path:
    return session_dir(paths, session_id) / "transcript.md"


# --- state load / save / shape ---


def default_state(session_id: str, campaign: str) -> dict[str, Any]:
    ts = now_iso()
    return {
        "schema_version": 3,
        "session": {
            "id": session_id,
            "campaign": campaign,
            "status": "active",
            "created_at": ts,
            "updated_at": ts,
            "wrapped_at": None,
            "summary": "",
            "turn_counter": 0,
        },
        "mode_stack": [],
        "pending_events": [],
        "note_intake": [],
        "entities": {},
        "threads": {},
        "turns": [],
        "next_speakers": [],
        "scene_closing_turns": None,
    }


def normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    state.setdefault("schema_version", 3)
    state.setdefault("mode_stack", [])
    state.setdefault("pending_events", [])
    state.setdefault("note_intake", [])
    state.setdefault("entities", {})
    state.setdefault("threads", {})
    state.setdefault("turns", [])
    state.setdefault("session", {})
    state.setdefault("next_speakers", [])
    state.setdefault("scene_closing_turns", None)
    legacy_next = state.pop("next_speaker", None)
    if isinstance(legacy_next, str) and legacy_next:
        state["next_speakers"].append({"agent": legacy_next})
    state["session"].setdefault("turn_counter", len(state["turns"]))
    state["session"].setdefault("status", "active")
    for legacy in (
        "characters", "dice_events", "mechanical_events",
        "uncommitted_event_ids", "messages",
    ):
        state.pop(legacy, None)
    return state


def load_state(paths: Paths, session_id: str | None = None) -> dict[str, Any]:
    session = session_id or active_session_id(paths)
    path = state_path(paths, session)
    if not path.exists():
        raise GlassError(f"unknown session: {session}")
    return normalize_state(json.loads(path.read_text(encoding="utf-8")))


def save_state(paths: Paths, state: dict[str, Any]) -> None:
    state["session"]["updated_at"] = now_iso()
    session = state["session"]["id"]
    directory = session_dir(paths, session)
    directory.mkdir(parents=True, exist_ok=True)
    path = state_path(paths, session)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


# --- audit + commit + events ---


def append_audit(
    paths: Paths,
    state: dict[str, Any],
    ctx: click.Context,
    event: str,
    params: dict[str, Any],
    result: dict[str, Any],
) -> None:
    session_id = state["session"]["id"]
    role = current_role()
    record = {
        "audit_id": new_id("audit"),
        "ts": now_iso(),
        "session_id": session_id,
        "role": role.raw or "operator",
        "actor": role.actor,
        "command": ctx.command_path,
        "event": event,
        "params": make_jsonable(params),
        "result": make_jsonable(result),
    }
    path = audit_path(paths, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def commit(
    paths: Paths,
    state: dict[str, Any],
    ctx: click.Context,
    event: str,
    params: dict[str, Any],
    result: dict[str, Any],
    *,
    save: bool = True,
) -> None:
    if save:
        save_state(paths, state)
    append_audit(paths, state, ctx, event, params, result)
    emit(result)


def queue_event(state: dict[str, Any], actor: str, summary: str) -> dict[str, Any]:
    """Queue a one-line summary to be inlined into the next turn's transcript."""
    event = {
        "event_id": new_id("event"),
        "actor": actor,
        "ts": now_iso(),
        "summary": summary,
    }
    state["pending_events"].append(event)
    return event


def inline_event_lines(events: list[dict[str, Any]]) -> list[str]:
    if not events:
        return []
    return [f"> {event['summary']}" for event in events]


def current_mode_record(state: dict[str, Any]) -> dict[str, Any] | None:
    stack = state.get("mode_stack", [])
    return stack[-1] if stack else None


def state_summary(state: dict[str, Any]) -> dict[str, Any]:
    current = current_mode_record(state)
    return {
        "session_id": state["session"]["id"],
        "campaign": state["session"]["campaign"],
        "status": state["session"]["status"],
        "created_at": state["session"]["created_at"],
        "updated_at": state["session"]["updated_at"],
        "wrapped_at": state["session"].get("wrapped_at"),
        "current_mode": current["mode"] if current else None,
        "current_scene": current["scene_id"] if current else None,
        "mode_stack": state.get("mode_stack", []),
        "turn_count": len(state.get("turns", [])),
        "pending_events": len(state.get("pending_events", [])),
        "pending_notes": [
            item["intake_id"]
            for item in state.get("note_intake", [])
            if item.get("status") == "pending"
        ],
    }
