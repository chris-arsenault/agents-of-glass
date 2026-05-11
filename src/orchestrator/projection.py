"""Per-turn actor-owned campaign workspace projections.

Agents are good at reading files directly, so each turn gets a campaign-shaped
workspace containing only the files that actor may see. The relative paths are
the same as the canonical campaign tree. The spawned actor owns the projection,
but persistent mutations still go through `glass`, not direct writes to the
canonical campaign tree.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .config import AogConfig
from . import permissions
from .state import Agent


READONLY_DIR_MODE = 0o550
READONLY_FILE_MODE = 0o440
WRITABLE_DIR_MODE = 0o2770
PROJECTION_PARENT_DIR_MODE = 0o710
WRITABLE_FILE_MODE = 0o660
PROJECTION_MANIFEST = ".glass-projection-manifest.json"

_TOP_LEVEL_FILES = {
    "README.md",
    "context.md",
    "summary.md",
    "transcript.md",
    "scene-framing.md",
}
_PUBLIC_DIRS = {
    "instructions",
    "methodologies",
    "srd",
    "how-to",
    "shared",
    "table",
}
_SKIP_FILE_NAMES = {
    ".glass-grants.json",
    PROJECTION_MANIFEST,
    "aog-state.json",
    "state.json",
    "audit.jsonl",
}
_SKIP_DIR_NAMES = {
    "__pycache__",
}
_PLAYER_OWN_ROOT_FILES = {
    "persona.md",
    "scratchpad.md",
    "signature-moves.md",
}
_PLAYER_OWN_DIRS = {
    "public",
    "secrets",
    "notes",
    "journal",
    "drafts",
    "inbox",
}
_ARC_PRIVATE_FILES = {
    "plan.md",
    "prep.md",
    "state.json",
    "audit.jsonl",
}


@dataclass(frozen=True)
class ProjectionPaths:
    root: Path
    turn_dir: Path
    turn_start_path: Path
    turn_prose_path: Path
    turn_closeout_path: Path


def projection_root_for(
    config: AogConfig,
    *,
    campaign: str,
    turn_number: int,
    agent: Agent,
) -> Path:
    """Return the per-turn projected cwd for an agent."""

    return (
        config.repo_root
        / ".glass-cwd"
        / campaign
        / f"{turn_number:04d}-{agent.id}"
    )


def projected_path(campaign_root: Path, projection_root: Path, canonical_path: Path) -> Path:
    return projection_root / canonical_path.relative_to(campaign_root)


def build_projection(
    *,
    config: AogConfig,
    campaign_root: Path,
    agent: Agent,
    turn_number: int,
    canonical_turn_start_path: Path,
    canonical_turn_prose_path: Path,
    canonical_turn_closeout_path: Path,
) -> ProjectionPaths:
    """Create a fresh actor-owned projection for one actor turn."""

    root = projection_root_for(
        config,
        campaign=campaign_root.name,
        turn_number=turn_number,
        agent=agent,
    )
    _ensure_projection_parents(root)
    _remove_tree(root)
    root.mkdir(parents=True, exist_ok=True)

    current_turn_dir_rel = canonical_turn_start_path.parent.relative_to(campaign_root)
    current_turn_start_rel = canonical_turn_start_path.relative_to(campaign_root)
    current_turn_prose_rel = canonical_turn_prose_path.relative_to(campaign_root)
    current_turn_closeout_rel = canonical_turn_closeout_path.relative_to(campaign_root)

    # Create visible empty directories first so table/handouts and similar
    # roots are still discoverable even before they contain files.
    for directory in sorted(_iter_dirs(campaign_root), key=lambda item: item[0]):
        rel, source = directory
        if _directory_visible(rel, agent, current_turn_dir_rel):
            (root / rel).mkdir(parents=True, exist_ok=True)

    manifest: dict[str, str] = {}
    for rel, source in sorted(_iter_files(campaign_root), key=lambda item: item[0]):
        if not _file_visible(rel, agent, current_turn_start_rel):
            continue
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        _copy_file(source, target, campaign_root=campaign_root)
        if target.exists() and target.is_file():
            manifest[str(rel)] = _hash_file(target)

    projected_turn_dir = root / current_turn_dir_rel
    projected_turn_dir.mkdir(parents=True, exist_ok=True)
    _prepare_tool_runtime_files(root)
    _write_projection_manifest(root, manifest)
    _ensure_authoring_surfaces(root, agent)

    _make_readonly(root)
    _make_authoring_surfaces_writable(root, agent)
    _make_writable_tree(projected_turn_dir)
    _make_writable_tree(root / ".claude")
    _chmod_if_possible(root / ".mcp.json", WRITABLE_FILE_MODE)
    _chmod_if_possible(root / PROJECTION_MANIFEST, WRITABLE_FILE_MODE)
    permissions.apply_projection_permissions(
        root,
        actor_user=permissions.player_user_for(agent.id),
    )

    return ProjectionPaths(
        root=root,
        turn_dir=projected_turn_dir,
        turn_start_path=root / current_turn_start_rel,
        turn_prose_path=root / current_turn_prose_rel,
        turn_closeout_path=root / current_turn_closeout_rel,
    )


def copy_turn_artifacts_to_canonical(
    *,
    projection: ProjectionPaths,
    canonical_turn_dir: Path,
    reader_user: str | None = None,
) -> None:
    """Copy generated turn artifacts from projection back to canonical storage."""

    for name in ("TURN.md", "turn-closeout.json", "claude-debug.log"):
        source = projection.turn_dir / name
        if not source.exists():
            continue
        target = canonical_turn_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        _copy_artifact(source, target, reader_user=reader_user)


def refresh_projection_from_canonical(
    *,
    config: AogConfig,
    campaign_root: Path,
    agent: Agent,
    turn_number: int,
    projection_root: Path | None = None,
) -> None:
    """Refresh canonical files into an existing per-turn projection.

    The local glass API mutates canonical campaign storage while the agent's
    cwd stays pointed at the projection. Refreshing after successful commands
    lets files created by `glass` become readable in the same turn without
    forcing agents to reach for absolute canonical paths.
    """

    root = projection_root or projection_root_for(
        config,
        campaign=campaign_root.name,
        turn_number=turn_number,
        agent=agent,
    )
    if not root.exists() or not root.is_dir():
        return

    current_turn_dir_rel = _current_turn_dir_rel(agent, turn_number)
    current_turn_start_rel = current_turn_dir_rel / "TURN_START.md"
    projected_turn_dir = root / current_turn_dir_rel

    _make_owner_writable(root)
    manifest = _load_projection_manifest(root)
    for rel, _source in sorted(_iter_dirs(campaign_root), key=lambda item: item[0]):
        if _directory_visible(rel, agent, current_turn_dir_rel):
            (root / rel).mkdir(parents=True, exist_ok=True)

    for rel, source in sorted(_iter_files(campaign_root), key=lambda item: item[0]):
        if not _file_visible(rel, agent, current_turn_start_rel):
            continue
        target = root / rel
        source_hash = _hash_file(source)
        old_hash = manifest.get(str(rel))
        if target.exists() and target.is_file():
            target_hash = _hash_file(target)
            if target_hash == source_hash:
                manifest[str(rel)] = source_hash
                continue
            if old_hash is None or target_hash != old_hash:
                continue
        target.parent.mkdir(parents=True, exist_ok=True)
        _copy_file(source, target, campaign_root=campaign_root)
        manifest[str(rel)] = source_hash

    _prepare_tool_runtime_files(root)
    _write_projection_manifest(root, manifest)
    _ensure_authoring_surfaces(root, agent)
    _make_readonly(root)
    _make_authoring_surfaces_writable(root, agent)
    _make_writable_tree(projected_turn_dir)
    _make_writable_tree(root / ".claude")
    _chmod_if_possible(root / ".mcp.json", WRITABLE_FILE_MODE)
    _chmod_if_possible(root / PROJECTION_MANIFEST, WRITABLE_FILE_MODE)
    permissions.apply_projection_permissions(
        root,
        actor_user=permissions.player_user_for(agent.id),
    )


def unsynced_workspace_changes(
    projection_root: Path,
    agent: Agent,
) -> list[dict[str, str]]:
    """Return writable projected markdown whose content is not in the manifest.

    The projection manifest records the hash of files copied in at turn start
    and files successfully committed through `glass sync apply`. Anything under
    a role-authorized document surface that differs from that manifest is a
    deterministic unsynced workspace edit.
    """

    root = projection_root
    if not root.exists() or not root.is_dir():
        return []
    manifest = _load_projection_manifest(root)
    changes: list[dict[str, str]] = []

    seen: set[str] = set()
    for path in sorted(root.rglob("*.md")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if not _is_syncable_authoring_path(rel, root=root, agent=agent):
            continue
        rel_text = str(rel)
        seen.add(rel_text)
        current_hash = _hash_file(path)
        manifest_hash = manifest.get(rel_text)
        if manifest_hash is None:
            changes.append({"path": rel_text, "status": "new"})
        elif manifest_hash != current_hash:
            changes.append({"path": rel_text, "status": "modified"})

    for rel_text in sorted(set(manifest) - seen):
        rel = Path(rel_text)
        if rel.suffix.lower() != ".md":
            continue
        if not _is_syncable_authoring_path(rel, root=root, agent=agent):
            continue
        if not (root / rel).exists():
            changes.append({"path": rel_text, "status": "deleted"})

    return changes


def _iter_dirs(root: Path) -> list[tuple[Path, Path]]:
    items: list[tuple[Path, Path]] = []
    for path in root.rglob("*"):
        if path.is_dir() and not _contains_skip_dir(path.relative_to(root)):
            items.append((path.relative_to(root), path))
    return items


def _iter_files(root: Path) -> list[tuple[Path, Path]]:
    items: list[tuple[Path, Path]] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if _contains_skip_dir(rel) or not path.is_file():
            continue
        items.append((rel, path))
    return items


def _directory_visible(rel: Path, agent: Agent, current_turn_dir_rel: Path) -> bool:
    if rel == Path("."):
        return True
    parts = rel.parts
    if not parts:
        return True
    if _is_turn_path(rel):
        return rel == current_turn_dir_rel or rel in current_turn_dir_rel.parents
    first = parts[0]
    if first in _PUBLIC_DIRS:
        return True
    if first == "arcs":
        return True
    if agent.role == "dm":
        return first in {"dm", "players"}
    if first == "players":
        if len(parts) == 1:
            return True
        player_id = parts[1]
        if len(parts) == 2:
            return True
        if player_id == agent.id:
            return parts[2] in _PLAYER_OWN_DIRS or parts[2] == "turns"
        return parts[2] == "public"
    return False


def _file_visible(rel: Path, agent: Agent, current_turn_start_rel: Path) -> bool:
    parts = rel.parts
    if not parts:
        return False
    if rel.name in _SKIP_FILE_NAMES:
        return False
    if rel == current_turn_start_rel:
        return True
    if _is_turn_path(rel):
        return False
    if len(parts) == 1:
        return parts[0] in _TOP_LEVEL_FILES
    first = parts[0]
    if first in _PUBLIC_DIRS:
        return True
    if first == "arcs":
        if agent.role == "dm":
            return True
        return rel.name not in _ARC_PRIVATE_FILES
    if agent.role == "dm":
        return first in {"dm", "players"}
    if first != "players" or len(parts) < 3:
        return False
    player_id = parts[1]
    if player_id == agent.id:
        if len(parts) == 3:
            return parts[2] in _PLAYER_OWN_ROOT_FILES
        return parts[2] in _PLAYER_OWN_DIRS
    return parts[2] == "public"


def _is_turn_path(rel: Path) -> bool:
    parts = rel.parts
    return "turns" in parts


def _contains_skip_dir(rel: Path) -> bool:
    return any(part in _SKIP_DIR_NAMES for part in rel.parts)


def _copy_file(source: Path, target: Path, *, campaign_root: Path) -> None:
    if source.is_symlink():
        resolved = source.resolve()
        try:
            resolved.relative_to(campaign_root.resolve())
        except ValueError:
            return
        if resolved.is_file():
            shutil.copy2(resolved, target)
        return
    shutil.copy2(source, target)


def _ensure_projection_parents(root: Path) -> None:
    root.parent.mkdir(parents=True, exist_ok=True)
    for path in (root.parent.parent, root.parent):
        if path.exists():
            try:
                os.chmod(path, PROJECTION_PARENT_DIR_MODE)
            except OSError:
                pass


def _prepare_tool_runtime_files(root: Path) -> None:
    # Claude may try to create local settings under cwd before it reads the
    # prompt. Keep these hidden runtime paths writable while the campaign
    # projection itself remains read-only.
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    mcp_path = root / ".mcp.json"
    if not mcp_path.exists():
        mcp_path.write_text("{}\n", encoding="utf-8")


def _load_projection_manifest(root: Path) -> dict[str, str]:
    path = root / PROJECTION_MANIFEST
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    if not isinstance(raw, dict):
        return {}
    files = raw.get("files", raw)
    if not isinstance(files, dict):
        return {}
    return {str(key): str(value) for key, value in files.items() if isinstance(value, str)}


def _write_projection_manifest(root: Path, manifest: dict[str, str]) -> None:
    path = root / PROJECTION_MANIFEST
    path.write_text(
        json.dumps({"files": manifest}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _make_readonly(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_dir():
            _chmod_if_possible(path, READONLY_DIR_MODE)
        else:
            _chmod_if_possible(path, READONLY_FILE_MODE)
    _chmod_if_possible(root, READONLY_DIR_MODE)


def writable_probe_dirs(root: Path, agent: Agent) -> list[Path]:
    """Directories where the actor must be able to create/edit temp files.

    These include writable document trees plus parents of writable singleton
    files. Atomic editors create sibling temp files, so a writable file with a
    read-only parent is not actually writable in practice.
    """

    dirs, files = _authoring_surfaces(root, agent)
    probes = list(dirs)
    probes.extend(path.parent for path in files)
    return sorted({path for path in probes if path.exists()})


def _make_authoring_surfaces_writable(root: Path, agent: Agent) -> None:
    dirs, files = _authoring_surfaces(root, agent)
    for directory in dirs:
        if not directory.exists():
            continue
        _make_writable_tree(directory)
    for path in files:
        _chmod_if_possible(path.parent, WRITABLE_DIR_MODE)
        if path.exists():
            try:
                os.chmod(path, WRITABLE_FILE_MODE)
            except OSError:
                pass


def _ensure_authoring_surfaces(root: Path, agent: Agent) -> None:
    dirs, files = _authoring_surfaces(root, agent)
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)


def _authoring_surfaces(root: Path, agent: Agent) -> tuple[list[Path], list[Path]]:
    if agent.role == "dm":
        dirs = [
            root / "arcs",
            root / "table",
            root / "shared",
            root / "dm" / "workspace",
            root / "dm" / "notes",
            root / "dm" / "journal",
            root / "dm" / "secret",
            root / "dm" / "intake",
        ]
        files = [
            root / "context.md",
            root / "summary.md",
            root / "dm" / "scratchpad.md",
            root / "dm" / "foundation.md",
        ]
        return dirs, files

    base = root / "players" / agent.id
    dirs = [base / item for item in _PLAYER_OWN_DIRS]
    files = [base / "scratchpad.md"]
    return dirs, files


def _is_syncable_authoring_path(rel: Path, *, root: Path, agent: Agent) -> bool:
    if rel.is_absolute() or any(part == ".." for part in rel.parts):
        return False
    if rel.suffix.lower() != ".md":
        return False
    if any(part.startswith(".") for part in rel.parts):
        return False
    if _is_turn_path(rel):
        return False
    if rel.name in {"transcript.md", "audit.jsonl"}:
        return False

    dirs, files = _authoring_surfaces(root, agent)
    dir_rels = [path.relative_to(root) for path in dirs]
    file_rels = [path.relative_to(root) for path in files]
    if rel in file_rels:
        return True
    return any(_path_is_relative_to(rel, directory) for directory in dir_rels)


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    return path == parent or path.parts[: len(parent.parts)] == parent.parts


def _make_owner_writable(root: Path) -> None:
    for path in root.rglob("*"):
        try:
            if path.is_dir():
                os.chmod(path, 0o755)
            else:
                os.chmod(path, 0o644)
        except OSError:
            pass
    try:
        os.chmod(root, 0o755)
    except OSError:
        pass


def _make_writable_tree(root: Path) -> None:
    if not root.exists():
        return
    for path in root.rglob("*"):
        try:
            if path.is_dir():
                os.chmod(path, WRITABLE_DIR_MODE)
            else:
                os.chmod(path, WRITABLE_FILE_MODE)
        except OSError:
            pass
    try:
        os.chmod(root, WRITABLE_DIR_MODE if root.is_dir() else WRITABLE_FILE_MODE)
    except OSError:
        pass


def _chmod_if_possible(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _copy_artifact(source: Path, target: Path, *, reader_user: str | None) -> None:
    try:
        shutil.copy2(source, target)
        return
    except PermissionError:
        if reader_user is None:
            raise

    import subprocess

    result = subprocess.run(
        ["sudo", "-n", "-u", reader_user, "--", "cat", str(source)],
        check=True,
        capture_output=True,
    )
    target.write_bytes(result.stdout)
    os.chmod(target, 0o600)


def _current_turn_dir_rel(agent: Agent, turn_number: int) -> Path:
    if agent.role == "dm":
        return Path("dm") / "turns" / f"{turn_number:04d}"
    return Path("players") / agent.id / "turns" / f"{turn_number:04d}"


def _remove_tree(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        try:
            os.chmod(path, 0o700 if path.is_dir() else 0o600)
        except OSError:
            pass
    try:
        os.chmod(root, 0o700)
    except OSError:
        pass
    shutil.rmtree(root)
