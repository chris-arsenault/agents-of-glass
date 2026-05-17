"""Quest commands."""

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
from ..errors import GlassError, agent_instruction
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
def quest() -> None:
    """Party-visible story log: beats."""


@quest.command("beat")
@click.argument("text_parts", nargs=-1, required=True)
@click.option("--scene", "scene_id", default=None, help="Scene id tag (defaults to active).")
@click.option("--arc", "arc_id", default=None, help="Arc id tag (defaults to active).")
@click.pass_context
def quest_beat(
    ctx: click.Context,
    text_parts: tuple[str, ...],
    scene_id: str | None,
    arc_id: str | None,
) -> None:
    """DM-only: append a story-shifting beat to shared/quest-log.md.

    A beat is a real campaign-shifting moment — an NPC's allegiance flips,
    a clock lands, a faction makes a move, a character commits. Not
    bookkeeping. Beats are party-visible canon for what happened in the
    campaign; the corpus consumes them.

    Bundled into `glass scene end --beats` for end-of-scene logging.
    """
    role = require_dm()
    text = " ".join(text_parts).strip()
    if not text:
        raise GlassError(
            agent_instruction(
                "quest beat text cannot be empty",
                "Pass one concrete campaign-shifting beat after the command, for example `glass quest beat <what changed>`.",
            )
        )
    workspace = _campaign_workspace()
    current = _workspace.current_scene(workspace) or {}
    scene = scene_id or current.get("scene_id")
    arc = arc_id or current.get("arc_id")
    beat_lines = [
        line.strip().lstrip("-*").strip()
        for line in _split_quest_beat_lines(text)
    ]
    beat_lines = [line for line in beat_lines if line]
    if not beat_lines:
        raise GlassError(
            agent_instruction(
                "quest beat text cannot be empty",
                "Pass one concrete campaign-shifting beat after the command, for example `glass quest beat <what changed>`.",
            )
        )
    log_path: Path | None = None
    for beat_text in beat_lines:
        log_path = _append_quest_beat(workspace, beat_text, scene_id=scene, arc_id=arc)
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    queue_event(state, role.actor, f"beat: {beat_lines[0][:60]}")
    result = {
        "log_path": display_path(log_path) if log_path else None,
        "scene_id": scene,
        "arc_id": arc,
        "text": "\n".join(beat_lines),
        "beats": beat_lines,
    }
    commit(
        paths, state, ctx, "quest.beat",
        command_params(scene=scene, arc=arc, text=text), result,
    )


def _append_quest_beat(
    workspace: _workspace.CampaignWorkspace,
    text: str,
    *,
    scene_id: str | None = None,
    arc_id: str | None = None,
) -> Path:
    log_path = workspace.root / "shared" / "quest-log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not log_path.exists():
        log_path.write_text(
            "---\ntitle: Quest Log\n---\n\n"
            "# Quest Log\n\n"
            "Party-visible log of story-shifting beats. Appended to via "
            "`glass quest beat` and `glass scene end --beats`.\n\n",
            encoding="utf-8",
        )
    tag_parts = []
    if arc_id:
        tag_parts.append(arc_id)
    if scene_id:
        tag_parts.append(scene_id)
    prefix = f"[{':'.join(tag_parts)}] " if tag_parts else ""
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"- {prefix}{text}\n")
    return log_path


def _split_quest_beat_lines(text: str) -> list[str]:
    normalized = (
        text.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
    )
    return normalized.splitlines()
