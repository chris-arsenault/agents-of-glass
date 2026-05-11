"""Opaque grants for the local glass API.

The API runs with operator credentials and receives commands from player
processes over localhost. Grants are the authorization boundary: each token is
campaign-bound, turn-bound, role-bound, short-lived, and restricted to the CLI
surface a player is allowed to use.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from .errors import GlassError


DEFAULT_API_URL = "http://127.0.0.1:8765"

_GRANT_FILE = ".glass-grants.json"
_DEFAULT_TTL_SECONDS = 7200

_PLAYER_ALLOWED: dict[str, set[str] | None] = {
    "character": None,
    "clock": {"list", "show"},
    "msg": None,
    "roll": None,
    "scene": {"tracker", "pressure"},
    "table": {"current", "show"},
    "entity": {
        "neighborhood",
        "similar",
        "find",
        "relations",
        "between",
        "edges",
        "stance",
        "claim",
    },
    "note": {"write", "propose"},
    "search": {"text", "semantic"},
    "turn": {"handoff"},
    "turns": {"find", "feed"},
    "summary": {"show", "append"},
    "sync": {"apply"},
    "tarot": {"current", "list"},
    "lore": {"list"},
}

_HELP_ARGS = {"-h", "--help"}
_ALWAYS_DENIED = {"api", "db"}


def mint_grant(
    campaigns_dir: Path,
    *,
    campaign_id: str,
    role: str,
    actor: str,
    glass_role: str,
    turn_id: str,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    workspace_root: Path | str | None = None,
    workspace_reader_user: str | None = None,
) -> str:
    """Create and persist a short-lived API grant."""

    token = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + ttl_seconds
    path = grant_store_path(campaigns_dir, campaign_id)
    data = _read_store(path)
    grants = data.setdefault("grants", {})
    _prune_expired(grants)
    grants[token] = {
        "campaign_id": campaign_id,
        "role": role,
        "actor": actor,
        "glass_role": glass_role,
        "turn_id": turn_id,
        "expires_at": expires_at,
        "created_at": int(time.time()),
    }
    if workspace_root is not None:
        grants[token]["workspace_root"] = str(workspace_root)
    if workspace_reader_user is not None:
        grants[token]["workspace_reader_user"] = workspace_reader_user
    _write_store(path, data)
    return token


def validate_grant(campaigns_dir: Path, token: str, args: list[str]) -> dict[str, Any]:
    """Return grant claims or raise GlassError."""

    if not token:
        raise GlassError("missing glass API grant")

    for path in _candidate_store_paths(campaigns_dir):
        data = _read_store(path)
        grants = data.get("grants", {})
        claim = grants.get(token)
        if not isinstance(claim, dict):
            continue
        if int(claim.get("expires_at", 0)) < int(time.time()):
            raise GlassError("expired glass API grant")
        _assert_command_allowed(claim, args)
        return claim

    raise GlassError("invalid glass API grant")


def grant_store_path(campaigns_dir: Path, campaign_id: str) -> Path:
    return campaigns_dir / campaign_id / _GRANT_FILE


def _candidate_store_paths(campaigns_dir: Path) -> list[Path]:
    if not campaigns_dir.exists():
        return []
    return [path / _GRANT_FILE for path in campaigns_dir.iterdir() if path.is_dir()]


def _assert_command_allowed(claim: dict[str, Any], args: list[str]) -> None:
    command = _first_command_token(args)
    if command is None:
        return
    if command in _HELP_ARGS:
        return
    if command in _ALWAYS_DENIED:
        raise GlassError(f"permission denied: glass {command} is not exposed over player API")

    role = str(claim.get("role", ""))
    if role != "player":
        return

    allowed = _PLAYER_ALLOWED.get(command)
    if allowed is None:
        if command in _PLAYER_ALLOWED:
            return
        raise GlassError(f"permission denied: player grant cannot run glass {command}")

    subcommand = _first_command_token(args[1:])
    if subcommand is None or subcommand in _HELP_ARGS or subcommand in allowed:
        return
    raise GlassError(
        f"permission denied: player grant cannot run glass {command} {subcommand}"
    )


def _first_command_token(args: list[str]) -> str | None:
    for arg in args:
        if arg in _HELP_ARGS:
            return arg
        if arg.startswith("-"):
            continue
        return arg
    return None


def _read_store(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"grants": {}}
    except json.JSONDecodeError as exc:
        raise GlassError(f"invalid glass API grant store: {path}: {exc}") from exc


def _write_store(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)


def _prune_expired(grants: dict[str, Any]) -> None:
    now = int(time.time())
    for token, claim in list(grants.items()):
        if not isinstance(claim, dict) or int(claim.get("expires_at", 0)) < now:
            grants.pop(token, None)
