"""CLI config: REPO_ROOT, Paths, get_paths."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Paths:
    content: Path
    campaigns: Path
    lore: Path | None = None


def load_config() -> dict[str, Any]:
    config_path = os.environ.get("GLASS_CONFIG")
    candidates = []
    if config_path:
        candidates.append(Path(config_path).expanduser())
    else:
        candidates.extend(
            [
                REPO_ROOT / "agents-of-glass.toml",
                REPO_ROOT / "agents-of-glass.local.toml",
            ]
        )

    for path in candidates:
        if path.exists():
            with path.open("rb") as handle:
                return tomllib.load(handle)
    return {}


def resolve_config_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def get_paths() -> Paths:
    config = load_config()
    path_config = config.get("paths", {})
    # `content` is the legacy alias; the modern key is `templates`.
    content = resolve_config_path(
        path_config.get("content") or path_config.get("templates"),
        REPO_ROOT / "templates",
    )
    campaigns = resolve_config_path(
        path_config.get("campaigns"), REPO_ROOT / "campaigns"
    )
    lore_cfg = config.get("lore", {}).get("path") if isinstance(config.get("lore"), dict) else None
    lore = resolve_config_path(lore_cfg, REPO_ROOT.parent / "the-glass-frontier-lore")
    return Paths(content=content, campaigns=campaigns, lore=lore)
