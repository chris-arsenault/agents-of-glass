"""Runtime state IO + audit + events.

One runtime state record per campaign. Postgres is the required canonical
store; `state.json` is not a supported runtime cache. Layout under
campaigns/<id>/:

  state.json          — stale legacy path only; removed on runtime saves
  transcript.md       — derived public transcript export
  audit.jsonl         — append-only command audit log
  scene-framing.md    — current scene framing (rewritten on scene start)
  table/              — current player-agent-visible short-term table state
  dm/turns/<NNNN>/    — DM's per-turn artifacts (TURN_START.md, TURN.md, closeout, stdout, stderr)
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
  turns:                list — structured turn rows mirrored from Postgres
  next_speakers:        list[{agent, rapid_prompt?, housekeeping?, scene_transition?}] — handoff queue
  action_order:         dict | None — persistent initiative order for action scenes
  scene_trackers:       dict — scene-local generic counters/clocks
  scene_closing_turns:  int | None — closing-down countdown (in agent commits)
"""

from __future__ import annotations

import json
import os
import hashlib
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import click

from . import db as _db
from .config import Paths
from .config import load_config
from .errors import GlassError, agent_instruction
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

    Contains TURN_START.md, TURN.md, turn-closeout.json, stdout, and stderr.
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
        "active_turn_id": None,
        "active_turn_number": None,
        "active_turn_actor": None,
        "active_turn_role": None,
        "active_turn_mode": None,
        "active_turn_scene_id": None,
        "active_turn_character_id": None,
        "active_turn_kind": None,
        "active_turn_turn_type_required": False,
        "active_turn_allow_player_scene_close": False,
        "active_turn_beat_checked_at": None,
        "active_turn_audit_ran_at": None,
        "closeout_summary": None,
        "closeout_next_speaker": None,
        "closeout_scene_status": None,
        "closeout_state_changes": [],
        "closeout_rolls": None,
        "closeout_open_questions": [],
        "closeout_position": None,
        "closeout_pressure": None,
        "closeout_turn_type": None,
        "closeout_valid": None,
        "closeout_problems": [],
        "closeout_updated_at": None,
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
    state.setdefault("active_turn_id", None)
    state.setdefault("active_turn_number", None)
    state.setdefault("active_turn_actor", None)
    state.setdefault("active_turn_role", None)
    state.setdefault("active_turn_mode", None)
    state.setdefault("active_turn_scene_id", None)
    state.setdefault("active_turn_character_id", None)
    state.setdefault("active_turn_kind", None)
    state.setdefault("active_turn_turn_type_required", False)
    state.setdefault("active_turn_allow_player_scene_close", False)
    state.setdefault("active_turn_beat_checked_at", None)
    state.setdefault("active_turn_audit_ran_at", None)
    state.setdefault("closeout_summary", None)
    state.setdefault("closeout_next_speaker", None)
    state.setdefault("closeout_scene_status", None)
    state.setdefault("closeout_state_changes", [])
    state.setdefault("closeout_rolls", None)
    state.setdefault("closeout_open_questions", [])
    state.setdefault("closeout_position", None)
    state.setdefault("closeout_pressure", None)
    state.setdefault("closeout_turn_type", None)
    state.setdefault("closeout_valid", None)
    state.setdefault("closeout_problems", [])
    state.setdefault("closeout_updated_at", None)

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
    _require_postgres_runtime()
    state = _load_state_from_postgres(campaign_id)
    if state is not None:
        return normalize_state(state)
    raise GlassError(
        agent_instruction(
            f"no runtime state for campaign {campaign_id!r} in Postgres",
            "Start or initialize the campaign runtime before running turn commands.",
            f"Use `aog campaign run {campaign_id}` for normal play, or run the campaign setup/migration commands for maintenance.",
        )
    )


def state_exists(paths: Paths, campaign_id: str) -> bool:
    _require_postgres_runtime()
    return _load_state_from_postgres(campaign_id) is not None


