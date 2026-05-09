"""Scene commands."""

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
def scene() -> None:
    """Scene lifecycle (DM-only): create, end, current, list."""


@scene.command("create")
@click.argument("scene_id")
@click.option(
    "--type",
    "scene_type",
    required=True,
    help="Scene type / mode: town, social, exploration, investigation, combat, travel, montage, wrap.",
)
@click.option("--arc", "arc_id", default=None, help="Override active arc.")
@click.pass_context
def scene_create(
    ctx: click.Context, scene_id: str, scene_type: str, arc_id: str | None
) -> None:
    require_dm()
    workspace = _campaign_workspace()
    try:
        scene_dir = _workspace.create_scene(workspace, scene_id, scene_type, arc_id=arc_id)
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        raise GlassError(str(exc)) from exc
    result = {
        "campaign_id": workspace.campaign_id,
        "scene_id": scene_id,
        "scene_type": scene_type,
        "arc_id": arc_id or _workspace.load_campaign_state(workspace).get("active_scene_arc"),
        "path": str(scene_dir),
        "files": ["prep.md", "context.md", "transcript.md", "audit.jsonl"],
    }
    emit(result)


@scene.command("end")
@click.option("--summary", default=None,
              help="Scene summary written to arcs/<arc>/scenes/<scene>/summary.md.")
@click.option("--beats", default=None,
              help="Newline-separated bullets appended to shared/quest-log.md, "
                   "tagged with the scene + arc.")
@click.option("--xp", "xp_spec", default=None,
              help="XP awards: 'tev=2,sumi=1,renno=3'. Calls character "
                   "award-xp per entry with reason=\"scene end: <scene_id>\".")
@click.pass_context
def scene_end_cmd(
    ctx: click.Context,
    summary: str | None,
    beats: str | None,
    xp_spec: str | None,
) -> None:
    """End the active scene + bundle wrap-up writes.

    Atomic: writes summary, appends beats, awards XP, then marks the scene
    as no-longer-active in the campaign workspace state. Also clears any
    scene_closing_turns countdown — the scene is over.
    """
    role = require_dm()
    workspace = _campaign_workspace()
    state = load_state(get_paths())
    paths = get_paths()
    campaign_id = active_campaign_id()
    session_id = state["session"]["id"]

    current = _workspace.current_scene(workspace)
    if not current:
        raise GlassError("no active scene to end")
    scene_id = current["scene_id"]
    arc_id = current["arc_id"]

    summary_path: str | None = None
    if summary and summary.strip():
        summary_path = _write_scene_summary(workspace, arc_id, scene_id, summary.strip())

    beat_lines: list[str] = []
    if beats:
        for line in beats.splitlines():
            text = line.strip().lstrip("-*").strip()
            if text:
                _append_quest_beat(workspace, text, scene_id=scene_id, arc_id=arc_id)
                beat_lines.append(text)

    xp_awards: list[dict[str, Any]] = []
    if xp_spec:
        with pg_connection() as conn:
            for agent, delta in _parse_xp_spec(xp_spec):
                character_id = lookup_player_character_id(campaign_id, agent)
                if not character_id:
                    raise GlassError(
                        f"can't award xp to {agent!r}: no character row "
                        f"or multiple characters in campaign"
                    )
                try:
                    updated, before, after = _db.character_award_xp(
                        conn,
                        campaign_id=campaign_id,
                        character_id=character_id,
                        delta=delta,
                        actor=role.actor,
                        reason=f"scene end: {scene_id}",
                        session_id=session_id,
                        scene_id=scene_id,
                    )
                except LookupError:
                    raise GlassError(f"unknown character {character_id!r}") from None
                xp_awards.append({
                    "player": agent,
                    "character_id": character_id,
                    "delta": delta,
                    "xp_before": before,
                    "xp_after": after,
                    "level": updated["level"],
                })

    try:
        ended = _workspace.end_scene(workspace)
    except ValueError as exc:
        raise GlassError(str(exc)) from exc

    state["scene_closing_turns"] = None
    queue_event(
        state, role.actor,
        f"scene end: {ended}"
        + (f" (+{len(xp_awards)} xp awards)" if xp_awards else ""),
    )
    result = {
        "campaign_id": workspace.campaign_id,
        "ended_scene": ended,
        "summary_path": summary_path,
        "beats_logged": beat_lines,
        "xp_awards": xp_awards,
    }
    commit(
        paths, state, ctx, "scene.end",
        command_params(summary=summary, beats=beats, xp=xp_spec),
        result,
    )


