"""Role identity + auth gates for the CLI.

GLASS_ROLE env determines the caller's identity:
  unset/empty → operator (can do anything)
  "dm"         → DM
  "player:tev" → player tev (etc.)
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .errors import GlassError, agent_instruction


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
        agent_instruction(
            f"invalid GLASS_ROLE {raw!r}",
            "Run agent CLI commands with `GLASS_ROLE=dm` for Mara, `GLASS_ROLE=player:<id>` for a player, or leave it unset only for operator maintenance.",
            "Use player ids such as `tev`, `sumi`, `renno`, or `kit`.",
        )
    )


def require_dm() -> Role:
    role = current_role()
    if role.can_do_anything or role.kind == "dm":
        return role
    raise GlassError(
        agent_instruction(
            "this command is DM-only",
            "Do not run this command from a player turn.",
            "If the DM needs to perform this action, close the current player turn with `glass done --summary <summary> --state <state change or no state change> --rolls <rolls or none> --next dm`.",
        )
    )


def require_player() -> Role:
    role = current_role()
    if role.can_do_anything or role.kind == "player":
        return role
    raise GlassError(
        agent_instruction(
            "this command is player-only",
            "Do not run this command from a DM turn.",
            "Use a player turn for this action, or choose the DM-facing command for the same intent.",
        )
    )


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
        agent_instruction(
            "players may mutate only their own character",
            f"This character belongs to `{character.get('player_id')}`; use your own character id for player-side updates.",
            "If another character must change, end the turn with `--next dm` and ask the DM to make the update.",
        )
    )