def initialize_state(paths: Paths, state: dict[str, Any]) -> None:
    """Create or replace the initial runtime-state row for a campaign.

    Normal command commits must use update_state_fields via commit(); this
    whole-row write is only for runtime provisioning/reset.
    """
    state = normalize_state(state)
    state["updated_at"] = now_iso()
    _require_postgres_runtime()
    _save_state_to_postgres(state)
    _remove_stale_runtime_json(paths, state["campaign"])


def update_state_fields(
    paths: Paths,
    campaign_id: str,
    fields: dict[str, Any],
    *,
    state: dict[str, Any] | None = None,
) -> None:
    """Write selected runtime-state fields directly to Postgres.

    When a caller already holds a state dict, keep it in sync so subsequent
    result rendering and audit/projection code sees the same values.
    """
    if state is not None:
        state.update(fields)
    _require_postgres_runtime()
    _update_state_fields_in_postgres(campaign_id, fields)
    _remove_stale_runtime_json(paths, campaign_id)


def _postgres_runtime_enabled() -> bool:
    return _db.postgres_configured(load_config())


def _require_postgres_runtime() -> None:
    if not _postgres_runtime_enabled():
        raise GlassError(
            agent_instruction(
                "Postgres runtime is required",
                "Configure `[postgres]` in `agents-of-glass.toml` or set libpq environment variables.",
                "Then run `glass db migrate` before using runtime-backed CLI commands.",
            )
        )


def _remove_stale_runtime_json(paths: Paths, campaign_id: str) -> None:
    for path in (
        state_path(paths, campaign_id),
        campaign_runtime_dir(paths, campaign_id) / "aog-state.json",
    ):
        if path.exists():
            path.unlink()


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
            agent_instruction(
                f"postgres runtime state load failed ({pg_config.describe()})",
                "Run `glass db migrate`, then retry the command.",
                f"Database detail: {exc}",
            )
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
            agent_instruction(
                f"postgres runtime state save failed ({pg_config.describe()})",
                "Run `glass db migrate`, then retry the command.",
                f"Database detail: {exc}",
            )
        ) from exc


def _update_state_fields_in_postgres(campaign_id: str, fields: dict[str, Any]) -> None:
    config = load_config()
    pg_config = _db.load_pg_config(config)
    try:
        with _db.connect(pg_config) as conn:
            _db.runtime_state_update_fields(conn, campaign_id, fields)
    except GlassError:
        raise
    except Exception as exc:
        raise GlassError(
            agent_instruction(
                f"postgres runtime state field update failed ({pg_config.describe()})",
                "Run `glass db migrate`, then retry the command.",
                f"Database detail: {exc}",
            )
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
    state_fields: Iterable[str] | None = None,
) -> None:
    if save:
        if state_fields is None:
            state_fields = _default_state_fields_for_event(event)
        if state_fields is None:
            raise GlassError(
                agent_instruction(
                    f"commit for {event!r} did not declare runtime state fields",
                    "Use explicit DB field updates instead of whole runtime-state saves.",
                    "Pass `state_fields=(...)` for the runtime fields this command changed, or `save=False` for read-only/audit-only commands.",
                )
            )
        update_state_fields(
            paths,
            state["campaign"],
            {field: state.get(field) for field in state_fields},
        )
    append_audit(paths, state, ctx, event, params, result)
    _refresh_projection_committed_paths(paths, state, result)
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


_ACTIVE_TURN_FIELDS = (
    "active_turn_id",
    "active_turn_number",
    "active_turn_actor",
    "active_turn_role",
    "active_turn_mode",
    "active_turn_scene_id",
    "active_turn_character_id",
    "active_turn_kind",
    "active_turn_turn_type_required",
    "active_turn_allow_player_scene_close",
    "active_turn_beat_checked_at",
    "active_turn_audit_ran_at",
)

