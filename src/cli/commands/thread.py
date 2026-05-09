"""Thread commands."""

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
def thread() -> None:
    """DM scaffolding thread commands."""


@thread.command("current")
@click.pass_context
def thread_current(ctx: click.Context) -> None:
    paths = get_paths()
    state = load_state(paths)
    result = {"threads": state.get("threads", {})}
    append_audit(paths, state, ctx, "thread.current", {}, result)
    emit(result)


@thread.command("beat")
@click.argument("thread_id")
@click.pass_context
def thread_beat(ctx: click.Context, thread_id: str) -> None:
    paths = get_paths()
    state = load_state(paths)
    record = state.get("threads", {}).get(thread_id)
    if not record:
        known = ", ".join(state["threads"]) or "none"
        raise GlassError(f"unknown thread {thread_id!r}; known threads: {known}")
    result = {"thread": record}
    append_audit(
        paths,
        state,
        ctx,
        "thread.beat",
        command_params(thread_id=thread_id),
        result,
    )
    emit(result)


@thread.command("advance")
@click.argument("thread_id")
@click.option("--note", default="")
@click.pass_context
def thread_advance(ctx: click.Context, thread_id: str, note: str) -> None:
    require_dm()
    paths = get_paths()
    state = load_state(paths)
    record = state.setdefault("threads", {}).setdefault(
        thread_id,
        {"thread_id": thread_id, "current_beat": 0, "history": []},
    )
    before = int(record.get("current_beat", 0))
    after = before + 1
    record["current_beat"] = after
    record.setdefault("history", []).append({"beat": after, "note": note, "ts": now_iso()})
    result = {"thread": record, "beat_before": before, "beat_after": after}
    commit(
        paths,
        state,
        ctx,
        "thread.advance",
        command_params(thread_id=thread_id, note=note),
        result,
    )


class MessageGroup(click.Group):
    """Allow both `glass msg read` and spec-shaped `glass msg <type> <to> <body>`."""

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        if args and args[0] in self.commands:
            return super().resolve_command(ctx, args)
        return super().resolve_command(ctx, ["send", *args])


