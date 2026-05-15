"""Arc commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from .. import db as _db
from .. import workspace as _workspace
from ..campaign import (
    pg_connection,
    resolve_active_campaign_workspace,
)
from ..config import get_paths
from ..entities import (
    parse_frontmatter,
    parse_sections,
)
from ..errors import GlassError, agent_instruction
from ..ids import now_iso
from ..outcomes import (
    append_outcome_section,
    normalize_outcomes,
    outcome_section,
)
from ..paths_resolve import display_path
from ..role import require_dm
from ..state import (
    append_audit,
    commit,
    load_state,
    queue_event,
)
from ..yaml_io import (
    command_params,
    emit,
)


_campaign_workspace = resolve_active_campaign_workspace


@click.group()
def arc() -> None:
    """Arc lifecycle (DM-only): create, check, close, list, current."""


@arc.command("create")
@click.argument("arc_id")
@click.option(
    "--pull-source",
    required=True,
    help="Non-adjacent real-world source/domain used to shape this arc.",
)
@click.option(
    "--pull-utilization",
    required=True,
    help="Where the source's concrete details appear in the arc pressure.",
)
@click.pass_context
def arc_create(
    ctx: click.Context,
    arc_id: str,
    pull_source: str,
    pull_utilization: str,
) -> None:
    require_dm()
    pull_source = _require_text(pull_source, "--pull-source")
    pull_utilization = _require_concrete_note(
        pull_utilization,
        "--pull-utilization",
        "Name the arc element changed by the pull: threat, node, clock, "
        "scarcity, strong start, clue, hazard, or end-state pressure.",
    )
    workspace = _campaign_workspace()
    paths = get_paths()
    try:
        arc_dir = _workspace.create_arc(workspace, arc_id)
    except FileExistsError as exc:
        raise GlassError(
            agent_instruction(
                str(exc),
                "Use the existing arc with `glass arc activate <arc-id>`, or choose a new arc id.",
            )
        ) from exc
    except ValueError as exc:
        raise GlassError(
            agent_instruction(
                str(exc),
                "Use a slug-like arc id, then retry `glass arc create <arc-id> "
                "--pull-source <source> --pull-utilization <note>`.",
            )
        ) from exc
    state = load_state(paths, workspace.campaign_id)
    normalized_arc_id = _workspace.slugify(arc_id)
    pull_note = _write_arc_pull_note(
        arc_dir,
        arc_id=normalized_arc_id,
        pull_source=pull_source,
        pull_utilization=pull_utilization,
    )
    queue_event(state, "dm", f"arc create: {normalized_arc_id} (pull note recorded)")
    result = {
        "campaign_id": workspace.campaign_id,
        "arc_id": normalized_arc_id,
        "path": str(arc_dir),
        "files": ["plan.md", "context.md", "pulls.md", "scenes/"],
        "pull_note": {
            "source": pull_source,
            "utilization": pull_utilization,
            "path": display_path(pull_note),
        },
    }
    commit(
        paths,
        state,
        ctx,
        "arc.create",
        command_params(
            arc_id=arc_id,
            pull_source=pull_source,
            pull_utilization=pull_utilization,
        ),
        result,
    )


def _write_arc_pull_note(
    arc_dir: Path,
    *,
    arc_id: str,
    pull_source: str,
    pull_utilization: str,
) -> Path:
    path = arc_dir / "pulls.md"
    body = "\n".join(
        [
            "---",
            f"title: {arc_id} Non-Adjacent Pull",
            "status: authored",
            "type: arc-pull-utilization",
            "---",
            "",
            "# Non-Adjacent Pull Utilization",
            "",
            f"- **Source/domain:** {pull_source}",
            f"- **Utilization:** {pull_utilization}",
            f"- **Recorded:** {now_iso()}",
            "",
        ]
    )
    path.write_text(body, encoding="utf-8")
    return path


def _require_text(value: str, option_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise GlassError(
            agent_instruction(
                f"{option_name} is required",
                f"Provide a non-empty value for `{option_name}`.",
            )
        )
    return cleaned


def _require_concrete_note(value: str, option_name: str, instruction: str) -> str:
    cleaned = _require_text(value, option_name)
    if len(cleaned.split()) < 6:
        raise GlassError(
            agent_instruction(
                f"{option_name} is too vague",
                instruction,
            )
        )
    return cleaned


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


@arc.command("close-check")
@click.argument("arc_id", required=False)
@click.pass_context
def arc_close_check(ctx: click.Context, arc_id: str | None) -> None:
    """DM-only: report whether an arc is ready to close."""
    require_dm()
    workspace = _campaign_workspace()
    paths = get_paths()
    state = load_state(paths, workspace.campaign_id)

    if arc_id is None:
        current_arc = _workspace.current_arc(workspace)
        if not current_arc:
            raise GlassError(
                agent_instruction(
                    "there is no active arc to check",
                    "Pass an arc id explicitly, or activate the intended arc with `glass arc activate <arc-id>`.",
                )
            )
        normalized_arc_id = str(current_arc["arc_id"])
    else:
        normalized_arc_id = _workspace.slugify(arc_id)

    arc_dir = workspace.arc_dir(normalized_arc_id)
    if not arc_dir.exists():
        raise GlassError(
            agent_instruction(
                f"arc {normalized_arc_id!r} does not exist",
                "Use an arc id from `glass arc list`, or create the arc first "
                "with `glass arc create <arc-id> --pull-source <source> "
                "--pull-utilization <note>`.",
            )
        )

    active_scene = _workspace.current_scene(workspace)
    required_before_close: list[str] = []
    recommended_before_close: list[str] = []
    if active_scene:
        required_before_close.append(
            f"active scene `{active_scene['scene_id']}` is still open; end it before closing an arc"
        )

    with pg_connection() as conn:
        arc_clocks = _db.clock_list(
            conn,
            campaign_id=workspace.campaign_id,
            scope="arc",
            anchor_id=normalized_arc_id,
            include_archived=True,
        )
    active_clocks = [clock for clock in arc_clocks if clock.get("status") == "active"]
    if active_clocks:
        required_before_close.append(
            "resolve or archive active arc clocks: "
            + ", ".join(str(clock["clock_id"]) for clock in active_clocks)
        )

    plan_status = _markdown_close_status(
        arc_dir / "plan.md",
        stub_markers=("_TBD._",),
    )
    context_status = _markdown_close_status(
        arc_dir / "context.md",
        stub_markers=("_Player-facing summary.",),
    )
    summary_status = _markdown_close_status(
        arc_dir / "summary.md",
        stub_markers=("_Running arc summary.",),
    )
    done_criteria = _plan_done_criteria_status(arc_dir / "plan.md")

    if not plan_status["meaningful"]:
        recommended_before_close.append("arc plan is missing or still stubbed")
    if not context_status["meaningful"]:
        recommended_before_close.append("arc context is missing or still stubbed")
    if not summary_status["meaningful"]:
        recommended_before_close.append(
            "arc summary is missing or still stubbed; write/update it during closeout"
        )
    if not done_criteria["meaningful"]:
        recommended_before_close.append(
            "done criteria are missing or still stubbed; name why the arc closes, continues, or reframes"
        )

    scenes = _arc_scene_summary_statuses(arc_dir)
    missing_scene_summaries = [
        scene["scene_id"]
        for scene in scenes
        if not scene["summary"]["meaningful"]
    ]
    if missing_scene_summaries:
        recommended_before_close.append(
            "scene summaries missing or still stubbed: "
            + ", ".join(missing_scene_summaries)
        )

    closed_arcs = {str(item) for item in state.get("closed_arcs", [])}
    result = {
        "campaign_id": workspace.campaign_id,
        "arc_id": normalized_arc_id,
        "closed": normalized_arc_id in closed_arcs,
        "ready_to_close": not required_before_close,
        "required_before_close": required_before_close,
        "recommended_before_close": recommended_before_close,
        "active_scene": active_scene,
        "arc_files": {
            "plan": plan_status,
            "context": context_status,
            "summary": summary_status,
            "done_criteria": done_criteria,
        },
        "scene_count": len(scenes),
        "scenes": scenes,
        "arc_clocks": arc_clocks,
        "active_arc_clocks": active_clocks,
        "arc_decision": {
            "choose": ["continue", "close", "reframe"],
            "record": (
                "Record the arc decision and reason in `glass done --state`. "
                "If closing, follow `methodologies/closeout.md` Act Close Sequence."
            ),
        },
    }
    append_audit(
        paths,
        state,
        ctx,
        "arc.close-check",
        command_params(arc_id=arc_id),
        result,
    )
    emit(result)


def _markdown_close_status(
    path: Path,
    *,
    stub_markers: tuple[str, ...],
) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {
            "path": display_path(path),
            "exists": False,
            "meaningful": False,
            "stub": True,
        }
    frontmatter = parse_frontmatter(text)
    stripped = text.strip()
    stub = frontmatter.get("status") == "stub" or any(
        marker in text for marker in stub_markers
    )
    return {
        "path": display_path(path),
        "exists": True,
        "meaningful": bool(stripped) and not stub,
        "stub": stub,
    }


def _plan_done_criteria_status(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {
            "path": display_path(path),
            "exists": False,
            "meaningful": False,
            "stub": True,
        }
    sections = parse_sections(text, "arc-plan")
    body = ""
    for section in sections:
        if "done criteria" in str(section.get("title", "")).lower():
            body = str(section.get("text") or "").strip()
            break
    stub = not body or "_TBD._" in body
    return {
        "path": display_path(path),
        "exists": True,
        "meaningful": bool(body) and not stub,
        "stub": stub,
    }


def _arc_scene_summary_statuses(arc_dir: Path) -> list[dict[str, Any]]:
    scenes_root = arc_dir / "scenes"
    if not scenes_root.exists():
        return []
    statuses: list[dict[str, Any]] = []
    for scene_dir in sorted(path for path in scenes_root.iterdir() if path.is_dir()):
        statuses.append(
            {
                "scene_id": scene_dir.name,
                "summary": _markdown_close_status(
                    scene_dir / "summary.md",
                    stub_markers=("_Scene summary is finalized",),
                ),
            }
        )
    return statuses


@arc.command("activate")
@click.argument("arc_id")
@click.pass_context
def arc_activate(ctx: click.Context, arc_id: str) -> None:
    require_dm()
    workspace = _campaign_workspace()
    paths = get_paths()
    try:
        arc_dir = _workspace.activate_arc(workspace, arc_id)
    except FileNotFoundError as exc:
        raise GlassError(
            agent_instruction(
                str(exc),
                "Create the arc first with `glass arc create <arc-id> "
                "--pull-source <source> --pull-utilization <note>`, or activate "
                "an arc returned by `glass arc list`.",
            )
        ) from exc
    except ValueError as exc:
        raise GlassError(
            agent_instruction(
                str(exc),
                "Use the slug-like arc id shown by `glass arc list`.",
            )
        ) from exc
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
            agent_instruction(
                "cannot close an arc while a scene is active",
                "End the active scene first with `glass scene end --outcome <outcome>`.",
                "Then run `glass arc close <arc-id> --outcome <outcome>`.",
            )
        )

    if arc_id is None:
        current_arc = _workspace.current_arc(workspace)
        if not current_arc:
            raise GlassError(
                agent_instruction(
                    "there is no active arc to close",
                    "Pass the arc id explicitly, or activate the intended arc with `glass arc activate <arc-id>` before closing it.",
                )
            )
        normalized_arc_id = str(current_arc["arc_id"])
    else:
        normalized_arc_id = _workspace.slugify(arc_id)

    arc_dir = workspace.arc_dir(normalized_arc_id)
    if not arc_dir.exists():
        raise GlassError(
            agent_instruction(
                f"arc {normalized_arc_id!r} does not exist",
                "Use an arc id from `glass arc list`, or create the arc first "
                "with `glass arc create <arc-id> --pull-source <source> "
                "--pull-utilization <note>`.",
            )
        )

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
