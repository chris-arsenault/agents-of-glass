"""Postgres connection + migration runner for the glass CLI.

Connection params are sourced (in order) from:

  1. The `[postgres]` section of the active TOML config.
  2. libpq env vars: PGHOST, PGPORT, PGDATABASE, PGUSER.
  3. Password specifically: AOG_PG_PASSWORD (preferred) or PGPASSWORD.

Migration files live at `<repo-root>/migrations/*.sql`, applied in
lexicographic order. Each migration's contents are checksummed (sha256);
re-running an applied migration with a changed file flags a checksum
mismatch but does not auto-update the database.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
import hashlib
import json
import logging
import os

try:
    import psycopg
except ImportError:  # pragma: no cover — caller surfaces the error
    psycopg = None  # type: ignore[assignment]


log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "migrations"


@dataclass(frozen=True)
class PgConfig:
    host: str | None
    port: int | None
    database: str | None
    user: str | None

    def to_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if self.host:
            kwargs["host"] = self.host
        if self.port:
            kwargs["port"] = self.port
        if self.database:
            kwargs["dbname"] = self.database
        if self.user:
            kwargs["user"] = self.user
        password = os.environ.get("AOG_PG_PASSWORD") or os.environ.get("PGPASSWORD")
        if password:
            kwargs["password"] = password
        return kwargs

    def describe(self) -> str:
        host = self.host or os.environ.get("PGHOST", "localhost")
        port = self.port or int(os.environ.get("PGPORT", "5432"))
        db = self.database or os.environ.get("PGDATABASE", "?")
        user = self.user or os.environ.get("PGUSER", "?")
        return f"postgres://{user}@{host}:{port}/{db}"


def load_pg_config(toml_data: dict[str, Any] | None = None) -> PgConfig:
    section = (toml_data or {}).get("postgres", {}) if toml_data else {}
    raw_port = section.get("port") if section else None
    return PgConfig(
        host=section.get("host") if section else None,
        port=int(raw_port) if raw_port is not None else None,
        database=section.get("database") if section else None,
        user=section.get("user") if section else None,
    )


def postgres_configured(toml_data: dict[str, Any] | None = None) -> bool:
    """True when Postgres connection details are configured."""
    if isinstance((toml_data or {}).get("postgres"), dict):
        return True
    return any(os.environ.get(name) for name in ("PGHOST", "PGDATABASE"))


@contextmanager
def connect(pg_config: PgConfig) -> Iterator["psycopg.Connection[Any]"]:
    """Open a Postgres connection. Caller manages transactions."""
    if psycopg is None:
        raise RuntimeError(
            "psycopg is not installed; install with `pip install psycopg[binary]`"
        )
    conn = psycopg.connect(**pg_config.to_kwargs())
    try:
        yield conn
    finally:
        conn.close()


# --- migration runner ---


def list_migration_files() -> list[Path]:
    if not MIGRATIONS_DIR.exists():
        return []
    return sorted(p for p in MIGRATIONS_DIR.glob("*.sql"))


def ensure_migrations_table(conn: "psycopg.Connection[Any]") -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS _migrations (
                id          text PRIMARY KEY,
                applied_at  timestamptz NOT NULL DEFAULT now(),
                checksum    text NOT NULL
            )
            """
        )
    conn.commit()


def list_applied(conn: "psycopg.Connection[Any]") -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute("SELECT id, checksum FROM _migrations ORDER BY id")
        return {row[0]: row[1] for row in cur.fetchall()}


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_migration(conn: "psycopg.Connection[Any]", path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    checksum = _checksum(path)
    with conn.cursor() as cur:
        cur.execute(sql)
        cur.execute(
            "INSERT INTO _migrations (id, checksum) VALUES (%s, %s)",
            (path.name, checksum),
        )
    conn.commit()


def migrate(conn: "psycopg.Connection[Any]") -> list[tuple[str, str]]:
    """Apply all pending migrations.

    Returns a list of (migration_id, action) where action is one of:
      'applied' — newly applied
      'already-applied' — skipped (checksum matches)
      'checksum-mismatch' — applied previously but file has changed; skipped
    """
    ensure_migrations_table(conn)
    applied = list_applied(conn)
    files = list_migration_files()
    actions: list[tuple[str, str]] = []
    for path in files:
        checksum = _checksum(path)
        if path.name in applied:
            if applied[path.name] != checksum:
                actions.append((path.name, "checksum-mismatch"))
            else:
                actions.append((path.name, "already-applied"))
            continue
        apply_migration(conn, path)
        actions.append((path.name, "applied"))
    return actions


def status(conn: "psycopg.Connection[Any]") -> dict[str, Any]:
    """Report applied + pending + checksum-mismatched migrations."""
    ensure_migrations_table(conn)
    applied = list_applied(conn)
    files = list_migration_files()
    on_disk = {p.name: _checksum(p) for p in files}

    applied_list = []
    for name, checksum in sorted(applied.items()):
        entry = {"id": name, "applied_checksum": checksum}
        if name not in on_disk:
            entry["status"] = "missing-from-disk"
        elif on_disk[name] != checksum:
            entry["status"] = "checksum-mismatch"
            entry["disk_checksum"] = on_disk[name]
        else:
            entry["status"] = "ok"
        applied_list.append(entry)

    pending_list = [
        {"id": p.name, "checksum": _checksum(p)}
        for p in files
        if p.name not in applied
    ]
    return {"applied": applied_list, "pending": pending_list}


# --- character queries ---


def _row_to_character(row: tuple[Any, ...]) -> dict[str, Any]:
    (
        campaign_id,
        character_id,
        player_id,
        name,
        archetype,
        species,
        culture,
        organization_role,
        pronouns,
        bio,
        goals,
        attributes,
        skills,
        momentum_current,
        momentum_floor,
        momentum_ceiling,
        hp_current,
        hp_max,
        inventory,
        tags,
        xp,
        level,
        skill_xp,
        created_at,
        updated_at,
    ) = row
    return {
        "campaign_id": campaign_id,
        "character_id": character_id,
        "player_id": player_id,
        "name": name,
        "archetype": archetype,
        "species": species,
        "culture": culture,
        "organization_role": organization_role,
        "pronouns": pronouns,
        "bio": bio,
        "goals": list(goals or []),
        "attributes": attributes or {},
        "skills": skills or {},
        "momentum": {
            "current": int(momentum_current),
            "floor": int(momentum_floor),
            "ceiling": int(momentum_ceiling),
        },
        "hp": {"current": int(hp_current), "max": int(hp_max)},
        "inventory": list(inventory or []),
        "tags": list(tags or []),
        "xp": int(xp),
        "level": int(level),
        "skill_xp": dict(skill_xp or {}),
        "created_at": _iso(created_at),
        "updated_at": _iso(updated_at),
    }


_CHARACTER_COLUMNS = (
    "campaign_id, character_id, player_id, name, archetype, species, culture, "
    "organization_role, pronouns, bio, goals, attributes, skills, "
    "momentum_current, momentum_floor, momentum_ceiling, "
    "hp_current, hp_max, inventory, tags, xp, level, skill_xp, "
    "created_at, updated_at"
)


# --- skill / attribute tier constants (kept in sync with main.py) ---


SKILL_TIER_RANK = {
    "fool": 0,
    "apprentice": 1,
    "artisan": 2,
    "virtuoso": 3,
    "legend": 4,
}

SKILL_AUTO_BUMP_THRESHOLDS = [
    (5,  "apprentice"),
    (15, "artisan"),
    (30, "virtuoso"),
]

ATTRIBUTE_TIER_LADDER = ["rudimentary", "standard", "advanced", "superior"]


def earned_skill_tier(xp: int) -> str:
    """Return the highest tier earned for a given skill_xp count."""
    tier = "fool"
    for threshold, t in SKILL_AUTO_BUMP_THRESHOLDS:
        if xp >= threshold:
            tier = t
    return tier


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


# --- runtime state ---


def _jsonb(value: Any) -> str:
    return json.dumps(value if value is not None else {})


def _jsonb_list(value: Any) -> str:
    return json.dumps(value if isinstance(value, list) else [])


def runtime_state_get(
    conn: "psycopg.Connection[Any]", campaign_id: str
) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT campaign_id, status, created_at, updated_at, wrapped_at, summary,
                   turn_counter, mode_stack, pending_events, note_intake, entities,
                   threads, next_speakers, scene_closing_turns, state_extra
            FROM campaign_runtime_states
            WHERE campaign_id = %s
            """,
            (campaign_id,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    (
        campaign,
        status,
        created_at,
        updated_at,
        wrapped_at,
        summary,
        turn_counter,
        mode_stack,
        pending_events,
        note_intake,
        entities,
        threads,
        next_speakers,
        scene_closing_turns,
        state_extra,
    ) = row
    state = {
        "schema_version": 5,
        "campaign": campaign,
        "status": status,
        "created_at": _iso(created_at),
        "updated_at": _iso(updated_at),
        "wrapped_at": _iso(wrapped_at),
        "summary": summary or "",
        "turn_counter": int(turn_counter),
        "mode_stack": list(mode_stack or []),
        "pending_events": list(pending_events or []),
        "note_intake": list(note_intake or []),
        "entities": dict(entities or {}),
        "threads": dict(threads or {}),
        "turns": turn_list(conn, campaign_id=campaign_id, limit=10000),
        "next_speakers": list(next_speakers or []),
        "scene_closing_turns": scene_closing_turns,
    }
    if isinstance(state_extra, dict):
        for key, value in state_extra.items():
            state.setdefault(key, value)
    max_turn = max((int(t["turn_id"]) for t in state["turns"]), default=0)
    state["turn_counter"] = max(int(state["turn_counter"]), max_turn)
    return state


def runtime_state_upsert(
    conn: "psycopg.Connection[Any]", state: dict[str, Any]
) -> None:
    known = {
        "schema_version",
        "campaign",
        "status",
        "created_at",
        "updated_at",
        "wrapped_at",
        "summary",
        "turn_counter",
        "mode_stack",
        "pending_events",
        "note_intake",
        "entities",
        "threads",
        "turns",
        "next_speakers",
        "scene_closing_turns",
    }
    extra = {key: value for key, value in state.items() if key not in known}
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO campaign_runtime_states (
                campaign_id, status, created_at, updated_at, wrapped_at, summary,
                turn_counter, mode_stack, pending_events, note_intake, entities,
                threads, next_speakers, scene_closing_turns, state_extra
            ) VALUES (
                %s, %s, COALESCE(%s::timestamptz, now()), COALESCE(%s::timestamptz, now()),
                %s::timestamptz, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                %s::jsonb, %s::jsonb, %s::jsonb, %s, %s::jsonb
            )
            ON CONFLICT (campaign_id) DO UPDATE SET
                status = EXCLUDED.status,
                updated_at = EXCLUDED.updated_at,
                wrapped_at = EXCLUDED.wrapped_at,
                summary = EXCLUDED.summary,
                turn_counter = EXCLUDED.turn_counter,
                mode_stack = EXCLUDED.mode_stack,
                pending_events = EXCLUDED.pending_events,
                note_intake = EXCLUDED.note_intake,
                entities = EXCLUDED.entities,
                threads = EXCLUDED.threads,
                next_speakers = EXCLUDED.next_speakers,
                scene_closing_turns = EXCLUDED.scene_closing_turns,
                state_extra = EXCLUDED.state_extra
            """,
            (
                state["campaign"],
                state.get("status", "active"),
                state.get("created_at"),
                state.get("updated_at"),
                state.get("wrapped_at"),
                state.get("summary", ""),
                int(state.get("turn_counter", 0)),
                _jsonb_list(state.get("mode_stack", [])),
                _jsonb_list(state.get("pending_events", [])),
                _jsonb_list(state.get("note_intake", [])),
                _jsonb(state.get("entities", {})),
                _jsonb(state.get("threads", {})),
                _jsonb_list(state.get("next_speakers", [])),
                state.get("scene_closing_turns"),
                _jsonb(extra),
            ),
        )
    conn.commit()


