"""Session commands."""

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
def session() -> None:
    """Session lifecycle commands."""


@session.command("new")
@click.option("--campaign", required=True, help="Human-readable campaign name.")
@click.option("--session-id", help="Explicit session id. Defaults to campaign slug + timestamp.")
@click.pass_context
def session_new(ctx: click.Context, campaign: str, session_id: str | None) -> None:
    paths = get_paths()
    paths.sessions.mkdir(parents=True, exist_ok=True)
    if not session_id:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        session_id = f"{slugify(campaign)}-{stamp}"
    session_id = slugify(session_id)
    directory = session_dir(paths, session_id)
    if directory.exists():
        raise GlassError(f"session already exists: {session_id}")

    state = default_state(session_id, campaign)
    directory.mkdir(parents=True, exist_ok=False)
    transcript_path(paths, session_id).write_text(
        f"# {campaign}\n\nSession: `{session_id}`\n\n", encoding="utf-8"
    )
    (directory / "scene-framing.md").write_text("# Scene Framing\n\n", encoding="utf-8")
    save_state(paths, state)
    write_active_session(paths, session_id)
    result = {
        "session_id": session_id,
        "campaign": campaign,
        "status": "active",
        "path": display_path(directory),
        "active": True,
    }
    append_audit(paths, state, ctx, "session.new", command_params(campaign=campaign), result)
    emit(result)


@session.command("show")
@click.option("--session-id", help="Session id to show. Defaults to GLASS_SESSION_ID or active.")
@click.pass_context
def session_show(ctx: click.Context, session_id: str | None) -> None:
    paths = get_paths()
    state = load_state(paths, session_id)
    result = state_summary(state)
    append_audit(paths, state, ctx, "session.show", command_params(session_id=session_id), result)
    emit(result)


@session.command("list")
@click.pass_context
def session_list(ctx: click.Context) -> None:
    paths = get_paths()
    paths.sessions.mkdir(parents=True, exist_ok=True)
    active = active_session_id(paths, required=False)
    records = []
    for path in sorted(paths.sessions.iterdir()):
        if not path.is_dir():
            continue
        state_file = path / "state.json"
        if not state_file.exists():
            continue
        state = normalize_state(json.loads(state_file.read_text(encoding="utf-8")))
        records.append(
            {
                "session_id": state["session"]["id"],
                "campaign": state["session"]["campaign"],
                "status": state["session"]["status"],
                "updated_at": state["session"]["updated_at"],
                "active": state["session"]["id"] == active,
            }
        )
    result = {"sessions": records}
    if active:
        state = load_state(paths, active)
        append_audit(paths, state, ctx, "session.list", {}, result)
    emit(result)


@session.command("wrap")
@click.option("--summary", help="Session summary text.")
@click.option("--from", "from_file", help="Read summary from this file, or '-' for stdin.")
@click.pass_context
def session_wrap(ctx: click.Context, summary: str | None, from_file: str | None) -> None:
    require_dm()
    paths = get_paths()
    state = load_state(paths)
    body = read_body(summary, from_file).strip()
    state["session"]["status"] = "wrapped"
    state["session"]["wrapped_at"] = now_iso()
    state["session"]["summary"] = body
    result = {
        "session_id": state["session"]["id"],
        "status": "wrapped",
        "wrapped_at": state["session"]["wrapped_at"],
        "summary": body,
    }
    commit(paths, state, ctx, "session.wrap", command_params(summary=body), result)


