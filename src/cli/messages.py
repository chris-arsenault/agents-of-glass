"""Message bus helpers + player roster."""

from __future__ import annotations

import difflib
import os
import re
from pathlib import Path
from typing import Any

from .config import Paths
from .constants import STARTER_MESSAGE_TYPES
from .errors import GlassError, agent_instruction
from .role import Role


def player_dirs(paths: Paths) -> list[str]:
    players_root = paths.content / "players"
    if not players_root.exists():
        return []
    return sorted(path.name for path in players_root.iterdir() if path.is_dir())


def roster(paths: Paths, state: dict[str, Any] | None = None) -> list[str]:
    runtime_players = _runtime_player_ids(state)
    if runtime_players:
        return runtime_players
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
    instructions_path = paths.content / "instructions" / "message-bus.md"
    if not instructions_path.exists():
        return set(STARTER_MESSAGE_TYPES)
    text = instructions_path.read_text(encoding="utf-8")
    found = set(
        re.findall(r"^### `([a-z][a-z0-9-]*)`", text, flags=re.MULTILINE)
    )
    return found or set(STARTER_MESSAGE_TYPES)


def require_message_type(paths: Paths, message_type: str) -> None:
    valid = load_message_types(paths)
    if message_type in valid:
        return
    suggestion = difflib.get_close_matches(message_type, sorted(valid), n=1)
    suffix = f" Did you mean {suggestion[0]!r}?" if suggestion else ""
    raise GlassError(
        agent_instruction(
            f"unknown message type {message_type!r}",
            f"Use one of: {', '.join(sorted(valid))}.{suffix}",
            "Send the message as `glass msg <type> <recipient> <body>`.",
        )
    )


def require_recipient(paths: Paths, state: dict[str, Any], recipient: str) -> str:
    if recipient in {"dm", "party"}:
        return recipient
    valid_players = roster(paths, state)
    if recipient in valid_players:
        return recipient
    _, character_to_player = _character_alias_maps(paths, state)
    if recipient in character_to_player:
        return character_to_player[recipient]
    options = ", ".join(_recipient_display_options(paths, valid_players, state))
    raise GlassError(
        agent_instruction(
            f"unknown recipient {recipient!r}",
            f"Use one of: {options}.",
            "Use `party` for the whole group, `dm` for Mara, or a listed player/character id for a private recipient.",
        )
    )


def canonicalize_actor_reference(
    paths: Paths,
    state: dict[str, Any],
    actor: str | None,
) -> str | None:
    if actor is None or actor in {"dm", "party"}:
        return actor
    if actor in roster(paths, state):
        return actor
    _, character_to_player = _character_alias_maps(paths, state)
    return character_to_player.get(actor, actor)


def render_message_identities(
    paths: Paths,
    state: dict[str, Any],
    message: dict[str, Any],
) -> dict[str, Any]:
    if not _prefer_character_aliases():
        return dict(message)
    player_to_character, _character_to_player = _character_alias_maps(paths, state)

    def alias(value: Any) -> Any:
        if not isinstance(value, str) or value in {"dm", "party"}:
            return value
        return player_to_character.get(value, value)

    rendered = dict(message)
    rendered["sender"] = alias(rendered.get("sender"))
    rendered["recipient"] = alias(rendered.get("recipient"))
    return rendered


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


def _runtime_player_ids(state: dict[str, Any] | None) -> list[str]:
    campaign_id = str((state or {}).get("campaign") or "").strip()
    if not campaign_id:
        return []
    try:
        from . import db as _db
        from .campaign import pg_connection

        with pg_connection() as conn:
            characters = _db.character_list(conn, campaign_id)
    except Exception:
        return []
    players = {
        str(character.get("player_id") or "").strip()
        for character in characters
        if character.get("player_id")
    }
    return sorted(player for player in players if player)


def _character_alias_maps(
    paths: Paths,
    state: dict[str, Any],
) -> tuple[dict[str, str], dict[str, str]]:
    from .campaign import lookup_player_character_id

    player_to_character: dict[str, str] = {}
    character_to_player: dict[str, str] = {}
    for player_id in roster(paths, state):
        character_id = lookup_player_character_id(state["campaign"], player_id)
        if not character_id:
            continue
        player_to_character[player_id] = character_id
        character_to_player[character_id] = player_id
    return player_to_character, character_to_player


def _recipient_display_options(
    paths: Paths,
    valid_players: list[str],
    state: dict[str, Any],
) -> list[str]:
    options: list[str] = ["dm", "party"]
    if _prefer_character_aliases():
        player_to_character, _character_to_player = _character_alias_maps(paths, state)
        options.extend(player_to_character.get(player_id, player_id) for player_id in valid_players)
    else:
        options.extend(valid_players)
    return sorted(set(options))


def _prefer_character_aliases() -> bool:
    return os.environ.get("AOG_PLAYER_SURFACE") == "character"
