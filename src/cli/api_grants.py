"""Opaque grants for the local glass API.

The API runs with operator credentials and receives commands from agent
processes over localhost. Grants are the authorization boundary: each token is
campaign-bound, turn-bound, role-bound, short-lived, and restricted to the CLI
surface an agent is allowed to use.

Grants are self-contained signed tokens. They do not create per-agent files,
workspace roots, prose paths, or closeout paths.
"""

from __future__ import annotations

import json
import os
import secrets
import time
import base64
import hashlib
import hmac
from pathlib import Path
from typing import Any

from .errors import GlassError, agent_instruction


DEFAULT_API_URL = "http://127.0.0.1:26001"

_DEFAULT_TTL_SECONDS = 7200

_PLAYER_ALLOWED: dict[str, set[str] | None] = {
    "check": None,
    "done": None,
    "fact": {"pack", "set"},
    "find": None,
    "lore": {"search", "read", "list"},
    "next": None,
    "beat": {"check", "start", "close", "convert"},
    "character": {
        "new",
        "get",
        "list",
        "bulk-get",
        "signature-add",
        "signature-status",
        "skill-declare",
        "set-hp",
        "award-xp",
        "level-up",
        "set-momentum",
        "inventory-add",
        "inventory-rm",
        "consequence-add",
        "consequence-list",
        "consequence-resolve",
    },
    "clock": {"list", "show"},
    "msg": None,
    "roll": None,
    "scene": {"clock", "tracker", "pressure"},
    "search": {"text", "semantic"},
    "turn": {"append", "audit", "end", "handoff"},
    "turns": {"find", "feed"},
    "tarot": {"current", "list"},
}
_DM_ALLOWED: dict[str, set[str] | None] = {
    "arc": None,
    "beat": None,
    "character": {
        "new",
        "get",
        "list",
        "bulk-get",
        "bulk-update",
        "signature-add",
        "signature-status",
        "skill-declare",
        "set-hp",
        "award-xp",
        "level-up",
        "set-momentum",
        "inventory-add",
        "inventory-rm",
        "consequence-add",
        "consequence-list",
        "consequence-resolve",
    },
    "check": None,
    "clock": None,
    "done": None,
    "fact": {"pack", "set"},
    "find": None,
    "lore": {"search", "read", "list"},
    "mode": None,
    "msg": None,
    "next": None,
    "quest": None,
    "roll": None,
    "scene": None,
    "search": {"text", "semantic"},
    "thread": None,
    "turn": {"append", "audit", "end", "handoff"},
    "turns": {"find", "feed"},
}

_HELP_ARGS = {"-h", "--help"}
_ALWAYS_DENIED = {"api", "campaign", "db", "sync", "table", "summary", "note"}


def mint_grant(
    campaigns_dir: Path,
    *,
    campaign_id: str,
    role: str,
    actor: str,
    glass_role: str,
    turn_id: str,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> str:
    """Create a short-lived signed API grant."""

    del campaigns_dir
    expires_at = int(time.time()) + ttl_seconds
    claim = {
        "campaign_id": campaign_id,
        "role": role,
        "actor": actor,
        "glass_role": glass_role,
        "turn_id": turn_id,
        "expires_at": expires_at,
        "created_at": int(time.time()),
        "nonce": secrets.token_urlsafe(16),
    }
    body = _b64encode(
        json.dumps(claim, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    signature = _sign(body)
    return f"{body}.{signature}"


def validate_grant(campaigns_dir: Path, token: str, args: list[str]) -> dict[str, Any]:
    """Return grant claims or raise GlassError."""
    del campaigns_dir

    if not token:
        raise GlassError(
            agent_instruction(
                "missing glass API grant",
                "Run Glass CLI commands through the orchestrated turn environment so the grant is supplied automatically.",
                "If you are doing operator maintenance, run the CLI directly instead of through the player API.",
            )
        )

    claim = _decode_token(token)
    if int(claim.get("expires_at", 0)) < int(time.time()):
        raise GlassError(
            agent_instruction(
                "expired glass API grant",
                "Stop using this stale turn environment and start a fresh orchestrated turn.",
            )
        )
    _assert_command_allowed(claim, args)
    return claim


def _decode_token(token: str) -> dict[str, Any]:
    try:
        body, signature = token.rsplit(".", 1)
    except ValueError as exc:
        raise GlassError(
            agent_instruction(
                "invalid glass API grant",
                "Use the API grant from the current orchestrated turn; do not reuse grants from older turns or other campaigns.",
            )
        ) from exc
    expected = _sign(body)
    if not hmac.compare_digest(signature, expected):
        raise GlassError(
            agent_instruction(
                "invalid glass API grant signature",
                "Use the API grant from the current orchestrated turn; do not reuse grants from older turns or other campaigns.",
            )
        )
    try:
        raw = json.loads(_b64decode(body).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise GlassError(
            agent_instruction(
                "invalid glass API grant payload",
                "Use the API grant from the current orchestrated turn; do not edit or reconstruct grant tokens.",
            )
        ) from exc
    if not isinstance(raw, dict):
        raise GlassError(
            agent_instruction(
                "invalid glass API grant payload",
                "Use the API grant from the current orchestrated turn; do not edit or reconstruct grant tokens.",
            )
        )
    return raw


def _assert_command_allowed(claim: dict[str, Any], args: list[str]) -> None:
    if any(arg in _HELP_ARGS for arg in args):
        return

    command = _first_command_token(args)
    if command is None:
        return
    if command in _ALWAYS_DENIED:
        raise GlassError(
            agent_instruction(
                f"`glass {command}` is not exposed over the player API",
                "Do not run maintenance commands from a player turn.",
                "Close the turn and ask the operator/DM to perform maintenance if needed.",
            )
        )

    role = str(claim.get("role", ""))
    if role == "player":
        command_allowed = _PLAYER_ALLOWED
        role_label = "player"
    elif role == "dm":
        command_allowed = _DM_ALLOWED
        role_label = "dm"
    else:
        return

    allowed = command_allowed.get(command)
    if allowed is None:
        if command in command_allowed:
            return
        raise GlassError(
            agent_instruction(
                f"{role_label} turns cannot run `glass {command}`",
                "Use one of the agent-facing commands allowed in the injected prompt.",
                "If the DM needs to act, close the turn with `glass done --summary <summary> --state <state change or no state change> --rolls <rolls or none> --next dm`.",
            )
        )

    subcommand = _first_command_token(args[1:])
    if subcommand is None or subcommand in _HELP_ARGS or subcommand in allowed:
        return
    raise GlassError(
        agent_instruction(
            f"{role_label} turns cannot run `glass {command} {subcommand}`",
            "Use an allowed agent-facing subcommand.",
            "If the DM needs this action, close the turn with `glass done --summary <summary> --state <state change or no state change> --rolls <rolls or none> --next dm`.",
        )
    )


def _first_command_token(args: list[str]) -> str | None:
    for arg in args:
        if arg in _HELP_ARGS:
            return arg
        if arg.startswith("-"):
            continue
        return arg
    return None


def _sign(body: str) -> str:
    return _b64encode(
        hmac.new(_grant_secret(), body.encode("ascii"), hashlib.sha256).digest()
    )


def _grant_secret() -> bytes:
    configured = os.environ.get("GLASS_API_SECRET", "").strip()
    if configured:
        return configured.encode("utf-8")
    config_path = os.environ.get("GLASS_CONFIG", "").strip()
    seed = f"agents-of-glass-local-api:{config_path}:{os.getuid()}"
    return hashlib.sha256(seed.encode("utf-8")).digest()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
