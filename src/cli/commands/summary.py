"""Summary file commands."""

from __future__ import annotations

from pathlib import Path

import click

from .. import workspace as _workspace
from ..campaign import (
    active_campaign_id,
    active_campaign_root,
    resolve_active_campaign_workspace,
)
from ..config import get_paths
from ..errors import GlassError, agent_instruction
from ..paths_resolve import display_path
from ..persistence import CampaignPersistence
from ..role import current_role
from ..state import append_audit, commit, current_mode_record, load_state, queue_event
from ..yaml_io import command_params, emit, read_body


@click.group()
def summary() -> None:
    """Campaign, arc/act, and scene summary files."""


@summary.command("show")
@click.argument("level", type=click.Choice(["campaign", "arc", "act", "scene"]))
@click.argument("target_id", required=False)
@click.option("--arc", "arc_id", default=None, help="Arc id for scene summaries.")
@click.pass_context
def summary_show(
    ctx: click.Context,
    level: str,
    target_id: str | None,
    arc_id: str | None,
) -> None:
    """Show a summary file without mutating it."""
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    workspace = resolve_active_campaign_workspace()
    path = _summary_path(workspace, level, target_id, arc_id=arc_id)
    body = path.read_text(encoding="utf-8") if path.exists() else ""
    result = {
        "level": "arc" if level == "act" else level,
        "path": display_path(path),
        "exists": path.exists(),
        "body": body,
    }
    append_audit(
        paths,
        state,
        ctx,
        "summary.show",
        command_params(level=level, target_id=target_id, arc=arc_id),
        result,
    )
    emit(result)


@summary.command("write")
@click.argument("level", type=click.Choice(["campaign", "arc", "act", "scene"]))
@click.argument("target_id", required=False)
@click.option("--arc", "arc_id", default=None, help="Arc id for scene summaries.")
@click.option("--body", help="Markdown body to write.")
@click.option("--from", "from_file", help="Read body from this file, or '-' for stdin.")
@click.pass_context
def summary_write(
    ctx: click.Context,
    level: str,
    target_id: str | None,
    arc_id: str | None,
    body: str | None,
    from_file: str | None,
) -> None:
    """DM-only: replace a summary file."""
    _write_summary(
        ctx,
        level,
        target_id,
        arc_id=arc_id,
        body=body,
        from_file=from_file,
        append=False,
    )


@summary.command("append")
@click.argument("level", type=click.Choice(["campaign", "arc", "act", "scene"]))
@click.argument("target_id", required=False)
@click.option("--arc", "arc_id", default=None, help="Arc id for scene summaries.")
@click.option("--body", help="Markdown body to append.")
@click.option("--from", "from_file", help="Read body from this file, or '-' for stdin.")
@click.pass_context
def summary_append(
    ctx: click.Context,
    level: str,
    target_id: str | None,
    arc_id: str | None,
    body: str | None,
    from_file: str | None,
) -> None:
    """DM-only: append to a summary file."""
    _write_summary(
        ctx,
        level,
        target_id,
        arc_id=arc_id,
        body=body,
        from_file=from_file,
        append=True,
    )


def _write_summary(
    ctx: click.Context,
    level: str,
    target_id: str | None,
    *,
    arc_id: str | None,
    body: str | None,
    from_file: str | None,
    append: bool,
) -> None:
    role = current_role()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    workspace = resolve_active_campaign_workspace()
    _assert_summary_write_allowed(
        role,
        state,
        level,
        target_id,
        append=append,
    )
    path = _summary_path(workspace, level, target_id, arc_id=arc_id)
    text = read_body(body, from_file).rstrip() + "\n"
    _assert_summary_body_allowed(role, level, append=append, text=text)
    path.parent.mkdir(parents=True, exist_ok=True)
    if append and path.exists():
        existing = path.read_text(encoding="utf-8")
        separator = "" if existing.endswith("\n") else "\n"
        path.write_text(existing + separator + text, encoding="utf-8")
        action = "summary.append"
    else:
        path.write_text(text, encoding="utf-8")
        action = "summary.write"
    persistence = CampaignPersistence(
        paths=paths,
        campaign_id=campaign_id,
        campaign_root=active_campaign_root(),
    )
    persisted = persistence.register_markdown(path, state=state, graph=False)
    resolved_level = "arc" if level == "act" else level
    queue_event(state, role.actor, f"{action} {resolved_level} {display_path(path)}")
    result = {
        "level": resolved_level,
        "path": display_path(path),
        "bytes": len(path.read_bytes()),
        "persistence": persisted.to_dict(),
    }
    commit(
        paths,
        state,
        ctx,
        action,
        command_params(
            level=level,
            target_id=target_id,
            arc=arc_id,
            bytes=result["bytes"],
        ),
        result,
    )


