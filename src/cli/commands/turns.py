"""Turns commands."""

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
def turns() -> None:
    """Corpus query commands."""


@turns.command("find")
@click.option("--scene")
@click.option("--speaker")
@click.option("--mode", "mode_name")
@click.option("--turn-id", type=int)
@click.option("--limit", type=int, default=20)
@click.pass_context
def turns_find(
    ctx: click.Context,
    scene: str | None,
    speaker: str | None,
    mode_name: str | None,
    turn_id: int | None,
    limit: int,
) -> None:
    paths = get_paths()
    state = load_state(paths)
    records = list(state.get("turns", []))
    if scene:
        records = [record for record in records if record["scene_id"] == scene]
    if speaker:
        records = [record for record in records if record["speaker"] == speaker]
    if mode_name:
        records = [record for record in records if record["mode"] == mode_name]
    if turn_id is not None:
        records = [record for record in records if record["turn_id"] == turn_id]
    records = records[-limit:]
    result = {"turns": records, "count": len(records)}
    append_audit(
        paths,
        state,
        ctx,
        "turns.find",
        command_params(
            scene=scene,
            speaker=speaker,
            mode=mode_name,
            turn_id=turn_id,
            limit=limit,
        ),
        result,
    )
    emit(result)


# ============================================================================
# Postgres / migrations
# ============================================================================


