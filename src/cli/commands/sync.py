"""Bulk workspace sync commands."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import hashlib
from pathlib import Path
from typing import Any

import click

from .. import workspace as _workspace
from ..campaign import active_campaign_id, active_campaign_root, resolve_active_campaign_workspace
from ..config import get_paths
from ..errors import GlassError
from ..paths_resolve import clean_relative_path, display_path, ensure_under, resolve_note_write_path
from ..persistence import CampaignPersistence
from ..role import current_role, require_dm
from ..state import commit, load_state, queue_event
from ..yaml_io import command_params, emit
from .summary import _summary_path
from .table import _resolve_table_path


@click.group()
def sync() -> None:
    """Bulk-commit workspace edits into persistent campaign state."""


@sync.command("apply")
@click.argument("path_args", nargs=-1)
@click.option(
    "--from",
    "from_file",
    help="Legacy JSON manifest file. Prefer editing real paths and passing paths.",
)
@click.option("--dry-run", is_flag=True, help="Validate and describe operations without writing.")
@click.pass_context
def sync_apply(
    ctx: click.Context,
    path_args: tuple[str, ...],
    from_file: str | None,
    dry_run: bool,
) -> None:
    """Commit workspace edits in one CLI invocation.

    Preferred:

      glass sync apply arcs/opening table

    With no paths, syncs changed writable markdown files in this workspace.
    The legacy --from JSON manifest remains supported for generated batches.
    """
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    workspace = resolve_active_campaign_workspace()
    role = current_role()
    persistence = CampaignPersistence(
        paths=paths,
        campaign_id=campaign_id,
        campaign_root=active_campaign_root(),
    )

    if from_file:
        if path_args:
            raise GlassError("sync apply accepts either paths or --from, not both")
        results = _apply_manifest_sync(
            from_file,
            state=state,
            workspace=workspace,
            persistence=persistence,
            dry_run=dry_run,
        )
        params = command_params(from_file=from_file, count=len(results))
    else:
        results = _apply_path_sync(
            list(path_args),
            state=state,
            workspace=workspace,
            persistence=persistence,
            dry_run=dry_run,
        )
        params = command_params(paths=list(path_args), count=len(results))

    payload = {
        "campaign_id": campaign_id,
        "dry_run": dry_run,
        "count": len(results),
        "operations": results,
    }
    if dry_run:
        emit(payload)
        return

    queue_event(
        state,
        role.actor,
        f"sync applied {len(results)} workspace operation(s)",
    )
    commit(
        paths,
        state,
        ctx,
        "sync.apply",
        params,
        payload,
    )


def _apply_manifest_sync(
    from_file: str,
    *,
    state: dict[str, Any],
    workspace: _workspace.CampaignWorkspace,
    persistence: CampaignPersistence,
    dry_run: bool,
) -> list[dict[str, Any]]:
    manifest = _load_manifest(from_file)
    ops = _manifest_ops(manifest)
    results: list[dict[str, Any]] = []
    for index, op in enumerate(ops, start=1):
        result = _apply_op(
            index,
            op,
            state=state,
            workspace=workspace,
            persistence=persistence,
            dry_run=dry_run,
        )
        results.append(result)
    return results


def _apply_path_sync(
    path_args: list[str],
    *,
    state: dict[str, Any],
    workspace: _workspace.CampaignWorkspace,
    persistence: CampaignPersistence,
    dry_run: bool,
) -> list[dict[str, Any]]:
    source_root = Path.cwd().resolve()
    campaign_root = active_campaign_root().resolve()
    if path_args:
        files = _files_from_path_args(path_args, source_root=source_root)
    else:
        files = _changed_projection_files(source_root, campaign_root=campaign_root)
    if not files:
        raise GlassError("sync apply found no changed markdown files to commit")

    results: list[dict[str, Any]] = []
    manifest_updates: dict[str, str] = {}
    for index, source in enumerate(files, start=1):
        rel = source.relative_to(source_root)
        result = _apply_projected_file(
            index,
            source,
            rel,
            state=state,
            workspace=workspace,
            persistence=persistence,
            dry_run=dry_run,
        )
        results.append(result)
        if not dry_run:
            manifest_updates[str(rel)] = _hash_file(source)
    if manifest_updates:
        _update_projection_manifest(source_root, manifest_updates)
    return results


def _apply_op(
    index: int,
    op: dict[str, Any],
    *,
    state: dict[str, Any],
    workspace: _workspace.CampaignWorkspace,
    persistence: CampaignPersistence,
    dry_run: bool,
) -> dict[str, Any]:
    kind = str(op.get("kind") or op.get("surface") or "").strip().lower()
    if kind == "note":
        return _apply_note(index, op, state=state, persistence=persistence, dry_run=dry_run)
    if kind == "table":
        return _apply_table(
            index,
            op,
            state=state,
            workspace=workspace,
            persistence=persistence,
            dry_run=dry_run,
        )
    if kind == "summary":
        return _apply_summary(
            index,
            op,
            state=state,
            workspace=workspace,
            persistence=persistence,
            dry_run=dry_run,
        )
    raise GlassError(
        f"sync operation #{index}: unsupported kind {kind!r}; "
        "expected note, table, or summary"
    )


def _apply_note(
    index: int,
    op: dict[str, Any],
    *,
    state: dict[str, Any],
    persistence: CampaignPersistence,
    dry_run: bool,
) -> dict[str, Any]:
    mode = _mode(op, default="write")
    if mode != "write":
        raise GlassError(f"sync operation #{index}: note supports only mode=write")
    campaign_id = active_campaign_id()
    destination = resolve_note_write_path(
        get_paths(),
        _required_str(op, "path", index=index),
        campaign_id=campaign_id,
    )
    text = _operation_body(op, index=index)
    result = {
        "index": index,
        "kind": "note",
        "mode": mode,
        "path": display_path(destination),
        "bytes": len(text.encode("utf-8")),
    }
    if dry_run:
        return result
    persisted = persistence.write_markdown(destination, text, state=state)
    return {**result, "persistence": persisted.to_dict()}


def _apply_table(
    index: int,
    op: dict[str, Any],
    *,
    state: dict[str, Any],
    workspace: _workspace.CampaignWorkspace,
    persistence: CampaignPersistence,
    dry_run: bool,
) -> dict[str, Any]:
    role = require_dm()
    mode = _mode(op, default="write")
    if mode not in {"write", "append"}:
        raise GlassError(f"sync operation #{index}: table mode must be write or append")
    path = _resolve_table_path(
        workspace.table_dir,
        _required_str(op, "path", index=index),
    )
    if path.exists() and path.is_dir():
        raise GlassError(f"sync operation #{index}: cannot write table directory")
    text = _operation_body(op, index=index)
    result = {
        "index": index,
        "kind": "table",
        "mode": mode,
        "path": display_path(path),
        "bytes": len(text.encode("utf-8")),
    }
    if dry_run:
        return result
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "append" and path.exists():
        existing = path.read_text(encoding="utf-8")
        separator = "" if not existing or existing.endswith("\n") else "\n"
        path.write_text(existing + separator + text, encoding="utf-8")
    else:
        path.write_text(text, encoding="utf-8")
    persisted = persistence.register_markdown(path, state=state, graph=False)
    queue_event(state, role.actor, f"table {mode} {display_path(path)}")
    return {**result, "persistence": persisted.to_dict()}


def _apply_summary(
    index: int,
    op: dict[str, Any],
    *,
    state: dict[str, Any],
    workspace: _workspace.CampaignWorkspace,
    persistence: CampaignPersistence,
    dry_run: bool,
) -> dict[str, Any]:
    role = require_dm()
    mode = _mode(op, default="write")
    if mode not in {"write", "append"}:
        raise GlassError(f"sync operation #{index}: summary mode must be write or append")
    level = _required_str(op, "level", index=index)
    target_id = op.get("target_id")
    arc_id = op.get("arc")
    if target_id is not None and not isinstance(target_id, str):
        raise GlassError(f"sync operation #{index}: target_id must be a string")
    if arc_id is not None and not isinstance(arc_id, str):
        raise GlassError(f"sync operation #{index}: arc must be a string")
    path = _summary_path(workspace, level, target_id, arc_id=arc_id)
    text = _operation_body(op, index=index).rstrip() + "\n"
    resolved_level = "arc" if level == "act" else level
    result = {
        "index": index,
        "kind": "summary",
        "mode": mode,
        "level": resolved_level,
        "path": display_path(path),
        "bytes": len(text.encode("utf-8")),
    }
    if dry_run:
        return result
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "append" and path.exists():
        existing = path.read_text(encoding="utf-8")
        separator = "" if existing.endswith("\n") else "\n"
        path.write_text(existing + separator + text, encoding="utf-8")
    else:
        path.write_text(text, encoding="utf-8")
    persisted = persistence.register_markdown(path, state=state, graph=False)
    queue_event(
        state,
        role.actor,
        f"summary.{mode} {resolved_level} {display_path(path)}",
    )
    return {
        **result,
        "bytes": len(path.read_bytes()),
        "persistence": persisted.to_dict(),
    }


def _apply_projected_file(
    index: int,
    source: Path,
    rel: Path,
    *,
    state: dict[str, Any],
    workspace: _workspace.CampaignWorkspace,
    persistence: CampaignPersistence,
    dry_run: bool,
) -> dict[str, Any]:
    graph = _validate_projected_sync_path(rel, workspace)
    text = _read_workspace_text(source)
    destination = (workspace.root / rel).resolve()
    result = {
        "index": index,
        "kind": "file",
        "path": display_path(destination),
        "source": str(rel),
        "bytes": len(text.encode("utf-8")),
    }
    if dry_run:
        return result
    persisted = persistence.write_markdown(destination, text, state=state, graph=graph)
    return {**result, "persistence": persisted.to_dict()}


def _files_from_path_args(path_args: list[str], *, source_root: Path) -> list[Path]:
    files: list[Path] = []
    for path_text in path_args:
        rel = clean_relative_path(path_text)
        source = ensure_under(
            (source_root / rel).resolve(),
            source_root,
            f"sync path must stay under the current workspace: {path_text!r}",
        )
        if not source.exists():
            raise GlassError(f"sync path not found: {path_text}")
        if source.is_dir():
            files.extend(sorted(path for path in source.rglob("*.md") if path.is_file()))
            continue
        if source.suffix.lower() != ".md":
            raise GlassError(f"sync can commit markdown files only: {path_text}")
        files.append(source)
    return _dedupe_files(files)


def _changed_projection_files(source_root: Path, *, campaign_root: Path) -> list[Path]:
    manifest = _load_projection_manifest(source_root)
    if not manifest:
        raise GlassError(
            "sync apply without paths requires a workspace change manifest; "
            "pass one or more paths explicitly"
        )
    files: list[Path] = []
    for source in sorted(source_root.rglob("*.md")):
        if not source.is_file():
            continue
        rel = source.relative_to(source_root)
        if _skip_projection_sync_candidate(rel):
            continue
        try:
            _validate_projected_sync_path(rel, _workspace.CampaignWorkspace("", campaign_root))
        except GlassError:
            continue
        current_hash = _hash_file(source)
        if manifest.get(str(rel)) != current_hash:
            files.append(source)
    return files


def _skip_projection_sync_candidate(rel: Path) -> bool:
    if any(part.startswith(".") for part in rel.parts):
        return True
    if rel.parts and rel.parts[0] in {
        "scratch",
        "instructions",
        "methodologies",
        "srd",
        "how-to",
    }:
        return True
    if "turns" in rel.parts:
        return True
    if rel.name in {"transcript.md", "audit.jsonl"}:
        return True
    return False


def _dedupe_files(files: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for path in files:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(resolved)
    return sorted(out)


def _validate_projected_sync_path(
    rel: Path,
    workspace: _workspace.CampaignWorkspace,
) -> bool | str:
    if rel.is_absolute() or any(part == ".." for part in rel.parts):
        raise GlassError(f"invalid sync path: {rel}")
    if rel.suffix.lower() != ".md":
        raise GlassError(f"sync can commit markdown files only: {rel}")
    if _skip_projection_sync_candidate(rel):
        raise GlassError(f"sync path is not a durable document surface: {rel}")

    role = current_role()
    parts = rel.parts
    if not parts:
        raise GlassError("empty sync path")

    if role.kind == "player":
        return _validate_player_projected_sync_path(rel, role.actor)
    if role.kind == "dm":
        return _validate_dm_projected_sync_path(rel, workspace)
    return "auto"


def _validate_player_projected_sync_path(rel: Path, actor: str) -> bool | str:
    parts = rel.parts
    if len(parts) >= 3 and parts[0] == "players" and parts[1] == actor:
        if rel == Path("players") / actor / "scratchpad.md":
            return "auto"
        if len(parts) >= 4 and parts[2] in {
            "public",
            "secrets",
            "notes",
            "journal",
            "drafts",
            "inbox",
        }:
            return "auto"
    raise GlassError(
        "permission denied: players can sync only their own public/, secrets/, "
        "notes/, journal/, drafts/, inbox/, or scratchpad.md files"
    )


def _validate_dm_projected_sync_path(
    rel: Path,
    workspace: _workspace.CampaignWorkspace,
) -> bool | str:
    parts = rel.parts
    if len(parts) == 1 and parts[0] in {"context.md", "summary.md"}:
        return False
    if parts[0] == "table":
        return False
    if parts[0] == "arcs":
        _validate_arc_path_exists(rel, workspace)
        return False
    if parts[0] == "shared":
        return "auto"
    if parts[0] == "dm":
        if rel in {Path("dm") / "scratchpad.md", Path("dm") / "foundation.md"}:
            return "auto"
        if len(parts) >= 3 and parts[1] in {
            "workspace",
            "notes",
            "journal",
            "secret",
            "intake",
        }:
            return "auto"
    raise GlassError(
        "permission denied: DM sync paths must be table/, arcs/, shared/, "
        "dm/workspace/, dm/notes/, dm/journal/, dm/secret/, dm/intake/, "
        "dm/scratchpad.md, dm/foundation.md, context.md, or summary.md"
    )


def _validate_arc_path_exists(rel: Path, workspace: _workspace.CampaignWorkspace) -> None:
    parts = rel.parts
    if len(parts) < 3:
        raise GlassError("arc sync paths must name a file under arcs/<arc>/")
    arc_dir = workspace.root / "arcs" / parts[1]
    if not arc_dir.exists():
        raise GlassError(f"arc {parts[1]!r} does not exist; run `glass arc create` first")
    if len(parts) >= 5 and parts[2] == "scenes":
        scene_dir = arc_dir / "scenes" / parts[3]
        if not scene_dir.exists():
            raise GlassError(
                f"scene {parts[3]!r} does not exist; run `glass scene create` first"
            )


def _load_projection_manifest(root: Path) -> dict[str, str]:
    path = root / ".glass-projection-manifest.json"
    try:
        raw = json.loads(_read_workspace_text(path))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    files = raw.get("files", raw) if isinstance(raw, dict) else {}
    if not isinstance(files, dict):
        return {}
    return {str(key): str(value) for key, value in files.items() if isinstance(value, str)}


def _update_projection_manifest(root: Path, updates: dict[str, str]) -> None:
    path = root / ".glass-projection-manifest.json"
    manifest = _load_projection_manifest(root)
    manifest.update(updates)
    try:
        path.write_text(
            json.dumps({"files": manifest}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
    except PermissionError:
        hasher.update(_read_workspace_bytes(path))
    return hasher.hexdigest()


def _read_workspace_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except PermissionError:
        return _read_workspace_bytes(path).decode("utf-8")


def _read_workspace_bytes(path: Path) -> bytes:
    reader_user = os.environ.get("GLASS_WORKSPACE_READER_USER")
    if not reader_user:
        raise PermissionError(f"permission denied reading workspace file: {path}")
    workspace_root = Path.cwd().resolve()
    source = ensure_under(
        path.resolve(),
        workspace_root,
        f"sync source must stay under the current workspace: {path}",
    )
    try:
        result = subprocess.run(
            ["sudo", "-n", "-u", reader_user, "--", "cat", str(source)],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        raise GlassError(
            f"sync could not read projected file as {reader_user}: {path}: {stderr.strip()}"
        ) from exc
    return result.stdout


def _load_manifest(from_file: str) -> dict[str, Any]:
    if from_file == "-":
        raw = sys.stdin.read()
    else:
        path = _scratch_source(from_file, index=0, field="manifest")
        raw = _read_workspace_text(path)
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GlassError(f"sync manifest must be JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise GlassError("sync manifest must be a JSON object")
    return manifest


def _manifest_ops(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    raw = manifest.get("writes", manifest.get("operations"))
    if not isinstance(raw, list):
        raise GlassError("sync manifest must contain a writes array")
    ops: list[dict[str, Any]] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise GlassError(f"sync operation #{index} must be an object")
        ops.append(item)
    if not ops:
        raise GlassError("sync manifest has no operations")
    return ops


def _operation_body(op: dict[str, Any], *, index: int) -> str:
    if "body" in op and "from" in op:
        raise GlassError(f"sync operation #{index}: use either body or from, not both")
    if "body" in op:
        body = op["body"]
        if not isinstance(body, str):
            raise GlassError(f"sync operation #{index}: body must be a string")
        return body
    source = _required_str(op, "from", index=index)
    return _read_workspace_text(_scratch_source(source, index=index, field="from"))


def _scratch_source(path_text: str, *, index: int, field: str) -> Path:
    rel = clean_relative_path(path_text)
    path = (Path.cwd() / rel).resolve()
    scratch = (Path.cwd() / "scratch").resolve()
    return ensure_under(
        path,
        scratch,
        (
            f"sync operation #{index}: {field} files must be under scratch/ "
            f"(got {path_text!r})"
        ),
    )


def _required_str(op: dict[str, Any], key: str, *, index: int) -> str:
    value = op.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GlassError(f"sync operation #{index}: missing string field {key!r}")
    return value


def _mode(op: dict[str, Any], *, default: str) -> str:
    return str(op.get("mode") or default).strip().lower()
