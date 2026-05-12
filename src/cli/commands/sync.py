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
from ..errors import GlassError, agent_instruction
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
            raise GlassError(
                agent_instruction(
                    "`glass sync apply` accepts either paths or `--from`, not both",
                    "For normal workspace edits, run `glass sync apply <path> [<path> ...]`.",
                    "For a legacy JSON manifest, run `glass sync apply --from <manifest.json>` with no path arguments.",
                )
            )
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
        raise GlassError(
            agent_instruction(
                "`glass sync apply` found no changed markdown files to commit",
                "Edit a durable markdown surface first, or pass the exact file or directory you changed.",
                "Do not sync TURN_START, turn closeout files, instructions, methodologies, SRD/how-to files, or other generated turn scaffolding.",
            )
        )

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
        agent_instruction(
            f"sync operation #{index} has unsupported kind {kind!r}",
            "Use `kind: note`, `kind: table`, or `kind: summary` in legacy manifests.",
            "Prefer direct path sync with `glass sync apply <path>` for normal agent turns.",
        )
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
        raise GlassError(
            agent_instruction(
                f"sync operation #{index}: notes support only `mode: write`",
                "Use `mode: write`, or switch to a table/summary operation if append semantics are required.",
            )
        )
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
        raise GlassError(
            agent_instruction(
                f"sync operation #{index}: table mode must be `write` or `append`",
                "Use `write` to replace a table artifact, or `append` to add to an existing table artifact.",
            )
        )
    path = _resolve_table_path(
        workspace.table_dir,
        _required_str(op, "path", index=index),
    )
    if path.exists() and path.is_dir():
        raise GlassError(
            agent_instruction(
                f"sync operation #{index}: table destination is a directory",
                "Write to a markdown file such as `scene.md`, `handouts/<slug>.md`, or `<kind>-<slug>.md`.",
            )
        )
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
        raise GlassError(
            agent_instruction(
                f"sync operation #{index}: summary mode must be `write` or `append`",
                "Use `write` to replace a summary or `append` to add a compact scene/arc/session summary.",
            )
        )
    level = _required_str(op, "level", index=index)
    target_id = op.get("target_id")
    arc_id = op.get("arc")
    if target_id is not None and not isinstance(target_id, str):
        raise GlassError(
            agent_instruction(
                f"sync operation #{index}: `target_id` must be a string",
                "Set `target_id` to the scene/session id as text, or omit it for levels that do not need one.",
            )
        )
    if arc_id is not None and not isinstance(arc_id, str):
        raise GlassError(
            agent_instruction(
                f"sync operation #{index}: `arc` must be a string",
                "Set `arc` to the arc id as text, or omit it when the active arc should be used.",
            )
        )
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
            f"sync path is outside the current workspace: {path_text!r}",
        )
        if not source.exists():
            raise GlassError(
                agent_instruction(
                    f"sync path does not exist: {path_text}",
                    "Pass a file or directory that exists in the current projected workspace.",
                    "Use workspace-relative paths, for example `table/scene.md` or `shared/lore/<kind>/<slug>.md`.",
                )
            )
        if source.is_dir():
            files.extend(sorted(path for path in source.rglob("*.md") if path.is_file()))
            continue
        if source.suffix.lower() != ".md":
            raise GlassError(
                agent_instruction(
                    f"sync can commit markdown files only: {path_text}",
                    "Choose a `.md` file or a directory containing markdown files.",
                )
            )
        files.append(source)
    return _dedupe_files(files)


def _changed_projection_files(source_root: Path, *, campaign_root: Path) -> list[Path]:
    manifest = _load_projection_manifest(source_root)
    if not manifest:
        raise GlassError(
            agent_instruction(
                "`glass sync apply` without paths needs a projection manifest",
                "Pass the changed path explicitly, for example `glass sync apply table/scene.md`.",
                "If you are outside an orchestrated workspace, run from the agent cwd created for the turn.",
            )
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
        raise GlassError(
            agent_instruction(
                f"invalid sync path: {rel}",
                "Use a workspace-relative path without `..`.",
            )
        )
    if rel.suffix.lower() != ".md":
        raise GlassError(
            agent_instruction(
                f"sync can commit markdown files only: {rel}",
                "Move durable text into a markdown file, then sync that `.md` file.",
            )
        )
    if _skip_projection_sync_candidate(rel):
        raise GlassError(
            agent_instruction(
                f"sync path is not a durable document surface: {rel}",
                "Sync campaign artifacts such as `table/*.md`, `shared/lore/**/*.md`, `arcs/**/*.md`, or player public/notes/journal files.",
                "Do not sync turn scaffolding, scratch, instructions, methodologies, SRD/how-to files, transcripts, or audit logs.",
            )
        )
    if rel == Path("table") / "index.md":
        raise GlassError(
            agent_instruction(
                "table/index.md is retired; sync scene.md or named table artifacts instead",
                "Use `table/scene.md` for the active scene description.",
                "Use named table artifacts such as `table/npc-<slug>.md`, `table/locale-<slug>.md`, `table/ship-<slug>.md`, or `table/handouts/<slug>.md` for player-visible lore.",
            )
        )

    role = current_role()
    parts = rel.parts
    if not parts:
        raise GlassError(
            agent_instruction(
                "sync path is empty",
                "Pass the specific markdown file or directory you want to commit.",
            )
        )

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
        agent_instruction(
            "players can sync only their own player workspace files",
            f"Use a path under `players/{actor}/public/`, `players/{actor}/secrets/`, `players/{actor}/notes/`, `players/{actor}/journal/`, `players/{actor}/drafts/`, or `players/{actor}/inbox/`.",
            "Do not sync another player, DM, shared, arc, or table file from a player turn.",
        )
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
        agent_instruction(
            "DM sync paths must be durable DM, shared, arc, or table surfaces",
            "Use `table/`, `arcs/`, `shared/`, `dm/workspace/`, `dm/notes/`, `dm/journal/`, `dm/secret/`, `dm/intake/`, `context.md`, or `summary.md`.",
            "Use `glass table`, `glass lore`, or `glass scene` commands when those commands express the intent more directly.",
        )
    )