_CLOSEOUT_FIELDS = (
    "closeout_summary",
    "closeout_next_speaker",
    "closeout_scene_status",
    "closeout_state_changes",
    "closeout_rolls",
    "closeout_open_questions",
    "closeout_position",
    "closeout_pressure",
    "closeout_turn_type",
    "closeout_valid",
    "closeout_problems",
    "closeout_updated_at",
)

_SCENE_POINTER_FIELDS = (
    "active_scene",
    "active_scene_arc",
    "active_scene_type",
)

_DEFAULT_EVENT_STATE_FIELDS: dict[str, tuple[str, ...]] = {
    "campaign.pull-note": ("pending_events", "entities"),
    "beat.check": ("active_turn_beat_checked_at",),
    "beat.start": ("pending_events",),
    "beat.close": ("pending_events",),
    "beat.convert": ("pending_events",),
    "msg.send": (),
    "msg.read": (),
    "roll": ("pending_events",),
    "arc.create": ("arcs", "active_arc", "pending_events"),
    "arc.activate": ("arcs", "active_arc", "pending_events"),
    "arc.close": ("closed_arcs", "active_arc", "pending_events"),
    "check": ("active_turn_beat_checked_at",),
    "done": ("active_turn_audit_ran_at", *_CLOSEOUT_FIELDS),
    "next.handoff": ("next_speakers", "pending_events"),
    "next.rapid-round": ("next_speakers", "pending_events"),
    "next.housekeeping-round": ("next_speakers", "pending_events"),
    "next.restart-order": ("next_speakers", "pending_events"),
    "next.clear": ("next_speakers",),
    "mode.start": ("mode_stack", "pending_events"),
    "mode.end": ("mode_stack", "action_order", "scene_trackers", "pending_events"),
    "scene.create": (*_SCENE_POINTER_FIELDS, "previous_table_snapshot", "pending_events"),
    "scene.end": (
        *_SCENE_POINTER_FIELDS,
        "scene_closing_turns",
        "action_order",
        "scene_trackers",
        "pending_events",
    ),
    "scene.transition": (
        *_SCENE_POINTER_FIELDS,
        "mode_stack",
        "scene_closing_turns",
        "action_order",
        "scene_trackers",
        "pending_events",
    ),
    "scene.closing-down": ("scene_closing_turns", "pending_events"),
    "scene.clock.declare": ("pending_events",),
    "scene.clock.tick": ("pending_events",),
    "scene.tracker.set": ("scene_trackers", "pending_events"),
    "scene.tracker.tick": ("scene_trackers", "pending_events"),
    "scene.pressure": ("pending_events",),
    "session.wrap": ("status", "wrapped_at", "summary"),
    "sync.apply": ("pending_events", "entities"),
    "note.write": ("entities",),
    "note.propose": ("note_intake",),
    "note.ratify": ("note_intake", "entities"),
    "note.reject": ("note_intake",),
    "thread.advance": ("threads",),
    "turn.begin": (*_ACTIVE_TURN_FIELDS, *_CLOSEOUT_FIELDS),
    "turn.append": (
        "turn_counter",
        "pending_events",
        "next_speakers",
        *_ACTIVE_TURN_FIELDS,
        *_CLOSEOUT_FIELDS,
    ),
    "turn.audit": ("active_turn_audit_ran_at",),
    "turn.end": (*_CLOSEOUT_FIELDS,),
    "turn.handoff": ("next_speakers", "pending_events"),
    "turn.initiative": ("action_order", "pending_events"),
    "turn.rapid-round": ("next_speakers", "pending_events"),
    "turn.housekeeping-round": ("next_speakers", "pending_events"),
    "turn.restart-order": ("next_speakers", "pending_events"),
    "turn.clear-handoff": ("next_speakers",),
    "quest.beat": ("pending_events",),
    "entity.upsert": ("entities",),
    "entity.claim": ("note_intake",),
    "entity.ratify-claim": ("note_intake",),
}