def runtime_next_speaker_peek(
    conn: "psycopg.Connection[Any]", campaign_id: str
) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT next_speakers FROM campaign_runtime_states WHERE campaign_id = %s",
            (campaign_id,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    queue = list(row[0] or [])
    if not queue:
        return None
    entry = queue[0]
    return entry if isinstance(entry, dict) else {"agent": entry}


def runtime_next_speaker_consume(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    expected_entry: dict[str, Any],
) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT next_speakers FROM campaign_runtime_states "
            "WHERE campaign_id = %s FOR UPDATE",
            (campaign_id,),
        )
        row = cur.fetchone()
        if row is None:
            return False
        queue = list(row[0] or [])
        if not queue:
            return False
        entry = queue[0]
        normalized = entry if isinstance(entry, dict) else {"agent": entry}
        if normalized != expected_entry:
            return False
        cur.execute(
            "UPDATE campaign_runtime_states SET next_speakers = %s::jsonb, "
            "updated_at = now() WHERE campaign_id = %s",
            (json.dumps(queue[1:]), campaign_id),
        )
    conn.commit()
    return True


def runtime_scene_closing_tick(
    conn: "psycopg.Connection[Any]", campaign_id: str
) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT scene_closing_turns FROM campaign_runtime_states "
            "WHERE campaign_id = %s FOR UPDATE",
            (campaign_id,),
        )
        row = cur.fetchone()
        if row is None or row[0] is None:
            return False
        cur.execute(
            "UPDATE campaign_runtime_states SET scene_closing_turns = %s, "
            "updated_at = now() WHERE campaign_id = %s",
            (int(row[0]) - 1, campaign_id),
        )
    conn.commit()
    return True


def runtime_state_delete(
    conn: "psycopg.Connection[Any]", campaign_id: str
) -> dict[str, int]:
    deleted: dict[str, int] = {}
    with conn.cursor() as cur:
        for table in (
            "events",
            "scene_trackers",
            "action_orders",
            "search_chunks",
            "tarot_influences",
        ):
            cur.execute(f"DELETE FROM {table} WHERE campaign_id = %s", (campaign_id,))
            deleted[table] = cur.rowcount
        cur.execute("DELETE FROM turns WHERE campaign_id = %s", (campaign_id,))
        deleted["turns"] = cur.rowcount
        cur.execute(
            "DELETE FROM campaign_runtime_states WHERE campaign_id = %s",
            (campaign_id,),
        )
        deleted["campaign_runtime_states"] = cur.rowcount
    conn.commit()
    return deleted


def character_get(
    conn: "psycopg.Connection[Any]",
    campaign_id: str,
    character_id: str,
) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {_CHARACTER_COLUMNS} FROM characters "
            "WHERE campaign_id = %s AND character_id = %s",
            (campaign_id, character_id),
        )
        row = cur.fetchone()
    return _row_to_character(row) if row else None


def character_exists(
    conn: "psycopg.Connection[Any]",
    campaign_id: str,
    character_id: str,
) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM characters WHERE campaign_id = %s AND character_id = %s",
            (campaign_id, character_id),
        )
        return cur.fetchone() is not None


def character_list(
    conn: "psycopg.Connection[Any]",
    campaign_id: str,
) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {_CHARACTER_COLUMNS} FROM characters "
            "WHERE campaign_id = %s ORDER BY character_id",
            (campaign_id,),
        )
        return [_row_to_character(row) for row in cur.fetchall()]


