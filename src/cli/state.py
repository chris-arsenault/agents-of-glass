"""Runtime state IO + audit + events.

One runtime state record per campaign. When Postgres is configured it is the
canonical store and no `state.json` runtime cache is written. Without
Postgres, the CLI falls back to a local `state.json` for tests and standalone
development. Layout under campaigns/<id>/:

  state.json          — file fallback only when Postgres is not configured
  transcript.md       — derived public transcript export
  audit.jsonl         — append-only command audit log
  scene-framing.md    — current scene framing (rewritten on scene start)
  table/              — current public short-term table state
  dm/turns/<NNNN>/    — DM's per-turn artifacts (in.md, out.md, stdout, stderr)
  players/<id>/turns/<NNNN>/ — that player's per-turn artifacts

There is no `session` concept. The campaign id is the only identifier;
the campaign workspace is the runtime root. There is no central
`turns/<NNNN>/` directory — turn artifacts always live inside the
specific agent's directory under the campaign workspace.

Schema (v5):

  schema_version:       5
  campaign:             text — same id as the campaign workspace dirname
  status:               'active' | 'wrapped'
  created_at, updated_at, wrapped_at, summary
  turn_counter:         int (global, increments across modes)
  mode_stack:           list[ModeFrame]
  pending_events:       list[{event_id, actor, ts, summary}]
  note_intake:          list — DM intake queue
  entities:             dict — graph mirror cache
  threads:              dict — DM thread tracker
  turns:                list — structured turn rows from Postgres or file fallback
  next_speakers:        list[{agent, rapid_prompt?}] — handoff queue
  action_order:         dict | None — persistent initiative order for action scenes
  scene_trackers:       dict — scene-local generic counters/clocks
  scene_closing_turns:  int | None — closing-down countdown (in agent commits)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import click

from . import db as _db
from .config import Paths
from .config import load_config
from .errors import GlassError
from .ids import new_id, now_iso
from .role import current_role
from .yaml_io import emit, make_jsonable


# --- runtime paths (all rooted at campaigns/<id>/) ---


def campaign_runtime_dir(paths: Paths, campaign_id: str) -> Path:
    return paths.campaigns / campaign_id


def state_path(paths: Paths, campaign_id: str) -> Path:
    return campaign_runtime_dir(paths, campaign_id) / "state.json"


def audit_path(paths: Paths, campaign_id: str) -> Path:
    return campaign_runtime_dir(paths, campaign_id) / "audit.jsonl"


def transcript_path(paths: Paths, campaign_id: str) -> Path:
    return campaign_runtime_dir(paths, campaign_id) / "transcript.md"


def scene_framing_path(paths: Paths, campaign_id: str) -> Path:
    return campaign_runtime_dir(paths, campaign_id) / "scene-framing.md"


def agent_turns_dir(
    paths: Paths,
    campaign_id: str,
    *,
    role_kind: str,
    agent_id: str,
) -> Path:
    """Directory containing this agent's per-turn artifact subdirectories.

    DM    -> campaigns/<id>/dm/turns/
    player -> campaigns/<id>/players/<player>/turns/
    """
    root = campaign_runtime_dir(paths, campaign_id)
    if role_kind == "dm":
        return root / "dm" / "turns"
    return root / "players" / agent_id / "turns"


def agent_turn_dir(
    paths: Paths,
    campaign_id: str,
    *,
    role_kind: str,
    agent_id: str,
    turn_number: int,
) -> Path:
    """A specific per-turn artifact directory.

    Contains in.md (TURN_START), out.md (TURN), stdout.txt, stderr.txt.
    """
    return agent_turns_dir(
        paths, campaign_id, role_kind=role_kind, agent_id=agent_id
    ) / f"{turn_number:04d}"


# --- state load / save / shape ---


def default_state(campaign_id: str) -> dict[str, Any]:
    ts = now_iso()
    return {
        "schema_version": 5,
        "campaign": campaign_id,
        "status": "active",
        "created_at": ts,
        "updated_at": ts,
        "wrapped_at": None,
        "summary": "",
        "turn_counter": 0,
        "mode_stack": [],
        "pending_events": [],
        "note_intake": [],
        "entities": {},
        "threads": {},
        "turns": [],
        "next_speakers": [],
        "action_order": None,
        "scene_trackers": {},
        "scene_closing_turns": None,
    }


def normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    # Migrate v3 (nested session{}) to v4 (flat) on load.
    if "session" in state and isinstance(state["session"], dict):
        legacy = state.pop("session")
        state.setdefault("campaign", legacy.get("campaign") or legacy.get("id", ""))
        state.setdefault("status", legacy.get("status", "active"))
        state.setdefault("created_at", legacy.get("created_at"))
        state.setdefault("updated_at", legacy.get("updated_at"))
        state.setdefault("wrapped_at", legacy.get("wrapped_at"))
        state.setdefault("summary", legacy.get("summary", ""))
        state.setdefault("turn_counter", legacy.get("turn_counter", 0))

    state.setdefault("schema_version", 5)
    state.setdefault("status", "active")
    state.setdefault("turn_counter", len(state.get("turns", [])))
    state.setdefault("mode_stack", [])
    state.setdefault("pending_events", [])
    state.setdefault("note_intake", [])
    state.setdefault("entities", {})
    state.setdefault("threads", {})
    state.setdefault("turns", [])
    state.setdefault("next_speakers", [])
    state.setdefault("action_order", None)
    state.setdefault("scene_trackers", {})
    state.setdefault("scene_closing_turns", None)

    legacy_next = state.pop("next_speaker", None)
    if isinstance(legacy_next, str) and legacy_next:
        state["next_speakers"].append({"agent": legacy_next})

    for legacy in (
        "characters", "dice_events", "mechanical_events",
        "uncommitted_event_ids", "messages",
    ):
        state.pop(legacy, None)
    return state


def load_state(paths: Paths, campaign_id: str) -> dict[str, Any]:
    path = state_path(paths, campaign_id)
    if _postgres_runtime_enabled():
        state = _load_state_from_postgres(campaign_id)
        if state is not None:
            return normalize_state(state)
        raise GlassError(f"no runtime state for campaign {campaign_id!r} in Postgres")
    if not path.exists():
        raise GlassError(f"no state for campaign {campaign_id!r} at {path}")
    return normalize_state(json.loads(path.read_text(encoding="utf-8")))


def state_exists(paths: Paths, campaign_id: str) -> bool:
    if _postgres_runtime_enabled():
        return _load_state_from_postgres(campaign_id) is not None
    return state_path(paths, campaign_id).exists()


def save_state(paths: Paths, state: dict[str, Any]) -> None:
    state = normalize_state(state)
    state["updated_at"] = now_iso()
    if _postgres_runtime_enabled():
        _save_state_to_postgres(state)
        path = state_path(paths, state["campaign"])
        if path.exists():
            path.unlink()
        return
    campaign_id = state["campaign"]
    directory = campaign_runtime_dir(paths, campaign_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = state_path(paths, campaign_id)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _postgres_runtime_enabled() -> bool:
    return _db.postgres_configured(load_config())


def _load_state_from_postgres(campaign_id: str) -> dict[str, Any] | None:
    config = load_config()
    pg_config = _db.load_pg_config(config)
    try:
        with _db.connect(pg_config) as conn:
            return _db.runtime_state_get(conn, campaign_id)
    except GlassError:
        raise
    except Exception as exc:
        raise GlassError(
            "postgres runtime state load failed "
            f"({pg_config.describe()}): {exc}. Run `glass db migrate`."
        ) from exc


def _save_state_to_postgres(state: dict[str, Any]) -> None:
    config = load_config()
    pg_config = _db.load_pg_config(config)
    try:
        with _db.connect(pg_config) as conn:
            _db.runtime_state_upsert(conn, state)
    except GlassError:
        raise
    except Exception as exc:
        raise GlassError(
            "postgres runtime state save failed "
            f"({pg_config.describe()}): {exc}. Run `glass db migrate`."
        ) from exc


# --- audit + commit + events ---


def append_audit(
    paths: Paths,
    state: dict[str, Any],
    ctx: click.Context,
    event: str,
    params: dict[str, Any],
    result: dict[str, Any],
) -> None:
    campaign_id = state["campaign"]
    role = current_role()
    record = {
        "audit_id": new_id("audit"),
        "ts": now_iso(),
        "campaign": campaign_id,
        "role": role.raw or "operator",
        "actor": role.actor,
        "command": ctx.command_path,
        "event": event,
        "params": make_jsonable(params),
        "result": make_jsonable(result),
    }
    path = audit_path(paths, campaign_id)
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
        "campaign": state["campaign"],
        "status": state["status"],
        "created_at": state["created_at"],
        "updated_at": state["updated_at"],
        "wrapped_at": state.get("wrapped_at"),
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
