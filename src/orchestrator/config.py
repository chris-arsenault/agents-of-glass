"""Configuration loading for the `aog` operator CLI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os
import tomllib

from .state import PLAYER_IDS


@dataclass(frozen=True)
class ClaudeConfig:
    model: str | None
    turn_timeout_seconds: int
    use_session_id: bool


@dataclass(frozen=True)
class CapsConfig:
    session_max_turns: int
    mode_default_max_turns: int
    mode_scene_play_max_turns: int
    mode_action_max_turns: int

    def budget_for(self, mode: str) -> int | None:
        normalized = mode.lower()
        if normalized == "worldbuilding":
            return None
        if normalized == "intermission":
            return 15
        if normalized == "scene-play":
            return self.mode_scene_play_max_turns
        if normalized == "action":
            return self.mode_action_max_turns
        if normalized == "wrap":
            return 3
        return self.mode_default_max_turns


@dataclass(frozen=True)
class OrchestratorConfig:
    turn_minimum_seconds: int


@dataclass(frozen=True)
class AogConfig:
    repo_root: Path
    config_path: Path | None
    templates_dir: Path
    campaigns_dir: Path
    lore_path: Path
    agent_provider: str
    codex_players: tuple[str, ...]
    skip_player_persona: bool
    claude: ClaudeConfig
    caps: CapsConfig
    orchestrator: OrchestratorConfig


DEFAULT_CONFIG: dict[str, Any] = {
    "paths": {
        "templates": "templates",
        "campaigns": "campaigns",
    },
    "lore": {
        "path": "../the-glass-frontier-lore",
    },
    "agent": {
        "provider": "claude",
        "codex_players": list(PLAYER_IDS[:2]),
        "skip_player_persona": False,
    },
    "claude": {
        "model": "opus",
        # Always track one Claude Code session id per actor in runtime state.
        # When enabled, pass that id to `claude -p --session-id ...`.
        "use_session_id": False,
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
        "mode_scene_play_max_turns": 120,
        "mode_action_max_turns": 120,
    },
    "orchestrator": {
        # Minimum wall-clock duration per successful turn. If an agent finishes
        # faster, the orchestrator waits before starting the next turn. This
        # keeps unattended runs from burning through the turn budget too fast.
        "turn_minimum_seconds": 600,
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
    agent = data.get("agent", {})
    claude = data.get("claude", {})
    caps = data.get("caps", {})
    orchestrator = data.get("orchestrator", {})

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
        agent_provider=_agent_provider(agent.get("provider", "claude")),
        codex_players=_codex_players(agent.get("codex_players", list(PLAYER_IDS[:2]))),
        skip_player_persona=_bool(agent.get("skip_player_persona", False)),
        claude=ClaudeConfig(
            model=_optional_string(claude.get("model")),
            turn_timeout_seconds=int(claude.get("turn_timeout_seconds", 300)),
            use_session_id=_bool(claude.get("use_session_id", False)),
        ),
        caps=CapsConfig(
            session_max_turns=int(caps.get("session_max_turns", 200)),
            mode_default_max_turns=int(caps.get("mode_default_max_turns", 12)),
            mode_scene_play_max_turns=int(
                caps.get("mode_scene_play_max_turns", 120)
            ),
            mode_action_max_turns=int(caps.get("mode_action_max_turns", 120)),
        ),
        orchestrator=OrchestratorConfig(
            turn_minimum_seconds=max(
                int(orchestrator.get("turn_minimum_seconds", 600)),
                0,
            ),
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


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _agent_provider(value: Any) -> str:
    provider = str(value or "claude").strip().lower()
    if provider == "claude":
        return "claude"
    if provider in {"codex", "mixed-codex"}:
        return "mixed-codex"
    raise ValueError(
        f"Unsupported [agent].provider {provider!r}; use 'claude' or 'mixed-codex'."
    )


def provider_for_actor(config: AogConfig, *, actor_id: str, role: str) -> str:
    if config.agent_provider != "mixed-codex":
        return "claude"
    if role == "dm":
        return "codex"
    if actor_id in config.codex_players:
        return "codex"
    return "claude"


def _codex_players(value: Any) -> tuple[str, ...]:
    if value is None:
        return tuple(PLAYER_IDS[:2])
    if isinstance(value, str):
        raw_items = [value]
    else:
        try:
            raw_items = list(value)
        except TypeError as exc:
            raise ValueError(
                "[agent].codex_players must be an array of player ids."
            ) from exc
    players: list[str] = []
    seen: set[str] = set()
    for raw in raw_items:
        player_id = str(raw).strip().lower()
        if not player_id:
            continue
        if player_id not in PLAYER_IDS:
            raise ValueError(
                f"Unknown [agent].codex_players entry {player_id!r}; expected one of {', '.join(PLAYER_IDS)}."
            )
        if player_id in seen:
            continue
        seen.add(player_id)
        players.append(player_id)
    return tuple(players)