def character_create(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    character_id: str,
    player_id: str,
    name: str,
    archetype: str,
    species: str,
    culture: str,
    organization_role: str,
    pronouns: str,
    bio: str,
    goals: list[str],
    attributes: dict[str, str],
    skills: dict[str, str],
    hp_max: int,
    tags: list[str],
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO characters (
                campaign_id, character_id, player_id, name, archetype, species,
                culture, organization_role, pronouns, bio, goals, attributes,
                skills, hp_current, hp_max, tags
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {_CHARACTER_COLUMNS}
            """,
            (
                campaign_id,
                character_id,
                player_id,
                name,
                archetype,
                species,
                culture,
                organization_role,
                pronouns,
                bio,
                json.dumps(goals),
                json.dumps(attributes),
                json.dumps(skills),
                hp_max,
                hp_max,
                tags,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return _row_to_character(row)


def character_update_fields(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    character_id: str,
    fields: dict[str, Any],
) -> dict[str, Any]:
    allowed = {
        "name",
        "archetype",
        "species",
        "culture",
        "organization_role",
        "pronouns",
        "bio",
        "goals",
        "attributes",
        "skills",
        "tags",
    }
    unknown = sorted(set(fields) - allowed)
    if unknown:
        raise ValueError(f"unsupported character field(s): {', '.join(unknown)}")
    if not fields:
        current = character_get(conn, campaign_id, character_id)
        if current is None:
            raise LookupError(character_id)
        return current

    set_parts: list[str] = []
    values: list[Any] = []
    for name, value in fields.items():
        if name in {"goals", "attributes", "skills"}:
            value = json.dumps(value)
            set_parts.append(f"{name} = %s::jsonb")
        else:
            set_parts.append(f"{name} = %s")
        values.append(value)
    values.extend([campaign_id, character_id])
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE characters SET {', '.join(set_parts)}
            WHERE campaign_id = %s AND character_id = %s
            RETURNING {_CHARACTER_COLUMNS}
            """,
            tuple(values),
        )
        row = cur.fetchone()
    if row is None:
        raise LookupError(character_id)
    conn.commit()
    return _row_to_character(row)


def character_update_hp(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    character_id: str,
    delta: int,
) -> tuple[dict[str, Any], int, int]:
    """Apply a clamped delta to hp_current. Returns (character, before, after)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT hp_current, hp_max FROM characters "
            "WHERE campaign_id = %s AND character_id = %s FOR UPDATE",
            (campaign_id, character_id),
        )
        row = cur.fetchone()
        if row is None:
            raise LookupError(character_id)
        before = int(row[0])
        hp_max = int(row[1])
        after = max(0, min(hp_max, before + delta))
        cur.execute(
            f"UPDATE characters SET hp_current = %s "
            f"WHERE campaign_id = %s AND character_id = %s "
            f"RETURNING {_CHARACTER_COLUMNS}",
            (after, campaign_id, character_id),
        )
        updated = cur.fetchone()
    conn.commit()
    return _row_to_character(updated), before, after


def character_update_momentum(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    character_id: str,
    value: int,
) -> tuple[dict[str, Any], int, int]:
    """Set momentum_current, clamped to [floor, ceiling]. Returns (character, before, after)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT momentum_current, momentum_floor, momentum_ceiling "
            "FROM characters WHERE campaign_id = %s AND character_id = %s FOR UPDATE",
            (campaign_id, character_id),
        )
        row = cur.fetchone()
        if row is None:
            raise LookupError(character_id)
        before = int(row[0])
        floor = int(row[1])
        ceiling = int(row[2])
        after = max(floor, min(ceiling, value))
        cur.execute(
            f"UPDATE characters SET momentum_current = %s "
            f"WHERE campaign_id = %s AND character_id = %s "
            f"RETURNING {_CHARACTER_COLUMNS}",
            (after, campaign_id, character_id),
        )
        updated = cur.fetchone()
    conn.commit()
    return _row_to_character(updated), before, after


def character_set_momentum_internal(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    character_id: str,
    value: int,
) -> None:
    """Set momentum without clamping or returning a row. Used by roll."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE characters SET momentum_current = %s "
            "WHERE campaign_id = %s AND character_id = %s",
            (value, campaign_id, character_id),
        )


def character_award_xp(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    character_id: str,
    delta: int,
    actor: str,
    reason: str | None = None,
    session_id: str | None = None,
    scene_id: str | None = None,
) -> tuple[dict[str, Any], int, int]:
    """Add `delta` to xp + log a row to xp_awards. Returns (character, before, after)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT xp FROM characters "
            "WHERE campaign_id = %s AND character_id = %s FOR UPDATE",
            (campaign_id, character_id),
        )
        row = cur.fetchone()
        if row is None:
            raise LookupError(character_id)
        before = int(row[0])
        after = max(0, before + delta)
        cur.execute(
            f"UPDATE characters SET xp = %s "
            f"WHERE campaign_id = %s AND character_id = %s "
            f"RETURNING {_CHARACTER_COLUMNS}",
            (after, campaign_id, character_id),
        )
        updated = cur.fetchone()
        cur.execute(
            """
            INSERT INTO xp_awards
                (campaign_id, character_id, actor, delta, xp_before, xp_after,
                 reason, session_id, scene_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                campaign_id, character_id, actor, delta, before, after,
                reason, session_id, scene_id,
            ),
        )
    conn.commit()
    return _row_to_character(updated), before, after


def character_level_up(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    character_id: str,
    actor: str,
    hp_roll: int,
    attribute_bumped: str | None,
    attribute_to_tier: str | None,
    momentum_ceiling_bumps: int,
    session_id: str | None = None,
    scene_id: str | None = None,
) -> dict[str, Any]:
    """Apply a single level-up resolution + log a row to level_ups.

    Caller (the CLI) is responsible for:
      - validating xp / level state (pending_level_ups > 0)
      - rolling the d6
      - validating the attribute choice (required iff new_level % 4 == 0)
      - computing momentum_ceiling_bumps (1 if new_level % 5 == 0 else 0)
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT level, hp_current, hp_max, momentum_ceiling, attributes "
            "FROM characters WHERE campaign_id = %s AND character_id = %s "
            "FOR UPDATE",
            (campaign_id, character_id),
        )
        row = cur.fetchone()
        if row is None:
            raise LookupError(character_id)
        from_level = int(row[0])
        hp_current_before = int(row[1])
        hp_max_before = int(row[2])
        momentum_ceiling_before = int(row[3])
        attributes = dict(row[4] or {})

        to_level = from_level + 1
        hp_max_after = hp_max_before + hp_roll
        # Level-up restores some hp but doesn't exceed the new max.
        hp_current_after = min(hp_current_before + hp_roll, hp_max_after)
        momentum_ceiling_after = momentum_ceiling_before + momentum_ceiling_bumps
        if attribute_bumped and attribute_to_tier:
            attributes[attribute_bumped] = attribute_to_tier

        cur.execute(
            f"""
            UPDATE characters SET
                level = %s,
                hp_current = %s,
                hp_max = %s,
                momentum_ceiling = %s,
                attributes = %s
            WHERE campaign_id = %s AND character_id = %s
            RETURNING {_CHARACTER_COLUMNS}
            """,
            (
                to_level, hp_current_after, hp_max_after,
                momentum_ceiling_after, json.dumps(attributes),
                campaign_id, character_id,
            ),
        )
        updated = cur.fetchone()
        cur.execute(
            """
            INSERT INTO level_ups
                (campaign_id, character_id, actor, from_level, to_level,
                 hp_roll, hp_max_before, hp_max_after,
                 attribute_bumped, attribute_to_tier,
                 momentum_ceiling_before, momentum_ceiling_after,
                 session_id, scene_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                campaign_id, character_id, actor, from_level, to_level,
                hp_roll, hp_max_before, hp_max_after,
                attribute_bumped, attribute_to_tier,
                momentum_ceiling_before, momentum_ceiling_after,
                session_id, scene_id,
            ),
        )
    conn.commit()
    return _row_to_character(updated)


def character_apply_skill_xp(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    character_id: str,
    skill: str,
    delta: int,
) -> tuple[int, int, str | None]:
    """Increment skill_xp[skill] by delta and auto-bump skills[skill] if a
    new threshold was crossed. Returns (xp_before, xp_after, bumped_to).

    bumped_to is the new tier name if the skill tier was raised, else None.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT skills, skill_xp FROM characters "
            "WHERE campaign_id = %s AND character_id = %s FOR UPDATE",
            (campaign_id, character_id),
        )
        row = cur.fetchone()
        if row is None:
            raise LookupError(character_id)
        skills = dict(row[0] or {})
        skill_xp = dict(row[1] or {})
        before = int(skill_xp.get(skill, 0))
        after = max(0, before + delta)
        skill_xp[skill] = after

        current_tier = skills.get(skill, "fool")
        earned_tier = earned_skill_tier(after)
        bumped_to: str | None = None
        if SKILL_TIER_RANK[earned_tier] > SKILL_TIER_RANK[current_tier]:
            skills[skill] = earned_tier
            bumped_to = earned_tier

        cur.execute(
            "UPDATE characters SET skills = %s, skill_xp = %s "
            "WHERE campaign_id = %s AND character_id = %s",
            (json.dumps(skills), json.dumps(skill_xp), campaign_id, character_id),
        )
    return before, after, bumped_to


def character_set_inventory(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    character_id: str,
    inventory: list[dict[str, Any]],
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE characters SET inventory = %s "
            f"WHERE campaign_id = %s AND character_id = %s "
            f"RETURNING {_CHARACTER_COLUMNS}",
            (json.dumps(inventory), campaign_id, character_id),
        )
        row = cur.fetchone()
    if row is None:
        raise LookupError(character_id)
    conn.commit()
    return _row_to_character(row)


