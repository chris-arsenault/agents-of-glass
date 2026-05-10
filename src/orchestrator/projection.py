"""Per-turn read-only campaign workspace projections.

Agents are good at reading files directly, so each turn gets a campaign-shaped
workspace containing only the files that actor may see. The relative paths are
the same as the canonical campaign tree; persistent mutations go through
`glass`, not filesystem writes into this projection.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .config import AogConfig
from .state import Agent


READONLY_DIR_MODE = 0o555
READONLY_FILE_MODE = 0o444
WRITABLE_DIR_MODE = 0o777

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
    turn_output_path: Path
    scratch_dir: Path


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
    canonical_turn_output_path: Path,
) -> ProjectionPaths:
    """Create a fresh read-only projection for one actor turn."""

    root = projection_root_for(
        config,
        campaign=campaign_root.name,
        turn_number=turn_number,
        agent=agent,
    )
    _remove_tree(root)
    root.mkdir(parents=True, exist_ok=True)

    current_turn_dir_rel = canonical_turn_start_path.parent.relative_to(campaign_root)
    current_turn_start_rel = canonical_turn_start_path.relative_to(campaign_root)
    current_turn_output_rel = canonical_turn_output_path.relative_to(campaign_root)

    # Create visible empty directories first so table/handouts and similar
    # roots are still discoverable even before they contain files.
    for directory in sorted(_iter_dirs(campaign_root), key=lambda item: item[0]):
        rel, source = directory
        if _directory_visible(rel, agent, current_turn_dir_rel):
            (root / rel).mkdir(parents=True, exist_ok=True)

    for rel, source in sorted(_iter_files(campaign_root), key=lambda item: item[0]):
        if not _file_visible(rel, agent, current_turn_start_rel):
            continue
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        _copy_file(source, target, campaign_root=campaign_root)

    projected_turn_dir = root / current_turn_dir_rel
    projected_turn_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir = root / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    _make_readonly(root)
    os.chmod(projected_turn_dir, WRITABLE_DIR_MODE)
    os.chmod(scratch_dir, WRITABLE_DIR_MODE)

    return ProjectionPaths(
        root=root,
        turn_dir=projected_turn_dir,
        turn_start_path=root / current_turn_start_rel,
        turn_output_path=root / current_turn_output_rel,
        scratch_dir=scratch_dir,
    )


def copy_turn_artifacts_to_canonical(
    *,
    projection: ProjectionPaths,
    canonical_turn_dir: Path,
) -> None:
    """Copy generated turn artifacts from projection back to canonical storage."""

    for name in ("out.md", "claude-debug.log"):
        source = projection.turn_dir / name
        if not source.exists():
            continue
        target = canonical_turn_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


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


def _make_readonly(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_dir():
            os.chmod(path, READONLY_DIR_MODE)
        else:
            os.chmod(path, READONLY_FILE_MODE)
    os.chmod(root, READONLY_DIR_MODE)


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
