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
from ..outcomes import (
    append_outcome_section,
    normalize_outcomes,
    outcome_section,
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
    """Arc lifecycle (DM-only): create, close, list, current."""


@arc.command("create")
@click.argument("arc_id")
@click.pass_context
def arc_create(ctx: click.Context, arc_id: str) -> None:
    require_dm()
    workspace = _campaign_workspace()
    paths = get_paths()
    try:
        arc_dir = _workspace.create_arc(workspace, arc_id)
    except (FileExistsError, ValueError) as exc:
        raise GlassError(str(exc)) from exc
    state = load_state(paths, workspace.campaign_id)
    normalized_arc_id = _workspace.slugify(arc_id)
    queue_event(state, "dm", f"arc create: {normalized_arc_id}")
    result = {
        "campaign_id": workspace.campaign_id,
        "arc_id": normalized_arc_id,
        "path": str(arc_dir),
        "files": ["plan.md", "context.md", "scenes/"],
    }
    commit(paths, state, ctx, "arc.create", command_params(arc_id=arc_id), result)


@arc.command("list")
@click.pass_context
def arc_list(ctx: click.Context) -> None:
    workspace = _campaign_workspace()
    paths = get_paths()
    state = load_state(paths, workspace.campaign_id)
    arcs = _workspace.list_arcs(workspace)
    result = {"campaign_id": workspace.campaign_id, "arcs": arcs}
    append_audit(paths, state, ctx, "arc.list", command_params(), result)
    emit(result)


@arc.command("current")
@click.pass_context
def arc_current(ctx: click.Context) -> None:
    workspace = _campaign_workspace()
    paths = get_paths()
    state = load_state(paths, workspace.campaign_id)
    current = _workspace.current_arc(workspace)
    result = {"campaign_id": workspace.campaign_id, "active_arc": current}
    append_audit(paths, state, ctx, "arc.current", command_params(), result)
    emit(result)


@arc.command("activate")
@click.argument("arc_id")
@click.pass_context
def arc_activate(ctx: click.Context, arc_id: str) -> None:
    require_dm()
    workspace = _campaign_workspace()
    paths = get_paths()
    try:
        arc_dir = _workspace.activate_arc(workspace, arc_id)
    except (FileNotFoundError, ValueError) as exc:
        raise GlassError(str(exc)) from exc
    state = load_state(paths, workspace.campaign_id)
    normalized_arc_id = _workspace.slugify(arc_id)
    queue_event(state, "dm", f"arc activate: {normalized_arc_id}")
    result = {
        "campaign_id": workspace.campaign_id,
        "active_arc": normalized_arc_id,
        "path": str(arc_dir),
    }
    commit(paths, state, ctx, "arc.activate", command_params(arc_id=arc_id), result)


@arc.command("close")
@click.argument("arc_id", required=False)
@click.option("--summary", default=None,
              help="Arc/act summary written to arcs/<arc>/summary.md.")
@click.option("--outcome", "outcome_values", multiple=True, required=True,
              help="Repeat 1-2 times. In-universe act outcome/consequence bullet.")
@click.pass_context
def arc_close(
    ctx: click.Context,
    arc_id: str | None,
    summary: str | None,
    outcome_values: tuple[str, ...],
) -> None:
    require_dm()
    workspace = _campaign_workspace()
    paths = get_paths()
    state = load_state(paths, workspace.campaign_id)

    current_scene = _workspace.current_scene(workspace)
    if current_scene:
        raise GlassError(
            "cannot close an arc while a scene is active; end the scene first"
        )

    if arc_id is None:
        current_arc = _workspace.current_arc(workspace)
        if not current_arc:
            raise GlassError("no active arc to close; pass an arc id")
        normalized_arc_id = str(current_arc["arc_id"])
    else:
        normalized_arc_id = _workspace.slugify(arc_id)

    arc_dir = workspace.arc_dir(normalized_arc_id)
    if not arc_dir.exists():
        raise GlassError(f"arc {normalized_arc_id!r} does not exist")

    outcome_lines = normalize_outcomes(outcome_values)
    summary_path = _write_arc_summary(
        workspace,
        normalized_arc_id,
        summary.strip() if summary else None,
        outcome_lines,
    )

    closed_arcs = state.setdefault("closed_arcs", [])
    if normalized_arc_id not in closed_arcs:
        closed_arcs.append(normalized_arc_id)
    if state.get("active_arc") == normalized_arc_id:
        state["active_arc"] = None

    queue_event(state, "dm", f"arc close: {normalized_arc_id}")
    result = {
        "campaign_id": workspace.campaign_id,
        "closed_arc": normalized_arc_id,
        "summary_path": summary_path,
        "outcomes": outcome_lines,
        "active_arc": state.get("active_arc"),
    }
    commit(
        paths,
        state,
        ctx,
        "arc.close",
        command_params(
            arc_id=arc_id,
            summary=summary,
            outcomes=outcome_lines,
        ),
        result,
    )


def _write_arc_summary(
    workspace: _workspace.CampaignWorkspace,
    arc_id: str,
    summary: str | None,
    outcomes: list[str],
) -> str:
    arc_dir = workspace.arc_dir(arc_id)
    arc_dir.mkdir(parents=True, exist_ok=True)
    path = arc_dir / "summary.md"
    header = f"# {arc_id} - summary\n\n"
    if summary:
        body = header + append_outcome_section(summary, outcomes)
    elif path.exists():
        body = append_outcome_section(path.read_text(encoding="utf-8"), outcomes)
    else:
        body = header + outcome_section(outcomes)
    path.write_text(body.rstrip() + "\n", encoding="utf-8")
    return display_path(path)
