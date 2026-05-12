"""Active campaign resolution + Postgres connection helper.

These helpers bridge the CLI to the running campaign workspace and the
Postgres backend. `active_campaign_id` is the source of truth for the
DB scope; `pg_connection` is the context manager every PG-touching
command goes through.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from . import db as _db
from . import workspace as _workspace
from .config import get_paths, load_config
from .errors import GlassError, agent_instruction


def active_campaign_id() -> str:
    """Return the campaign id for character/roll DB scope.

    Resolves from GLASS_CAMPAIGN_ID, then the most-recently-modified campaign
    workspace under paths.campaigns. Raises GlassError if neither is available.
    """
    explicit = os.environ.get("GLASS_CAMPAIGN_ID")
    if explicit:
        return explicit
    paths = get_paths()
    if paths.campaigns is None:
        raise GlassError(
            agent_instruction(
                "active campaign is required",
                "Run from a campaign workspace, set `GLASS_CAMPAIGN_ID=<campaign-id>`, or configure `paths.campaigns` in `agents-of-glass.toml`.",
            )
        )
    try:
        return _workspace.resolve_active_campaign(paths.campaigns).campaign_id
    except FileNotFoundError as exc:
        raise GlassError(
            agent_instruction(
                str(exc),
                "Start the campaign with `aog campaign run <campaign-id>` or set `GLASS_CAMPAIGN_ID` to an existing campaign.",
            )
        ) from exc


def active_campaign_root() -> Path:
    """Return the filesystem root of the active campaign workspace.

    Falls back to paths.content (templates) when no campaign is active —
    used for tests and dev where the runtime workspace doesn't exist.
    """
    explicit = os.environ.get("GLASS_CAMPAIGN_ID")
    paths = get_paths()
    if paths.campaigns is None:
        return paths.content
    try:
        if explicit:
            return _workspace.resolve_active_campaign(
                paths.campaigns, env_id=explicit
            ).root
        return _workspace.resolve_active_campaign(paths.campaigns).root
    except FileNotFoundError:
        return paths.content


def lookup_player_character_id(campaign_id: str, player_id: str) -> str | None:
    """Look up the character id for a player in the active campaign. Returns
    None if the player has no character or has multiple."""
    try:
        with pg_connection() as conn:
            characters = _db.character_list(conn, campaign_id)
    except GlassError:
        return None
    candidates = [c["character_id"] for c in characters if c.get("player_id") == player_id]
    if len(candidates) == 1:
        return candidates[0]
    return None


@contextmanager
def pg_connection() -> Iterator[Any]:
    """Open a Postgres connection from the resolved config."""
    pg_config = _db.load_pg_config(load_config())
    try:
        with _db.connect(pg_config) as conn:
            yield conn
    except GlassError:
        raise
    except Exception as exc:
        raise GlassError(
            agent_instruction(
                f"postgres connection failed ({pg_config.describe()})",
                "Ensure Postgres is running and the campaign database settings are correct.",
                "Run `glass db status` or `glass db migrate` after fixing the connection.",
                f"Connection detail: {exc}",
            )
        ) from exc


def resolve_active_campaign_workspace() -> _workspace.CampaignWorkspace:
    """Used by arc/scene/lore commands. GlassError-friendly wrapper around
    workspace.resolve_active_campaign."""
    paths = get_paths()
    if paths.campaigns is None:
        raise GlassError(
            agent_instruction(
                "`paths.campaigns` is not configured",
                "Configure `paths.campaigns` in `agents-of-glass.toml` or run from an orchestrated campaign environment.",
            )
        )
    env_id = os.environ.get("GLASS_CAMPAIGN_ID")
    try:
        return _workspace.resolve_active_campaign(paths.campaigns, env_id=env_id)
    except FileNotFoundError as exc:
        raise GlassError(
            agent_instruction(
                str(exc),
                "Start the campaign with `aog campaign run <campaign-id>` or set `GLASS_CAMPAIGN_ID` to an existing campaign.",
            )
        ) from exc
