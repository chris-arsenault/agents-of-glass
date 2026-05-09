"""Configuration loading for the `aog` operator CLI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os
import tomllib


@dataclass(frozen=True)
class ClaudeConfig:
    model: str | None
    turn_timeout_seconds: int


@dataclass(frozen=True)
class CapsConfig:
    session_max_turns: int
    mode_default_max_turns: int
    mode_combat_max_turns: int
    mode_travel_max_turns: int

    def budget_for(self, mode: str) -> int | None:
        normalized = mode.lower()
        if normalized == "worldbuilding":
            return None
        if normalized == "combat":
            return self.mode_combat_max_turns
        if normalized in {"travel", "travel/montage", "montage"}:
            return self.mode_travel_max_turns
        if normalized == "wrap":
            return 3
        return self.mode_default_max_turns


@dataclass(frozen=True)
class AogConfig:
    repo_root: Path
    config_path: Path | None
    templates_dir: Path
    campaigns_dir: Path
    lore_path: Path
    claude: ClaudeConfig
    caps: CapsConfig


DEFAULT_CONFIG: dict[str, Any] = {
    "paths": {
        "templates": "templates",
        "campaigns": "campaigns",
    },
    "lore": {
        "path": "../the-glass-frontier-lore",
    },
    "claude": {
        "model": "claude-sonnet-4-6",
        # 60 minutes per turn. The DM in campaign-planning mode reads the
        # methodology, persona, world bible, does web search for the
        # anti-sameness pulls, and writes 8+ files per invocation. Tight
        # caps cut the agent off mid-thought and produce timeout failures
        # rather than transcripts. Override in agents-of-glass.toml if
        # you observe a different cadence.
        "turn_timeout_seconds": 3600,
    },
    "caps": {
        "session_max_turns": 200,
        "mode_default_max_turns": 12,
        "mode_combat_max_turns": 8,
        "mode_travel_max_turns": 4,
    },
}


def find_repo_root(start: Path | None = None) -> Path:
    """Find the project root by walking up to `pyproject.toml`."""

    cursor = (start or Path.cwd()).resolve()
    for candidate in (cursor, *cursor.parents):
        if (candidate / "pyproject.toml").exists():
            return candidate
    return cursor


def load_config(config_path: str | Path | None = None) -> AogConfig:
    repo_root = find_repo_root()
    explicit_path = Path(config_path).expanduser() if config_path else None

    data = _deep_merge({}, DEFAULT_CONFIG)
    loaded_paths: list[Path] = []

    if explicit_path:
        path = explicit_path.resolve()
        if not path.exists():
            raise FileNotFoundError(f"Config file does not exist: {path}")
        data = _deep_merge(data, _load_toml(path))
        loaded_paths.append(path)
    else:
        for name in ("agents-of-glass.toml", "agents-of-glass.local.toml"):
            path = repo_root / name
            if path.exists():
                data = _deep_merge(data, _load_toml(path))
                loaded_paths.append(path)

    base_dir = loaded_paths[0].parent if loaded_paths else repo_root
    paths = data.get("paths", {})
    lore = data.get("lore", {})
    claude = data.get("claude", {})
    caps = data.get("caps", {})

    return AogConfig(
        repo_root=repo_root,
        config_path=loaded_paths[-1] if loaded_paths else None,
        templates_dir=_resolve_path(
            base_dir,
            paths.get("templates", paths.get("content", "templates")),
        ),
        campaigns_dir=_resolve_path(
            base_dir,
            paths.get("campaigns", "campaigns"),
        ),
        lore_path=_resolve_path(base_dir, lore.get("path", "../the-glass-frontier-lore")),
        claude=ClaudeConfig(
            model=_optional_string(claude.get("model")),
            turn_timeout_seconds=int(claude.get("turn_timeout_seconds", 300)),
        ),
        caps=CapsConfig(
            session_max_turns=int(caps.get("session_max_turns", 200)),
            mode_default_max_turns=int(caps.get("mode_default_max_turns", 12)),
            mode_combat_max_turns=int(caps.get("mode_combat_max_turns", 8)),
            mode_travel_max_turns=int(caps.get("mode_travel_max_turns", 4)),
        ),
    )


def config_env_value(config: AogConfig) -> str:
    if config.config_path:
        return str(config.config_path)
    fallback = config.repo_root / "agents-of-glass.toml"
    return str(fallback)


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _resolve_path(base_dir: Path, value: str | os.PathLike[str]) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _deep_merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
