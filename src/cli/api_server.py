"""Local HTTP API for player-facing glass CLI calls."""

from __future__ import annotations

import contextlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Iterator

from click.testing import CliRunner

from . import db
from . import graph as graph_db
from . import workspace as workspace_db
from .api_grants import DEFAULT_API_URL, validate_grant
from .config import get_paths, load_config
from .errors import GlassError


_server: HTTPServer | None = None
_server_thread: threading.Thread | None = None
_server_url: str | None = None
_invoke_lock = threading.Lock()
_READABLE_FILE_SUFFIXES = {".jsonl", ".md", ".txt"}
_EXCLUDED_FILE_NAMES = {".glass-grants.json"}
_EXCLUDED_PATH_PARTS = {".git", ".glass-cwd", "__pycache__"}
_MAX_FILE_BYTES = 512_000
_CURSOR_SEPARATOR = "::"
_FILE_SECTION_TERMS = {
    "journal": ["journal", "players/"],
    "lore": ["lore", "context", "summary"],
    "arcs": ["arc", "previous"],
    "scenes": ["scene", "table/scene", "transcript"],
    "dm": ["dm/", "scratchpad", "prep"],
    "audit": ["audit", ".jsonl"],
}


def ensure_background_server(
    *,
    url: str = DEFAULT_API_URL,
    config_path: str | None = None,
) -> str:
    """Start the local API in this process unless something healthy exists."""

    global _server, _server_thread, _server_url
    if config_path:
        os.environ["GLASS_CONFIG"] = config_path
    if _server_thread is not None and _server_thread.is_alive() and _server_url == url:
        return url

    health = _server_health(url)
    if health is not None:
        server_config = health.get("config_path")
        if config_path and server_config and server_config != config_path:
            raise RuntimeError(
                f"glass API already running at {url} with different config: {server_config}"
            )
        return url

    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 26001
    _server = HTTPServer((host, port), _GlassApiHandler)
    _server_thread = threading.Thread(
        target=_server.serve_forever,
        name="glass-api",
        daemon=True,
    )
    _server_thread.start()
    _server_url = url
    _wait_for_health(url)
    return url


def serve_forever(
    *,
    host: str = "127.0.0.1",
    port: int = 26001,
    config_path: str | None = None,
) -> None:
    if config_path:
        os.environ["GLASS_CONFIG"] = config_path
    server = HTTPServer((host, port), _GlassApiHandler)
    server.serve_forever()


def is_server_available(url: str = DEFAULT_API_URL) -> bool:
    return _server_health(url) is not None


def _server_health(url: str = DEFAULT_API_URL) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/v1/health", timeout=1) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("utf-8"))
            return payload if isinstance(payload, dict) else None
    except OSError:
        return None
    except json.JSONDecodeError:
        return None


def _wait_for_health(url: str) -> None:
    deadline = time.time() + 2
    while time.time() < deadline:
        if is_server_available(url):
            return
        time.sleep(0.05)
    raise RuntimeError(f"glass API did not become healthy at {url}")