# --- character consequences ---


_CONSEQUENCE_COLUMNS = (
    "id, campaign_id, character_id, label, description, severity, scope, "
    "visibility, status, created_by, resolved_by, resolution_note, "
    "created_at, resolved_at"
)


def _row_to_consequence(row: tuple[Any, ...]) -> dict[str, Any]:
    (
        consequence_id,
        campaign_id,
        character_id,
        label,
        description,
        severity,
        scope,
        visibility,
        status,
        created_by,
        resolved_by,
        resolution_note,
        created_at,
        resolved_at,
    ) = row
    return {
        "consequence_id": str(consequence_id),
        "campaign_id": campaign_id,
        "character_id": character_id,
        "label": label,
        "description": description,
        "severity": severity,
        "scope": scope,
        "visibility": visibility,
        "status": status,
        "created_by": created_by,
        "resolved_by": resolved_by,
        "resolution_note": resolution_note,
        "created_at": _iso(created_at),
        "resolved_at": _iso(resolved_at),
    }


def character_consequence_add(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    character_id: str,
    label: str,
    description: str,
    severity: str,
    scope: str,
    visibility: str,
    actor: str,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM characters WHERE campaign_id = %s AND character_id = %s",
            (campaign_id, character_id),
        )
        if cur.fetchone() is None:
            raise LookupError(character_id)
        cur.execute(
            f"""
            INSERT INTO character_consequences (
                campaign_id, character_id, label, description, severity, scope,
                visibility, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {_CONSEQUENCE_COLUMNS}
            """,
            (
                campaign_id,
                character_id,
                label,
                description,
                severity,
                scope,
                visibility,
                actor,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return _row_to_consequence(row)


def character_consequence_list(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    character_id: str | None = None,
    include_hidden: bool = False,
    include_resolved: bool = False,
) -> list[dict[str, Any]]:
    where = ["campaign_id = %s"]
    params: list[Any] = [campaign_id]
    if character_id:
        where.append("character_id = %s")
        params.append(character_id)
    if not include_hidden:
        where.append("visibility = 'public'")
    if not include_resolved:
        where.append("status = 'active'")
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_CONSEQUENCE_COLUMNS}
            FROM character_consequences
            WHERE {' AND '.join(where)}
            ORDER BY created_at, id
            """,
            params,
        )
        rows = cur.fetchall()
    return [_row_to_consequence(row) for row in rows]


def character_consequence_resolve(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    character_id: str,
    consequence_id: str,
    actor: str,
    note: str,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE character_consequences
            SET status = 'resolved',
                resolved_by = %s,
                resolved_at = now(),
                resolution_note = %s
            WHERE campaign_id = %s AND id = %s
              AND character_id = %s
            RETURNING {_CONSEQUENCE_COLUMNS}
            """,
            (actor, note, campaign_id, consequence_id, character_id),
        )
        row = cur.fetchone()
    if row is None:
        raise LookupError(consequence_id)
    conn.commit()
    return _row_to_consequence(row)


# --- roll queries ---


_ROLL_COLUMNS = (
    "id, campaign_id, session_id, scene_id, character_id, actor, skill, attribute, "
    "risk, dice, skill_tier, skill_modifier, attribute_tier, attribute_modifier, "
    "momentum_in, total, target, margin, outcome, momentum_delta, momentum_out, "
    "target_id, metadata, created_at"
)


def _row_to_roll(row: tuple[Any, ...]) -> dict[str, Any]:
    (
        roll_id,
        campaign_id,
        session_id,
        scene_id,
        character_id,
        actor,
        skill,
        attribute,
        risk,
        dice,
        skill_tier,
        skill_modifier,
        attribute_tier,
        attribute_modifier,
        momentum_in,
        total,
        target,
        margin,
        outcome,
        momentum_delta,
        momentum_out,
        target_id,
        metadata,
        created_at,
    ) = row
    return {
        "roll_id": str(roll_id),
        "campaign_id": campaign_id,
        "session_id": session_id,
        "scene_id": scene_id,
        "character_id": character_id,
        "actor": actor,
        "skill": skill,
        "attribute": attribute,
        "risk": risk,
        "dice": list(dice),
        "skill_tier": skill_tier,
        "skill_modifier": int(skill_modifier),
        "attribute_tier": attribute_tier,
        "attribute_modifier": int(attribute_modifier),
        "momentum_in": int(momentum_in),
        "total": int(total),
        "target": int(target),
        "margin": int(margin),
        "outcome": outcome,
        "momentum_delta": int(momentum_delta),
        "momentum_out": int(momentum_out),
        "target_id": target_id,
        "metadata": metadata or {},
        "created_at": _iso(created_at),
    }


# --- message bus ---


_MESSAGE_COLUMNS = (
    "id, campaign_id, session_id, sender, recipient, type, body, created_at"
)


def _row_to_message(row: tuple[Any, ...]) -> dict[str, Any]:
    msg_id, campaign_id, session_id, sender, recipient, type_, body, created_at = row
    return {
        "id": str(msg_id),
        "campaign_id": campaign_id,
        "session_id": session_id,
        "sender": sender,
        "recipient": recipient,
        "type": type_,
        "body": body,
        "created_at": _iso(created_at),
    }


