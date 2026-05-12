"""Player-agent-visible table-state commands."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import click

from .. import workspace as _workspace
from ..campaign import (
    active_campaign_id,
    active_campaign_root,
    resolve_active_campaign_workspace,
)
from ..errors import GlassError, agent_instruction
from ..config import get_paths
from ..ids import now_iso
from ..paths_resolve import clean_relative_path, display_path, ensure_under
from ..persistence import CampaignPersistence
from ..role import require_dm
from ..state import append_audit, commit, load_state, queue_event
from ..yaml_io import command_params, emit, read_body


@click.group()
def table() -> None:
    """Current player-agent-visible table state and named artifacts."""


@table.command("current")
@click.pass_context
def table_current(ctx: click.Context) -> None:
    """Show the live table location and files."""
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    workspace = resolve_active_campaign_workspace()
    root = workspace.table_dir
    current = _workspace.current_scene(workspace)
    files = _table_files(root)
    result = {
        "campaign_id": campaign_id,
        "active_scene": current,
        "path": display_path(root),
        "scene": display_path(root / "scene.md"),
        "handouts": display_path(root / "handouts"),
        "files": files,
    }
    append_audit(paths, state, ctx, "table.current", {}, result)
    emit(result)


@table.command("show")
@click.argument("path_text", required=False, default="")
@click.pass_context
def table_show(ctx: click.Context, path_text: str) -> None:
    """Read a player-agent-visible table file, or list table files."""
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    workspace = resolve_active_campaign_workspace()
    path = _resolve_table_path(workspace.table_dir, path_text, allow_root=True)
    if path.is_dir():
        files = _table_files(path)
        result = {"path": display_path(path), "files": files}
    else:
        if not path.exists():
            raise GlassError(
                agent_instruction(
                    f"table file does not exist: {display_path(path)}",
                    "Run `glass table current` or `glass table show` to see existing table files.",
                    "If this is a new visible artifact, the DM should create it with `glass table write <path>.md --body <markdown>`.",
                )
            )
        result = {
            "path": display_path(path),
            "body": path.read_text(encoding="utf-8"),
        }
    append_audit(paths, state, ctx, "table.show", command_params(path=path_text), result)
    emit(result)


@table.command("write")
@click.argument("path_text")
@click.option("--body", help="Markdown body to write.")
@click.option("--from", "from_file", help="Read body from this file, or '-' for stdin.")
@click.pass_context
def table_write(
    ctx: click.Context, path_text: str, body: str | None, from_file: str | None
) -> None:
    """DM-only: replace a player-agent-visible table file."""
    role = require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    workspace = resolve_active_campaign_workspace()
    path = _resolve_table_path(workspace.table_dir, path_text)
    if path.exists() and path.is_dir():
        raise GlassError(
            agent_instruction(
                f"table destination is a directory: {display_path(path)}",
                "Write to a markdown file under the table, such as `scene.md`, `handouts/<slug>.md`, or `<kind>-<slug>.md`.",
            )
        )
    text = read_body(body, from_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    persistence = CampaignPersistence(
        paths=paths,
        campaign_id=campaign_id,
        campaign_root=active_campaign_root(),
    )
    persisted = persistence.register_markdown(path, state=state, graph=False)
    queue_event(state, role.actor, f"table write {display_path(path)}")
    result = {
        "path": display_path(path),
        "bytes": len(text.encode("utf-8")),
        "persistence": persisted.to_dict(),
    }
    commit(
        paths,
        state,
        ctx,
        "table.write",
        command_params(path=path_text, bytes=result["bytes"]),
        result,
    )


@table.command("append")
@click.argument("path_text")
@click.option("--body", help="Markdown body to append.")
@click.option("--from", "from_file", help="Read body from this file, or '-' for stdin.")
@click.pass_context
def table_append(
    ctx: click.Context, path_text: str, body: str | None, from_file: str | None
) -> None:
    """DM-only: append to a player-agent-visible table file."""
    role = require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    workspace = resolve_active_campaign_workspace()
    path = _resolve_table_path(workspace.table_dir, path_text)
    if path.exists() and path.is_dir():
        raise GlassError(
            agent_instruction(
                f"table destination is a directory: {display_path(path)}",
                "Append to a markdown file under the table, such as `scene.md`, `handouts/<slug>.md`, or `<kind>-<slug>.md`.",
            )
        )
    text = read_body(body, from_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = ""
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            prefix = "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(prefix + text)
    persistence = CampaignPersistence(
        paths=paths,
        campaign_id=campaign_id,
        campaign_root=active_campaign_root(),
    )
    persisted = persistence.register_markdown(path, state=state, graph=False)
    queue_event(state, role.actor, f"table append {display_path(path)}")
    result = {
        "path": display_path(path),
        "bytes": len(text.encode("utf-8")),
        "persistence": persisted.to_dict(),
    }
    commit(
        paths,
        state,
        ctx,
        "table.append",
        command_params(path=path_text, bytes=result["bytes"]),
        result,
    )


@table.command("use")
@click.argument("source_path")
@click.option(
    "--as",
    "table_path",
    default=None,
    help="Destination path under table/. Defaults to the source filename.",
)
@click.pass_context
def table_use(ctx: click.Context, source_path: str, table_path: str | None) -> None:
    """DM-only: copy visible campaign lore or markdown onto the active table."""
    role = require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    workspace = resolve_active_campaign_workspace()
    campaign_root = active_campaign_root().resolve()
    source_rel = clean_relative_path(source_path)
    if source_rel.parts and source_rel.parts[0] == "table":
        raise GlassError(
            agent_instruction(
                "the source is already on the table",
                "Use `glass table append <path> --body <markdown>` to add to it, or `glass table write <path> --body <markdown>` to replace it.",
            )
        )
    source = ensure_under(
        (campaign_root / source_rel).resolve(),
        campaign_root,
        "table source paths must stay under the active campaign",
    )
    if not source.exists() or not source.is_file():
        raise GlassError(
            agent_instruction(
                f"table source file does not exist: {display_path(source)}",
                "Choose an existing campaign markdown file, or create the visible artifact directly with `glass table write <path>.md --body <markdown>`.",
            )
        )
    if source.suffix.lower() != ".md":
        raise GlassError(
            agent_instruction(
                "table source must be a markdown file",
                "Use a `.md` campaign file as the source, or create a new table artifact with `glass table write <path>.md --body <markdown>`.",
            )
        )
    destination_name = table_path or source.name
    destination = _resolve_table_path(workspace.table_dir, destination_name)
    if destination.exists() and destination.is_dir():
        raise GlassError(
            agent_instruction(
                f"table destination is a directory: {display_path(destination)}",
                "Choose a markdown file destination under the table, such as `handouts/<slug>.md` or `<kind>-<slug>.md`.",
            )
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    persistence = CampaignPersistence(
        paths=paths,
        campaign_id=campaign_id,
        campaign_root=campaign_root,
    )
    persisted = persistence.register_markdown(destination, state=state, graph=False)
    queue_event(
        state,
        role.actor,
        f"table use {display_path(source)} -> {display_path(destination)}",
    )
    result = {
        "source": display_path(source),
        "path": display_path(destination),
        "bytes": destination.stat().st_size,
        "persistence": persisted.to_dict(),
    }
    commit(
        paths,
        state,
        ctx,
        "table.use",
        command_params(source_path=source_path, table_path=table_path),
        result,
    )


@table.command("snapshot")
@click.option("--label", default="snapshot", help="Archive label.")
@click.pass_context
def table_snapshot(ctx: click.Context, label: str) -> None:
    """DM-only: snapshot the live table into the active scene archive."""
    role = require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    workspace = resolve_active_campaign_workspace()
    current = _workspace.current_scene(workspace)
    if not current:
        raise GlassError(
            agent_instruction(
                "there is no active scene to snapshot the table into",
                "Start or activate the scene first, then retry `glass table snapshot`.",
                "If the scene is already over, use `glass table archive` only while a scene is active.",
            )
        )
    try:
        destination = _workspace.snapshot_table(
            workspace,
            arc_id=str(current["arc_id"]),
            scene_id=str(current["scene_id"]),
            label=label,
        )
    except FileNotFoundError as exc:
        raise GlassError(
            agent_instruction(
                str(exc),
                "Make sure the active scene has a table directory before snapshotting.",
                "Use `glass table write scene.md --body <markdown>` to create the live table content first.",
            )
        ) from exc
    queue_event(state, role.actor, f"table snapshot {display_path(destination)}")
    result = {
        "path": display_path(destination),
        "label": label,
        "snapshot_at": now_iso(),
    }
    commit(
        paths,
        state,
        ctx,
        "table.snapshot",
        command_params(label=label),
        result,
    )


@table.command("archive")
@click.option(
    "--keep-live",
    is_flag=True,
    help="Archive final table without replacing live table with an inactive pointer.",
)
@click.pass_context
def table_archive(ctx: click.Context, keep_live: bool) -> None:
    """DM-only: archive the live table as the active scene's final table."""
    role = require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    workspace = resolve_active_campaign_workspace()
    current = _workspace.current_scene(workspace)
    if not current:
        raise GlassError(
            agent_instruction(
                "there is no active scene to archive the table into",
                "Run table archive before ending the scene, or start/activate the intended scene before archiving.",
            )
        )
    try:
        destination = _workspace.archive_table(
            workspace,
            arc_id=str(current["arc_id"]),
            scene_id=str(current["scene_id"]),
            clear_live=not keep_live,
        )
    except FileNotFoundError as exc:
        raise GlassError(
            agent_instruction(
                str(exc),
                "Make sure the active scene has live table content before archiving.",
                "Use `glass table write scene.md --body <markdown>` or create named table artifacts first.",
            )
        ) from exc
    queue_event(state, role.actor, f"table archive {display_path(destination)}")
    result = {"path": display_path(destination), "live_cleared": not keep_live}
    commit(
        paths,
        state,
        ctx,
        "table.archive",
        command_params(keep_live=keep_live),
        result,
    )


