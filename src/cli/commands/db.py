"""Db commands."""

from __future__ import annotations

import json
import os
import random
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

from .. import db as _db
from .. import workspace as _workspace
from ..campaign import (
    active_campaign_id,
    active_campaign_root,
    lookup_player_character_id,
    pg_connection,
    resolve_active_campaign_workspace,
)
from ..config import REPO_ROOT, Paths, get_paths, load_config
from ..constants import (
    ATTRIBUTE_TIERS,
    ATTRIBUTES,
    RISK_THRESHOLDS,
    SKILL_TIERS,
    STARTER_MESSAGE_TYPES,
)
from ..entities import (
    markdown_title,
    parse_frontmatter,
    parse_sections,
    upsert_entity_from_path,
)
from ..errors import GlassError
from ..ids import new_id, now_iso, slugify
from ..messages import (
    infer_player_from_path,
    load_message_types,
    message_visible_to,
    player_dirs,
    require_message_type,
    require_recipient,
    roster,
)
from ..paths_resolve import (
    clean_relative_path,
    display_path,
    ensure_under,
    ensure_under_any,
    resolve_content_path,
    resolve_note_write_path,
)
from ..role import (
    Role,
    actor_for_turn,
    assert_character_writable,
    current_role,
    require_dm,
    require_player,
    role_label_for_turn,
)
from ..state import (
    append_audit,
    audit_path,
    commit,
    current_mode_record,
    default_state,
    inline_event_lines,
    load_state,
    normalize_state,
    queue_event,
    save_state,
    state_path,
    state_summary,
    transcript_path,)
from ..validation import (
    assert_attribute_name,
    clamp,
    outcome_for_margin,
    validate_key_values,
)
from ..yaml_io import (
    command_params,
    emit,
    make_jsonable,
    read_body,
    to_yaml,
    yaml_scalar,
)


@click.group()
def db() -> None:
    """Postgres connection + migration runner."""


@db.command("migrate")
@click.pass_context
def db_migrate(ctx: click.Context) -> None:
    """Apply pending SQL migrations from the repo's migrations/ directory."""
    config = load_config()
    pg_config = _db.load_pg_config(config)
    try:
        with _db.connect(pg_config) as conn:
            actions = _db.migrate(conn)
    except Exception as exc:
        raise GlassError(f"db migrate failed against {pg_config.describe()}: {exc}") from exc

    result = {"target": pg_config.describe(), "actions": actions}
    # Best-effort audit: skip if no active session, or if the active-session
    # pointer is stale (points to a cleared/deleted session).
    paths = get_paths()
    try:
        campaign_id = active_campaign_id()
        state = load_state(paths, campaign_id)
    except GlassError:
        state = None
    if state is not None:
        append_audit(paths, state, ctx, "db.migrate", command_params(), result)
    emit(result)


@db.command("status")
@click.pass_context
def db_status(ctx: click.Context) -> None:
    """Show applied + pending migrations and any checksum mismatches."""
    config = load_config()
    pg_config = _db.load_pg_config(config)
    try:
        with _db.connect(pg_config) as conn:
            report = _db.status(conn)
    except Exception as exc:
        raise GlassError(f"db status failed against {pg_config.describe()}: {exc}") from exc
    report["target"] = pg_config.describe()
    emit(report)


# ============================================================================
# Campaign workspace: arc / scene / lore
# ============================================================================


def _campaign_workspace() -> _workspace.CampaignWorkspace:
    paths = get_paths()
    if paths.campaigns is None:
        raise GlassError("paths.campaigns is not configured")
    env_id = os.environ.get("GLASS_CAMPAIGN_ID")
    try:
        return _workspace.resolve_active_campaign(paths.campaigns, env_id=env_id)
    except FileNotFoundError as exc:
        raise GlassError(str(exc)) from exc