def message_send(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    session_id: str,
    sender: str,
    recipient: str,
    type_: str,
    body: str,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO messages (campaign_id, session_id, sender, recipient, type, body)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING {_MESSAGE_COLUMNS}
            """,
            (campaign_id, session_id, sender, recipient, type_, body),
        )
        row = cur.fetchone()
    conn.commit()
    return _row_to_message(row)


def message_list(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    agent_id: str | None = None,
    only_unread: bool = False,
    sender: str | None = None,
    type_: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """List messages for a campaign, oldest-first.

    `only_unread` requires `agent_id`: returns only messages not yet in
    message_reads for that agent.
    """
    if only_unread and not agent_id:
        raise ValueError("only_unread=True requires agent_id")

    where = ["m.campaign_id = %s"]
    params: list[Any] = [campaign_id]
    if sender:
        where.append("m.sender = %s")
        params.append(sender)
    if type_:
        where.append("m.type = %s")
        params.append(type_)

    join = ""
    if only_unread:
        join = "LEFT JOIN message_reads r ON r.message_id = m.id AND r.agent_id = %s"
        params.insert(0, agent_id)
        where.append("r.message_id IS NULL")

    sql = (
        f"SELECT {_MESSAGE_COLUMNS} FROM messages m {join} "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY m.created_at, m.id "
        "LIMIT %s"
    )
    params.append(limit)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [_row_to_message(row) for row in rows]


def message_mark_read(
    conn: "psycopg.Connection[Any]",
    *,
    agent_id: str,
    message_ids: list[str],
) -> int:
    """Insert read-checkpoints for a list of message ids. Idempotent (ON CONFLICT)."""
    if not message_ids:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO message_reads (agent_id, message_id) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING",
            [(agent_id, mid) for mid in message_ids],
        )
        marked = cur.rowcount
    conn.commit()
    return marked


def roll_record(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    session_id: str,
    scene_id: str | None,
    character_id: str,
    actor: str,
    skill: str,
    attribute: str,
    risk: str,
    dice: list[int],
    skill_tier: str,
    skill_modifier: int,
    attribute_tier: str,
    attribute_modifier: int,
    momentum_in: int,
    total: int,
    target: int,
    margin: int,
    outcome: str,
    momentum_delta: int,
    momentum_out: int,
    target_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO rolls (
                campaign_id, session_id, scene_id, character_id, actor, skill, attribute,
                risk, dice, skill_tier, skill_modifier, attribute_tier, attribute_modifier,
                momentum_in, total, target, margin, outcome, momentum_delta, momentum_out,
                target_id, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {_ROLL_COLUMNS}
            """,
            (
                campaign_id,
                session_id,
                scene_id,
                character_id,
                actor,
                skill,
                attribute,
                risk,
                list(dice),
                skill_tier,
                skill_modifier,
                attribute_tier,
                attribute_modifier,
                momentum_in,
                total,
                target,
                margin,
                outcome,
                momentum_delta,
                momentum_out,
                target_id,
                json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return _row_to_roll(row)


# --- structured turns / public corpus ---


_TURN_COLUMNS = (
    "campaign_id, turn_id, session_id, scene_id, mode, speaker, role, "
    "character_id, source_path, prose, event_summaries, events, markdown, "
    "created_at, arc_id, scene_type, turn_number_in_scene, visibility, "
    "turn_summary, next_speaker, scene_status, state_changes, rolls, "
    "open_questions, position, pressure, turn_end"
)


def _row_to_turn(row: tuple[Any, ...]) -> dict[str, Any]:
    (
        campaign_id,
        turn_id,
        session_id,
        scene_id,
        mode,
        speaker,
        role,
        character_id,
        source_path,
        prose,
        event_summaries,
        events,
        markdown,
        created_at,
        arc_id,
        scene_type,
        turn_number_in_scene,
        visibility,
        turn_summary,
        next_speaker,
        scene_status,
        state_changes,
        rolls,
        open_questions,
        position,
        pressure,
        turn_end,
    ) = row
    return {
        "campaign_id": campaign_id,
        "turn_id": int(turn_id),
        "session_id": session_id,
        "scene_id": scene_id,
        "mode": mode,
        "speaker": speaker,
        "role": role,
        "character_id": character_id,
        "source_path": source_path,
        "prose": prose,
        "event_summaries": list(event_summaries or []),
        "events": list(events or []),
        "markdown": markdown,
        "created_at": _iso(created_at),
        "ts": _iso(created_at),
        "arc_id": arc_id,
        "scene_type": scene_type,
        "turn_number_in_scene": (
            int(turn_number_in_scene) if turn_number_in_scene is not None else None
        ),
        "visibility": visibility,
        "turn_summary": turn_summary or "",
        "next_speaker": next_speaker or "default",
        "scene_status": scene_status or "active",
        "state_changes": list(state_changes or []),
        "rolls": rolls or "",
        "open_questions": list(open_questions or []),
        "position": position or "",
        "pressure": pressure or "",
        "turn_end": dict(turn_end or {}),
    }


def turn_insert(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    turn_id: int,
    session_id: str,
    scene_id: str,
    mode: str,
    speaker: str,
    role: str,
    character_id: str | None,
    source_path: str | None,
    prose: str,
    event_summaries: list[str],
    events: list[dict[str, Any]],
    markdown: str,
    created_at: str,
    arc_id: str | None = None,
    scene_type: str | None = None,
    turn_number_in_scene: int | None = None,
    visibility: str = "public",
    turn_summary: str = "",
    next_speaker: str = "default",
    scene_status: str = "active",
    state_changes: list[str] | None = None,
    rolls: str = "",
    open_questions: list[str] | None = None,
    position: str = "",
    pressure: str = "",
    turn_end: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO turns (
                campaign_id, turn_id, session_id, scene_id, mode, speaker, role,
                character_id, source_path, prose, event_summaries, events,
                markdown, created_at, arc_id, scene_type, turn_number_in_scene,
                visibility, turn_summary, next_speaker, scene_status,
                state_changes, rolls, open_questions, position, pressure, turn_end
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s::jsonb, %s::jsonb, %s, %s::timestamptz, %s, %s, %s, %s,
                %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s, %s::jsonb
            )
            RETURNING {_TURN_COLUMNS}
            """,
            (
                campaign_id,
                turn_id,
                session_id,
                scene_id,
                mode,
                speaker,
                role,
                character_id,
                source_path,
                prose,
                json.dumps(event_summaries),
                json.dumps(events),
                markdown,
                created_at,
                arc_id,
                scene_type,
                turn_number_in_scene,
                visibility,
                turn_summary,
                next_speaker,
                scene_status,
                json.dumps(state_changes or []),
                rolls,
                json.dumps(open_questions or []),
                position,
                pressure,
                json.dumps(turn_end or {}),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return _row_to_turn(row)


def turn_count(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    scene: str | None = None,
) -> int:
    where = ["campaign_id = %s"]
    params: list[Any] = [campaign_id]
    if scene:
        where.append("scene_id = %s")
        params.append(scene)
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT count(*) FROM turns WHERE {' AND '.join(where)}",
            params,
        )
        return int(cur.fetchone()[0])


def turn_list(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    scene: str | None = None,
    speaker: str | None = None,
    mode: str | None = None,
    turn_id: int | None = None,
    after_turn: int | None = None,
    text: str | None = None,
    limit: int = 200,
    latest: bool = False,
) -> list[dict[str, Any]]:
    where = ["campaign_id = %s"]
    params: list[Any] = [campaign_id]
    if scene:
        where.append("scene_id = %s")
        params.append(scene)
    if speaker:
        where.append("speaker = %s")
        params.append(speaker)
    if mode:
        where.append("mode = %s")
        params.append(mode)
    if turn_id is not None:
        where.append("turn_id = %s")
        params.append(turn_id)
    if after_turn is not None:
        where.append("turn_id > %s")
        params.append(after_turn)
    if text:
        where.append(
            "(prose ILIKE %s OR markdown ILIKE %s OR event_summaries::text ILIKE %s "
            "OR turn_summary ILIKE %s OR state_changes::text ILIKE %s "
            "OR open_questions::text ILIKE %s)"
        )
        pattern = f"%{text}%"
        params.extend([pattern, pattern, pattern, pattern, pattern, pattern])
    params.append(limit)
    order = "DESC" if latest else "ASC"
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_TURN_COLUMNS}
            FROM turns
            WHERE {' AND '.join(where)}
            ORDER BY turn_id {order}
            LIMIT %s
            """,
            params,
        )
        rows = cur.fetchall()
    records = [_row_to_turn(row) for row in rows]
    if latest:
        records.reverse()
    return records


# --- event log ---


def event_insert_many(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    scene_id: str | None,
    turn_id: int | None,
    events: list[dict[str, Any]],
    event_type: str = "turn.inline",
    visibility: str = "public",
) -> list[dict[str, Any]]:
    if not events:
        return []
    rows: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        for event in events:
            event_id = str(event.get("event_id") or f"event-{campaign_id}-{turn_id}-{len(rows)}")
            actor = str(event.get("actor") or "unknown")
            summary = str(event.get("summary") or "")
            created_at = event.get("ts")
            payload = {key: value for key, value in event.items() if key != "summary"}
            cur.execute(
                """
                INSERT INTO events (
                    event_id, campaign_id, scene_id, turn_id, actor, event_type,
                    visibility, summary, payload, created_at, claimed_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
                    COALESCE(%s::timestamptz, now()),
                    CASE WHEN %s IS NULL THEN NULL ELSE now() END
                )
                ON CONFLICT (event_id) DO UPDATE SET
                    turn_id = EXCLUDED.turn_id,
                    scene_id = EXCLUDED.scene_id,
                    visibility = EXCLUDED.visibility,
                    summary = EXCLUDED.summary,
                    payload = EXCLUDED.payload,
                    claimed_at = EXCLUDED.claimed_at
                RETURNING event_id, campaign_id, scene_id, turn_id, actor,
                          event_type, visibility, summary, payload, created_at,
                          claimed_at
                """,
                (
                    event_id,
                    campaign_id,
                    scene_id,
                    turn_id,
                    actor,
                    event_type,
                    visibility,
                    summary,
                    json.dumps(payload),
                    created_at,
                    turn_id,
                ),
            )
            row = cur.fetchone()
            rows.append(
                {
                    "event_id": row[0],
                    "campaign_id": row[1],
                    "scene_id": row[2],
                    "turn_id": row[3],
                    "actor": row[4],
                    "event_type": row[5],
                    "visibility": row[6],
                    "summary": row[7],
                    "payload": row[8] or {},
                    "created_at": _iso(row[9]),
                    "claimed_at": _iso(row[10]),
                }
            )
    conn.commit()
    return rows


# --- scene trackers ---


_SCENE_TRACKER_COLUMNS = (
    "campaign_id, tracker_id, scene_id, label, value, max_value, resistance, "
    "impact_resistance, visibility, status, updated_by, created_at, updated_at"
)


def _row_to_scene_tracker(row: tuple[Any, ...]) -> dict[str, Any]:
    (
        campaign_id,
        tracker_id,
        scene_id,
        label,
        value,
        max_value,
        resistance,
        impact_resistance,
        visibility,
        status,
        updated_by,
        created_at,
        updated_at,
    ) = row
    return {
        "campaign_id": campaign_id,
        "tracker_id": tracker_id,
        "scene_id": scene_id,
        "label": label,
        "value": int(value),
        "max": int(max_value),
        "resistance": int(resistance),
        "impact_resistance": int(impact_resistance),
        "public": visibility == "public",
        "visibility": visibility,
        "status": status,
        "updated_by": updated_by,
        "created_at": _iso(created_at),
        "updated_at": _iso(updated_at),
    }


def scene_tracker_get(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    tracker_id: str,
) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {_SCENE_TRACKER_COLUMNS} FROM scene_trackers "
            "WHERE campaign_id = %s AND tracker_id = %s",
            (campaign_id, tracker_id),
        )
        row = cur.fetchone()
    return _row_to_scene_tracker(row) if row else None


def scene_tracker_list(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    scene_id: str | None = None,
    visibility: str | None = None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    where = ["campaign_id = %s"]
    params: list[Any] = [campaign_id]
    if scene_id:
        where.append("scene_id = %s")
        params.append(scene_id)
    if visibility:
        where.append("visibility = %s")
        params.append(visibility)
    if not include_archived:
        where.append("status <> 'archived'")
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_SCENE_TRACKER_COLUMNS}
            FROM scene_trackers
            WHERE {' AND '.join(where)}
            ORDER BY scene_id, tracker_id
            """,
            params,
        )
        rows = cur.fetchall()
    return [_row_to_scene_tracker(row) for row in rows]


def scene_tracker_upsert(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    tracker_id: str,
    scene_id: str,
    label: str,
    value: int,
    max_value: int,
    resistance: int,
    impact_resistance: int,
    visibility: str,
    actor: str,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO scene_trackers (
                campaign_id, tracker_id, scene_id, label, value, max_value,
                resistance, impact_resistance, visibility, updated_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (campaign_id, tracker_id) DO UPDATE SET
                scene_id = EXCLUDED.scene_id,
                label = EXCLUDED.label,
                value = EXCLUDED.value,
                max_value = EXCLUDED.max_value,
                resistance = EXCLUDED.resistance,
                impact_resistance = EXCLUDED.impact_resistance,
                visibility = EXCLUDED.visibility,
                status = 'active',
                updated_by = EXCLUDED.updated_by,
                updated_at = now()
            RETURNING {_SCENE_TRACKER_COLUMNS}
            """,
            (
                campaign_id,
                tracker_id,
                scene_id,
                label,
                value,
                max_value,
                resistance,
                impact_resistance,
                visibility,
                actor,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return _row_to_scene_tracker(row)


def scene_tracker_tick(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    tracker_id: str,
    delta: int,
    actor: str,
) -> tuple[dict[str, Any], int, int]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT value, max_value FROM scene_trackers "
            "WHERE campaign_id = %s AND tracker_id = %s FOR UPDATE",
            (campaign_id, tracker_id),
        )
        row = cur.fetchone()
        if row is None:
            raise LookupError(tracker_id)
        before = int(row[0])
        max_value = int(row[1])
        after = max(0, min(max_value, before + delta))
        cur.execute(
            f"""
            UPDATE scene_trackers
            SET value = %s, updated_by = %s, updated_at = now()
            WHERE campaign_id = %s AND tracker_id = %s
            RETURNING {_SCENE_TRACKER_COLUMNS}
            """,
            (after, actor, campaign_id, tracker_id),
        )
        updated = cur.fetchone()
    conn.commit()
    return _row_to_scene_tracker(updated), before, after


def scene_tracker_set_value(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    tracker_id: str,
    value: int,
    actor: str,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE scene_trackers
            SET value = %s, updated_by = %s, updated_at = now()
            WHERE campaign_id = %s AND tracker_id = %s
            RETURNING {_SCENE_TRACKER_COLUMNS}
            """,
            (value, actor, campaign_id, tracker_id),
        )
        row = cur.fetchone()
    if row is None:
        raise LookupError(tracker_id)
    conn.commit()
    return _row_to_scene_tracker(row)


def scene_tracker_delete_scene(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    scene_id: str,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM scene_trackers WHERE campaign_id = %s AND scene_id = %s",
            (campaign_id, scene_id),
        )
        deleted = cur.rowcount
    conn.commit()
    return int(deleted)


# --- action order ---


def action_order_get(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    mode: str,
    scene_id: str,
) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT campaign_id, mode, scene_id, label, round, cursor,
                   order_agents, rolls, active, created_by, created_at, updated_at
            FROM action_orders
            WHERE campaign_id = %s AND mode = %s AND scene_id = %s AND active
            """,
            (campaign_id, mode, scene_id),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return _row_to_action_order(row)


def action_order_upsert(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    mode: str,
    scene_id: str,
    label: str,
    order: list[str],
    rolls: list[dict[str, Any]],
    actor: str,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO action_orders (
                campaign_id, mode, scene_id, label, round, cursor, order_agents,
                rolls, active, created_by
            ) VALUES (%s, %s, %s, %s, 1, 0, %s::jsonb, %s::jsonb, true, %s)
            ON CONFLICT (campaign_id, mode, scene_id) DO UPDATE SET
                label = EXCLUDED.label,
                round = 1,
                cursor = 0,
                order_agents = EXCLUDED.order_agents,
                rolls = EXCLUDED.rolls,
                active = true,
                created_by = EXCLUDED.created_by,
                updated_at = now()
            RETURNING campaign_id, mode, scene_id, label, round, cursor,
                      order_agents, rolls, active, created_by, created_at, updated_at
            """,
            (
                campaign_id,
                mode,
                scene_id,
                label,
                json.dumps(order),
                json.dumps(rolls),
                actor,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return _row_to_action_order(row)


def action_order_advance(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    mode: str,
    scene_id: str,
    expected_agent: str,
) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT campaign_id, mode, scene_id, label, round, cursor,
                   order_agents, rolls, active, created_by, created_at, updated_at
            FROM action_orders
            WHERE campaign_id = %s AND mode = %s AND scene_id = %s AND active
            FOR UPDATE
            """,
            (campaign_id, mode, scene_id),
        )
        row = cur.fetchone()
        if row is None:
            return None
        order = _row_to_action_order(row)
        agents = order.get("order", [])
        if not agents:
            return order
        cursor = int(order.get("cursor", 0)) % len(agents)
        if str(agents[cursor]) != expected_agent:
            return order
        cursor += 1
        round_no = int(order.get("round", 1))
        if cursor >= len(agents):
            cursor = 0
            round_no += 1
        cur.execute(
            """
            UPDATE action_orders
            SET cursor = %s, round = %s, updated_at = now()
            WHERE campaign_id = %s AND mode = %s AND scene_id = %s
            RETURNING campaign_id, mode, scene_id, label, round, cursor,
                      order_agents, rolls, active, created_by, created_at, updated_at
            """,
            (cursor, round_no, campaign_id, mode, scene_id),
        )
        updated = cur.fetchone()
    conn.commit()
    return _row_to_action_order(updated)


def action_order_clear_scene(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    scene_id: str,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE action_orders SET active = false, updated_at = now() "
            "WHERE campaign_id = %s AND scene_id = %s AND active",
            (campaign_id, scene_id),
        )
        changed = cur.rowcount
    conn.commit()
    return int(changed)


def _row_to_action_order(row: tuple[Any, ...]) -> dict[str, Any]:
    (
        campaign_id,
        mode,
        scene_id,
        label,
        round_no,
        cursor,
        order_agents,
        rolls,
        active,
        created_by,
        created_at,
        updated_at,
    ) = row
    return {
        "campaign_id": campaign_id,
        "mode": mode,
        "scene_id": scene_id,
        "label": label,
        "round": int(round_no),
        "cursor": int(cursor),
        "order": [str(item) for item in list(order_agents or [])],
        "rolls": list(rolls or []),
        "active": bool(active),
        "created_by": created_by,
        "created_at": _iso(created_at),
        "updated_at": _iso(updated_at),
    }


# --- search chunks ---


def search_chunk_upsert(
    conn: "psycopg.Connection[Any]",
    *,
    chunk_id: str,
    campaign_id: str,
    source_type: str,
    source_id: str,
    visibility: str,
    owner_actor: str | None,
    path: str | None,
    title: str,
    body: str,
    metadata: dict[str, Any] | None = None,
    embedding: list[float] | None = None,
    embedding_model: str | None = None,
    embedding_provider: str | None = None,
) -> None:
    embedding_dim = len(embedding) if embedding is not None else None
    embedding_vector = _vector_literal(embedding) if embedding is not None else None
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO search_chunks (
                chunk_id, campaign_id, source_type, source_id, visibility,
                owner_actor, path, title, body, metadata, embedding_vector,
                embedding_model, embedding_provider, embedding_dim, embedded_at,
                updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
                CASE WHEN %s::text IS NULL THEN NULL ELSE %s::vector END,
                %s, %s, %s, CASE WHEN %s::text IS NULL THEN NULL ELSE now() END, now()
            )
            ON CONFLICT (chunk_id) DO UPDATE SET
                source_type = EXCLUDED.source_type,
                source_id = EXCLUDED.source_id,
                visibility = EXCLUDED.visibility,
                owner_actor = EXCLUDED.owner_actor,
                path = EXCLUDED.path,
                title = EXCLUDED.title,
                body = EXCLUDED.body,
                metadata = EXCLUDED.metadata,
                embedding_vector = EXCLUDED.embedding_vector,
                embedding_model = EXCLUDED.embedding_model,
                embedding_provider = EXCLUDED.embedding_provider,
                embedding_dim = EXCLUDED.embedding_dim,
                embedded_at = EXCLUDED.embedded_at,
                updated_at = now()
            """,
            (
                chunk_id,
                campaign_id,
                source_type,
                source_id,
                visibility,
                owner_actor,
                path,
                title,
                body,
                json.dumps(metadata or {}),
                embedding_vector,
                embedding_vector,
                embedding_model,
                embedding_provider,
                embedding_dim,
                embedding_vector,
            ),
        )


def search_chunks_delete_source(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    source_type: str,
    source_prefix: str | None = None,
) -> int:
    with conn.cursor() as cur:
        if source_prefix is None:
            cur.execute(
                "DELETE FROM search_chunks WHERE campaign_id = %s AND source_type = %s",
                (campaign_id, source_type),
            )
        else:
            cur.execute(
                "DELETE FROM search_chunks WHERE campaign_id = %s "
                "AND source_type = %s AND source_id LIKE %s",
                (campaign_id, source_type, f"{source_prefix}%"),
            )
        deleted = cur.rowcount
    return int(deleted)


def search_query(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    query: str,
    role_kind: str,
    actor: str,
    source_type: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    where = ["campaign_id = %s"]
    params: list[Any] = [campaign_id]
    if role_kind == "player":
        where.append(
            "(visibility = 'public' OR (visibility = 'private' AND owner_actor = %s))"
        )
        params.append(actor)
    if source_type:
        where.append("source_type = %s")
        params.append(source_type)
    # Full text search is the primary implementation. The ILIKE fallback keeps
    # obvious proper-noun queries useful even when tokenization is unhelpful.
    sql_params = [query, *params, query, query, query, limit]
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT chunk_id, source_type, source_id, visibility, owner_actor,
                   path, title, body, metadata,
                   ts_rank_cd(search_vector, websearch_to_tsquery('english', %s)) AS rank
            FROM search_chunks
            WHERE {' AND '.join(where)}
              AND (
                search_vector @@ websearch_to_tsquery('english', %s)
                OR title ILIKE ('%%' || %s || '%%')
                OR body ILIKE ('%%' || %s || '%%')
              )
            ORDER BY rank DESC, updated_at DESC
            LIMIT %s
            """,
            sql_params,
        )
        rows = cur.fetchall()
    return [
        {
            "chunk_id": row[0],
            "source_type": row[1],
            "source_id": row[2],
            "visibility": row[3],
            "owner_actor": row[4],
            "path": row[5],
            "title": row[6],
            "preview": _preview_text(row[7], query),
            "metadata": row[8] or {},
            "rank": float(row[9] or 0),
        }
        for row in rows
    ]


def search_query_semantic(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    query: str,
    query_embedding: list[float],
    role_kind: str,
    actor: str,
    source_type: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    where = [
        "campaign_id = %s",
        "embedding_vector IS NOT NULL",
        "embedding_dim = %s",
    ]
    params: list[Any] = [campaign_id, len(query_embedding)]
    if role_kind == "player":
        where.append(
            "(visibility = 'public' OR (visibility = 'private' AND owner_actor = %s))"
        )
        params.append(actor)
    if source_type:
        where.append("source_type = %s")
        params.append(source_type)

    query_vector = _vector_literal(query_embedding)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT chunk_id, source_type, source_id, visibility, owner_actor,
                   path, title, body, metadata,
                   1 - (embedding_vector <=> %s::vector) AS rank,
                   embedding_model, embedding_provider
            FROM search_chunks
            WHERE {' AND '.join(where)}
            ORDER BY embedding_vector <=> %s::vector, updated_at DESC
            LIMIT %s
            """,
            [query_vector, *params, query_vector, limit],
        )
        rows = cur.fetchall()
    return [
        {
            "chunk_id": row[0],
            "source_type": row[1],
            "source_id": row[2],
            "visibility": row[3],
            "owner_actor": row[4],
            "path": row[5],
            "title": row[6],
            "preview": _preview_text(row[7], query),
            "metadata": row[8] or {},
            "rank": float(row[9] or 0),
            "embedding_model": row[10],
            "embedding_provider": row[11],
        }
        for row in rows
    ]


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(format(float(value), ".9g") for value in values) + "]"


def _preview_text(body: str, query: str, *, limit: int = 300) -> str:
    if len(body) <= limit:
        return body
    needle = query.casefold()
    idx = body.casefold().find(needle)
    if idx < 0:
        return body[:limit].rstrip()
    start = max(0, idx - limit // 3)
    end = min(len(body), start + limit)
    return body[start:end].strip()


# --- creative influences ---


_TAROT_COLUMNS = (
    "id, campaign_id, actor, deck_id, deck_name, card_id, card_name, "
    "influence, source_note, starts_turn, expires_turn, active, created_at"
)


def _row_to_tarot(row: tuple[Any, ...]) -> dict[str, Any]:
    (
        tarot_id,
        campaign_id,
        actor,
        deck_id,
        deck_name,
        card_id,
        card_name,
        influence,
        source_note,
        starts_turn,
        expires_turn,
        active,
        created_at,
    ) = row
    return {
        "id": str(tarot_id),
        "campaign_id": campaign_id,
        "actor": actor,
        "deck_id": deck_id,
        "deck_name": deck_name,
        "card_id": card_id,
        "card_name": card_name,
        "influence": influence,
        "source_note": source_note,
        "starts_turn": int(starts_turn),
        "expires_turn": int(expires_turn),
        "active": bool(active),
        "created_at": _iso(created_at),
    }


def tarot_current(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    actor: str,
    turn_number: int,
) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_TAROT_COLUMNS}
            FROM tarot_influences
            WHERE campaign_id = %s
              AND actor = %s
              AND active
              AND starts_turn <= %s
              AND expires_turn >= %s
            ORDER BY starts_turn DESC, created_at DESC
            LIMIT 1
            """,
            (campaign_id, actor, turn_number, turn_number),
        )
        row = cur.fetchone()
    return _row_to_tarot(row) if row else None


def tarot_draw(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    actor: str,
    deck_id: str,
    deck_name: str,
    card_id: str,
    card_name: str,
    influence: str,
    source_note: str,
    starts_turn: int,
    expires_turn: int,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tarot_influences
            SET active = false
            WHERE campaign_id = %s AND actor = %s AND active
            """,
            (campaign_id, actor),
        )
        cur.execute(
            f"""
            INSERT INTO tarot_influences (
                campaign_id, actor, deck_id, deck_name, card_id, card_name,
                influence, source_note, starts_turn, expires_turn, active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true)
            RETURNING {_TAROT_COLUMNS}
            """,
            (
                campaign_id,
                actor,
                deck_id,
                deck_name,
                card_id,
                card_name,
                influence,
                source_note,
                starts_turn,
                expires_turn,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return _row_to_tarot(row)


def tarot_list(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    actor: str | None = None,
    active_only: bool = True,
    turn_number: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    where = ["campaign_id = %s"]
    params: list[Any] = [campaign_id]
    if actor:
        where.append("actor = %s")
        params.append(actor)
    if active_only:
        where.append("active")
    if turn_number is not None:
        where.append("starts_turn <= %s")
        where.append("expires_turn >= %s")
        params.extend([turn_number, turn_number])
    params.append(limit)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_TAROT_COLUMNS}
            FROM tarot_influences
            WHERE {' AND '.join(where)}
            ORDER BY starts_turn DESC, created_at DESC
            LIMIT %s
            """,
            params,
        )
        rows = cur.fetchall()
    return [_row_to_tarot(row) for row in rows]


# --- durable clocks ---


_CLOCK_COLUMNS = (
    "campaign_id, clock_id, scope, anchor_id, label, description, value, "
    "max_value, direction, visibility, status, created_by, updated_by, "
    "created_at, updated_at, resolved_at, resolution_note"
)


def _row_to_clock(row: tuple[Any, ...]) -> dict[str, Any]:
    (
        campaign_id,
        clock_id,
        scope,
        anchor_id,
        label,
        description,
        value,
        max_value,
        direction,
        visibility,
        status,
        created_by,
        updated_by,
        created_at,
        updated_at,
        resolved_at,
        resolution_note,
    ) = row
    return {
        "campaign_id": campaign_id,
        "clock_id": clock_id,
        "scope": scope,
        "anchor_id": anchor_id,
        "label": label,
        "description": description,
        "value": int(value),
        "max": int(max_value),
        "direction": direction,
        "visibility": visibility,
        "status": status,
        "created_by": created_by,
        "updated_by": updated_by,
        "created_at": _iso(created_at),
        "updated_at": _iso(updated_at),
        "resolved_at": _iso(resolved_at),
        "resolution_note": resolution_note,
    }


def clock_get(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    clock_id: str,
) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {_CLOCK_COLUMNS} FROM clocks "
            "WHERE campaign_id = %s AND clock_id = %s",
            (campaign_id, clock_id),
        )
        row = cur.fetchone()
    return _row_to_clock(row) if row else None