def _validate_arc_path_exists(rel: Path, workspace: _workspace.CampaignWorkspace) -> None:
    parts = rel.parts
    if len(parts) < 3:
        raise GlassError(
            agent_instruction(
                "arc sync paths must name a file under `arcs/<arc>/`",
                "Use a path such as `arcs/<arc>/plan.md`, `arcs/<arc>/context.md`, or `arcs/<arc>/scenes/<scene>/summary.md`.",
            )
        )
    arc_dir = workspace.root / "arcs" / parts[1]
    if not arc_dir.exists():
        raise GlassError(
            agent_instruction(
                f"arc {parts[1]!r} does not exist",
                f"Create it first with `glass arc create {parts[1]} "
                "--pull-source <source> --pull-utilization <note>` or sync a file "
                "under an existing arc.",
            )
        )
    if len(parts) >= 5 and parts[2] == "scenes":
        scene_dir = arc_dir / "scenes" / parts[3]
        if not scene_dir.exists():
            raise GlassError(
                agent_instruction(
                    f"scene {parts[3]!r} does not exist under arc {parts[1]!r}",
                    f"Create it first with `glass scene create {parts[3]} --type <scene-type> --arc {parts[1]}` or sync a file under an existing scene.",
                )
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
            agent_instruction(
                f"sync could not read projected file as {reader_user}: {path}",
                "Run from the agent's current projected workspace and pass a readable markdown path.",
                "If the host user setup changed, repair the workspace users or rerun with the correct `GLASS_WORKSPACE_READER_USER`.",
                f"Read command detail: {stderr.strip()}",
            )
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
        raise GlassError(
            agent_instruction(
                "sync manifest must be valid JSON",
                "Fix the manifest JSON or prefer direct path sync with `glass sync apply <path>`.",
                f"JSON parser detail: {exc}",
            )
        ) from exc
    if not isinstance(manifest, dict):
        raise GlassError(
            agent_instruction(
                "sync manifest must be a JSON object",
                "Use an object with a `writes` array, or prefer direct path sync with `glass sync apply <path>`.",
            )
        )
    return manifest


def _manifest_ops(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    raw = manifest.get("writes", manifest.get("operations"))
    if not isinstance(raw, list):
        raise GlassError(
            agent_instruction(
                "sync manifest must contain a `writes` array",
                "Use `{\"writes\": [{\"kind\": \"note|table|summary\", ...}]}` or prefer direct path sync with `glass sync apply <path>`.",
            )
        )
    ops: list[dict[str, Any]] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise GlassError(
                agent_instruction(
                    f"sync operation #{index} must be an object",
                    "Each manifest write must be an object with `kind`, `path` or summary target fields, and `body` or `from`.",
                )
            )
        ops.append(item)
    if not ops:
        raise GlassError(
            agent_instruction(
                "sync manifest has no operations",
                "Add at least one write object, or prefer direct path sync with `glass sync apply <path>`.",
            )
        )
    return ops


def _operation_body(op: dict[str, Any], *, index: int) -> str:
    if "body" in op and "from" in op:
        raise GlassError(
            agent_instruction(
                f"sync operation #{index}: use either `body` or `from`, not both",
                "Put inline markdown in `body`, or place the body in a scratch file and reference it with `from`.",
            )
        )
    if "body" in op:
        body = op["body"]
        if not isinstance(body, str):
            raise GlassError(
                agent_instruction(
                    f"sync operation #{index}: `body` must be a string",
                    "Set `body` to the markdown text to write.",
                )
            )
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
            f"sync operation #{index}: {field} file is outside scratch/: {path_text!r}"
        ),
    )


def _required_str(op: dict[str, Any], key: str, *, index: int) -> str:
    value = op.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GlassError(
            agent_instruction(
                f"sync operation #{index}: missing string field {key!r}",
                f"Set `{key}` to a non-empty string.",
            )
        )
    return value


def _mode(op: dict[str, Any], *, default: str) -> str:
    return str(op.get("mode") or default).strip().lower()
