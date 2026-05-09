"""Mode commands."""

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
    active_session_file,
    active_session_id,
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
    session_dir,
    state_path,
    state_summary,
    transcript_path,
    write_active_session,
)
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
def mode() -> None:
    """Mode stack commands."""


@mode.command("start")
@click.argument("mode_name")
@click.argument("scene_id")
@click.pass_context
def mode_start(ctx: click.Context, mode_name: str, scene_id: str) -> None:
    role = require_dm()
    paths = get_paths()
    state = load_state(paths)
    record = {
        "mode": slugify(mode_name),
        "scene_id": slugify(scene_id),
        "started_at": now_iso(),
        "started_by": role.actor,
    }
    state["mode_stack"].append(record)
    queue_event(
        state,
        role.actor,
        f"mode start {record['mode']} @ {record['scene_id']}",
    )
    result = {
        "current_mode": record["mode"],
        "current_scene": record["scene_id"],
        "mode_stack": state["mode_stack"],
    }
    commit(
        paths,
        state,
        ctx,
        "mode.start",
        command_params(mode_name=mode_name, scene_id=scene_id),
        result,
    )


@mode.command("end")
@click.pass_context
def mode_end(ctx: click.Context) -> None:
    role = require_dm()
    paths = get_paths()
    state = load_state(paths)
    if not state["mode_stack"]:
        raise GlassError("cannot end mode: mode stack is empty")
    ended = state["mode_stack"].pop()
    ended["ended_at"] = now_iso()
    current = current_mode_record(state)
    queue_event(
        state,
        role.actor,
        f"mode end {ended['mode']} @ {ended['scene_id']}",
    )
    result = {
        "ended": ended,
        "current_mode": current["mode"] if current else None,
        "current_scene": current["scene_id"] if current else None,
        "mode_stack": state["mode_stack"],
    }
    commit(paths, state, ctx, "mode.end", {}, result)


@mode.command("current")
@click.pass_context
def mode_current(ctx: click.Context) -> None:
    paths = get_paths()
    state = load_state(paths)
    current = current_mode_record(state)
    result = {
        "current_mode": current["mode"] if current else None,
        "current_scene": current["scene_id"] if current else None,
        "mode_stack": state["mode_stack"],
    }
    append_audit(paths, state, ctx, "mode.current", {}, result)
    emit(result)


