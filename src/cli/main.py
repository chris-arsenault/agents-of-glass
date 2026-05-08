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
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click


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
    content = resolve_config_path(path_config.get("content"), REPO_ROOT / "content")
    sessions = resolve_config_path(path_config.get("sessions"), content / "sessions")
    return Paths(content=content, sessions=sessions)


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
        "schema_version": 1,
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
        "characters": {},
        "dice_events": [],
        "mechanical_events": [],
        "uncommitted_event_ids": [],
        "messages": [],
        "note_intake": [],
        "entities": {},
        "threads": {},
        "turns": [],
    }


def normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    state.setdefault("schema_version", 1)
    state.setdefault("mode_stack", [])
    state.setdefault("characters", {})
    state.setdefault("dice_events", [])
    state.setdefault("mechanical_events", [])
    state.setdefault("uncommitted_event_ids", [])
    state.setdefault("messages", [])
    state.setdefault("note_intake", [])
    state.setdefault("entities", {})
    state.setdefault("threads", {})
    state.setdefault("turns", [])
    state.setdefault("session", {})
    state["session"].setdefault("turn_counter", len(state["turns"]))
    state["session"].setdefault("status", "active")
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


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def resolve_content_path(paths: Paths, path_text: str) -> Path:
    raw = Path(path_text).expanduser()
    if raw.is_absolute():
        return ensure_under(
            raw,
            paths.content,
            "invalid path: absolute paths must stay under content/",
        )
    rel = clean_relative_path(path_text)
    if rel.parts and rel.parts[0] == "content":
        rel = Path(*rel.parts[1:])
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
    players = set(player_dirs(paths))
    if state:
        for character in state.get("characters", {}).values():
            player_id = character.get("player_id")
            if player_id:
                players.add(player_id)
    return sorted(players)


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


def require_character(state: dict[str, Any], character_id: str) -> dict[str, Any]:
    character = state["characters"].get(character_id)
    if not character:
        valid = ", ".join(sorted(state["characters"])) or "none"
        raise GlassError(f"unknown character {character_id!r}; known characters: {valid}")
    return character


def require_character_write(character: dict[str, Any]) -> Role:
    role = current_role()
    if role.can_do_anything or role.kind == "dm":
        return role
    if role.kind == "player" and character.get("player_id") == role.actor:
        return role
    raise GlassError(
        "permission denied: players may mutate only their own character "
        f"(owner: {character.get('player_id')})"
    )