def _assert_summary_write_allowed(
    role,
    state: dict,
    level: str,
    target_id: str | None,
    *,
    append: bool,
) -> None:
    if role.can_do_anything or role.kind == "dm":
        return
    normalized = "arc" if level == "act" else level
    if role.kind != "player" or not append or normalized != "scene":
        raise GlassError(
            agent_instruction(
                "players may only append to the active scene summary",
                "Use `glass summary append scene --body <brief update>` from a player turn.",
                "Ask the DM to write arc/campaign summaries or replace summary files.",
            )
        )
    active = current_mode_record(state) or {}
    active_scene = str(active.get("scene_id") or "")
    requested = _workspace.slugify(target_id or active_scene)
    if not active_scene or requested != _workspace.slugify(active_scene):
        raise GlassError(
            agent_instruction(
                "players may only append to the active scene summary",
                "Append only to the current active scene; do not write summaries for inactive scenes from a player turn.",
            )
        )


def _assert_summary_body_allowed(role, level: str, *, append: bool, text: str) -> None:
    normalized = "arc" if level == "act" else level
    if role.kind == "player" and append and normalized == "scene":
        max_chars = 1500
        if len(text.strip()) > max_chars:
            raise GlassError(
                agent_instruction(
                    f"scene summary append is too long for a player turn ({len(text.strip())}/{max_chars} chars)",
                    "Keep the append to 2-4 sentences or bullets.",
                    "Use `glass done --summary` for compact turn continuity; do not duplicate a full transcript here.",
                )
            )


def _summary_path(
    workspace: _workspace.CampaignWorkspace,
    level: str,
    target_id: str | None,
    *,
    arc_id: str | None,
) -> Path:
    normalized = "arc" if level == "act" else level
    if normalized == "campaign":
        return workspace.root / "summary.md"
    state = _workspace.load_campaign_state(workspace)
    if normalized == "arc":
        arc = _workspace.slugify(target_id or state.get("active_arc") or "")
        if not arc:
            raise GlassError(
                agent_instruction(
                    "arc summary needs an arc id or active arc",
                    "Pass the arc id, or activate the intended arc before reading/writing its summary.",
                )
            )
        return workspace.arc_dir(arc) / "summary.md"
    if normalized == "scene":
        scene = _workspace.slugify(target_id or state.get("active_scene") or "")
        if not scene:
            raise GlassError(
                agent_instruction(
                    "scene summary needs a scene id or active scene",
                    "Pass the scene id, or create/activate the intended scene first.",
                )
            )
        arc = _resolve_scene_arc(workspace, state, scene, arc_id)
        return workspace.scene_dir(arc, scene) / "summary.md"
    raise GlassError(
        agent_instruction(
            f"unknown summary level {level!r}",
            "Use one of: campaign, arc, act, scene.",
        )
    )


def _resolve_scene_arc(
    workspace: _workspace.CampaignWorkspace,
    state: dict,
    scene_id: str,
    arc_id: str | None,
) -> str:
    if arc_id:
        return _workspace.slugify(arc_id)
    active_scene = state.get("active_scene")
    if active_scene == scene_id and state.get("active_scene_arc"):
        return str(state["active_scene_arc"])
    if state.get("active_arc"):
        candidate = workspace.scene_dir(str(state["active_arc"]), scene_id)
        if candidate.exists():
            return str(state["active_arc"])
    matches = []
    if workspace.arcs_dir.exists():
        for arc_dir in workspace.arcs_dir.iterdir():
            if (arc_dir / "scenes" / scene_id).exists():
                matches.append(arc_dir.name)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise GlassError(
            agent_instruction(
                f"cannot find scene {scene_id!r}",
                "Pass `--arc <arc-id>` if the scene belongs to a specific arc, or create the scene first.",
            )
        )
    raise GlassError(
        agent_instruction(
            f"scene {scene_id!r} exists in multiple arcs: {', '.join(sorted(matches))}",
            "Pass `--arc <arc-id>` to choose the intended scene summary path.",
        )
    )