def clock_list(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    scope: str | None = None,
    anchor_id: str | None = None,
    visibility: str | None = None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    where = ["campaign_id = %s"]
    params: list[Any] = [campaign_id]
    if scope:
        where.append("scope = %s")
        params.append(scope)
    if anchor_id:
        where.append("anchor_id = %s")
        params.append(anchor_id)
    if visibility:
        where.append("visibility = %s")
        params.append(visibility)
    if not include_archived:
        where.append("status <> 'archived'")
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_CLOCK_COLUMNS}
            FROM clocks
            WHERE {' AND '.join(where)}
            ORDER BY scope, anchor_id NULLS FIRST, clock_id
            """,
            params,
        )
        rows = cur.fetchall()
    return [_row_to_clock(row) for row in rows]


def clock_upsert(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    clock_id: str,
    scope: str,
    anchor_id: str | None,
    label: str,
    description: str,
    value: int,
    max_value: int,
    direction: str,
    visibility: str,
    actor: str,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT value FROM clocks WHERE campaign_id = %s AND clock_id = %s",
            (campaign_id, clock_id),
        )
        existing = cur.fetchone()
        before = int(existing[0]) if existing else None
        cur.execute(
            f"""
            INSERT INTO clocks (
                campaign_id, clock_id, scope, anchor_id, label, description,
                value, max_value, direction, visibility, created_by, updated_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (campaign_id, clock_id) DO UPDATE SET
                scope = EXCLUDED.scope,
                anchor_id = EXCLUDED.anchor_id,
                label = EXCLUDED.label,
                description = EXCLUDED.description,
                value = EXCLUDED.value,
                max_value = EXCLUDED.max_value,
                direction = EXCLUDED.direction,
                visibility = EXCLUDED.visibility,
                status = 'active',
                updated_by = EXCLUDED.updated_by,
                resolved_at = NULL,
                resolution_note = NULL
            RETURNING {_CLOCK_COLUMNS}
            """,
            (
                campaign_id,
                clock_id,
                scope,
                anchor_id,
                label,
                description,
                value,
                max_value,
                direction,
                visibility,
                actor,
                actor,
            ),
        )
        row = cur.fetchone()
        cur.execute(
            """
            INSERT INTO clock_events (
                campaign_id, clock_id, actor, event_type, value_before,
                value_after, note
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                campaign_id,
                clock_id,
                actor,
                "set",
                before,
                value,
                description,
            ),
        )
    conn.commit()
    return _row_to_clock(row)


