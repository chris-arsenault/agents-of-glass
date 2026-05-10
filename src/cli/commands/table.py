"""Public table-state commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from .. import workspace as _workspace
from ..campaign import active_campaign_id, resolve_active_campaign_workspace
from ..errors import GlassError
from ..config import get_paths
from ..ids import now_iso
from ..paths_resolve import clean_relative_path, display_path, ensure_under
from ..role import require_dm
from ..state import append_audit, commit, load_state, queue_event
from ..yaml_io import command_params, emit, read_body


@click.group()
def table() -> None:
    """Current public table state: index, scene kickoff, and handouts."""


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
        "index": display_path(root / "index.md"),
        "scene": display_path(root / "scene.md"),
        "handouts": display_path(root / "handouts"),
        "files": files,
    }
    append_audit(paths, state, ctx, "table.current", {}, result)
    emit(result)


@table.command("show")
@click.argument("path_text", required=False, default="index.md")
@click.pass_context
def table_show(ctx: click.Context, path_text: str) -> None:
    """Read a public table file."""
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    workspace = resolve_active_campaign_workspace()
    path = _resolve_table_path(workspace.table_dir, path_text)
    if path.is_dir():
        files = _table_files(path)
        result = {"path": display_path(path), "files": files}
    else:
        if not path.exists():
            raise GlassError(f"table file not found: {display_path(path)}")
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
    """DM-only: replace a public table file."""
    role = require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    workspace = resolve_active_campaign_workspace()
    path = _resolve_table_path(workspace.table_dir, path_text)
    if path.exists() and path.is_dir():
        raise GlassError(f"cannot write table directory: {display_path(path)}")
    text = read_body(body, from_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    queue_event(state, role.actor, f"table write {display_path(path)}")
    result = {
        "path": display_path(path),
        "bytes": len(text.encode("utf-8")),
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
    """DM-only: append to a public table file."""
    role = require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    workspace = resolve_active_campaign_workspace()
    path = _resolve_table_path(workspace.table_dir, path_text)
    if path.exists() and path.is_dir():
        raise GlassError(f"cannot append to table directory: {display_path(path)}")
    text = read_body(body, from_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = ""
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            prefix = "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(prefix + text)
    queue_event(state, role.actor, f"table append {display_path(path)}")
    result = {
        "path": display_path(path),
        "bytes": len(text.encode("utf-8")),
    }
    commit(
        paths,
        state,
        ctx,
        "table.append",
        command_params(path=path_text, bytes=result["bytes"]),
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
        raise GlassError("cannot snapshot table: no active scene")
    try:
        destination = _workspace.snapshot_table(
            workspace,
            arc_id=str(current["arc_id"]),
            scene_id=str(current["scene_id"]),
            label=label,
        )
    except FileNotFoundError as exc:
        raise GlassError(str(exc)) from exc
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
        raise GlassError("cannot archive table: no active scene")
    try:
        destination = _workspace.archive_table(
            workspace,
            arc_id=str(current["arc_id"]),
            scene_id=str(current["scene_id"]),
            clear_live=not keep_live,
        )
    except FileNotFoundError as exc:
        raise GlassError(str(exc)) from exc
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


def _resolve_table_path(root: Path, path_text: str) -> Path:
    rel = clean_relative_path(path_text or "index.md")
    if rel.parts and rel.parts[0] == "table":
        rel = Path(*rel.parts[1:]) if len(rel.parts) > 1 else Path("index.md")
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
        out.append(
            {
                "path": str(rel),
                "type": "file",
                "bytes": path.stat().st_size,
            }
        )
    return out
