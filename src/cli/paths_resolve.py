"""Path resolution helpers for CLI command arguments.

These functions take a user-supplied path string and produce a validated
filesystem path under one of the allowed roots (templates/ or campaigns/).
Path traversal (`..`) is rejected. Absolute paths must stay under an
allowed root. Relative paths resolve against cwd if cwd is inside a
campaign or templates root, else against templates/.
"""

from __future__ import annotations

from pathlib import Path

from .config import REPO_ROOT, Paths
from .errors import GlassError
from .role import current_role


def clean_relative_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        path = Path(*path.parts[1:])
    if any(part == ".." for part in path.parts):
        raise GlassError("invalid path: '..' is not allowed")
    return path


def ensure_under(path: Path, root: Path, message: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise GlassError(message) from exc
    return resolved


def ensure_under_any(path: Path, roots: list[Path], message: str) -> Path:
    """Like ensure_under but accepts any of several allowed roots."""
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return resolved
        except ValueError:
            continue
    raise GlassError(message)


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def resolve_content_path(paths: Paths, path_text: str) -> Path:
    """Resolve a path argument from a CLI command.

    Absolute paths are accepted under templates/ or campaigns/ (or, when
    invoked from inside a campaign workspace, are taken as-is). Relative
    paths are resolved against the current working directory; if the cwd
    is a campaign workspace, that becomes the root.
    """
    raw = Path(path_text).expanduser()
    if raw.is_absolute():
        allowed = [paths.content]
        if paths.campaigns is not None:
            allowed.append(paths.campaigns)
        return ensure_under_any(
            raw,
            allowed,
            f"invalid path: absolute paths must stay under templates/ or campaigns/; got {raw}",
        )
    rel = clean_relative_path(path_text)
    # Strip a leading 'content' or 'templates' segment for backwards-compat.
    if rel.parts and rel.parts[0] in {"content", "templates"}:
        rel = Path(*rel.parts[1:])
    # Try cwd-relative first if cwd is inside a campaign workspace.
    cwd_candidate = (Path.cwd() / rel).resolve()
    if paths.campaigns is not None:
        try:
            cwd_candidate.relative_to(paths.campaigns.resolve())
            return cwd_candidate
        except ValueError:
            pass
        try:
            cwd_candidate.relative_to(paths.content.resolve())
            return cwd_candidate
        except ValueError:
            pass
    return paths.content / rel


def resolve_note_write_path(paths: Paths, path_text: str) -> Path:
    role = current_role()
    rel = clean_relative_path(path_text)
    if rel.parts and rel.parts[0] == "content":
        rel = Path(*rel.parts[1:])

    if role.kind == "player":
        if rel.parts and rel.parts[0] in {"journal", "drafts"}:
            rel = Path("players") / role.actor / rel
        allowed_roots = [
            Path("players") / role.actor / "journal",
            Path("players") / role.actor / "drafts",
        ]
        if not any(rel == root or root in rel.parents for root in allowed_roots):
            raise GlassError(
                "permission denied: players may write only their own journal/ or drafts/"
            )
    elif role.kind == "dm":
        if rel.parts and rel.parts[0] == "workspace":
            rel = Path("dm") / "workspace" / Path(*rel.parts[1:])
        elif rel.parts and rel.parts[0] == "lore":
            rel = Path("shared") / "lore" / Path(*rel.parts[1:])
        allowed_roots = [
            Path("dm") / "workspace",
            Path("dm") / "canonical-notes",
            Path("dm") / "intake",
            Path("shared") / "lore",
            Path("sessions") / "shared" / "lore",
        ]
        if not any(rel == root or root in rel.parents for root in allowed_roots):
            raise GlassError(
                "permission denied: DM note writes must stay in workspace/, dm/intake/, "
                "dm/canonical-notes/, or shared lore"
            )

    return paths.content / rel
