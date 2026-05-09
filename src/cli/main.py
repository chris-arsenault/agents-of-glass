"""Entry point for the `glass` CLI.

The CLI is the in-session tool surface for Agents of Glass. It intentionally
keeps prose in markdown and records only coherence-critical state: sessions,
mode labels, dice, character numbers, messages, note ratification state, and
turn metadata.
"""

from __future__ import annotations

import difflib
import json
import os
import random
import re
import shutil
import sys
import tomllib
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

import click

from . import db as _db
from . import workspace as _workspace


REPO_ROOT = Path(__file__).resolve().parents[2]

RISK_THRESHOLDS = {
    "controlled": 7,
    "standard": 8,
    "risky": 9,
    "desperate": 10,
}
ATTRIBUTE_TIERS = {
    "rudimentary": -2,
    "standard": 0,
    "advanced": 1,
    "superior": 2,
    "transcendent": 4,
}
SKILL_TIERS = {
    "fool": -2,
    "apprentice": 0,
    "artisan": 1,
    "virtuoso": 2,
    "legend": 4,
}
ATTRIBUTES = (
    "vitality",
    "finesse",
    "focus",
    "resolve",
    "attunement",
    "ingenuity",
    "presence",
)
STARTER_MESSAGE_TYPES = {
    "table-talk",
    "banter",
    "instruction",
    "plot-hint",
    "secret",
}


class GlassError(click.ClickException):
    """Agent-friendly CLI error."""


@dataclass(frozen=True)
class Role:
    kind: str
    actor: str
    raw: str | None

    @property
    def can_do_anything(self) -> bool:
        return self.kind == "operator"


@dataclass(frozen=True)
class Paths:
    content: Path
    sessions: Path
    campaigns: Path | None = None
    lore: Path | None = None


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "session"


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
    sessions = resolve_config_path(path_config.get("sessions"), content / "sessions")
    campaigns = resolve_config_path(
        path_config.get("campaigns"), REPO_ROOT / "campaigns"
    )
    lore_cfg = config.get("lore", {}).get("path") if isinstance(config.get("lore"), dict) else None
    lore = resolve_config_path(lore_cfg, REPO_ROOT.parent / "the-glass-frontier-lore")
    return Paths(content=content, sessions=sessions, campaigns=campaigns, lore=lore)


def active_campaign_id() -> str:
    """Return the campaign id for character/roll DB scope.

    Resolves from GLASS_CAMPAIGN_ID, then the most-recently-modified campaign
    workspace under paths.campaigns. Raises GlassError if neither is available.
    """
    explicit = os.environ.get("GLASS_CAMPAIGN_ID")
    if explicit:
        return explicit
    paths = get_paths()
    if paths.campaigns is None:
        raise GlassError(
            "active campaign required: set GLASS_CAMPAIGN_ID or configure paths.campaigns"
        )
    try:
        return _workspace.resolve_active_campaign(paths.campaigns).campaign_id
    except FileNotFoundError as exc:
        raise GlassError(str(exc)) from exc


def active_campaign_root() -> Path:
    """Return the filesystem root of the active campaign workspace.

    Falls back to paths.content (templates) when no campaign is active —
    used for tests and dev where the runtime workspace doesn't exist.
    """
    explicit = os.environ.get("GLASS_CAMPAIGN_ID")
    paths = get_paths()
    if paths.campaigns is None:
        return paths.content
    try:
        if explicit:
            return _workspace.resolve_active_campaign(
                paths.campaigns, env_id=explicit
            ).root
        return _workspace.resolve_active_campaign(paths.campaigns).root
    except FileNotFoundError:
        return paths.content


def lookup_player_character_id(campaign_id: str, player_id: str) -> str | None:
    """Look up the character id for a player in the active campaign. Returns
    None if the player has no character or has multiple."""
    try:
        with pg_connection() as conn:
            characters = _db.character_list(conn, campaign_id)
    except GlassError:
        return None
    candidates = [c["character_id"] for c in characters if c.get("player_id") == player_id]
    if len(candidates) == 1:
        return candidates[0]
    return None


@contextmanager
def pg_connection() -> Iterator[Any]:
    """Open a Postgres connection from the resolved config."""
    pg_config = _db.load_pg_config(load_config())
    try:
        with _db.connect(pg_config) as conn:
            yield conn
    except GlassError:
        raise
    except Exception as exc:
        raise GlassError(f"postgres connection failed ({pg_config.describe()}): {exc}") from exc


def current_role() -> Role:
    raw = os.environ.get("GLASS_ROLE")
    if raw is None or raw == "":
        return Role(kind="operator", actor="operator", raw=raw)
    if raw == "dm":
        return Role(kind="dm", actor="dm", raw=raw)
    if raw.startswith("player:"):
        actor = raw.split(":", 1)[1].strip()
        if actor:
            return Role(kind="player", actor=actor, raw=raw)
    if raw.startswith("player_"):
        actor = raw.split("_", 1)[1].strip()
        if actor:
            return Role(kind="player", actor=actor, raw=raw)
    raise GlassError(
        "invalid GLASS_ROLE: expected unset/operator, 'dm', or 'player:<id>' "
        f"(got {raw!r})"
    )


def require_dm() -> Role:
    role = current_role()
    if role.can_do_anything or role.kind == "dm":
        return role
    raise GlassError("permission denied: this command is DM-only")


def require_player() -> Role:
    role = current_role()
    if role.can_do_anything or role.kind == "player":
        return role
    raise GlassError("permission denied: this command is player-only")


def active_session_file(paths: Paths) -> Path:
    return paths.sessions / ".active-session"


def write_active_session(paths: Paths, session_id: str) -> None:
    paths.sessions.mkdir(parents=True, exist_ok=True)
    active_session_file(paths).write_text(f"{session_id}\n", encoding="utf-8")


def active_session_id(paths: Paths, required: bool = True) -> str | None:
    env_session = os.environ.get("GLASS_SESSION_ID")
    if env_session:
        return env_session
    active = active_session_file(paths)
    if active.exists():
        value = active.read_text(encoding="utf-8").strip()
        if value:
            return value
    if required:
        raise GlassError("no active session: set GLASS_SESSION_ID or run 'glass session new'")
    return None


def session_dir(paths: Paths, session_id: str) -> Path:
    return paths.sessions / session_id


def state_path(paths: Paths, session_id: str) -> Path:
    return session_dir(paths, session_id) / "state.json"


def audit_path(paths: Paths, session_id: str) -> Path:
    return session_dir(paths, session_id) / "audit.jsonl"


def transcript_path(paths: Paths, session_id: str) -> Path:
    return session_dir(paths, session_id) / "transcript.md"


def default_state(session_id: str, campaign: str) -> dict[str, Any]:
    ts = now_iso()
    return {
        "schema_version": 3,
        "session": {
            "id": session_id,
            "campaign": campaign,
            "status": "active",
            "created_at": ts,
            "updated_at": ts,
            "wrapped_at": None,
            "summary": "",
            "turn_counter": 0,
        },
        "mode_stack": [],
        "pending_events": [],
        "note_intake": [],
        "entities": {},
        "threads": {},
        "turns": [],
        "next_speaker": None,
    }


def normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    state.setdefault("schema_version", 3)
    state.setdefault("mode_stack", [])
    state.setdefault("pending_events", [])
    state.setdefault("note_intake", [])
    state.setdefault("entities", {})
    state.setdefault("threads", {})
    state.setdefault("turns", [])
    state.setdefault("session", {})
    state.setdefault("next_speaker", None)
    state["session"].setdefault("turn_counter", len(state["turns"]))
    state["session"].setdefault("status", "active")
    # Drop any legacy keys silently — pre-v1 state may include them.
    for legacy in (
        "characters", "dice_events", "mechanical_events",
        "uncommitted_event_ids", "messages",
    ):
        state.pop(legacy, None)
    return state


def load_state(paths: Paths, session_id: str | None = None) -> dict[str, Any]:
    session = session_id or active_session_id(paths)
    path = state_path(paths, session)
    if not path.exists():
        raise GlassError(f"unknown session: {session}")
    return normalize_state(json.loads(path.read_text(encoding="utf-8")))


def save_state(paths: Paths, state: dict[str, Any]) -> None:
    state["session"]["updated_at"] = now_iso()
    session = state["session"]["id"]
    directory = session_dir(paths, session)
    directory.mkdir(parents=True, exist_ok=True)
    path = state_path(paths, session)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def append_audit(
    paths: Paths,
    state: dict[str, Any],
    ctx: click.Context,
    event: str,
    params: dict[str, Any],
    result: dict[str, Any],
) -> None:
    session_id = state["session"]["id"]
    role = current_role()
    record = {
        "audit_id": new_id("audit"),
        "ts": now_iso(),
        "session_id": session_id,
        "role": role.raw or "operator",
        "actor": role.actor,
        "command": ctx.command_path,
        "event": event,
        "params": make_jsonable(params),
        "result": make_jsonable(result),
    }
    path = audit_path(paths, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def commit(
    paths: Paths,
    state: dict[str, Any],
    ctx: click.Context,
    event: str,
    params: dict[str, Any],
    result: dict[str, Any],
    *,
    save: bool = True,
) -> None:
    if save:
        save_state(paths, state)
    append_audit(paths, state, ctx, event, params, result)
    emit(result)


def make_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [make_jsonable(item) for item in value]
    if isinstance(value, list):
        return [make_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): make_jsonable(item) for key, item in value.items()}
    return value


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "":
        return '""'
    simple = re.fullmatch(r"[A-Za-z0-9_./:+-]+", text)
    lower = text.lower()
    if simple and lower not in {"null", "true", "false", "yes", "no"}:
        return text
    return json.dumps(text)