def clock_tick(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    clock_id: str,
    delta: int,
    actor: str,
    note: str,
) -> tuple[dict[str, Any], int, int]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT value, max_value FROM clocks "
            "WHERE campaign_id = %s AND clock_id = %s FOR UPDATE",
            (campaign_id, clock_id),
        )
        row = cur.fetchone()
        if row is None:
            raise LookupError(clock_id)
        before = int(row[0])
        max_value = int(row[1])
        after = max(0, min(max_value, before + delta))
        cur.execute(
            f"""
            UPDATE clocks
            SET value = %s, updated_by = %s
            WHERE campaign_id = %s AND clock_id = %s
            RETURNING {_CLOCK_COLUMNS}
            """,
            (after, actor, campaign_id, clock_id),
        )
        updated = cur.fetchone()
        cur.execute(
            """
            INSERT INTO clock_events (
                campaign_id, clock_id, actor, event_type, delta,
                value_before, value_after, note
            ) VALUES (%s, %s, %s, 'tick', %s, %s, %s, %s)
            """,
            (campaign_id, clock_id, actor, delta, before, after, note),
        )
    conn.commit()
    return _row_to_clock(updated), before, after


def clock_set_status(
    conn: "psycopg.Connection[Any]",
    *,
    campaign_id: str,
    clock_id: str,
    status: str,
    actor: str,
    note: str,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        if status == "resolved":
            cur.execute(
                f"""
                UPDATE clocks
                SET status = 'resolved',
                    updated_by = %s,
                    resolved_at = now(),
                    resolution_note = %s
                WHERE campaign_id = %s AND clock_id = %s
                RETURNING {_CLOCK_COLUMNS}
                """,
                (actor, note, campaign_id, clock_id),
            )
        else:
            cur.execute(
                f"""
                UPDATE clocks
                SET status = %s,
                    updated_by = %s,
                    resolution_note = COALESCE(%s, resolution_note)
                WHERE campaign_id = %s AND clock_id = %s
                RETURNING {_CLOCK_COLUMNS}
                """,
                (status, actor, note, campaign_id, clock_id),
            )
        row = cur.fetchone()
        if row is None:
            raise LookupError(clock_id)
        cur.execute(
            """
            INSERT INTO clock_events (campaign_id, clock_id, actor, event_type, note)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (campaign_id, clock_id, actor, status, note),
        )
    conn.commit()
    return _row_to_clock(row)


# --- campaign-wide deletion ---


def delete_campaign_data(
    conn: "psycopg.Connection[Any]", campaign_id: str
) -> dict[str, int]:
    """Remove every row tied to the campaign across all tables.

    Order matters because of FK constraints: rolls / xp_awards / level_ups
    reference characters via (campaign_id, character_id), so they go first.
    message_reads cascades from messages on delete, so deleting messages is
    enough. Returns a dict of {table: rows_deleted}.
    """
    deleted: dict[str, int] = {}
    with conn.cursor() as cur:
        for table in (
            "events",
            "scene_trackers",
            "action_orders",
            "search_chunks",
            "tarot_influences",
            "turns",
            "campaign_runtime_states",
            "clock_events",
            "clocks",
        ):
            cur.execute(f"DELETE FROM {table} WHERE campaign_id = %s", (campaign_id,))
            deleted[table] = cur.rowcount
        for table in ("rolls", "xp_awards", "level_ups", "character_consequences"):
            cur.execute(f"DELETE FROM {table} WHERE campaign_id = %s", (campaign_id,))
            deleted[table] = cur.rowcount
        cur.execute("DELETE FROM messages WHERE campaign_id = %s", (campaign_id,))
        deleted["messages"] = cur.rowcount
        # message_reads: cascaded via FK, but defensively count by joining.
        cur.execute(
            "SELECT COUNT(*) FROM message_reads r "
            "WHERE NOT EXISTS (SELECT 1 FROM messages m WHERE m.id = r.message_id)"
        )
        # The cascade has already happened by this point; we're only
        # reporting that the table is consistent.
        deleted["message_reads_orphans"] = int(cur.fetchone()[0])
        cur.execute(
            "DELETE FROM characters WHERE campaign_id = %s", (campaign_id,)
        )
        deleted["characters"] = cur.rowcount
    conn.commit()
    return deleted
