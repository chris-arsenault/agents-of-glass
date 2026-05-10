"""Local repo `.env` loading for operator-owned processes."""

from __future__ import annotations

from pathlib import Path
import os

from .config import REPO_ROOT


def load_repo_env(
    path: Path | None = None,
    *,
    override: bool = False,
) -> dict[str, str]:
    """Load repo-local `.env` values into ``os.environ``.

    This is intentionally small: KEY=VALUE lines, optional single/double quotes,
    comments, and blank lines. Caller-provided environment wins by default so
    `with-cred` can override the local file.
    """

    values = dotenv_values(path or REPO_ROOT / ".env")
    for key, value in values.items():
        if override or key not in os.environ:
            os.environ[key] = value
    return values


def dotenv_values(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return {}

    values: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]
        values[key] = value
    return values