# A "round" is one full cycle through the speaker order. For all current
# modes (character-creation, scene-play) the rotation is 5 agents long
# (4 players + DM). Action modes will customize this when they exist.
_AGENTS_PER_ROUND = 5


@scene.command("closing-down")
@click.option("--rounds", "round_budget", type=int, default=4, show_default=True,
              help="How many rounds (full cycles through the table) of soft "
                   "closing pressure.")
@click.option("--turns", "turn_budget", type=int, default=None,
              help="Escape hatch: raw agent-commit count (overrides --rounds).")
@click.pass_context
def scene_closing_down(
    ctx: click.Context, round_budget: int, turn_budget: int | None,
) -> None:
    """DM-only: declare the scene is closing down.

    Sets a countdown that surfaces in every subsequent TURN_START.md as
    "Scene closing — N rounds left" so players know to converge their
    threads. When the counter hits 0, agents see a "Final round" section
    instead. The DM closes with `glass scene end`.

    The countdown is informational pressure, not a hard cap — the DM is
    expected to actually call `glass scene end` when ready. The
    methodology says imperfect closure beats a forever-running scene.

    Use `--rounds N` for the typical case (1 round = ~5 agent turns).
    `--turns N` is an escape hatch for fine-grained control.
    """
    role = require_dm()
    if turn_budget is not None:
        if turn_budget <= 0:
            raise GlassError("--turns must be positive")
        commits = turn_budget
        unit_label = f"{turn_budget} turn(s)"
    else:
        if round_budget <= 0:
            raise GlassError("--rounds must be positive")
        commits = round_budget * _AGENTS_PER_ROUND
        unit_label = f"~{round_budget} round(s)"
    paths = get_paths()
    state = load_state(paths)
    # Stored as commits+1 because the orchestrator decrements once on the
    # commit of the DM's setting turn. The first non-DM turn that follows
    # sees the user-friendly value in TURN_START.
    state["scene_closing_turns"] = commits + 1
    queue_event(state, role.actor, f"scene closing down ({unit_label} left)")
    result = {
        "scene_closing_turns": commits,
        "rounds": round_budget if turn_budget is None else None,
    }
    commit(
        paths, state, ctx, "scene.closing-down",
        command_params(rounds=round_budget, turns=turn_budget), result,
    )


def _parse_xp_spec(spec: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for entry in spec.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "=" not in entry:
            raise GlassError(f"invalid xp award {entry!r}; expected agent=delta")
        agent, delta_text = entry.split("=", 1)
        agent = agent.strip()
        try:
            delta = int(delta_text.strip())
        except ValueError:
            raise GlassError(f"invalid xp delta {delta_text!r} (must be int)") from None
        out.append((agent, delta))
    return out


def _write_scene_summary(
    workspace: _workspace.CampaignWorkspace,
    arc_id: str | None,
    scene_id: str,
    body: str,
) -> str | None:
    if not arc_id:
        return None
    scene_dir = workspace.scene_dir(arc_id, scene_id)
    if not scene_dir.exists():
        scene_dir.mkdir(parents=True, exist_ok=True)
    path = scene_dir / "summary.md"
    header = f"# {scene_id} — summary\n\n"
    path.write_text(header + body.rstrip() + "\n", encoding="utf-8")
    return display_path(path)


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
    line = f"- {prefix}{text}\n"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line)
    return log_path


@scene.command("current")
@click.pass_context
def scene_current(ctx: click.Context) -> None:
    workspace = _campaign_workspace()
    emit({
        "campaign_id": workspace.campaign_id,
        "active_scene": _workspace.current_scene(workspace),
    })


@scene.command("list")
@click.option("--arc", "arc_id", default=None, help="List scenes in a specific arc (default: active).")
@click.pass_context
def scene_list(ctx: click.Context, arc_id: str | None) -> None:
    workspace = _campaign_workspace()
    scenes = _workspace.list_scenes(workspace, arc_id=arc_id)
    emit({"campaign_id": workspace.campaign_id, "arc_id": arc_id, "scenes": scenes})