def to_yaml(value: Any, indent: int = 0) -> str:
    pad = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{pad}{key}:")
                lines.append(to_yaml(item, indent + 2))
            elif isinstance(item, dict):
                lines.append(f"{pad}{key}: {{}}")
            elif isinstance(item, list):
                lines.append(f"{pad}{key}: []")
            else:
                lines.append(f"{pad}{key}: {yaml_scalar(item)}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{pad}[]"
        lines = []
        for item in value:
            if isinstance(item, dict):
                lines.append(f"{pad}-")
                lines.append(to_yaml(item, indent + 2))
            elif isinstance(item, list):
                lines.append(f"{pad}-")
                lines.append(to_yaml(item, indent + 2))
            else:
                lines.append(f"{pad}- {yaml_scalar(item)}")
        return "\n".join(lines)
    return f"{pad}{yaml_scalar(value)}"


def emit(value: dict[str, Any]) -> None:
    click.echo(to_yaml(value))


def read_body(body: str | None, from_file: str | None) -> str:
    if body is not None:
        return body
    if from_file:
        if from_file == "-":
            return sys.stdin.read()
        return Path(from_file).expanduser().read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


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


def player_dirs(paths: Paths) -> list[str]:
    players_root = paths.content / "players"
    if not players_root.exists():
        return []
    return sorted(path.name for path in players_root.iterdir() if path.is_dir())


def roster(paths: Paths, state: dict[str, Any] | None = None) -> list[str]:
    return sorted(set(player_dirs(paths)))


def infer_player_from_path(paths: Paths, path: Path) -> str | None:
    try:
        rel = path.resolve().relative_to(paths.content.resolve())
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) >= 3 and parts[0] == "players" and parts[2] == "drafts":
        return parts[1]
    return None


def validate_key_values(
    values: tuple[str, ...],
    valid_values: dict[str, int],
    label: str,
) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise GlassError(f"invalid {label}: expected name=tier, got {value!r}")
        name, tier = value.split("=", 1)
        name = name.strip()
        tier = tier.strip()
        if not name:
            raise GlassError(f"invalid {label}: name cannot be empty")
        if tier not in valid_values:
            options = ", ".join(sorted(valid_values))
            raise GlassError(f"invalid {label} tier {tier!r}; valid tiers: {options}")
        parsed[name] = tier
    return parsed


def assert_attribute_name(attribute: str) -> None:
    if attribute not in ATTRIBUTES:
        raise GlassError(
            f"unknown attribute {attribute!r}; valid attributes: {', '.join(ATTRIBUTES)}"
        )


def clamp(value: int, floor: int, ceiling: int) -> int:
    return max(floor, min(ceiling, value))


def outcome_for_margin(margin: int) -> tuple[str, int]:
    if margin >= 2:
        return "breakthrough", 2
    if margin >= 0:
        return "advance", 1
    if margin == -1:
        return "stall", 0
    if margin >= -3:
        return "regress", -1
    return "collapse", -2


def assert_character_writable(character: dict[str, Any]) -> Role:
    role = current_role()
    if role.can_do_anything or role.kind == "dm":
        return role
    if role.kind == "player" and character.get("player_id") == role.actor:
        return role
    raise GlassError(
        "permission denied: players may mutate only their own character "
        f"(owner: {character.get('player_id')})"
    )


def queue_event(state: dict[str, Any], actor: str, summary: str) -> dict[str, Any]:
    """Queue a one-line summary to be inlined into the next turn's transcript."""
    event = {
        "event_id": new_id("event"),
        "actor": actor,
        "ts": now_iso(),
        "summary": summary,
    }
    state["pending_events"].append(event)
    return event


def inline_event_lines(events: list[dict[str, Any]]) -> list[str]:
    if not events:
        return []
    return [f"> {event['summary']}" for event in events]


def current_mode_record(state: dict[str, Any]) -> dict[str, Any] | None:
    stack = state.get("mode_stack", [])
    return stack[-1] if stack else None


def role_label_for_turn(role: Role, explicit_role: str | None) -> str:
    if explicit_role:
        return explicit_role
    if role.kind == "dm":
        return "dm"
    if role.kind == "player":
        return "player"
    return "operator"


def actor_for_turn(role: Role, speaker: str | None) -> str:
    if speaker:
        return speaker
    return role.actor


def state_summary(state: dict[str, Any]) -> dict[str, Any]:
    current = current_mode_record(state)
    return {
        "session_id": state["session"]["id"],
        "campaign": state["session"]["campaign"],
        "status": state["session"]["status"],
        "created_at": state["session"]["created_at"],
        "updated_at": state["session"]["updated_at"],
        "wrapped_at": state["session"].get("wrapped_at"),
        "current_mode": current["mode"] if current else None,
        "current_scene": current["scene_id"] if current else None,
        "mode_stack": state.get("mode_stack", []),
        "turn_count": len(state.get("turns", [])),
        "pending_events": len(state.get("pending_events", [])),
        "pending_notes": [
            item["intake_id"]
            for item in state.get("note_intake", [])
            if item.get("status") == "pending"
        ],
    }


def load_message_types(paths: Paths) -> set[str]:
    vocab_path = paths.content / "shared" / "vocabulary" / "message-types.md"
    if not vocab_path.exists():
        return set(STARTER_MESSAGE_TYPES)
    text = vocab_path.read_text(encoding="utf-8")
    found = set(re.findall(r"`([a-z][a-z0-9-]*)`", text))
    for line in text.splitlines():
        match = re.match(r"\s*[-*]\s+([a-z][a-z0-9-]*)(?:\s*[-:;.]|\s*$)", line)
        if match and match.group(1) not in {"stub"}:
            found.add(match.group(1))
    return found or set(STARTER_MESSAGE_TYPES)


def require_message_type(paths: Paths, message_type: str) -> None:
    valid = load_message_types(paths)
    if message_type in valid:
        return
    suggestion = difflib.get_close_matches(message_type, sorted(valid), n=1)
    suffix = f" Did you mean {suggestion[0]!r}?" if suggestion else ""
    raise GlassError(
        f"unknown message type {message_type!r}; valid types: {', '.join(sorted(valid))}.{suffix}"
    )


def require_recipient(paths: Paths, state: dict[str, Any], recipient: str) -> None:
    valid = {"dm", "party", *roster(paths, state)}
    if recipient in valid:
        return
    options = ", ".join(sorted(valid))
    raise GlassError(f"unknown recipient {recipient!r}; valid recipients: {options}")


def message_visible_to(message: dict[str, Any], role: Role) -> bool:
    if role.can_do_anything or role.kind == "dm":
        return True
    if role.kind != "player":
        return False
    recipient = message["recipient"]
    return (
        recipient == "party"
        or recipient == role.actor
        or message["sender"] == role.actor
    )


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    raw = text[4:end]
    data: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


