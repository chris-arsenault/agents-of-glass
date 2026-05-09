"""Message bus helpers + player roster."""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any

from .config import Paths
from .constants import STARTER_MESSAGE_TYPES
from .errors import GlassError
from .role import Role


def player_dirs(paths: Paths) -> list[str]:
    players_root = paths.content / "players"
    if not players_root.exists():
        return []
    return sorted(path.name for path in players_root.iterdir() if path.is_dir())


def roster(paths: Paths, state: dict[str, Any] | None = None) -> list[str]:
    return sorted(set(player_dirs(paths)))


def infer_player_from_path(paths: Paths, path: Path) -> str | None:
    try:
        rel = path.resolve().relative_to(paths.content.resolve())
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) >= 3 and parts[0] == "players" and parts[2] == "drafts":
        return parts[1]
    return None


def load_message_types(paths: Paths) -> set[str]:
    vocab_path = paths.content / "shared" / "vocabulary" / "message-types.md"
    if not vocab_path.exists():
        return set(STARTER_MESSAGE_TYPES)
    text = vocab_path.read_text(encoding="utf-8")
    found = set(re.findall(r"`([a-z][a-z0-9-]*)`", text))
    for line in text.splitlines():
        match = re.match(r"\s*[-*]\s+([a-z][a-z0-9-]*)(?:\s*[-:;.]|\s*$)", line)
        if match and match.group(1) not in {"stub"}:
            found.add(match.group(1))
    return found or set(STARTER_MESSAGE_TYPES)


def require_message_type(paths: Paths, message_type: str) -> None:
    valid = load_message_types(paths)
    if message_type in valid:
        return
    suggestion = difflib.get_close_matches(message_type, sorted(valid), n=1)
    suffix = f" Did you mean {suggestion[0]!r}?" if suggestion else ""
    raise GlassError(
        f"unknown message type {message_type!r}; valid types: {', '.join(sorted(valid))}.{suffix}"
    )


def require_recipient(paths: Paths, state: dict[str, Any], recipient: str) -> None:
    valid = {"dm", "party", *roster(paths, state)}
    if recipient in valid:
        return
    options = ", ".join(sorted(valid))
    raise GlassError(f"unknown recipient {recipient!r}; valid recipients: {options}")


def message_visible_to(message: dict[str, Any], role: Role) -> bool:
    if role.can_do_anything or role.kind == "dm":
        return True
    if role.kind != "player":
        return False
    recipient = message["recipient"]
    return (
        recipient == "party"
        or recipient == role.actor
        or message["sender"] == role.actor
    )