class _GlassApiHandler(BaseHTTPRequestHandler):
    server_version = "glass-api/0.1"

    def do_OPTIONS(self) -> None:
        self._write_empty(204)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/v1/health":
            self._write_json(
                200,
                {
                    "status": "ok",
                    "pid": os.getpid(),
                    "config_path": os.environ.get("GLASS_CONFIG"),
                },
            )
            return
        try:
            payload = _read_api_payload(parsed.path, urllib.parse.parse_qs(parsed.query))
        except GlassError as exc:
            self._write_json(400, {"error": str(exc)})
            return
        except Exception as exc:
            self._write_json(500, {"error": f"glass API read error: {exc}"})
            return
        if payload is not None:
            self._write_json(200, payload)
            return
        self._write_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/v1/command":
            self._write_json(404, {"error": "not found"})
            return
        self._handle_command()

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _handle_command(self) -> None:
        try:
            payload = self._read_payload()
            token = str(payload.get("grant") or "")
            args = payload.get("args")
            if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
                raise GlassError("invalid glass API payload: args must be a string list")
            paths = get_paths()
            claim = validate_grant(paths.campaigns, token, args)
            result = _invoke_glass(args, claim)
            self._write_json(200, result)
        except GlassError as exc:
            self._write_json(
                403,
                {
                    "exit_code": 77,
                    "output": f"Error: {exc}\n",
                },
            )
        except Exception as exc:
            self._write_json(
                500,
                {
                    "exit_code": 70,
                    "output": f"glass API internal error: {exc}\n",
                },
            )

    def _read_payload(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise GlassError("invalid Content-Length") from exc
        raw = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            raise GlassError(f"invalid JSON payload: {exc}") from exc
        if not isinstance(payload, dict):
            raise GlassError("invalid glass API payload: expected object")
        return payload

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._write_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _write_empty(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self._write_cors_headers()
        self.end_headers()

    def _write_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def _read_api_payload(path: str, query: dict[str, list[str]]) -> dict[str, Any] | None:
    segments = [urllib.parse.unquote(part) for part in path.strip("/").split("/") if part]
    if segments == ["v1", "campaigns"]:
        return _campaigns_payload()
    if len(segments) != 4 or segments[:2] != ["v1", "campaigns"]:
        return None
    campaign_id = _validate_campaign_id(segments[2])
    route = segments[3]
    if route == "dashboard":
        return _campaign_dashboard_payload(campaign_id, query)
    if route == "summary":
        return _campaign_summary_payload(campaign_id)
    if route == "live":
        return _campaign_live_payload(campaign_id, query)
    if route in {"current-turn-output", "turn-output"}:
        return _campaign_current_turn_output_payload(campaign_id, query)
    if route == "table":
        return _campaign_table_resource_payload(campaign_id)
    if route == "turns":
        return _campaign_turns_payload(campaign_id, query)
    if route == "messages":
        return _campaign_messages_payload(campaign_id, query)
    if route == "events":
        return _campaign_events_payload(campaign_id, query)
    if route == "rolls":
        return _campaign_rolls_payload(campaign_id, query)
    if route == "files":
        return _campaign_files_payload(campaign_id, query)
    return None


def _campaigns_payload() -> dict[str, Any]:
    campaigns_dir = get_paths().campaigns
    campaigns: list[dict[str, Any]] = []
    if campaigns_dir.exists():
        for campaign_root in sorted(campaigns_dir.iterdir(), key=lambda path: path.name):
            if not campaign_root.is_dir() or campaign_root.name.startswith("."):
                continue
            campaigns.append(
                {
                    "campaign_id": campaign_root.name,
                    "dashboard_url": f"/v1/campaigns/{campaign_root.name}/dashboard",
                    "files_url": f"/v1/campaigns/{campaign_root.name}/files",
                    "updated_at": _path_mtime(campaign_root),
                }
            )
    return {"campaigns": campaigns}


def _campaign_dashboard_payload(
    campaign_id: str,
    query: dict[str, list[str]],
) -> dict[str, Any]:
    """Compatibility route for ad-hoc debugging.

    The web UI uses the resource routes below. This route intentionally returns
    only current summary + initial live window, not the campaign file tree.
    """
    live = _campaign_live_payload(campaign_id, query)
    summary = _campaign_summary_payload(campaign_id)
    table = _campaign_table_resource_payload(campaign_id)
    return {**summary, **table, **live}


def _campaign_summary_payload(campaign_id: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "campaign_id": campaign_id,
        "generated_at": _now_iso(),
        "runtime": None,
        "characters": [],
        "clocks": [],
        "scene_trackers": [],
        "tarot": [],
        "graph": _graph_payload(campaign_id),
        "dm_surface": _campaign_dm_surface_payload(campaign_id),
    }
    try:
        config = load_config()
        with db.connect(db.load_pg_config(config)) as conn:
            payload["runtime"] = _runtime_payload(conn, campaign_id)
            payload["characters"] = db.character_list(conn, campaign_id)
            payload["clocks"] = db.clock_list(
                conn,
                campaign_id=campaign_id,
                include_archived=True,
            )
            payload["scene_trackers"] = db.scene_tracker_list(
                conn,
                campaign_id=campaign_id,
                include_archived=True,
            )
            payload["tarot"] = db.tarot_list(
                conn,
                campaign_id=campaign_id,
                active_only=False,
                limit=100,
            )
            payload["dm_surface"] = _campaign_dm_surface_payload(campaign_id)
    except Exception as exc:
        payload["database_error"] = str(exc)
    return payload


def _campaign_live_payload(
    campaign_id: str,
    query: dict[str, list[str]],
) -> dict[str, Any]:
    turn_limit = _query_int(query, "turns", default=20, minimum=1, maximum=100)
    message_limit = _query_int(query, "messages", default=100, minimum=1, maximum=500)
    event_limit = _query_int(query, "events", default=100, minimum=1, maximum=500)
    roll_limit = _query_int(query, "rolls", default=50, minimum=1, maximum=250)
    after_turn = _query_int_or_none(query, "after_turn", minimum=0, maximum=1_000_000)
    messages_after = _first_query_value(query, "messages_after")
    events_after = _first_query_value(query, "events_after")
    rolls_after = _first_query_value(query, "rolls_after")
    include_state = _query_bool(query, "include_state", default=False)
    payload: dict[str, Any] = {
        "campaign_id": campaign_id,
        "generated_at": _now_iso(),
        "turns": [],
        "messages": [],
        "events": [],
        "rolls": [],
        "cursors": {
            "turn": after_turn,
            "messages": messages_after,
            "events": events_after,
            "rolls": rolls_after,
        },
    }
    try:
        config = load_config()
        with db.connect(db.load_pg_config(config)) as conn:
            turns = _turn_delta(conn, campaign_id, after_turn=after_turn, limit=turn_limit)
            messages = _message_delta(
                conn,
                campaign_id,
                cursor=messages_after,
                limit=message_limit,
            )
            events = _event_delta(
                conn,
                campaign_id,
                cursor=events_after,
                limit=event_limit,
            )
            rolls = _roll_delta(
                conn,
                campaign_id,
                cursor=rolls_after,
                limit=roll_limit,
            )
            payload["turns"] = turns["items"]
            payload["messages"] = messages["items"]
            payload["events"] = events["items"]
            payload["rolls"] = rolls["items"]
            payload["cursors"] = {
                "turn": turns["cursor"],
                "messages": messages["cursor"],
                "events": events["cursor"],
                "rolls": rolls["cursor"],
            }
            if include_state:
                payload["runtime"] = _runtime_payload(conn, campaign_id)
                payload["clocks"] = db.clock_list(
                    conn,
                    campaign_id=campaign_id,
                    include_archived=True,
                )
                payload["scene_trackers"] = db.scene_tracker_list(
                    conn,
                    campaign_id=campaign_id,
                    include_archived=True,
                )
                payload["tarot"] = db.tarot_list(
                    conn,
                    campaign_id=campaign_id,
                    active_only=False,
                    limit=100,
                )
                payload["dm_surface"] = _campaign_dm_surface_payload(campaign_id)
    except Exception as exc:
        payload["database_error"] = str(exc)
    return payload


def _campaign_table_resource_payload(campaign_id: str) -> dict[str, Any]:
    campaign_root = _campaign_root(campaign_id)
    return {
        "campaign_id": campaign_id,
        "generated_at": _now_iso(),
        "table": _campaign_table_payload(campaign_root),
    }


def _campaign_turns_payload(
    campaign_id: str,
    query: dict[str, list[str]],
) -> dict[str, Any]:
    limit = _query_int(query, "limit", default=50, minimum=1, maximum=500)
    after_turn = _query_int_or_none(query, "after_turn", minimum=0, maximum=1_000_000)
    payload: dict[str, Any] = {
        "campaign_id": campaign_id,
        "items": [],
        "cursor": after_turn,
    }
    try:
        with db.connect(db.load_pg_config(load_config())) as conn:
            payload.update(_turn_delta(conn, campaign_id, after_turn=after_turn, limit=limit))
    except Exception as exc:
        payload["database_error"] = str(exc)
    return payload


def _campaign_messages_payload(
    campaign_id: str,
    query: dict[str, list[str]],
) -> dict[str, Any]:
    limit = _query_int(query, "limit", default=100, minimum=1, maximum=1000)
    cursor = _first_query_value(query, "after")
    payload: dict[str, Any] = {"campaign_id": campaign_id, "items": [], "cursor": cursor}
    try:
        with db.connect(db.load_pg_config(load_config())) as conn:
            payload.update(_message_delta(conn, campaign_id, cursor=cursor, limit=limit))
    except Exception as exc:
        payload["database_error"] = str(exc)
    return payload


def _campaign_events_payload(
    campaign_id: str,
    query: dict[str, list[str]],
) -> dict[str, Any]:
    limit = _query_int(query, "limit", default=100, minimum=1, maximum=1000)
    cursor = _first_query_value(query, "after")
    payload: dict[str, Any] = {"campaign_id": campaign_id, "items": [], "cursor": cursor}
    try:
        with db.connect(db.load_pg_config(load_config())) as conn:
            payload.update(_event_delta(conn, campaign_id, cursor=cursor, limit=limit))
    except Exception as exc:
        payload["database_error"] = str(exc)
    return payload


def _campaign_rolls_payload(
    campaign_id: str,
    query: dict[str, list[str]],
) -> dict[str, Any]:
    limit = _query_int(query, "limit", default=50, minimum=1, maximum=500)
    cursor = _first_query_value(query, "after")
    payload: dict[str, Any] = {"campaign_id": campaign_id, "items": [], "cursor": cursor}
    try:
        with db.connect(db.load_pg_config(load_config())) as conn:
            payload.update(_roll_delta(conn, campaign_id, cursor=cursor, limit=limit))
    except Exception as exc:
        payload["database_error"] = str(exc)
    return payload


def _campaign_files_payload(
    campaign_id: str,
    query: dict[str, list[str]],
) -> dict[str, Any]:
    campaign_root = _campaign_root(campaign_id)
    raw_path = _first_query_value(query, "path")
    if raw_path:
        return _file_content_payload(campaign_root, raw_path)
    section = _first_query_value(query, "section")
    prefix = _first_query_value(query, "prefix")
    include_all = _query_bool(query, "all", default=False)
    limit = _query_int(query, "limit", default=100, minimum=1, maximum=5000)
    files = _file_tree_payload(campaign_root)
    if section:
        files = [entry for entry in files if _file_entry_matches_section(entry, section)]
    elif prefix:
        files = [entry for entry in files if entry["path"].startswith(prefix)]
    elif not include_all:
        return {
            "campaign_id": campaign_id,
            "root": campaign_root.name,
            "sections": _file_section_counts(files),
            "files": [],
        }
    return {
        "campaign_id": campaign_id,
        "root": campaign_root.name,
        "files": files[:limit],
    }


def _campaign_current_turn_output_payload(
    campaign_id: str,
    query: dict[str, list[str]],
) -> dict[str, Any]:
    campaign_root = _campaign_root(campaign_id)
    max_bytes = _query_int(
        query,
        "max_bytes",
        default=128_000,
        minimum=1_024,
        maximum=_MAX_FILE_BYTES,
    )
    payload: dict[str, Any] = {
        "campaign_id": campaign_id,
        "generated_at": _now_iso(),
    }
    try:
        with db.connect(db.load_pg_config(load_config())) as conn:
            state = db.runtime_state_get(conn, campaign_id)
    except Exception as exc:
        payload.update(_empty_current_turn_output(campaign_id))
        payload["database_error"] = str(exc)
        return payload
    payload.update(
        _current_turn_output_payload(
            campaign_root,
            runtime_state=state,
            max_bytes=max_bytes,
        )
    )
    return payload


def _current_turn_output_payload(
    campaign_root: Path,
    *,
    runtime_state: dict[str, Any] | None,
    max_bytes: int,
) -> dict[str, Any]:
    campaign_id = campaign_root.name
    if not runtime_state:
        return _empty_current_turn_output(campaign_id)
    status = str(runtime_state.get("aog_status") or runtime_state.get("status") or "")
    if status != "running":
        payload = _empty_current_turn_output(campaign_id)
        payload["status"] = status
        return payload

    committed_turn = int(
        runtime_state.get("aog_turn_number")
        or runtime_state.get("turn_counter")
        or 0
    )
    turn_number = committed_turn + 1
    candidate = _current_turn_artifact(campaign_root, turn_number)
    payload: dict[str, Any] = {
        "active": True,
        "status": status,
        "turn_id": f"{campaign_id}-t{turn_number:04d}",
        "turn_number": turn_number,
        "speaker": None,
        "role": None,
        "turn_dir": None,
        "stdout": "",
        "stderr": "",
        "stdout_bytes": 0,
        "stderr_bytes": 0,
        "stdout_truncated": False,
        "stderr_truncated": False,
        "updated_at": None,
        "files": {
            "stdout": None,
            "stderr": None,
        },
    }
    if candidate is None:
        return payload

    turn_dir, speaker, role = candidate
    stdout_path = turn_dir / "agent-stdout.txt"
    stderr_path = turn_dir / "agent-stderr.txt"
    stdout_text, stdout_bytes, stdout_truncated, stdout_mtime = _read_tail_text(
        stdout_path,
        max_bytes=max_bytes,
    )
    stderr_text, stderr_bytes, stderr_truncated, stderr_mtime = _read_tail_text(
        stderr_path,
        max_bytes=max_bytes,
    )
    mtimes = [value for value in (stdout_mtime, stderr_mtime) if value is not None]
    payload.update(
        {
            "speaker": speaker,
            "role": role,
            "turn_dir": turn_dir.relative_to(campaign_root).as_posix(),
            "stdout": stdout_text,
            "stderr": stderr_text,
            "stdout_bytes": stdout_bytes,
            "stderr_bytes": stderr_bytes,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "updated_at": _iso_from_timestamp(max(mtimes)) if mtimes else None,
            "files": {
                "stdout": stdout_path.relative_to(campaign_root).as_posix(),
                "stderr": stderr_path.relative_to(campaign_root).as_posix(),
            },
        }
    )
    return payload


def _empty_current_turn_output(campaign_id: str) -> dict[str, Any]:
    return {
        "active": False,
        "status": None,
        "turn_id": None,
        "turn_number": None,
        "speaker": None,
        "role": None,
        "turn_dir": None,
        "stdout": "",
        "stderr": "",
        "stdout_bytes": 0,
        "stderr_bytes": 0,
        "stdout_truncated": False,
        "stderr_truncated": False,
        "updated_at": None,
        "files": {
            "stdout": None,
            "stderr": None,
        },
    }


def _current_turn_artifact(
    campaign_root: Path,
    turn_number: int,
) -> tuple[Path, str, str] | None:
    turn_name = f"{turn_number:04d}"
    candidates: list[tuple[Path, str, str]] = []
    dm_dir = campaign_root / "dm" / "turns" / turn_name
    if dm_dir.is_dir():
        candidates.append((dm_dir, "dm", "dm"))
    players_dir = campaign_root / "players"
    if players_dir.is_dir():
        for player_dir in sorted(players_dir.iterdir(), key=lambda path: path.name):
            turn_dir = player_dir / "turns" / turn_name
            if turn_dir.is_dir():
                candidates.append((turn_dir, player_dir.name, "player"))
    if not candidates:
        return None
    return max(candidates, key=lambda item: _path_latest_mtime(item[0]))


def _path_latest_mtime(path: Path) -> float:
    latest = path.stat().st_mtime
    for child in path.iterdir():
        try:
            latest = max(latest, child.stat().st_mtime)
        except OSError:
            continue
    return latest


def _read_tail_text(path: Path, *, max_bytes: int) -> tuple[str, int, bool, float | None]:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return "", 0, False, None
    stat = path.stat()
    size = stat.st_size
    with path.open("rb") as handle:
        if size > max_bytes:
            handle.seek(size - max_bytes)
        raw = handle.read(max_bytes)
    return raw.decode("utf-8", errors="replace"), size, size > max_bytes, stat.st_mtime


def _runtime_payload(conn: Any, campaign_id: str) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT campaign_id, status, created_at, updated_at, wrapped_at, summary,
                   turn_counter, mode_stack, pending_events, note_intake,
                   next_speakers, scene_closing_turns
            FROM campaign_runtime_states
            WHERE campaign_id = %s
            """,
            (campaign_id,),
        )
        row = cur.fetchone()
        cur.execute(
            "SELECT count(*), max(turn_id) FROM turns WHERE campaign_id = %s",
            (campaign_id,),
        )
        turn_row = cur.fetchone()
    if row is None:
        return None
    (
        campaign,
        status,
        created_at,
        updated_at,
        wrapped_at,
        summary,
        turn_counter,
        mode_stack,
        pending_events,
        note_intake,
        next_speakers,
        scene_closing_turns,
    ) = row
    turn_count = int(turn_row[0] or 0) if turn_row else 0
    latest_turn_id = int(turn_row[1]) if turn_row and turn_row[1] is not None else None
    return {
        "schema_version": 5,
        "campaign": campaign,
        "status": status,
        "created_at": _iso(created_at),
        "updated_at": _iso(updated_at),
        "wrapped_at": _iso(wrapped_at),
        "summary": summary or "",
        "turn_counter": max(int(turn_counter), latest_turn_id or 0),
        "mode_stack": list(mode_stack or []),
        "pending_events": list(pending_events or []),
        "note_intake": list(note_intake or []),
        "next_speakers": list(next_speakers or []),
        "scene_closing_turns": scene_closing_turns,
        "turns": {
            "count": turn_count,
            "latest_turn_id": latest_turn_id,
        },
    }


def _latest_messages(
    conn: Any,
    campaign_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {db._MESSAGE_COLUMNS}
            FROM messages
            WHERE campaign_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (campaign_id, limit),
        )
        rows = cur.fetchall()
    return [db._row_to_message(row) for row in reversed(rows)]


def _latest_events(
    conn: Any,
    campaign_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT event_id, campaign_id, scene_id, turn_id, actor, event_type,
                   visibility, summary, payload, created_at, claimed_at
            FROM events
            WHERE campaign_id = %s
            ORDER BY created_at DESC, event_id DESC
            LIMIT %s
            """,
            (campaign_id, limit),
        )
        rows = cur.fetchall()
    events = [
        {
            "event_id": str(row[0]),
            "campaign_id": row[1],
            "scene_id": row[2],
            "turn_id": row[3],
            "actor": row[4],
            "event_type": row[5],
            "visibility": row[6],
            "summary": row[7],
            "payload": row[8] or {},
            "created_at": _iso(row[9]),
            "claimed_at": _iso(row[10]),
        }
        for row in reversed(rows)
    ]
    return events


def _latest_rolls(
    conn: Any,
    campaign_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {db._ROLL_COLUMNS}
            FROM rolls
            WHERE campaign_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (campaign_id, limit),
        )
        rows = cur.fetchall()
    return [db._row_to_roll(row) for row in reversed(rows)]


def _turn_delta(
    conn: Any,
    campaign_id: str,
    *,
    after_turn: int | None,
    limit: int,
) -> dict[str, Any]:
    turns = db.turn_list(
        conn,
        campaign_id=campaign_id,
        after_turn=after_turn,
        limit=limit,
        latest=after_turn is None,
    )
    cursor = turns[-1]["turn_id"] if turns else after_turn
    return {"items": turns, "cursor": cursor}


def _message_delta(
    conn: Any,
    campaign_id: str,
    *,
    cursor: str | None,
    limit: int,
) -> dict[str, Any]:
    rows = _created_id_delta_rows(
        conn,
        table="messages",
        id_column="id",
        id_cast="uuid",
        columns=db._MESSAGE_COLUMNS,
        campaign_id=campaign_id,
        cursor=cursor,
        limit=limit,
    )
    messages = [db._row_to_message(row) for row in rows]
    next_cursor = _cursor_from_rows(rows, created_at_index=7, id_index=0) or cursor
    return {"items": messages, "cursor": next_cursor}


def _event_delta(
    conn: Any,
    campaign_id: str,
    *,
    cursor: str | None,
    limit: int,
) -> dict[str, Any]:
    columns = (
        "event_id, campaign_id, scene_id, turn_id, actor, event_type, "
        "visibility, summary, payload, created_at, claimed_at"
    )
    rows = _created_id_delta_rows(
        conn,
        table="events",
        id_column="event_id",
        id_cast=None,
        columns=columns,
        campaign_id=campaign_id,
        cursor=cursor,
        limit=limit,
    )
    events = [_row_to_event(row) for row in rows]
    next_cursor = _cursor_from_rows(rows, created_at_index=9, id_index=0) or cursor
    return {"items": events, "cursor": next_cursor}


def _roll_delta(
    conn: Any,
    campaign_id: str,
    *,
    cursor: str | None,
    limit: int,
) -> dict[str, Any]:
    rows = _created_id_delta_rows(
        conn,
        table="rolls",
        id_column="id",
        id_cast="uuid",
        columns=db._ROLL_COLUMNS,
        campaign_id=campaign_id,
        cursor=cursor,
        limit=limit,
    )
    rolls = [db._row_to_roll(row) for row in rows]
    next_cursor = _cursor_from_rows(rows, created_at_index=23, id_index=0) or cursor
    return {"items": rolls, "cursor": next_cursor}


def _created_id_delta_rows(
    conn: Any,
    *,
    table: str,
    id_column: str,
    id_cast: str | None,
    columns: str,
    campaign_id: str,
    cursor: str | None,
    limit: int,
) -> list[tuple[Any, ...]]:
    params: list[Any] = [campaign_id]
    where = ["campaign_id = %s"]
    if cursor:
        created_at, row_id = _parse_created_id_cursor(cursor)
        cast = f"::{id_cast}" if id_cast else ""
        where.append(f"(created_at, {id_column}) > (%s::timestamptz, %s{cast})")
        params.extend([created_at, row_id])
        order = "created_at ASC, {id_column} ASC"
    else:
        order = "created_at DESC, {id_column} DESC"
    params.append(limit)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {columns}
            FROM {table}
            WHERE {' AND '.join(where)}
            ORDER BY {order.format(id_column=id_column)}
            LIMIT %s
            """,
            params,
        )
        rows = cur.fetchall()
    if cursor:
        return rows
    return list(reversed(rows))


def _row_to_event(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "event_id": str(row[0]),
        "campaign_id": row[1],
        "scene_id": row[2],
        "turn_id": row[3],
        "actor": row[4],
        "event_type": row[5],
        "visibility": row[6],
        "summary": row[7],
        "payload": row[8] or {},
        "created_at": _iso(row[9]),
        "claimed_at": _iso(row[10]),
    }


def _cursor_from_rows(
    rows: list[tuple[Any, ...]],
    *,
    created_at_index: int,
    id_index: int,
) -> str | None:
    if not rows:
        return None
    row = rows[-1]
    return f"{_iso(row[created_at_index])}{_CURSOR_SEPARATOR}{row[id_index]}"


def _parse_created_id_cursor(cursor: str) -> tuple[str, str]:
    parts = cursor.split(_CURSOR_SEPARATOR, 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise GlassError("invalid cursor")
    return parts[0], parts[1]


def _graph_payload(campaign_id: str) -> dict[str, Any]:
    config = graph_db.load_falkor_config(load_config())
    payload: dict[str, Any] = {
        "available": False,
        "target": config.describe(),
        "entities": [],
        "edges": [],
        "entity_types": [],
    }
    try:
        with graph_db.connect(config) as g:
            g.query("RETURN 1")
            payload["available"] = True
            payload["entities"] = graph_db.find_entities(
                g,
                campaign_id=campaign_id,
                limit=50,
            )
            payload["edges"] = _graph_edges(g, campaign_id, limit=100)
            payload["entity_types"] = _graph_entity_types(g, campaign_id)
    except Exception as exc:
        payload["error"] = str(exc)
    return payload


def _graph_edges(g: Any, campaign_id: str, *, limit: int) -> list[dict[str, Any]]:
    result = g.query(
        """
        MATCH (a:Entity {campaign_id: $campaign})-[r]->(b:Entity {campaign_id: $campaign})
        RETURN type(r), a.id, a.title, b.id, b.title
        ORDER BY a.title, b.title
        LIMIT $limit
        """,
        {"campaign": campaign_id, "limit": limit},
    )
    return [
        {
            "type": str(row[0]),
            "source": row[1],
            "source_title": row[2],
            "target": row[3],
            "target_title": row[4],
        }
        for row in result.result_set
    ]


def _graph_entity_types(g: Any, campaign_id: str) -> list[dict[str, Any]]:
    result = g.query(
        """
        MATCH (e:Entity {campaign_id: $campaign})
        RETURN e.type, count(e)
        ORDER BY count(e) DESC, e.type
        """,
        {"campaign": campaign_id},
    )
    return [
        {
            "type": row[0] or "entity",
            "count": int(row[1]),
        }
        for row in result.result_set
    ]


def _campaign_table_payload(campaign_root: Path) -> dict[str, Any]:
    table_dir = campaign_root / "table"
    payload: dict[str, Any] = {
        "index": _optional_file_payload(table_dir / "index.md"),
        "scene": _optional_file_payload(table_dir / "scene.md"),
        "files": [],
    }
    if table_dir.exists():
        files = []
        for path in sorted(table_dir.rglob("*"), key=lambda item: item.as_posix()):
            if path.name in {"index.md", "scene.md"}:
                continue
            if _is_readable_campaign_file(campaign_root, path):
                files.append({**_file_entry(campaign_root, path), "content": _read_text(path)})
        payload["files"] = files
    return payload


def _campaign_dm_surface_payload(campaign_id: str) -> dict[str, Any]:
    campaign_root = _campaign_root(campaign_id)
    current = _current_scene_payload(campaign_root)
    return {
        "current_scene": current,
        "beats": _quest_beats(campaign_root / "shared" / "quest-log.md", limit=12),
        "files": _dm_play_files(campaign_root, current),
    }


def _current_scene_payload(campaign_root: Path) -> dict[str, Any] | None:
    workspace = workspace_db.CampaignWorkspace(campaign_root.name, campaign_root)
    try:
        current = workspace_db.current_scene(workspace)
    except Exception:
        return None
    if not current:
        return None
    raw_path = current.get("path")
    path = None
    if raw_path:
        with contextlib.suppress(ValueError):
            path = Path(raw_path).relative_to(campaign_root).as_posix()
    return {
        "arc_id": current.get("arc_id"),
        "scene_id": current.get("scene_id"),
        "scene_type": current.get("scene_type"),
        "path": path,
    }


_QUEST_BEAT_RE = re.compile(r"^\s*[-*]\s+(?:\[([^\]]+)\]\s*)?(.+?)\s*$")


def _quest_beats(path: Path, *, limit: int) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    beats: list[dict[str, Any]] = []
    for line in _read_text(path).splitlines():
        match = _QUEST_BEAT_RE.match(line)
        if not match:
            continue
        tag, text = match.groups()
        arc_id: str | None = None
        scene_id: str | None = None
        if tag:
            parts = [part for part in tag.split(":") if part]
            if parts:
                arc_id = parts[0]
            if len(parts) > 1:
                scene_id = parts[1]
        beats.append(
            {
                "text": text,
                "arc_id": arc_id,
                "scene_id": scene_id,
                "source_path": "shared/quest-log.md",
            }
        )
    return beats[-limit:]


def _dm_play_files(
    campaign_root: Path,
    current: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not current:
        return []
    scene_path = current.get("path")
    if not scene_path:
        return []
    files: list[dict[str, Any]] = []
    for name in ("prep.md",):
        path = campaign_root / scene_path / name
        if _is_readable_campaign_file(campaign_root, path):
            files.append(
                {**_file_entry(campaign_root, path), "content": _read_text(path)}
            )
    return files


def _optional_file_payload(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    return {
        "path": path.name,
        "title": _file_title(path),
        "content": _read_text(path),
        "updated_at": _path_mtime(path),
    }


def _file_tree_payload(campaign_root: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    if not campaign_root.exists():
        return files
    for path in sorted(campaign_root.rglob("*"), key=lambda item: item.as_posix()):
        if _is_readable_campaign_file(campaign_root, path):
            files.append(_file_entry(campaign_root, path))
    return files


def _file_section_counts(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "section": section,
            "count": sum(1 for entry in files if _file_entry_matches_section(entry, section)),
        }
        for section in _FILE_SECTION_TERMS
    ]


def _file_entry_matches_section(entry: dict[str, Any], section: str) -> bool:
    terms = _FILE_SECTION_TERMS.get(section, [section])
    haystack = f"{entry.get('path', '')} {entry.get('title', '')} {entry.get('section', '')}".lower()
    return any(term.lower() in haystack for term in terms)


def _file_content_payload(campaign_root: Path, raw_path: str) -> dict[str, Any]:
    path = _safe_campaign_path(campaign_root, raw_path)
    if not _is_readable_campaign_file(campaign_root, path):
        raise GlassError(f"campaign file is not readable: {raw_path}")
    entry = _file_entry(campaign_root, path)
    return {
        **entry,
        "campaign_id": campaign_root.name,
        "content": _read_text(path),
    }


def _safe_campaign_path(campaign_root: Path, raw_path: str) -> Path:
    if not raw_path or raw_path.startswith(("/", "\\")):
        raise GlassError("campaign file path must be relative")
    root = campaign_root.resolve()
    path = (root / raw_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise GlassError("campaign file path escapes campaign root") from exc
    return path


def _is_readable_campaign_file(campaign_root: Path, path: Path) -> bool:
    if not path.is_file():
        return False
    if path.is_symlink():
        return False
    if path.name in _EXCLUDED_FILE_NAMES:
        return False
    if path.suffix.lower() not in _READABLE_FILE_SUFFIXES:
        return False
    try:
        relative = path.relative_to(campaign_root)
    except ValueError:
        return False
    if any(part in _EXCLUDED_PATH_PARTS or part.startswith(".") for part in relative.parts):
        return False
    return True


def _file_entry(campaign_root: Path, path: Path) -> dict[str, Any]:
    relative = path.relative_to(campaign_root).as_posix()
    section = relative.split("/", 1)[0]
    stat = path.stat()
    return {
        "path": relative,
        "name": path.name,
        "section": section,
        "title": _file_title(path),
        "size": stat.st_size,
        "updated_at": _iso_from_timestamp(stat.st_mtime),
    }


def _file_title(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for _ in range(30):
                line = handle.readline()
                if not line:
                    break
                stripped = line.strip()
                if stripped.startswith("#"):
                    return stripped.lstrip("#").strip() or path.stem
                if stripped.lower().startswith("title:"):
                    return stripped.split(":", 1)[1].strip().strip("\"'") or path.stem
    except OSError:
        return path.stem
    return path.stem.replace("-", " ").replace("_", " ").strip() or path.name


def _read_text(path: Path) -> str:
    with path.open("rb") as handle:
        raw = handle.read(_MAX_FILE_BYTES + 1)
    truncated = len(raw) > _MAX_FILE_BYTES
    if truncated:
        raw = raw[:_MAX_FILE_BYTES]
    text = raw.decode("utf-8", errors="replace")
    if truncated:
        text = f"{text}\n\n[truncated at {_MAX_FILE_BYTES} bytes]"
    return text


def _campaign_root(campaign_id: str) -> Path:
    campaign_root = get_paths().campaigns / campaign_id
    if not campaign_root.exists() or not campaign_root.is_dir():
        raise GlassError(f"unknown campaign: {campaign_id}")
    return campaign_root


def _validate_campaign_id(campaign_id: str) -> str:
    if not campaign_id or "/" in campaign_id or "\\" in campaign_id:
        raise GlassError("invalid campaign id")
    if campaign_id in {".", ".."} or campaign_id.startswith("."):
        raise GlassError("invalid campaign id")
    return campaign_id


def _query_int(
    query: dict[str, list[str]],
    name: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw = _first_query_value(query, name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise GlassError(f"invalid {name}: expected integer") from exc
    return min(max(value, minimum), maximum)


def _query_int_or_none(
    query: dict[str, list[str]],
    name: str,
    *,
    minimum: int,
    maximum: int,
) -> int | None:
    raw = _first_query_value(query, name)
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise GlassError(f"invalid {name}: expected integer") from exc
    return min(max(value, minimum), maximum)


def _query_bool(
    query: dict[str, list[str]],
    name: str,
    *,
    default: bool,
) -> bool:
    raw = _first_query_value(query, name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _first_query_value(query: dict[str, list[str]], name: str) -> str | None:
    values = query.get(name)
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _path_mtime(path: Path) -> str:
    return _iso_from_timestamp(path.stat().st_mtime)


def _iso_from_timestamp(value: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(value))


def _now_iso() -> str:
    return _iso_from_timestamp(time.time())


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _invoke_glass(args: list[str], claim: dict[str, Any]) -> dict[str, Any]:
    from .main import main as glass_main

    campaigns_dir = get_paths().campaigns
    campaign_id = str(claim["campaign_id"])
    campaign_root = campaigns_dir / campaign_id
    workspace_root = _claim_workspace_root(claim, fallback=campaign_root)
    env = os.environ.copy()
    env.update(
        {
            "GLASS_API_INTERNAL": "1",
            "GLASS_CAMPAIGN_ID": campaign_id,
            "GLASS_ROLE": str(claim["glass_role"]),
            "GLASS_TURN_ID": str(claim["turn_id"]),
        }
    )
    workspace_reader_user = claim.get("workspace_reader_user")
    if isinstance(workspace_reader_user, str) and workspace_reader_user:
        env["GLASS_WORKSPACE_READER_USER"] = workspace_reader_user
    runner = CliRunner()
    with _invoke_lock, _pushd(workspace_root):
        raw = runner.invoke(glass_main, args, env=env, prog_name="glass")
        if raw.exit_code == 0:
            _refresh_projection(campaign_root, workspace_root, claim)
    return {
        "exit_code": raw.exit_code,
        "output": raw.output,
    }


def _claim_workspace_root(claim: dict[str, Any], *, fallback: Path) -> Path:
    value = claim.get("workspace_root")
    if not isinstance(value, str) or not value:
        return fallback
    path = Path(value).expanduser()
    if not path.exists() or not path.is_dir():
        return fallback
    return path


def _refresh_projection(
    campaign_root: Path,
    workspace_root: Path,
    claim: dict[str, Any],
) -> None:
    if workspace_root.resolve() == campaign_root.resolve():
        return
    turn_number = _turn_number_from_claim(claim)
    if turn_number is None:
        return
    try:
        from orchestrator.config import load_config as _load_aog_config
        from orchestrator.projection import refresh_projection_from_canonical
        from orchestrator.state import Agent

        role = str(claim.get("role") or "")
        actor = str(claim.get("actor") or "")
        agent = Agent(
            id=actor,
            display_name=actor,
            role="dm" if role == "dm" else "player",
        )
        refresh_projection_from_canonical(
            config=_load_aog_config(os.environ.get("GLASS_CONFIG")),
            campaign_root=campaign_root,
            agent=agent,
            turn_number=turn_number,
            projection_root=workspace_root,
        )
    except Exception:
        # Command success should remain authoritative; projection refresh is a
        # same-turn convenience and the next turn rebuilds from canonical state.
        return


def _turn_number_from_claim(claim: dict[str, Any]) -> int | None:
    raw = str(claim.get("turn_id") or "")
    marker = raw.rsplit("t", 1)
    if len(marker) != 2 or not marker[1].isdigit():
        return None
    return int(marker[1])


@contextlib.contextmanager
def _pushd(path: Path) -> Iterator[None]:
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)