def markdown_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def parse_sections(text: str, entity_id: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current_title = "body"
    current_lines: list[str] = []

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if body:
            section_id = f"{entity_id}:{slugify(current_title)}"
            sections.append(
                {
                    "section_id": section_id,
                    "title": current_title,
                    "text": body,
                }
            )

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            current_title = line[3:].strip() or "section"
            current_lines = []
        else:
            current_lines.append(line)
    flush()
    return sections


def upsert_entity_from_path(paths: Paths, state: dict[str, Any], path: Path) -> dict[str, Any]:
    allowed_roots = [paths.content]
    if paths.campaigns is not None:
        allowed_roots.append(paths.campaigns)
    path = ensure_under_any(
        path,
        allowed_roots,
        f"entity paths must stay under templates/ or campaigns/; got {path}",
    )
    if not path.exists():
        raise GlassError(f"entity source not found: {display_path(path)}")
    text = path.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(text)
    entity_id = frontmatter.get("id") or slugify(path.stem)
    record = {
        "entity_id": entity_id,
        "title": frontmatter.get("title") or markdown_title(text, path.stem),
        "path": display_path(path),
        "updated_at": now_iso(),
        "sections": parse_sections(text, entity_id),
        "frontmatter": frontmatter,
        "edges": [],
    }
    state["entities"][entity_id] = record
    return record


def command_params(**kwargs: Any) -> dict[str, Any]:
    return make_jsonable(kwargs)


@click.group()
def main() -> None:
    """In-session state CLI for Agents of Glass."""


@main.group()
def session() -> None:
    """Session lifecycle commands."""


@session.command("new")
@click.option("--campaign", required=True, help="Human-readable campaign name.")
@click.option("--session-id", help="Explicit session id. Defaults to campaign slug + timestamp.")
@click.pass_context
def session_new(ctx: click.Context, campaign: str, session_id: str | None) -> None:
    paths = get_paths()
    paths.sessions.mkdir(parents=True, exist_ok=True)
    if not session_id:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        session_id = f"{slugify(campaign)}-{stamp}"
    session_id = slugify(session_id)
    directory = session_dir(paths, session_id)
    if directory.exists():
        raise GlassError(f"session already exists: {session_id}")

    state = default_state(session_id, campaign)
    directory.mkdir(parents=True, exist_ok=False)
    transcript_path(paths, session_id).write_text(
        f"# {campaign}\n\nSession: `{session_id}`\n\n", encoding="utf-8"
    )
    (directory / "scene-framing.md").write_text("# Scene Framing\n\n", encoding="utf-8")
    save_state(paths, state)
    write_active_session(paths, session_id)
    result = {
        "session_id": session_id,
        "campaign": campaign,
        "status": "active",
        "path": display_path(directory),
        "active": True,
    }
    append_audit(paths, state, ctx, "session.new", command_params(campaign=campaign), result)
    emit(result)


@session.command("show")
@click.option("--session-id", help="Session id to show. Defaults to GLASS_SESSION_ID or active.")
@click.pass_context
def session_show(ctx: click.Context, session_id: str | None) -> None:
    paths = get_paths()
    state = load_state(paths, session_id)
    result = state_summary(state)
    append_audit(paths, state, ctx, "session.show", command_params(session_id=session_id), result)
    emit(result)


@session.command("list")
@click.pass_context
def session_list(ctx: click.Context) -> None:
    paths = get_paths()
    paths.sessions.mkdir(parents=True, exist_ok=True)
    active = active_session_id(paths, required=False)
    records = []
    for path in sorted(paths.sessions.iterdir()):
        if not path.is_dir():
            continue
        state_file = path / "state.json"
        if not state_file.exists():
            continue
        state = normalize_state(json.loads(state_file.read_text(encoding="utf-8")))
        records.append(
            {
                "session_id": state["session"]["id"],
                "campaign": state["session"]["campaign"],
                "status": state["session"]["status"],
                "updated_at": state["session"]["updated_at"],
                "active": state["session"]["id"] == active,
            }
        )
    result = {"sessions": records}
    if active:
        state = load_state(paths, active)
        append_audit(paths, state, ctx, "session.list", {}, result)
    emit(result)


@session.command("wrap")
@click.option("--summary", help="Session summary text.")
@click.option("--from", "from_file", help="Read summary from this file, or '-' for stdin.")
@click.pass_context
def session_wrap(ctx: click.Context, summary: str | None, from_file: str | None) -> None:
    require_dm()
    paths = get_paths()
    state = load_state(paths)
    body = read_body(summary, from_file).strip()
    state["session"]["status"] = "wrapped"
    state["session"]["wrapped_at"] = now_iso()
    state["session"]["summary"] = body
    result = {
        "session_id": state["session"]["id"],
        "status": "wrapped",
        "wrapped_at": state["session"]["wrapped_at"],
        "summary": body,
    }
    commit(paths, state, ctx, "session.wrap", command_params(summary=body), result)


@main.group()
def mode() -> None:
    """Mode stack commands."""


@mode.command("start")
@click.argument("mode_name")
@click.argument("scene_id")
@click.pass_context
def mode_start(ctx: click.Context, mode_name: str, scene_id: str) -> None:
    role = require_dm()
    paths = get_paths()
    state = load_state(paths)
    record = {
        "mode": slugify(mode_name),
        "scene_id": slugify(scene_id),
        "started_at": now_iso(),
        "started_by": role.actor,
    }
    state["mode_stack"].append(record)
    queue_event(
        state,
        role.actor,
        f"mode start {record['mode']} @ {record['scene_id']}",
    )
    result = {
        "current_mode": record["mode"],
        "current_scene": record["scene_id"],
        "mode_stack": state["mode_stack"],
    }
    commit(
        paths,
        state,
        ctx,
        "mode.start",
        command_params(mode_name=mode_name, scene_id=scene_id),
        result,
    )


@mode.command("end")
@click.pass_context
def mode_end(ctx: click.Context) -> None:
    role = require_dm()
    paths = get_paths()
    state = load_state(paths)
    if not state["mode_stack"]:
        raise GlassError("cannot end mode: mode stack is empty")
    ended = state["mode_stack"].pop()
    ended["ended_at"] = now_iso()
    current = current_mode_record(state)
    queue_event(
        state,
        role.actor,
        f"mode end {ended['mode']} @ {ended['scene_id']}",
    )
    result = {
        "ended": ended,
        "current_mode": current["mode"] if current else None,
        "current_scene": current["scene_id"] if current else None,
        "mode_stack": state["mode_stack"],
    }
    commit(paths, state, ctx, "mode.end", {}, result)


@mode.command("current")
@click.pass_context
def mode_current(ctx: click.Context) -> None:
    paths = get_paths()
    state = load_state(paths)
    current = current_mode_record(state)
    result = {
        "current_mode": current["mode"] if current else None,
        "current_scene": current["scene_id"] if current else None,
        "mode_stack": state["mode_stack"],
    }
    append_audit(paths, state, ctx, "mode.current", {}, result)
    emit(result)


@main.command("roll")
@click.argument("skill")
@click.argument("attribute")
@click.option("--risk", required=True, type=click.Choice(sorted(RISK_THRESHOLDS)))
@click.option("--character", "character_id", required=True)
@click.option("--target", "target_id")
@click.pass_context
def roll(
    ctx: click.Context,
    skill: str,
    attribute: str,
    risk: str,
    character_id: str,
    target_id: str | None,
) -> None:
    assert_attribute_name(attribute)
    paths = get_paths()
    state = load_state(paths)
    role = current_role()
    campaign_id = active_campaign_id()

    with pg_connection() as conn:
        character = _db.character_get(conn, campaign_id, character_id)
        if character is None:
            raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
        if role.kind == "player" and character.get("player_id") != role.actor:
            raise GlassError(
                "permission denied: players may roll only their own character "
                f"(owner: {character.get('player_id')})"
            )

        skill_tier = character["skills"].get(skill, "fool")
        attribute_tier = character["attributes"].get(attribute, "standard")
        skill_modifier = SKILL_TIERS[skill_tier]
        attribute_modifier = ATTRIBUTE_TIERS[attribute_tier]
        momentum_in = int(character["momentum"]["current"])
        floor = int(character["momentum"]["floor"])
        ceiling = int(character["momentum"]["ceiling"])

        dice = [random.SystemRandom().randint(1, 6), random.SystemRandom().randint(1, 6)]
        target = RISK_THRESHOLDS[risk]
        total = sum(dice) + skill_modifier + attribute_modifier + momentum_in
        margin = total - target
        outcome, momentum_delta = outcome_for_margin(margin)
        momentum_out = clamp(momentum_in + momentum_delta, floor, ceiling)

        scene_id: str | None = None
        current = current_mode_record(state)
        if current and current.get("scene_id") and current["scene_id"] != "none":
            scene_id = current["scene_id"]

        roll_row = _db.roll_record(
            conn,
            campaign_id=campaign_id,
            session_id=state["session"]["id"],
            scene_id=scene_id,
            character_id=character_id,
            actor=role.actor,
            skill=skill,
            attribute=attribute,
            risk=risk,
            dice=dice,
            skill_tier=skill_tier,
            skill_modifier=skill_modifier,
            attribute_tier=attribute_tier,
            attribute_modifier=attribute_modifier,
            momentum_in=momentum_in,
            total=total,
            target=target,
            margin=margin,
            outcome=outcome,
            momentum_delta=momentum_delta,
            momentum_out=momentum_out,
            target_id=target_id,
        )
        # Persist new momentum back to the character row.
        _db.character_set_momentum_internal(
            conn,
            campaign_id=campaign_id,
            character_id=character_id,
            value=momentum_out,
        )
        # Skill-by-use: advance grants 1 skill_xp, breakthrough grants 2.
        # Failures do not award skill_xp.
        skill_xp_delta = 0
        if outcome == "advance":
            skill_xp_delta = 1
        elif outcome == "breakthrough":
            skill_xp_delta = 2
        existing_xp = int(character["skill_xp"].get(skill, 0))
        skill_xp_before = existing_xp
        skill_xp_after = existing_xp
        skill_bumped_to: str | None = None
        if skill_xp_delta:
            (
                skill_xp_before,
                skill_xp_after,
                skill_bumped_to,
            ) = _db.character_apply_skill_xp(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                skill=skill,
                delta=skill_xp_delta,
            )
        conn.commit()

    target_suffix = f" -> {target_id}" if target_id else ""
    summary = (
        f"roll {skill} ({attribute}) @ {risk}: {total} vs {target} -> "
        f"{outcome} ({momentum_in:+d} to {momentum_out:+d} momentum){target_suffix}"
    )
    queue_event(state, role.actor, summary)
    if skill_bumped_to:
        queue_event(
            state,
            role.actor,
            f"{character_id} skill {skill} -> {skill_bumped_to} (xp {skill_xp_after})",
        )
    roll_row["skill_xp_before"] = skill_xp_before
    roll_row["skill_xp_after"] = skill_xp_after
    roll_row["skill_bumped_to"] = skill_bumped_to
    commit(
        paths,
        state,
        ctx,
        "roll",
        command_params(
            skill=skill,
            attribute=attribute,
            risk=risk,
            character_id=character_id,
            target_id=target_id,
        ),
        roll_row,
    )


@main.group()
def character() -> None:
    """Character sheet and hard-state commands."""


@character.command("new")
@click.argument("character_id")
@click.option("--player", "player_id", required=True)
@click.option("--name")
@click.option("--archetype", default="")
@click.option("--pronouns", default="")
@click.option("--hp", "hp_max", type=int, default=10)
@click.option("--attribute", "attribute_values", multiple=True, help="Repeatable name=tier.")
@click.option("--skill", "skill_values", multiple=True, help="Repeatable name=tier.")
@click.option("--tag", "tags", multiple=True)
@click.pass_context
def character_new(
    ctx: click.Context,
    character_id: str,
    player_id: str,
    name: str | None,
    archetype: str,
    pronouns: str,
    hp_max: int,
    attribute_values: tuple[str, ...],
    skill_values: tuple[str, ...],
    tags: tuple[str, ...],
) -> None:
    role = current_role()
    if role.kind == "player" and player_id != role.actor:
        raise GlassError("permission denied: players may create only their own character")
    if hp_max <= 0:
        raise GlassError("--hp must be greater than zero")
    paths = get_paths()
    state = load_state(paths)
    campaign_id = active_campaign_id()

    attributes = {attribute: "standard" for attribute in ATTRIBUTES}
    attributes.update(validate_key_values(attribute_values, ATTRIBUTE_TIERS, "attribute"))
    for attribute_name in attributes:
        assert_attribute_name(attribute_name)
    skills = validate_key_values(skill_values, SKILL_TIERS, "skill")

    with pg_connection() as conn:
        if _db.character_exists(conn, campaign_id, character_id):
            raise GlassError(
                f"character already exists in campaign {campaign_id!r}: {character_id}"
            )
        record = _db.character_create(
            conn,
            campaign_id=campaign_id,
            character_id=character_id,
            player_id=player_id,
            name=name or character_id,
            archetype=archetype,
            pronouns=pronouns,
            attributes=attributes,
            skills=skills,
            hp_max=hp_max,
            tags=list(tags),
        )

    queue_event(
        state,
        role.actor,
        f"character new {character_id} ({record['name']}, {player_id})",
    )
    commit(
        paths,
        state,
        ctx,
        "character.new",
        command_params(character_id=character_id, player_id=player_id),
        {"character": record},
    )


@character.command("get")
@click.argument("character_id")
@click.pass_context
def character_get(ctx: click.Context, character_id: str) -> None:
    paths = get_paths()
    state = load_state(paths)
    campaign_id = active_campaign_id()
    with pg_connection() as conn:
        character = _db.character_get(conn, campaign_id, character_id)
    if character is None:
        raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
    result = {"character": character}
    append_audit(
        paths,
        state,
        ctx,
        "character.get",
        command_params(character_id=character_id),
        result,
    )
    emit(result)


@character.command("list")
@click.pass_context
def character_list(ctx: click.Context) -> None:
    paths = get_paths()
    state = load_state(paths)
    campaign_id = active_campaign_id()
    with pg_connection() as conn:
        characters = _db.character_list(conn, campaign_id)
    result = {
        "campaign_id": campaign_id,
        "characters": [
            {
                "character_id": c["character_id"],
                "player_id": c["player_id"],
                "name": c["name"],
                "archetype": c["archetype"],
                "hp": c["hp"],
                "momentum": c["momentum"],
            }
            for c in characters
        ],
    }
    append_audit(paths, state, ctx, "character.list", {}, result)
    emit(result)


@character.command("set-hp", context_settings={"ignore_unknown_options": True})
@click.argument("character_id")
@click.argument("delta", type=int)
@click.pass_context
def character_set_hp(ctx: click.Context, character_id: str, delta: int) -> None:
    paths = get_paths()
    state = load_state(paths)
    campaign_id = active_campaign_id()

    with pg_connection() as conn:
        existing = _db.character_get(conn, campaign_id, character_id)
        if existing is None:
            raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
        role = assert_character_writable(existing)
        try:
            updated, before, after = _db.character_update_hp(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                delta=delta,
            )
        except LookupError:
            raise GlassError(f"unknown character {character_id!r}") from None

    sign = f"{delta:+d}"
    summary = f"{character_id} hp {sign} ({before} -> {after})"
    queue_event(state, role.actor, summary)
    result = {
        "character_id": character_id,
        "hp_before": before,
        "delta": delta,
        "applied_delta": after - before,
        "hp_after": after,
        "hp_max": updated["hp"]["max"],
    }
    commit(
        paths,
        state,
        ctx,
        "character.set-hp",
        command_params(character_id=character_id, delta=delta),
        result,
    )


@character.command("award-xp", context_settings={"ignore_unknown_options": True})
@click.argument("character_id")
@click.argument("delta", type=int)
@click.option("--reason", default=None, help="Free-form note logged with the award.")
@click.pass_context
def character_award_xp(
    ctx: click.Context, character_id: str, delta: int, reason: str | None
) -> None:
    """DM-only: award (or revoke) XP. Bumps `xp`; `level` is unchanged.

    Resolution of crossed level thresholds happens via `glass character level-up`.
    """
    role = require_dm()
    paths = get_paths()
    state = load_state(paths)
    campaign_id = active_campaign_id()
    session_id = state["session"]["id"]
    scene_id = None
    current = current_mode_record(state)
    if current and current.get("scene_id") and current["scene_id"] != "none":
        scene_id = current["scene_id"]

    with pg_connection() as conn:
        existing = _db.character_get(conn, campaign_id, character_id)
        if existing is None:
            raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
        try:
            updated, before, after = _db.character_award_xp(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                delta=delta,
                actor=role.actor,
                reason=reason,
                session_id=session_id,
                scene_id=scene_id,
            )
        except LookupError:
            raise GlassError(f"unknown character {character_id!r}") from None

    sign = f"{delta:+d}"
    summary = f"{character_id} xp {sign} ({before} -> {after}, level {updated['level']})"
    queue_event(state, role.actor, summary)
    pending_levels = max(0, (after // 10) + 1 - int(updated["level"]))
    result = {
        "character_id": character_id,
        "xp_before": before,
        "delta": delta,
        "xp_after": after,
        "level": updated["level"],
        "pending_level_ups": pending_levels,
        "reason": reason,
    }
    commit(
        paths,
        state,
        ctx,
        "character.award-xp",
        command_params(character_id=character_id, delta=delta, reason=reason),
        result,
    )


@character.command("level-up")
@click.argument("character_id")
@click.option("--attribute", "attribute_name", default=None,
              help="Required when crossing a level that's a multiple of 4. "
                   "Bumps that attribute one tier (cap at superior).")
@click.pass_context
def character_level_up(
    ctx: click.Context, character_id: str, attribute_name: str | None
) -> None:
    """Resolve one pending level. Each call bumps level by 1.

    Mechanical effects:
      - hp_max += d6 (hp_current grows by the same amount, capped at new max)
      - new_level % 4 == 0: --attribute required; that attribute bumps one tier
      - new_level % 5 == 0: momentum_ceiling += 1 (automatic)
    """
    paths = get_paths()
    state = load_state(paths)
    campaign_id = active_campaign_id()
    session_id = state["session"]["id"]
    scene_id = None
    current = current_mode_record(state)
    if current and current.get("scene_id") and current["scene_id"] != "none":
        scene_id = current["scene_id"]

    with pg_connection() as conn:
        existing = _db.character_get(conn, campaign_id, character_id)
        if existing is None:
            raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
        role = assert_character_writable(existing)

        from_level = int(existing["level"])
        xp = int(existing["xp"])
        if (xp // 10) + 1 <= from_level:
            raise GlassError(
                f"{character_id} has no pending level-ups (xp {xp}, level {from_level})"
            )

        to_level = from_level + 1
        attribute_to_tier: str | None = None
        if to_level % 4 == 0:
            if not attribute_name:
                raise GlassError(
                    f"reaching level {to_level} requires an attribute bump; "
                    f"pass --attribute <name>"
                )
            assert_attribute_name(attribute_name)
            current_tier = existing["attributes"].get(attribute_name, "standard")
            ladder = _db.ATTRIBUTE_TIER_LADDER
            try:
                idx = ladder.index(current_tier)
            except ValueError:
                raise GlassError(
                    f"attribute {attribute_name!r} is at non-bumpable tier {current_tier!r}"
                ) from None
            if idx >= len(ladder) - 1:
                raise GlassError(
                    f"attribute {attribute_name!r} is already at {current_tier!r}; "
                    f"cannot bump further (transcendent is plot-only)"
                )
            attribute_to_tier = ladder[idx + 1]
        elif attribute_name:
            raise GlassError(
                f"--attribute is only valid when crossing a multiple of 4 "
                f"(this is level {to_level})"
            )

        hp_roll = random.SystemRandom().randint(1, 6)
        momentum_ceiling_bumps = 1 if to_level % 5 == 0 else 0

        try:
            updated = _db.character_level_up(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                actor=role.actor,
                hp_roll=hp_roll,
                attribute_bumped=attribute_name if attribute_to_tier else None,
                attribute_to_tier=attribute_to_tier,
                momentum_ceiling_bumps=momentum_ceiling_bumps,
                session_id=session_id,
                scene_id=scene_id,
            )
        except LookupError:
            raise GlassError(f"unknown character {character_id!r}") from None

    parts = [f"{character_id} level {from_level} -> {to_level}", f"hp_max +{hp_roll}"]
    if attribute_to_tier:
        parts.append(f"{attribute_name} -> {attribute_to_tier}")
    if momentum_ceiling_bumps:
        parts.append(
            f"momentum_ceiling -> {existing['momentum']['ceiling'] + momentum_ceiling_bumps}"
        )
    summary = ", ".join(parts)
    queue_event(state, role.actor, summary)
    result = {
        "character_id": character_id,
        "from_level": from_level,
        "to_level": to_level,
        "hp_roll": hp_roll,
        "hp_max_before": existing["hp"]["max"],
        "hp_max_after": updated["hp"]["max"],
        "attribute_bumped": attribute_name if attribute_to_tier else None,
        "attribute_to_tier": attribute_to_tier,
        "momentum_ceiling_before": existing["momentum"]["ceiling"],
        "momentum_ceiling_after": updated["momentum"]["ceiling"],
        "pending_level_ups": max(0, (updated["xp"] // 10) + 1 - updated["level"]),
    }
    commit(
        paths,
        state,
        ctx,
        "character.level-up",
        command_params(character_id=character_id, attribute=attribute_name),
        result,
    )


@character.command("set-momentum", context_settings={"ignore_unknown_options": True})
@click.argument("character_id")
@click.argument("value", type=int)
@click.pass_context
def character_set_momentum(ctx: click.Context, character_id: str, value: int) -> None:
    paths = get_paths()
    state = load_state(paths)
    campaign_id = active_campaign_id()

    with pg_connection() as conn:
        existing = _db.character_get(conn, campaign_id, character_id)
        if existing is None:
            raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
        role = assert_character_writable(existing)
        try:
            updated, before, after = _db.character_update_momentum(
                conn,
                campaign_id=campaign_id,
                character_id=character_id,
                value=value,
            )
        except LookupError:
            raise GlassError(f"unknown character {character_id!r}") from None

    summary = f"{character_id} momentum {before:+d} -> {after:+d}"
    queue_event(state, role.actor, summary)
    result = {
        "character_id": character_id,
        "momentum_before": before,
        "requested": value,
        "momentum_after": after,
        "floor": updated["momentum"]["floor"],
        "ceiling": updated["momentum"]["ceiling"],
    }
    commit(
        paths,
        state,
        ctx,
        "character.set-momentum",
        command_params(character_id=character_id, value=value),
        result,
    )


@character.command("inventory-add")
@click.argument("character_id")
@click.argument("item_id")
@click.option("--qty", type=int, default=1)
@click.pass_context
def character_inventory_add(
    ctx: click.Context, character_id: str, item_id: str, qty: int
) -> None:
    if qty <= 0:
        raise GlassError("--qty must be greater than zero")
    paths = get_paths()
    state = load_state(paths)
    campaign_id = active_campaign_id()

    with pg_connection() as conn:
        existing = _db.character_get(conn, campaign_id, character_id)
        if existing is None:
            raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
        role = assert_character_writable(existing)
        inventory = list(existing["inventory"])
        item = next((entry for entry in inventory if entry.get("id") == item_id), None)
        before = int(item["qty"]) if item else 0
        if item:
            item["qty"] = before + qty
        else:
            inventory.append({"id": item_id, "qty": qty})
        after = before + qty
        updated = _db.character_set_inventory(
            conn,
            campaign_id=campaign_id,
            character_id=character_id,
            inventory=inventory,
        )

    queue_event(
        state,
        role.actor,
        f"{character_id} inventory +{qty} {item_id} ({before} -> {after})",
    )
    result = {
        "character_id": character_id,
        "item_id": item_id,
        "qty_before": before,
        "delta": qty,
        "qty_after": after,
        "inventory": updated["inventory"],
    }
    commit(
        paths,
        state,
        ctx,
        "character.inventory-add",
        command_params(character_id=character_id, item_id=item_id, qty=qty),
        result,
    )


@character.command("inventory-rm")
@click.argument("character_id")
@click.argument("item_id")
@click.option("--qty", type=int, default=1)
@click.pass_context
def character_inventory_rm(
    ctx: click.Context, character_id: str, item_id: str, qty: int
) -> None:
    if qty <= 0:
        raise GlassError("--qty must be greater than zero")
    paths = get_paths()
    state = load_state(paths)
    campaign_id = active_campaign_id()

    with pg_connection() as conn:
        existing = _db.character_get(conn, campaign_id, character_id)
        if existing is None:
            raise GlassError(f"unknown character {character_id!r} in campaign {campaign_id!r}")
        role = assert_character_writable(existing)
        inventory = list(existing["inventory"])
        item = next((entry for entry in inventory if entry.get("id") == item_id), None)
        before = int(item["qty"]) if item else 0
        after = max(0, before - qty)
        if item:
            item["qty"] = after
        inventory = [entry for entry in inventory if int(entry.get("qty", 0)) > 0]
        updated = _db.character_set_inventory(
            conn,
            campaign_id=campaign_id,
            character_id=character_id,
            inventory=inventory,
        )

    queue_event(
        state,
        role.actor,
        f"{character_id} inventory -{qty} {item_id} ({before} -> {after})",
    )
    result = {
        "character_id": character_id,
        "item_id": item_id,
        "qty_before": before,
        "delta": -qty,
        "applied_delta": after - before,
        "qty_after": after,
        "inventory": updated["inventory"],
    }
    commit(
        paths,
        state,
        ctx,
        "character.inventory-rm",
        command_params(character_id=character_id, item_id=item_id, qty=qty),
        result,
    )


@main.group()
def note() -> None:
    """Lore draft and journal commands."""


@note.command("write")
@click.argument("path_text")
@click.option("--body", help="Markdown body to write.")
@click.option("--from", "from_file", help="Read body from this file, or '-' for stdin.")
@click.pass_context
def note_write(
    ctx: click.Context, path_text: str, body: str | None, from_file: str | None
) -> None:
    paths = get_paths()
    state = load_state(paths)
    destination = resolve_note_write_path(paths, path_text)
    text = read_body(body, from_file)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    result = {
        "path": display_path(destination),
        "bytes": len(text.encode("utf-8")),
    }
    commit(
        paths,
        state,
        ctx,
        "note.write",
        command_params(path=path_text, bytes=result["bytes"]),
        result,
    )


@note.command("propose")
@click.argument("path_text")
@click.pass_context
def note_propose(ctx: click.Context, path_text: str) -> None:
    role = require_player()
    paths = get_paths()
    state = load_state(paths)
    source = resolve_content_path(paths, path_text)
    workspace_root = active_campaign_root()

    def _player_drafts_root(workspace: Path, player: str) -> Path:
        return (workspace / "players" / player / "drafts").resolve()

    if role.kind == "player":
        # Source must be under <campaign or templates>/players/<actor>/drafts/
        candidates = [_player_drafts_root(workspace_root, role.actor)]
        if workspace_root != paths.content:
            candidates.append(_player_drafts_root(paths.content, role.actor))
        if not any(
            str(source.resolve()).startswith(str(root) + os.sep) or source.resolve() == root
            for root in candidates
        ):
            raise GlassError(
                "permission denied: players can propose only their own drafts/"
            )
        player_id = role.actor
    else:
        player_id = infer_player_from_path(paths, source)
        if not player_id and workspace_root != paths.content:
            try:
                rel = source.resolve().relative_to(workspace_root.resolve())
                if len(rel.parts) >= 3 and rel.parts[0] == "players" and rel.parts[2] == "drafts":
                    player_id = rel.parts[1]
            except ValueError:
                pass
        if not player_id:
            raise GlassError(
                "operator note propose needs a path under players/<id>/drafts/"
            )
    if not source.exists():
        raise GlassError(f"draft not found: {display_path(source)}")
    intake_id = new_id("intake")
    destination_name = f"{intake_id}--{player_id}--{source.name}"
    destination = workspace_root / "dm" / "intake" / destination_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    record = {
        "intake_id": intake_id,
        "player_id": player_id,
        "source_path": display_path(source),
        "intake_path": display_path(destination),
        "status": "pending",
        "created_at": now_iso(),
        "resolved_at": None,
        "ratified_path": None,
    }
    state["note_intake"].append(record)
    result = {"intake": record}
    commit(
        paths,
        state,
        ctx,
        "note.propose",
        command_params(path=path_text),
        result,
    )


def require_intake(state: dict[str, Any], intake_id: str) -> dict[str, Any]:
    for item in state.get("note_intake", []):
        if item["intake_id"] == intake_id:
            return item
    pending = ", ".join(item["intake_id"] for item in state.get("note_intake", [])) or "none"
    raise GlassError(f"unknown intake id {intake_id!r}; known intake ids: {pending}")


@note.command("ratify")
@click.argument("intake_id")
@click.option("--to", "target_path",
              help="Target path relative to shared/lore/. Defaults to "
                   "shared/lore/<original-filename>.")
@click.pass_context
def note_ratify(
    ctx: click.Context,
    intake_id: str,
    target_path: str | None,
) -> None:
    """DM-only: ratify an intake (e.g. a public journal entry) into shared lore.

    propose/ratify is intended for public journal entries — text the player
    wants to publish to the party. Character sheets, intros, and relationships
    are written by the player directly into their own dirs without going
    through this loop.
    """
    require_dm()
    paths = get_paths()
    state = load_state(paths)
    item = require_intake(state, intake_id)
    if item["status"] != "pending":
        raise GlassError(f"intake {intake_id} is already {item['status']}")
    source = REPO_ROOT / item["intake_path"]
    workspace_root = active_campaign_root()
    lore_root = workspace_root / "shared" / "lore"

    if target_path:
        rel = clean_relative_path(target_path)
        while rel.parts and rel.parts[0] in {"content", "shared", "lore"}:
            rel = Path(*rel.parts[1:])
        destination = lore_root / rel
    else:
        # Strip the "<intake_id>--<player_id>--" prefix off the intake filename.
        original_name = source.name.split("--", 2)[-1]
        destination = lore_root / original_name

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    item["status"] = "ratified"
    item["resolved_at"] = now_iso()
    item["ratified_path"] = display_path(destination)
    entity = upsert_entity_from_path(paths, state, destination)
    result = {"intake": item, "entity": entity}
    commit(
        paths,
        state,
        ctx,
        "note.ratify",
        command_params(intake_id=intake_id, target_path=target_path),
        result,
    )


@note.command("reject")
@click.argument("intake_id")
@click.option("--reason", default="")
@click.pass_context
def note_reject(ctx: click.Context, intake_id: str, reason: str) -> None:
    require_dm()
    paths = get_paths()
    state = load_state(paths)
    item = require_intake(state, intake_id)
    if item["status"] != "pending":
        raise GlassError(f"intake {intake_id} is already {item['status']}")
    item["status"] = "rejected"
    item["resolved_at"] = now_iso()
    item["reason"] = reason
    result = {"intake": item}
    commit(
        paths,
        state,
        ctx,
        "note.reject",
        command_params(intake_id=intake_id, reason=reason),
        result,
    )


@main.group()
def entity() -> None:
    """Campaign-lore graph mirror commands."""


@entity.command("upsert")
@click.argument("path_text")
@click.option("--campaign-id", default=None, help="Override campaign id (default: GLASS_CAMPAIGN_ID).")
@click.pass_context
def entity_upsert(ctx: click.Context, path_text: str, campaign_id: str | None) -> None:
    require_dm()
    paths = get_paths()
    state = load_state(paths)
    path = resolve_content_path(paths, path_text)
    record = upsert_entity_from_path(paths, state, path)

    # Mirror the entity into FalkorDB. Best-effort: if the graph is
    # unreachable, the JSON state still has the data and the operation
    # remains useful — but we surface the error so the operator knows.
    graph_status = _mirror_entity_to_graph(record, path, campaign_id)

    result = {"entity": record, "graph": graph_status}
    commit(
        paths,
        state,
        ctx,
        "entity.upsert",
        command_params(path=path_text),
        result,
    )


def _mirror_entity_to_graph(
    record: dict[str, Any], path: Path, campaign_id_override: str | None
) -> dict[str, Any]:
    """Push an entity to FalkorDB. Returns a status dict describing the result."""
    from . import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        return {"status": "unavailable", "target": config.describe()}

    text = path.read_text(encoding="utf-8")
    mentions = _graph.extract_mentions(text)
    fm = record.get("frontmatter", {}) or {}
    campaign_id = (
        campaign_id_override
        or os.environ.get("GLASS_CAMPAIGN_ID")
        or fm.get("campaign_id")
        or "<unknown>"
    )
    entity_type = fm.get("type") or "entity"
    tags_raw = fm.get("tags")
    if isinstance(tags_raw, str):
        tags = [t.strip() for t in tags_raw.strip("[]").split(",") if t.strip()]
    elif isinstance(tags_raw, list):
        tags = [str(t) for t in tags_raw]
    else:
        tags = []

    try:
        with _graph.connect(config) as g:
            _graph.upsert_entity(
                g,
                entity_id=record["entity_id"],
                campaign_id=campaign_id,
                title=record.get("title", record["entity_id"]),
                entity_type=entity_type,
                file_path=record.get("path", str(path)),
                tags=tags,
                prominence=fm.get("prominence"),
                status=fm.get("status"),
                source=fm.get("source"),
                sections=record.get("sections", []),
                mentions=mentions,
            )
    except Exception as exc:
        return {"status": "error", "target": config.describe(), "message": str(exc)}
    return {
        "status": "upserted",
        "target": config.describe(),
        "campaign_id": campaign_id,
        "mentions": mentions,
    }


@entity.command("neighborhood")
@click.argument("entity_id")
@click.pass_context
def entity_neighborhood(ctx: click.Context, entity_id: str) -> None:
    """Show an entity's outgoing edges, incoming edges, and sections.

    Prefers FalkorDB; falls back to JSON state if the graph is unreachable.
    """
    from . import graph as _graph

    paths = get_paths()
    state = load_state(paths)

    config = _graph.load_falkor_config(load_config())
    if _graph.is_available(config):
        try:
            with _graph.connect(config) as g:
                payload = _graph.neighborhood(g, entity_id)
        except Exception as exc:
            payload = {"found": False, "error": str(exc)}
        if payload.get("found"):
            result = {**payload, "source": "falkordb", "target": config.describe()}
            append_audit(
                paths, state, ctx, "entity.neighborhood",
                command_params(entity_id=entity_id), result,
            )
            emit(result)
            return

    # Fallback: JSON state.
    entity_record = state.get("entities", {}).get(entity_id)
    if not entity_record:
        known = ", ".join(sorted(state.get("entities", {}))) or "none"
        raise GlassError(f"unknown entity {entity_id!r}; known entities: {known}")
    result = {
        "entity_id": entity_id,
        "entity": entity_record,
        "outgoing": entity_record.get("edges", []),
        "incoming": [],
        "source": "json-fallback",
    }
    append_audit(
        paths, state, ctx, "entity.neighborhood",
        command_params(entity_id=entity_id), result,
    )
    emit(result)


@entity.command("similar")
@click.argument("section_id")
@click.option("--limit", type=int, default=5)
@click.pass_context
def entity_similar(ctx: click.Context, section_id: str, limit: int) -> None:
    paths = get_paths()
    state = load_state(paths)
    sections = []
    target: dict[str, Any] | None = None
    for entity_record in state.get("entities", {}).values():
        for section in entity_record.get("sections", []):
            merged = {**section, "entity_id": entity_record["entity_id"]}
            sections.append(merged)
            if section["section_id"] == section_id:
                target = merged
    if target is None:
        known = ", ".join(section["section_id"] for section in sections) or "none"
        raise GlassError(f"unknown section {section_id!r}; known sections: {known}")
    target_words = set(re.findall(r"[a-z0-9]+", target["text"].lower()))
    scored = []
    for section in sections:
        if section["section_id"] == section_id:
            continue
        words = set(re.findall(r"[a-z0-9]+", section["text"].lower()))
        score = len(target_words & words)
        if score:
            scored.append({**section, "score": score})
    scored.sort(key=lambda item: item["score"], reverse=True)
    result = {"section_id": section_id, "matches": scored[:limit]}
    append_audit(
        paths,
        state,
        ctx,
        "entity.similar",
        command_params(section_id=section_id, limit=limit),
        result,
    )
    emit(result)


@entity.command("find")
@click.option("--query", "-q", default=None, help="Substring search on id/title.")
@click.option("--type", "type_filter", default=None, help="Filter by entity type.")
@click.option("--campaign-id", default=None, help="Filter by campaign.")
@click.option("--limit", type=int, default=25, show_default=True)
@click.pass_context
def entity_find(
    ctx: click.Context,
    query: str | None,
    type_filter: str | None,
    campaign_id: str | None,
    limit: int,
) -> None:
    """Search entities in the graph by substring + filters."""
    from . import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(f"falkordb is not reachable at {config.describe()}")

    campaign = campaign_id or os.environ.get("GLASS_CAMPAIGN_ID")
    try:
        with _graph.connect(config) as g:
            matches = _graph.find_entities(
                g,
                query=query,
                type_filter=type_filter,
                campaign_id=campaign,
                limit=limit,
            )
    except Exception as exc:
        raise GlassError(f"falkordb find failed: {exc}") from exc

    emit({
        "target": config.describe(),
        "query": query,
        "type": type_filter,
        "campaign_id": campaign,
        "matches": matches,
        "count": len(matches),
    })


@entity.command("link")
@click.argument("src_id")
@click.argument("edge_type")
@click.argument("dst_id")
@click.option("--prop", "props", multiple=True, help="key=value edge property; repeatable.")
@click.pass_context
def entity_link(
    ctx: click.Context,
    src_id: str,
    edge_type: str,
    dst_id: str,
    props: tuple[str, ...],
) -> None:
    """Add a typed edge between two entities (DM-only).

    Edge types are UPPERCASE_SNAKE_CASE — e.g. LOCATED_IN, MEMBER_OF,
    ADVANCES_BEAT. Creates either entity as a `shell` if it does not yet
    exist (so you can link to entities that haven't been ratified yet).
    """
    require_dm()
    from . import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(f"falkordb is not reachable at {config.describe()}")

    properties: dict[str, Any] = {}
    for raw in props:
        if "=" not in raw:
            raise GlassError(f"--prop must be key=value: {raw!r}")
        k, v = raw.split("=", 1)
        properties[k.strip()] = v.strip()

    try:
        with _graph.connect(config) as g:
            _graph.link_entities(
                g, src_id=src_id, edge_type=edge_type, dst_id=dst_id, properties=properties
            )
    except (ValueError, Exception) as exc:
        raise GlassError(f"falkordb link failed: {exc}") from exc

    emit({
        "target": config.describe(),
        "src": src_id,
        "edge_type": edge_type,
        "dst": dst_id,
        "properties": properties,
        "status": "linked",
    })


@entity.command("unlink")
@click.argument("src_id")
@click.argument("edge_type")
@click.argument("dst_id")
@click.pass_context
def entity_unlink(ctx: click.Context, src_id: str, edge_type: str, dst_id: str) -> None:
    """Remove a typed edge between two entities (DM-only)."""
    require_dm()
    from . import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(f"falkordb is not reachable at {config.describe()}")
    try:
        with _graph.connect(config) as g:
            removed = _graph.unlink_entities(g, src_id=src_id, edge_type=edge_type, dst_id=dst_id)
    except Exception as exc:
        raise GlassError(f"falkordb unlink failed: {exc}") from exc
    emit({"src": src_id, "edge_type": edge_type, "dst": dst_id, "removed": removed})


@entity.command("query")
@click.argument("cypher")
@click.option("--param", "params", multiple=True, help="key=value query param; repeatable.")
@click.pass_context
def entity_query(ctx: click.Context, cypher: str, params: tuple[str, ...]) -> None:
    """Run an arbitrary Cypher query against the campaign graph (DM-only).

    Use for ad-hoc analysis the other commands don't cover. Examples:

        glass entity query "MATCH (e:Entity {type: 'faction'}) RETURN e.id, e.title"
        glass entity query "MATCH (a:Entity)-[:GOVERNS]->(b) RETURN a.id, b.id"

    Properties are returned as plain dicts; nodes get a `_kind` of 'node',
    edges get `_kind: 'edge'` and a `_relation` field.
    """
    require_dm()
    from . import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(f"falkordb is not reachable at {config.describe()}")

    parameters: dict[str, Any] = {}
    for raw in params:
        if "=" not in raw:
            raise GlassError(f"--param must be key=value: {raw!r}")
        k, v = raw.split("=", 1)
        parameters[k.strip()] = v.strip()

    try:
        with _graph.connect(config) as g:
            payload = _graph.run_query(g, cypher, parameters)
    except Exception as exc:
        raise GlassError(f"falkordb query failed: {exc}") from exc

    emit({"target": config.describe(), "cypher": cypher, "params": parameters, **payload})


@entity.command("stats")
@click.pass_context
def entity_stats(ctx: click.Context) -> None:
    """Show graph counts: entities, sections, edges, top edge types, top entity types."""
    from . import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(f"falkordb is not reachable at {config.describe()}")
    try:
        with _graph.connect(config) as g:
            stats = _graph.graph_stats(g)
    except Exception as exc:
        raise GlassError(f"falkordb stats failed: {exc}") from exc
    emit({"target": config.describe(), **stats})


@main.group()
def thread() -> None:
    """DM scaffolding thread commands."""


@thread.command("current")
@click.pass_context
def thread_current(ctx: click.Context) -> None:
    paths = get_paths()
    state = load_state(paths)
    result = {"threads": state.get("threads", {})}
    append_audit(paths, state, ctx, "thread.current", {}, result)
    emit(result)


@thread.command("beat")
@click.argument("thread_id")
@click.pass_context
def thread_beat(ctx: click.Context, thread_id: str) -> None:
    paths = get_paths()
    state = load_state(paths)
    record = state.get("threads", {}).get(thread_id)
    if not record:
        known = ", ".join(state["threads"]) or "none"
        raise GlassError(f"unknown thread {thread_id!r}; known threads: {known}")
    result = {"thread": record}
    append_audit(
        paths,
        state,
        ctx,
        "thread.beat",
        command_params(thread_id=thread_id),
        result,
    )
    emit(result)


@thread.command("advance")
@click.argument("thread_id")
@click.option("--note", default="")
@click.pass_context
def thread_advance(ctx: click.Context, thread_id: str, note: str) -> None:
    require_dm()
    paths = get_paths()
    state = load_state(paths)
    record = state.setdefault("threads", {}).setdefault(
        thread_id,
        {"thread_id": thread_id, "current_beat": 0, "history": []},
    )
    before = int(record.get("current_beat", 0))
    after = before + 1
    record["current_beat"] = after
    record.setdefault("history", []).append({"beat": after, "note": note, "ts": now_iso()})
    result = {"thread": record, "beat_before": before, "beat_after": after}
    commit(
        paths,
        state,
        ctx,
        "thread.advance",
        command_params(thread_id=thread_id, note=note),
        result,
    )


class MessageGroup(click.Group):
    """Allow both `glass msg read` and spec-shaped `glass msg <type> <to> <body>`."""

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        if args and args[0] in self.commands:
            return super().resolve_command(ctx, args)
        return super().resolve_command(ctx, ["send", *args])


@main.group(cls=MessageGroup, name="msg")
def msg_group() -> None:
    """Typed inter-agent message bus.

    Send with: glass msg <type> <recipient> <body>
    Read with: glass msg read [--since-checkpoint]
    """


@msg_group.command("send", hidden=True)
@click.argument("message_type")
@click.argument("recipient")
@click.argument("body_parts", nargs=-1, required=True)
@click.pass_context
def msg_send(
    ctx: click.Context, message_type: str, recipient: str, body_parts: tuple[str, ...]
) -> None:
    paths = get_paths()
    state = load_state(paths)
    require_message_type(paths, message_type)
    require_recipient(paths, state, recipient)
    role = current_role()
    body = " ".join(body_parts)
    campaign_id = active_campaign_id()
    with pg_connection() as conn:
        message = _db.message_send(
            conn,
            campaign_id=campaign_id,
            session_id=state["session"]["id"],
            sender=role.actor,
            recipient=recipient,
            type_=message_type,
            body=body,
        )
    result = {"message": message}
    commit(
        paths,
        state,
        ctx,
        "msg.send",
        command_params(message_type=message_type, recipient=recipient),
        result,
    )


@msg_group.command("read")
@click.option("--since-checkpoint", is_flag=True,
              help="Show only messages this agent hasn't read yet (recommended at turn start).")
@click.option("--from", "sender")
@click.option("--type", "message_type")
@click.option("--no-mark", is_flag=True,
              help="Do not write read-checkpoints. Useful for spot-checking the bus.")
@click.pass_context
def msg_read(
    ctx: click.Context,
    since_checkpoint: bool,
    sender: str | None,
    message_type: str | None,
    no_mark: bool,
) -> None:
    paths = get_paths()
    state = load_state(paths)
    if message_type:
        require_message_type(paths, message_type)
    role = current_role()
    campaign_id = active_campaign_id()
    with pg_connection() as conn:
        rows = _db.message_list(
            conn,
            campaign_id=campaign_id,
            agent_id=role.actor,
            only_unread=since_checkpoint,
            sender=sender,
            type_=message_type,
            limit=500,
        )
        # Visibility filter at the app layer (DM sees all; players see
        # party broadcasts, addressed-to-them, and self-sent).
        visible = [m for m in rows if message_visible_to(m, role)]
        if not no_mark and visible:
            _db.message_mark_read(
                conn,
                agent_id=role.actor,
                message_ids=[m["id"] for m in visible],
            )
    result = {"messages": visible, "count": len(visible)}
    commit(
        paths,
        state,
        ctx,
        "msg.read",
        command_params(
            since_checkpoint=since_checkpoint,
            sender=sender,
            message_type=message_type,
            no_mark=no_mark,
        ),
        result,
    )


@main.group()
def turn() -> None:
    """Turn append command."""


@turn.command("append")
@click.argument("markdown_file")
@click.option("--speaker")
@click.option("--role", "turn_role", type=click.Choice(["dm", "player", "operator"]))
@click.option("--mode", "mode_name")
@click.option("--scene", "scene_id")
@click.option("--character", "character_id")
@click.pass_context
def turn_append(
    ctx: click.Context,
    markdown_file: str,
    speaker: str | None,
    turn_role: str | None,
    mode_name: str | None,
    scene_id: str | None,
    character_id: str | None,
) -> None:
    paths = get_paths()
    state = load_state(paths)
    source = Path(markdown_file).expanduser()
    if not source.is_absolute():
        source = Path.cwd() / source
    if not source.exists():
        raise GlassError(f"turn markdown not found: {markdown_file}")
    body = source.read_text(encoding="utf-8").strip()
    role = current_role()
    speaker_id = actor_for_turn(role, speaker)
    resolved_role = role_label_for_turn(role, turn_role)
    current = current_mode_record(state)
    resolved_mode = mode_name or (current["mode"] if current else "none")
    resolved_scene = scene_id or (current["scene_id"] if current else "none")
    state["session"]["turn_counter"] = int(state["session"].get("turn_counter", 0)) + 1
    turn_id = state["session"]["turn_counter"]

    flushed: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for event in state.get("pending_events", []):
        if event.get("actor") == speaker_id or role.can_do_anything:
            flushed.append(event)
        else:
            remaining.append(event)
    state["pending_events"] = remaining

    header = (
        f"## Turn {turn_id} - {speaker_id} ({resolved_role}) - "
        f"{resolved_mode}, {resolved_scene}"
    )
    parts = [header, "", body]
    event_lines = inline_event_lines(flushed)
    if event_lines:
        parts.extend(["", *event_lines])
    turn_markdown = "\n".join(parts).rstrip() + "\n\n"
    with transcript_path(paths, state["session"]["id"]).open("a", encoding="utf-8") as handle:
        handle.write(turn_markdown)

    record = {
        "turn_id": turn_id,
        "session_id": state["session"]["id"],
        "scene_id": resolved_scene,
        "mode": resolved_mode,
        "speaker": speaker_id,
        "role": resolved_role,
        "character_id": character_id,
        "ts": now_iso(),
        "source_path": str(source),
        "event_summaries": [event["summary"] for event in flushed],
        "markdown": turn_markdown,
    }
    state["turns"].append(record)
    result = {
        "turn": {key: value for key, value in record.items() if key != "markdown"},
        "events_flushed": flushed,
        "transcript_path": display_path(transcript_path(paths, state["session"]["id"])),
    }
    commit(
        paths,
        state,
        ctx,
        "turn.append",
        command_params(markdown_file=markdown_file, speaker=speaker_id),
        result,
    )


_HANDOFF_AGENT_IDS = ("dm", "tev", "sumi", "renno", "kit")


@turn.command("handoff")
@click.argument("agent_id")
@click.pass_context
def turn_handoff(ctx: click.Context, agent_id: str) -> None:
    """Hand off the next turn to a specific agent.

    Sets state["next_speaker"]; the orchestrator consumes the override on
    the next turn-start (one-shot, falls back to round-robin if unset).
    Use this to call the DM with a question, pass focus to a specific PC,
    or bend the table order when the situation demands it. Don't use it
    casually — the default round-robin should handle most flow.
    """
    if agent_id not in _HANDOFF_AGENT_IDS:
        raise GlassError(
            f"unknown agent id {agent_id!r}; valid: {', '.join(_HANDOFF_AGENT_IDS)}"
        )
    paths = get_paths()
    state = load_state(paths)
    role = current_role()
    state["next_speaker"] = agent_id
    queue_event(state, role.actor, f"handoff -> {agent_id}")
    result = {"next_speaker": agent_id}
    commit(
        paths,
        state,
        ctx,
        "turn.handoff",
        command_params(agent_id=agent_id),
        result,
    )


@turn.command("clear-handoff")
@click.pass_context
def turn_clear_handoff(ctx: click.Context) -> None:
    """Clear any pending handoff (operator/DM only). Rare — usually the
    orchestrator consumes it automatically on the next turn."""
    require_dm()
    paths = get_paths()
    state = load_state(paths)
    previous = state.get("next_speaker")
    state["next_speaker"] = None
    result = {"cleared": previous}
    commit(paths, state, ctx, "turn.clear-handoff", {}, result)


@main.group()
def turns() -> None:
    """Corpus query commands."""


@turns.command("find")
@click.option("--scene")
@click.option("--speaker")
@click.option("--mode", "mode_name")
@click.option("--turn-id", type=int)
@click.option("--limit", type=int, default=20)
@click.pass_context
def turns_find(
    ctx: click.Context,
    scene: str | None,
    speaker: str | None,
    mode_name: str | None,
    turn_id: int | None,
    limit: int,
) -> None:
    paths = get_paths()
    state = load_state(paths)
    records = list(state.get("turns", []))
    if scene:
        records = [record for record in records if record["scene_id"] == scene]
    if speaker:
        records = [record for record in records if record["speaker"] == speaker]
    if mode_name:
        records = [record for record in records if record["mode"] == mode_name]
    if turn_id is not None:
        records = [record for record in records if record["turn_id"] == turn_id]
    records = records[-limit:]
    result = {"turns": records, "count": len(records)}
    append_audit(
        paths,
        state,
        ctx,
        "turns.find",
        command_params(
            scene=scene,
            speaker=speaker,
            mode=mode_name,
            turn_id=turn_id,
            limit=limit,
        ),
        result,
    )
    emit(result)


# ============================================================================
# Postgres / migrations
# ============================================================================


@main.group()
def db() -> None:
    """Postgres connection + migration runner."""


@db.command("migrate")
@click.pass_context
def db_migrate(ctx: click.Context) -> None:
    """Apply pending SQL migrations from the repo's migrations/ directory."""
    config = load_config()
    pg_config = _db.load_pg_config(config)
    try:
        with _db.connect(pg_config) as conn:
            actions = _db.migrate(conn)
    except Exception as exc:
        raise GlassError(f"db migrate failed against {pg_config.describe()}: {exc}") from exc

    result = {"target": pg_config.describe(), "actions": actions}
    # Best-effort audit: skip if no active session, or if the active-session
    # pointer is stale (points to a cleared/deleted session).
    paths = get_paths()
    if active_session_file(paths).exists():
        try:
            state = load_state(paths)
        except GlassError:
            state = None
        if state is not None:
            append_audit(paths, state, ctx, "db.migrate", command_params(), result)
    emit(result)


@db.command("status")
@click.pass_context
def db_status(ctx: click.Context) -> None:
    """Show applied + pending migrations and any checksum mismatches."""
    config = load_config()
    pg_config = _db.load_pg_config(config)
    try:
        with _db.connect(pg_config) as conn:
            report = _db.status(conn)
    except Exception as exc:
        raise GlassError(f"db status failed against {pg_config.describe()}: {exc}") from exc
    report["target"] = pg_config.describe()
    emit(report)


# ============================================================================
# Campaign workspace: arc / scene / lore
# ============================================================================


def _campaign_workspace() -> _workspace.CampaignWorkspace:
    paths = get_paths()
    if paths.campaigns is None:
        raise GlassError("paths.campaigns is not configured")
    env_id = os.environ.get("GLASS_CAMPAIGN_ID")
    try:
        return _workspace.resolve_active_campaign(paths.campaigns, env_id=env_id)
    except FileNotFoundError as exc:
        raise GlassError(str(exc)) from exc


@main.group()
def arc() -> None:
    """Arc lifecycle (DM-only): create, list, current."""


@arc.command("create")
@click.argument("arc_id")
@click.pass_context
def arc_create(ctx: click.Context, arc_id: str) -> None:
    require_dm()
    workspace = _campaign_workspace()
    try:
        arc_dir = _workspace.create_arc(workspace, arc_id)
    except (FileExistsError, ValueError) as exc:
        raise GlassError(str(exc)) from exc
    result = {
        "campaign_id": workspace.campaign_id,
        "arc_id": arc_id,
        "path": str(arc_dir),
        "files": ["plan.md", "context.md", "scenes/"],
    }
    emit(result)


@arc.command("list")
@click.pass_context
def arc_list(ctx: click.Context) -> None:
    workspace = _campaign_workspace()
    arcs = _workspace.list_arcs(workspace)
    emit({"campaign_id": workspace.campaign_id, "arcs": arcs})


@arc.command("current")
@click.pass_context
def arc_current(ctx: click.Context) -> None:
    workspace = _campaign_workspace()
    current = _workspace.current_arc(workspace)
    emit({"campaign_id": workspace.campaign_id, "active_arc": current})


@main.group()
def scene() -> None:
    """Scene lifecycle (DM-only): create, end, current, list."""


@scene.command("create")
@click.argument("scene_id")
@click.option(
    "--type",
    "scene_type",
    required=True,
    help="Scene type / mode: town, social, exploration, investigation, combat, travel, montage, wrap.",
)
@click.option("--arc", "arc_id", default=None, help="Override active arc.")
@click.pass_context
def scene_create(
    ctx: click.Context, scene_id: str, scene_type: str, arc_id: str | None
) -> None:
    require_dm()
    workspace = _campaign_workspace()
    try:
        scene_dir = _workspace.create_scene(workspace, scene_id, scene_type, arc_id=arc_id)
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        raise GlassError(str(exc)) from exc
    result = {
        "campaign_id": workspace.campaign_id,
        "scene_id": scene_id,
        "scene_type": scene_type,
        "arc_id": arc_id or _workspace.load_campaign_state(workspace).get("active_scene_arc"),
        "path": str(scene_dir),
        "files": ["prep.md", "context.md", "transcript.md", "audit.jsonl"],
    }
    emit(result)


@scene.command("end")
@click.pass_context
def scene_end_cmd(ctx: click.Context) -> None:
    require_dm()
    workspace = _campaign_workspace()
    try:
        ended = _workspace.end_scene(workspace)
    except ValueError as exc:
        raise GlassError(str(exc)) from exc
    emit({"campaign_id": workspace.campaign_id, "ended_scene": ended})


@scene.command("current")
@click.pass_context
def scene_current(ctx: click.Context) -> None:
    workspace = _campaign_workspace()
    emit({
        "campaign_id": workspace.campaign_id,
        "active_scene": _workspace.current_scene(workspace),
    })


@scene.command("list")
@click.option("--arc", "arc_id", default=None, help="List scenes in a specific arc (default: active).")
@click.pass_context
def scene_list(ctx: click.Context, arc_id: str | None) -> None:
    workspace = _campaign_workspace()
    scenes = _workspace.list_scenes(workspace, arc_id=arc_id)
    emit({"campaign_id": workspace.campaign_id, "arc_id": arc_id, "scenes": scenes})


@main.group()
def lore() -> None:
    """Lore curation: import / list / search."""


@lore.command("import")
@click.argument("source_path")
@click.option("--as", "alias", default=None, help="Override destination filename.")
@click.pass_context
def lore_import(ctx: click.Context, source_path: str, alias: str | None) -> None:
    """Import an entry from the world bible into the campaign's curated lore.

    SOURCE_PATH is interpreted relative to the lore root (`lore.path` in config),
    or as an absolute path. Examples:
      glass lore import player/concepts/ringglass.md
      glass lore import dm/themes/builders-gone.md
    """
    require_dm()
    workspace = _campaign_workspace()
    paths = get_paths()
    if paths.lore is None:
        raise GlassError("lore.path is not configured")

    source = Path(source_path)
    if not source.is_absolute():
        source = (paths.lore / source).resolve()
    try:
        dest = _workspace.import_lore(workspace, source, paths.lore, alias=alias)
    except (FileExistsError, FileNotFoundError) as exc:
        raise GlassError(str(exc)) from exc

    # Mirror the imported entry into the graph (best-effort).
    state = load_state(paths) if active_session_file(paths).exists() else {"entities": {}}
    record = upsert_entity_from_path(paths, state, dest) if False else _record_for_lore_import(dest)
    graph_status = _mirror_entity_to_graph(record, dest, workspace.campaign_id)

    result = {
        "campaign_id": workspace.campaign_id,
        "source": str(source),
        "destination": str(dest),
        "graph": graph_status,
    }
    emit(result)


def _record_for_lore_import(path: Path) -> dict[str, Any]:
    """Build the same record shape as upsert_entity_from_path, but without the
    paths-must-be-under-content guard (lore lands in campaigns/<id>/shared/lore/).
    """
    text = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    entity_id = fm.get("id") or slugify(path.stem)
    return {
        "entity_id": entity_id,
        "title": fm.get("title") or markdown_title(text, path.stem),
        "path": str(path),
        "updated_at": now_iso(),
        "sections": parse_sections(text, entity_id),
        "frontmatter": fm,
        "edges": [],
    }


@lore.command("list")
@click.pass_context
def lore_list(ctx: click.Context) -> None:
    workspace = _campaign_workspace()
    entries = _workspace.list_lore(workspace)
    emit({"campaign_id": workspace.campaign_id, "lore": entries, "count": len(entries)})


@lore.command("search")
@click.argument("query")
@click.option("--limit", type=int, default=20, show_default=True)
@click.pass_context
def lore_search(ctx: click.Context, query: str, limit: int) -> None:
    """Search the world bible (DM only) — for finding candidates to import."""
    require_dm()
    paths = get_paths()
    if paths.lore is None:
        raise GlassError("lore.path is not configured")
    matches = _workspace.search_lore(paths.lore, query, limit=limit)
    emit({"query": query, "lore_root": str(paths.lore), "matches": matches, "count": len(matches)})


@lore.command("new")
@click.argument("entity_type")
@click.argument("slug")
@click.option("--title", default=None, help="Entry title (defaults to slug, title-cased).")
@click.option("--tags", default="", help="Comma-separated tag list.")
@click.option(
    "--prominence",
    type=click.Choice(["forgotten", "marginal", "recognized", "renowned", "mythic"]),
    default=None,
)
@click.option(
    "--category",
    default=None,
    help="Subdirectory under shared/lore/ (e.g. 'npcs', 'factions', 'locales'). "
    "Defaults to the plural of <entity_type> when sensible.",
)
@click.pass_context
def lore_new(
    ctx: click.Context,
    entity_type: str,
    slug: str,
    title: str | None,
    tags: str,
    prominence: str | None,
    category: str | None,
) -> None:
    """Scaffold a new lore entry under campaigns/<id>/shared/lore/.

    Creates a file with valid frontmatter, ready for the DM to fill in. Does
    NOT upsert to the graph — the DM edits the body, then runs `glass lore
    upsert <path>` once the entry is real. Run with empty body, fill in
    afterward.

    Example:
      glass lore new npc patrol-leader-verra --title "Patrol Leader Verra" \\
                     --tags "patrol,accord" --prominence marginal
    """
    require_dm()
    workspace = _campaign_workspace()
    slug_clean = _workspace.slugify(slug)
    cat = category or _default_category_for(entity_type)
    dest_dir = workspace.lore_dir / cat
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{slug_clean}.md"
    if dest.exists():
        raise GlassError(f"lore entry already exists: {dest}")

    title_value = title or slug_clean.replace("-", " ").title()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    fm_lines = [
        "---",
        f"title: {title_value}",
        f"type: {entity_type}",
        f"id: {slug_clean}",
    ]
    if tag_list:
        fm_lines.append("tags: [" + ", ".join(tag_list) + "]")
    if prominence:
        fm_lines.append(f"prominence: {prominence}")
    fm_lines.extend(["status: draft", "---", "", f"# {title_value}", "", "_Body to be authored._", ""])
    dest.write_text("\n".join(fm_lines), encoding="utf-8")

    emit({
        "campaign_id": workspace.campaign_id,
        "id": slug_clean,
        "type": entity_type,
        "title": title_value,
        "path": str(dest),
        "next": [
            f"edit {dest} to fill in the body",
            f"glass lore upsert {dest.relative_to(workspace.root)} to register in the graph",
        ],
    })


def _default_category_for(entity_type: str) -> str:
    plurals = {
        "npc": "npcs",
        "faction": "factions",
        "location": "locales",
        "locale": "locales",
        "creature": "creatures",
        "artifact": "artifacts",
        "ship": "ships",
        "transport": "ships",
        "event": "events",
        "occurrence": "events",
        "concept": "concepts",
        "thread": "threads",
        "loop": "loops",
        "theme": "themes",
        "hook": "hooks",
        "secret": "secrets",
    }
    return plurals.get(entity_type.lower(), entity_type.lower() + "s")


@lore.command("upsert")
@click.argument("path_text")
@click.pass_context
def lore_upsert(ctx: click.Context, path_text: str) -> None:
    """Register an authored lore entry in the FalkorDB graph.

    Use this after writing a lore file (either with `glass lore new` then
    your editor, or directly with the agent's Write tool). The path can be
    relative to the campaign workspace or absolute.

    Example:
      glass lore upsert shared/lore/npcs/patrol-leader-verra.md
    """
    require_dm()
    paths = get_paths()
    state = load_state(paths)

    raw = Path(path_text).expanduser()
    if not raw.is_absolute():
        # Resolve relative to cwd (typically the campaign workspace).
        raw = (Path.cwd() / raw).resolve()

    if not raw.exists():
        raise GlassError(f"file not found: {raw}")

    record = upsert_entity_from_path(paths, state, raw)
    graph_status = _mirror_entity_to_graph(
        record, raw, os.environ.get("GLASS_CAMPAIGN_ID")
    )
    result = {"entity": record, "graph": graph_status}
    commit(paths, state, ctx, "lore.upsert", command_params(path=path_text), result)


if __name__ == "__main__":
    main()