def record_mechanical_event(
    state: dict[str, Any],
    kind: str,
    actor: str,
    summary: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    event = {
        "event_id": new_id("event"),
        "kind": kind,
        "actor": actor,
        "ts": now_iso(),
        "summary": summary,
        "payload": make_jsonable(payload),
        "committed_turn_id": None,
    }
    state["mechanical_events"].append(event)
    state["uncommitted_event_ids"].append(event["event_id"])
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
        "characters": sorted(state.get("characters", {})),
        "turn_count": len(state.get("turns", [])),
        "message_count": len(state.get("messages", [])),
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
    return recipient == "party" or recipient == role.actor or message["sender"] == role.actor


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
    path = ensure_under(path, paths.content, "entity paths must stay under content/")
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
    event = record_mechanical_event(
        state,
        "mode.start",
        role.actor,
        f"mode start {record['mode']} @ {record['scene_id']}",
        record,
    )
    result = {
        "current_mode": record["mode"],
        "current_scene": record["scene_id"],
        "mode_stack": state["mode_stack"],
        "event_id": event["event_id"],
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
    event = record_mechanical_event(
        state,
        "mode.end",
        role.actor,
        f"mode end {ended['mode']} @ {ended['scene_id']}",
        ended,
    )
    result = {
        "ended": ended,
        "current_mode": current["mode"] if current else None,
        "current_scene": current["scene_id"] if current else None,
        "mode_stack": state["mode_stack"],
        "event_id": event["event_id"],
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
    character = require_character(state, character_id)
    role = current_role()
    if role.kind == "player" and character.get("player_id") != role.actor:
        raise GlassError(
            "permission denied: players may roll only their own character "
            f"(owner: {character.get('player_id')})"
        )

    dice = [random.SystemRandom().randint(1, 6), random.SystemRandom().randint(1, 6)]
    skill_tier = character.get("skills", {}).get(skill, "fool")
    attribute_tier = character.get("attributes", {}).get(attribute, "standard")
    skill_modifier = SKILL_TIERS[skill_tier]
    attribute_modifier = ATTRIBUTE_TIERS[attribute_tier]
    momentum_in = int(character.get("momentum", {}).get("current", 0))
    target = RISK_THRESHOLDS[risk]
    total = sum(dice) + skill_modifier + attribute_modifier + momentum_in
    margin = total - target
    outcome, momentum_delta = outcome_for_margin(margin)
    momentum = character.setdefault("momentum", {"current": 0, "floor": -2, "ceiling": 3})
    momentum_out = clamp(
        momentum_in + momentum_delta,
        int(momentum.get("floor", -2)),
        int(momentum.get("ceiling", 3)),
    )
    momentum["current"] = momentum_out

    roll_id = new_id("roll")
    result = {
        "roll_id": roll_id,
        "session_id": state["session"]["id"],
        "character_id": character_id,
        "skill": skill,
        "attribute": attribute,
        "risk": risk,
        "dice": dice,
        "skill_tier": skill_tier,
        "skill_modifier": skill_modifier,
        "attribute_tier": attribute_tier,
        "attribute_modifier": attribute_modifier,
        "momentum_in": momentum_in,
        "total": total,
        "target": target,
        "target_id": target_id,
        "margin": margin,
        "outcome": outcome,
        "momentum_delta": momentum_delta,
        "momentum_out": momentum_out,
    }
    state["dice_events"].append({**result, "ts": now_iso(), "actor": role.actor})
    target_suffix = f" -> {target_id}" if target_id else ""
    summary = (
        f"roll {skill} ({attribute}) @ {risk}: {total} vs {target} -> "
        f"{outcome} ({momentum_in:+d} to {momentum_out:+d} momentum){target_suffix}"
    )
    event = record_mechanical_event(state, "roll", role.actor, summary, result)
    result["event_id"] = event["event_id"]
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
        result,
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
    if character_id in state["characters"]:
        raise GlassError(f"character already exists: {character_id}")
    attributes = {attribute: "standard" for attribute in ATTRIBUTES}
    attributes.update(validate_key_values(attribute_values, ATTRIBUTE_TIERS, "attribute"))
    for attribute_name in attributes:
        assert_attribute_name(attribute_name)
    skills = validate_key_values(skill_values, SKILL_TIERS, "skill")
    record = {
        "character_id": character_id,
        "player_id": player_id,
        "name": name or character_id,
        "archetype": archetype,
        "pronouns": pronouns,
        "attributes": attributes,
        "skills": skills,
        "momentum": {"current": 0, "floor": -2, "ceiling": 3},
        "hp": {"current": hp_max, "max": hp_max},
        "inventory": [],
        "tags": list(tags),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    state["characters"][character_id] = record
    result = {"character": record}
    commit(
        paths,
        state,
        ctx,
        "character.new",
        command_params(character_id=character_id, player_id=player_id),
        result,
    )


@character.command("get")
@click.argument("character_id")
@click.pass_context
def character_get(ctx: click.Context, character_id: str) -> None:
    paths = get_paths()
    state = load_state(paths)
    character = require_character(state, character_id)
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


@character.command("set-hp", context_settings={"ignore_unknown_options": True})
@click.argument("character_id")
@click.argument("delta", type=int)
@click.pass_context
def character_set_hp(ctx: click.Context, character_id: str, delta: int) -> None:
    paths = get_paths()
    state = load_state(paths)
    character = require_character(state, character_id)
    role = require_character_write(character)
    hp = character.setdefault("hp", {"current": 10, "max": 10})
    before = int(hp.get("current", 0))
    after = clamp(before + delta, 0, int(hp.get("max", before + delta)))
    hp["current"] = after
    character["updated_at"] = now_iso()
    result = {
        "character_id": character_id,
        "hp_before": before,
        "delta": delta,
        "applied_delta": after - before,
        "hp_after": after,
        "hp_max": hp["max"],
    }
    sign = f"{delta:+d}"
    summary = f"{character_id} hp {sign} ({before} -> {after})"
    event = record_mechanical_event(state, "character.hp", role.actor, summary, result)
    result["event_id"] = event["event_id"]
    commit(
        paths,
        state,
        ctx,
        "character.set-hp",
        command_params(character_id=character_id, delta=delta),
        result,
    )


@character.command("set-momentum", context_settings={"ignore_unknown_options": True})
@click.argument("character_id")
@click.argument("value", type=int)
@click.pass_context
def character_set_momentum(ctx: click.Context, character_id: str, value: int) -> None:
    paths = get_paths()
    state = load_state(paths)
    character = require_character(state, character_id)
    role = require_character_write(character)
    momentum = character.setdefault("momentum", {"current": 0, "floor": -2, "ceiling": 3})
    before = int(momentum.get("current", 0))
    after = clamp(value, int(momentum.get("floor", -2)), int(momentum.get("ceiling", 3)))
    momentum["current"] = after
    character["updated_at"] = now_iso()
    result = {
        "character_id": character_id,
        "momentum_before": before,
        "requested": value,
        "momentum_after": after,
        "floor": momentum["floor"],
        "ceiling": momentum["ceiling"],
    }
    summary = f"{character_id} momentum {before:+d} -> {after:+d}"
    event = record_mechanical_event(state, "character.momentum", role.actor, summary, result)
    result["event_id"] = event["event_id"]
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
    character = require_character(state, character_id)
    role = require_character_write(character)
    inventory = character.setdefault("inventory", [])
    item = next((entry for entry in inventory if entry["id"] == item_id), None)
    before = int(item["qty"]) if item else 0
    if item:
        item["qty"] = before + qty
    else:
        inventory.append({"id": item_id, "qty": qty})
    after = before + qty
    character["updated_at"] = now_iso()
    result = {
        "character_id": character_id,
        "item_id": item_id,
        "qty_before": before,
        "delta": qty,
        "qty_after": after,
        "inventory": inventory,
    }
    event = record_mechanical_event(
        state,
        "character.inventory-add",
        role.actor,
        f"{character_id} inventory +{qty} {item_id} ({before} -> {after})",
        result,
    )
    result["event_id"] = event["event_id"]
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
    character = require_character(state, character_id)
    role = require_character_write(character)
    inventory = character.setdefault("inventory", [])
    item = next((entry for entry in inventory if entry["id"] == item_id), None)
    before = int(item["qty"]) if item else 0
    after = max(0, before - qty)
    if item:
        item["qty"] = after
    inventory[:] = [entry for entry in inventory if int(entry["qty"]) > 0]
    character["updated_at"] = now_iso()
    result = {
        "character_id": character_id,
        "item_id": item_id,
        "qty_before": before,
        "delta": -qty,
        "applied_delta": after - before,
        "qty_after": after,
        "inventory": inventory,
    }
    event = record_mechanical_event(
        state,
        "character.inventory-rm",
        role.actor,
        f"{character_id} inventory -{qty} {item_id} ({before} -> {after})",
        result,
    )
    result["event_id"] = event["event_id"]
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
    if role.kind == "player":
        allowed = (paths.content / "players" / role.actor / "drafts").resolve()
        ensure_under(
            source,
            allowed,
            "permission denied: players can propose only their own drafts/",
        )
        player_id = role.actor
    else:
        player_id = infer_player_from_path(paths, source)
        if not player_id:
            raise GlassError(
                "operator note propose needs a path under content/players/<id>/drafts/"
            )
    if not source.exists():
        raise GlassError(f"draft not found: {display_path(source)}")
    intake_id = new_id("intake")
    destination_name = f"{intake_id}--{player_id}--{source.name}"
    destination = paths.content / "dm" / "intake" / destination_name
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
@click.option("--to", "target_path", help="Target path under content/shared/lore/.")
@click.pass_context
def note_ratify(ctx: click.Context, intake_id: str, target_path: str | None) -> None:
    require_dm()
    paths = get_paths()
    state = load_state(paths)
    item = require_intake(state, intake_id)
    if item["status"] != "pending":
        raise GlassError(f"intake {intake_id} is already {item['status']}")
    source = REPO_ROOT / item["intake_path"]
    if target_path:
        rel = clean_relative_path(target_path)
        if rel.parts and rel.parts[0] in {"content", "shared", "lore"}:
            while rel.parts and rel.parts[0] in {"content", "shared", "lore"}:
                rel = Path(*rel.parts[1:])
        destination = paths.content / "shared" / "lore" / rel
    else:
        destination = paths.content / "shared" / "lore" / source.name.split("--", 2)[-1]
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
@click.pass_context
def entity_upsert(ctx: click.Context, path_text: str) -> None:
    require_dm()
    paths = get_paths()
    state = load_state(paths)
    path = resolve_content_path(paths, path_text)
    record = upsert_entity_from_path(paths, state, path)
    result = {"entity": record}
    commit(
        paths,
        state,
        ctx,
        "entity.upsert",
        command_params(path=path_text),
        result,
    )


@entity.command("neighborhood")
@click.argument("entity_id")
@click.pass_context
def entity_neighborhood(ctx: click.Context, entity_id: str) -> None:
    paths = get_paths()
    state = load_state(paths)
    entity_record = state.get("entities", {}).get(entity_id)
    if not entity_record:
        known = ", ".join(sorted(state.get("entities", {}))) or "none"
        raise GlassError(f"unknown entity {entity_id!r}; known entities: {known}")
    result = {
        "entity_id": entity_id,
        "entity": entity_record,
        "outgoing": entity_record.get("edges", []),
        "incoming": [],
    }
    append_audit(
        paths,
        state,
        ctx,
        "entity.neighborhood",
        command_params(entity_id=entity_id),
        result,
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
    message = {
        "id": new_id("msg"),
        "ts": now_iso(),
        "session_id": state["session"]["id"],
        "sender": role.actor,
        "recipient": recipient,
        "type": message_type,
        "body": body,
        "read_by": {},
    }
    state["messages"].append(message)
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
@click.option("--since-checkpoint", is_flag=True)
@click.option("--from", "sender")
@click.option("--type", "message_type")
@click.pass_context
def msg_read(
    ctx: click.Context,
    since_checkpoint: bool,
    sender: str | None,
    message_type: str | None,
) -> None:
    paths = get_paths()
    state = load_state(paths)
    if message_type:
        require_message_type(paths, message_type)
    role = current_role()
    visible = [message for message in state["messages"] if message_visible_to(message, role)]
    if since_checkpoint:
        visible = [message for message in visible if role.actor not in message.get("read_by", {})]
    if sender:
        visible = [message for message in visible if message["sender"] == sender]
    if message_type:
        visible = [message for message in visible if message["type"] == message_type]
    read_ts = now_iso()
    for message in visible:
        message.setdefault("read_by", {})[role.actor] = read_ts
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

    event_lookup = {
        event["event_id"]: event for event in state.get("mechanical_events", [])
    }
    uncommitted = []
    remaining_ids = []
    for event_id in state.get("uncommitted_event_ids", []):
        event = event_lookup.get(event_id)
        if not event:
            continue
        if event.get("actor") == speaker_id or role.can_do_anything:
            event["committed_turn_id"] = turn_id
            uncommitted.append(event)
        else:
            remaining_ids.append(event_id)
    state["uncommitted_event_ids"] = remaining_ids

    header = (
        f"## Turn {turn_id} - {speaker_id} ({resolved_role}) - "
        f"{resolved_mode}, {resolved_scene}"
    )
    parts = [header, "", body]
    event_lines = inline_event_lines(uncommitted)
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
        "mechanical_event_ids": [event["event_id"] for event in uncommitted],
        "markdown": turn_markdown,
    }
    state["turns"].append(record)
    result = {
        "turn": {key: value for key, value in record.items() if key != "markdown"},
        "mechanical_events": uncommitted,
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


if __name__ == "__main__":
    main()
