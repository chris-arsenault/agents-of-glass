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
from ..config import REPO_ROOT, Paths, get_paths
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
def turns() -> None:
    """Corpus query commands."""


@turns.command("find")
@click.option("--scene")
@click.option("--speaker")
@click.option("--mode", "mode_name")
@click.option("--turn-id", type=int)
@click.option("--text", "text_query", help="Case-insensitive text search across turn prose/events.")
@click.option("--limit", type=int, default=20)
@click.pass_context
def turns_find(
    ctx: click.Context,
    scene: str | None,
    speaker: str | None,
    mode_name: str | None,
    turn_id: int | None,
    text_query: str | None,
    limit: int,
) -> None:
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    with pg_connection() as conn:
        records = _db.turn_list(
            conn,
            campaign_id=campaign_id,
            scene=scene,
            speaker=speaker,
            mode=mode_name,
            turn_id=turn_id,
            text=text_query,
            limit=limit,
            latest=turn_id is None,
        )
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
            text=text_query,
            limit=limit,
        ),
        result,
    )
    emit(result)


@turns.command("feed")
@click.option("--after-turn", type=int, default=0, show_default=True)
@click.option("--limit", type=int, default=50, show_default=True)
@click.pass_context
def turns_feed(ctx: click.Context, after_turn: int, limit: int) -> None:
    """Structured public turn feed for viewers/UI polling.

    This is the replacement for parsing transcript.md. Each returned item is
    stable, ordered, and already split into metadata, prose, and event lines.
    """
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    with pg_connection() as conn:
        turns = _db.turn_list(
            conn,
            campaign_id=campaign_id,
            after_turn=after_turn,
            limit=limit,
        )
    events = [
        {
            "event_type": "turn.committed",
            "campaign_id": turn.get("campaign_id") or campaign_id,
            "turn_id": turn["turn_id"],
            "scene_id": turn["scene_id"],
            "mode": turn["mode"],
            "speaker": turn["speaker"],
            "role": turn["role"],
            "created_at": turn.get("created_at") or turn.get("ts"),
            "payload": {
                "character_id": turn.get("character_id"),
                "prose": turn.get("prose") or _strip_turn_header(turn.get("markdown", "")),
                "event_summaries": turn.get("event_summaries", []),
                "events": turn.get("events", []),
                "markdown": turn.get("markdown", ""),
            },
        }
        for turn in turns
    ]
    result = {
        "campaign_id": campaign_id,
        "after_turn": after_turn,
        "events": events,
        "count": len(events),
        "next_after_turn": events[-1]["turn_id"] if events else after_turn,
    }
    append_audit(
        paths,
        state,
        ctx,
        "turns.feed",
        command_params(after_turn=after_turn, limit=limit),
        result,
    )
    emit(result)


def _strip_turn_header(markdown: str) -> str:
    lines = markdown.splitlines()
    if lines and lines[0].startswith("## Turn "):
        lines = lines[1:]
        if lines and not lines[0].strip():
            lines = lines[1:]
    return "\n".join(lines).strip()


def _turn_search_text(record: dict[str, Any]) -> str:
    parts = [
        str(record.get("prose") or ""),
        str(record.get("markdown") or ""),
    ]
    parts.extend(str(item) for item in record.get("event_summaries", []) or [])
    return "\n".join(parts)


# ============================================================================
# Postgres / migrations
# ============================================================================
