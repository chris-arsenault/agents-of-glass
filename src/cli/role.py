"""Role identity + auth gates for the CLI.

GLASS_ROLE env determines the caller's identity:
  unset/empty → operator (can do anything)
  "dm"         → DM
  "player:tev" → player tev (etc.)
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .errors import GlassError


@dataclass(frozen=True)
class Role:
    kind: str
    actor: str
    raw: str | None

    @property
    def can_do_anything(self) -> bool:
        return self.kind == "operator"


def current_role() -> Role:
    raw = os.environ.get("GLASS_ROLE")
    if raw is None or raw == "":
        return Role(kind="operator", actor="operator", raw=raw)
    if raw == "dm":
        return Role(kind="dm", actor="dm", raw=raw)
    if raw.startswith("player:"):
        actor = raw.split(":", 1)[1].strip()
        if actor:
            return Role(kind="player", actor=actor, raw=raw)
    if raw.startswith("player_"):
        actor = raw.split("_", 1)[1].strip()
        if actor:
            return Role(kind="player", actor=actor, raw=raw)
    raise GlassError(
        "invalid GLASS_ROLE: expected unset/operator, 'dm', or 'player:<id>' "
        f"(got {raw!r})"
    )


def require_dm() -> Role:
    role = current_role()
    if role.can_do_anything or role.kind == "dm":
        return role
    raise GlassError("permission denied: this command is DM-only")


def require_player() -> Role:
    role = current_role()
    if role.can_do_anything or role.kind == "player":
        return role
    raise GlassError("permission denied: this command is player-only")


def role_label_for_turn(role: Role, explicit_role: str | None) -> str:
    if explicit_role:
        return explicit_role
    if role.kind == "dm":
        return "dm"
    if role.kind == "player":
        return "player"
    return "operator"


def actor_for_turn(role: Role, speaker: str | None) -> str:
    if speaker:
        return speaker
    return role.actor


def assert_character_writable(character: dict) -> Role:
    """Permission gate for character mutations.

    DM/operator can write any character. Players can write only their own.
    Raises GlassError otherwise. Returns the resolved current Role.
    """
    role = current_role()
    if role.can_do_anything or role.kind == "dm":
        return role
    if role.kind == "player" and character.get("player_id") == role.actor:
        return role
    raise GlassError(
        "permission denied: players may mutate only their own character "
        f"(owner: {character.get('player_id')})"
    )
