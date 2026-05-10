"""Arc commands."""

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


_campaign_workspace = resolve_active_campaign_workspace


@click.group()
def arc() -> None:
    """Arc lifecycle (DM-only): create, list, current."""


@arc.command("create")
@click.argument("arc_id")
@click.pass_context
def arc_create(ctx: click.Context, arc_id: str) -> None:
    require_dm()
    workspace = _campaign_workspace()
    try:
        arc_dir = _workspace.create_arc(workspace, arc_id)
    except (FileExistsError, ValueError) as exc:
        raise GlassError(str(exc)) from exc
    result = {
        "campaign_id": workspace.campaign_id,
        "arc_id": arc_id,
        "path": str(arc_dir),
        "files": ["plan.md", "context.md", "scenes/"],
    }
    emit(result)


@arc.command("list")
@click.pass_context
def arc_list(ctx: click.Context) -> None:
    workspace = _campaign_workspace()
    arcs = _workspace.list_arcs(workspace)
    emit({"campaign_id": workspace.campaign_id, "arcs": arcs})


@arc.command("current")
@click.pass_context
def arc_current(ctx: click.Context) -> None:
    workspace = _campaign_workspace()
    current = _workspace.current_arc(workspace)
    emit({"campaign_id": workspace.campaign_id, "active_arc": current})


@arc.command("activate")
@click.argument("arc_id")
@click.pass_context
def arc_activate(ctx: click.Context, arc_id: str) -> None:
    require_dm()
    workspace = _campaign_workspace()
    try:
        arc_dir = _workspace.activate_arc(workspace, arc_id)
    except (FileNotFoundError, ValueError) as exc:
        raise GlassError(str(exc)) from exc
    emit(
        {
            "campaign_id": workspace.campaign_id,
            "active_arc": arc_id,
            "path": str(arc_dir),
        }
    )