def _resolve_table_path(root: Path, path_text: str, *, allow_root: bool = False) -> Path:
    if path_text:
        rel = clean_relative_path(path_text)
    elif allow_root:
        rel = Path(".")
    else:
        raise GlassError(
            agent_instruction(
                "table path is required",
                "Use a table-relative markdown path such as `scene.md`, `handouts/<slug>.md`, or `<kind>-<slug>.md`.",
            )
        )
    if rel.parts and rel.parts[0] == "table":
        rel = Path(*rel.parts[1:]) if len(rel.parts) > 1 else Path(".")
    if rel in {Path("index.md"), Path("table") / "index.md"}:
        raise GlassError(
            agent_instruction(
                "table/index.md is retired; write scene.md or a named table artifact instead",
                "Use `glass table write scene.md --body <markdown>` for the live scene description.",
                "Use `glass table write <kind>-<slug>.md --body <markdown>` for NPCs, locales, ships, documents, handouts, and other durable visible artifacts.",
            )
        )
    if rel == Path(".") and not allow_root:
        raise GlassError(
            agent_instruction(
                "table path is required",
                "Use `scene.md` for the live scene description or a named markdown artifact for anything else visible to players.",
            )
        )
    path = (root / rel).resolve()
    return ensure_under(path, root, "table paths must stay under table/")


def _table_files(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if path.is_dir():
            if rel.parts == ("handouts",):
                out.append({"path": f"{rel}/", "type": "dir"})
            continue
        if rel == Path("index.md"):
            continue
        out.append(
            {
                "path": str(rel),
                "type": "file",
                "bytes": path.stat().st_size,
            }
        )
    return out
