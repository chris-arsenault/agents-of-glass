"""Turn commands."""

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
def turn() -> None:
    """Turn append command."""


@turn.command("append")
@click.argument("markdown_file")
@click.option("--speaker")
@click.option("--role", "turn_role", type=click.Choice(["dm", "player", "operator"]))
@click.option("--mode", "mode_name")
@click.option("--scene", "scene_id")
@click.option("--character", "character_id")
@click.pass_context
def turn_append(
    ctx: click.Context,
    markdown_file: str,
    speaker: str | None,
    turn_role: str | None,
    mode_name: str | None,
    scene_id: str | None,
    character_id: str | None,
) -> None:
    paths = get_paths()
    state = load_state(paths)
    source = Path(markdown_file).expanduser()
    if not source.is_absolute():
        source = Path.cwd() / source
    if not source.exists():
        raise GlassError(f"turn markdown not found: {markdown_file}")
    body = source.read_text(encoding="utf-8").strip()
    role = current_role()
    speaker_id = actor_for_turn(role, speaker)
    resolved_role = role_label_for_turn(role, turn_role)
    current = current_mode_record(state)
    resolved_mode = mode_name or (current["mode"] if current else "none")
    resolved_scene = scene_id or (current["scene_id"] if current else "none")
    state["session"]["turn_counter"] = int(state["session"].get("turn_counter", 0)) + 1
    turn_id = state["session"]["turn_counter"]

    flushed: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for event in state.get("pending_events", []):
        if event.get("actor") == speaker_id or role.can_do_anything:
            flushed.append(event)
        else:
            remaining.append(event)
    state["pending_events"] = remaining

    header = (
        f"## Turn {turn_id} - {speaker_id} ({resolved_role}) - "
        f"{resolved_mode}, {resolved_scene}"
    )
    parts = [header, "", body]
    event_lines = inline_event_lines(flushed)
    if event_lines:
        parts.extend(["", *event_lines])
    turn_markdown = "\n".join(parts).rstrip() + "\n\n"
    with transcript_path(paths, state["session"]["id"]).open("a", encoding="utf-8") as handle:
        handle.write(turn_markdown)

    record = {
        "turn_id": turn_id,
        "session_id": state["session"]["id"],
        "scene_id": resolved_scene,
        "mode": resolved_mode,
        "speaker": speaker_id,
        "role": resolved_role,
        "character_id": character_id,
        "ts": now_iso(),
        "source_path": str(source),
        "event_summaries": [event["summary"] for event in flushed],
        "markdown": turn_markdown,
    }
    state["turns"].append(record)
    result = {
        "turn": {key: value for key, value in record.items() if key != "markdown"},
        "events_flushed": flushed,
        "transcript_path": display_path(transcript_path(paths, state["session"]["id"])),
    }
    commit(
        paths,
        state,
        ctx,
        "turn.append",
        command_params(markdown_file=markdown_file, speaker=speaker_id),
        result,
    )


_HANDOFF_AGENT_IDS = ("dm", "tev", "sumi", "renno", "kit")
_PLAYER_AGENT_IDS = ("tev", "sumi", "renno", "kit")


@turn.command("handoff")
@click.argument("agent_id")
@click.pass_context
def turn_handoff(ctx: click.Context, agent_id: str) -> None:
    """Append a one-off override to the next-speaker queue.

    Each call appends; multiple calls in a single turn queue up multiple
    redirects in the order called. The orchestrator pops one off per
    turn. After the queue is drained, round-robin resumes from the last
    redirected agent.

    Example: a DM in their turn calls `glass turn handoff sumi` then
    `glass turn handoff dm`. Sumi runs next, then the DM, then rotation
    continues from the DM (dm -> next-in-rotation).
    """
    if agent_id not in _HANDOFF_AGENT_IDS:
        raise GlassError(
            f"unknown agent id {agent_id!r}; valid: {', '.join(_HANDOFF_AGENT_IDS)}"
        )
    paths = get_paths()
    state = load_state(paths)
    role = current_role()
    state["next_speakers"].append({"agent": agent_id})
    queue_event(state, role.actor, f"handoff -> {agent_id}")
    result = {"queue": list(state["next_speakers"])}
    commit(
        paths, state, ctx, "turn.handoff",
        command_params(agent_id=agent_id), result,
    )


@turn.command("rapid-round")
@click.argument("prompt_parts", nargs=-1, required=True)
@click.option("--players", "players_csv", default=None,
              help="Comma-separated player ids (subset of tev,sumi,renno,kit). "
                   "Order matters. Defaults to all four in declaration order.")
@click.pass_context
def turn_rapid_round(
    ctx: click.Context, prompt_parts: tuple[str, ...], players_csv: str | None,
) -> None:
    """DM-only: queue a single-shot rapid response from each player.

    Each queued turn sees the prompt in TURN_START.md and is told to give
    a brief reactive narration only — no rolls, no full menu, no handoff.
    Use this when the DM needs each player's character to react to the
    same stimulus quickly without spending a full per-player turn.
    """
    require_dm()
    if players_csv:
        targets = [p.strip() for p in players_csv.split(",") if p.strip()]
    else:
        targets = list(_PLAYER_AGENT_IDS)
    for player in targets:
        if player not in _PLAYER_AGENT_IDS:
            raise GlassError(
                f"unknown player {player!r}; valid: {', '.join(_PLAYER_AGENT_IDS)}"
            )
    paths = get_paths()
    state = load_state(paths)
    role = current_role()
    prompt = " ".join(prompt_parts).strip()
    if not prompt:
        raise GlassError("rapid-round prompt cannot be empty")
    for player in targets:
        state["next_speakers"].append({
            "agent": player,
            "rapid_prompt": prompt,
        })
    queue_event(
        state, role.actor,
        f"rapid-round queued for {','.join(targets)}: {prompt[:60]}",
    )
    result = {"queue": list(state["next_speakers"]), "prompt": prompt}
    commit(
        paths, state, ctx, "turn.rapid-round",
        command_params(prompt=prompt, players=targets), result,
    )


@turn.command("restart-order")
@click.argument("agent_id")
@click.pass_context
def turn_restart_order(ctx: click.Context, agent_id: str) -> None:
    """DM-only: clear any pending handoff queue + redirect to AGENT_ID.

    Use this when the rotation needs a hard reset — e.g., a player went
    out of order and you want to restart from a specific PC. Round-robin
    resumes from the new agent on subsequent turns.
    """
    require_dm()
    if agent_id not in _HANDOFF_AGENT_IDS:
        raise GlassError(
            f"unknown agent id {agent_id!r}; valid: {', '.join(_HANDOFF_AGENT_IDS)}"
        )
    paths = get_paths()
    state = load_state(paths)
    role = current_role()
    cleared = list(state["next_speakers"])
    state["next_speakers"] = [{"agent": agent_id}]
    queue_event(state, role.actor, f"restart turn order -> {agent_id}")
    result = {"cleared": cleared, "queue": list(state["next_speakers"])}
    commit(
        paths, state, ctx, "turn.restart-order",
        command_params(agent_id=agent_id), result,
    )


@turn.command("clear-handoff")
@click.pass_context
def turn_clear_handoff(ctx: click.Context) -> None:
    """DM-only: wipe any pending handoff queue (rare — usually the
    orchestrator consumes entries automatically on each turn)."""
    require_dm()
    paths = get_paths()
    state = load_state(paths)
    previous = list(state.get("next_speakers", []))
    state["next_speakers"] = []
    result = {"cleared": previous}
    commit(paths, state, ctx, "turn.clear-handoff", {}, result)