_DEFAULT_EVENT_FIELD_PREFIXES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("character.", ("pending_events",)),
    ("clock.", ("pending_events",)),
    ("table.", ("pending_events",)),
    ("summary.", ("pending_events", "entities")),
    ("lore.", ("entities", "pending_events")),
)


def _default_state_fields_for_event(event: str) -> tuple[str, ...] | None:
    fields = _DEFAULT_EVENT_STATE_FIELDS.get(event)
    if fields is not None:
        return fields
    for prefix, prefix_fields in _DEFAULT_EVENT_FIELD_PREFIXES:
        if event.startswith(prefix):
            return prefix_fields
    return None


def inline_event_lines(events: list[dict[str, Any]]) -> list[str]:
    if not events:
        return []
    return [f"> {event['summary']}" for event in events]


def current_mode_record(state: dict[str, Any]) -> dict[str, Any] | None:
    stack = state.get("mode_stack", [])
    return stack[-1] if stack else None


def _refresh_projection_committed_paths(
    paths: Paths,
    state: dict[str, Any],
    result: dict[str, Any],
) -> None:
    """Mirror committed canonical files back into a projected cwd.

    Agent-facing `glass` commands run in the actor projection but mutate the
    canonical campaign tree. When a command result names committed files, keep
    those paths in the projection and manifest aligned so the post-turn sync
    checker does not report files that were already committed.
    """

    projection_root = Path.cwd().resolve()
    manifest_path = projection_root / ".glass-projection-manifest.json"
    if not manifest_path.exists() or paths.campaigns is None:
        return

    campaign_id = str(state.get("campaign") or "")
    if not campaign_id:
        return
    campaign_root = campaign_runtime_dir(paths, campaign_id).resolve()
    if projection_root == campaign_root:
        return

    rels = _committed_result_paths(result, campaign_root=campaign_root, campaign_id=campaign_id)
    if not rels:
        return

    manifest = _load_projection_manifest_for_commit(manifest_path)
    changed = False
    for rel in sorted(rels):
        source = campaign_root / rel
        target = projection_root / rel
        if not source.exists() or not source.is_file():
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            os.chmod(target, 0o660)
        except OSError:
            pass
        else:
            manifest[str(rel)] = _hash_file_for_commit(source)
            changed = True
    if changed:
        _write_projection_manifest_for_commit(manifest_path, manifest)


def _committed_result_paths(
    value: Any,
    *,
    campaign_root: Path,
    campaign_id: str,
) -> set[Path]:
    paths: set[Path] = set()

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if key == "path" and isinstance(child, str):
                    rel = _result_path_to_campaign_rel(
                        child,
                        campaign_root=campaign_root,
                        campaign_id=campaign_id,
                    )
                    if rel is not None:
                        paths.add(rel)
                else:
                    visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return paths


def _result_path_to_campaign_rel(
    text: str,
    *,
    campaign_root: Path,
    campaign_id: str,
) -> Path | None:
    if not text:
        return None
    raw = Path(text)
    try:
        if raw.is_absolute():
            return raw.resolve().relative_to(campaign_root)
        if len(raw.parts) >= 2 and raw.parts[0] == "campaigns" and raw.parts[1] == campaign_id:
            return Path(*raw.parts[2:])
    except ValueError:
        return None
    return None


def _load_projection_manifest_for_commit(path: Path) -> dict[str, str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    files = raw.get("files", raw)
    if not isinstance(files, dict):
        return {}
    return {str(key): str(value) for key, value in files.items() if isinstance(value, str)}


def _write_projection_manifest_for_commit(path: Path, manifest: dict[str, str]) -> None:
    try:
        os.chmod(path, 0o660)
    except OSError:
        pass
    try:
        path.write_text(
            json.dumps({"files": manifest}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError:
        # The durable command has already succeeded. Projection manifest refresh
        # is a same-turn convenience; failing it must not make `glass` report a
        # failed mutation to the agent.
        return


def _hash_file_for_commit(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


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
