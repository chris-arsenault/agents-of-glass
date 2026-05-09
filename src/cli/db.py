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
        pronouns,
        bio,
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
        "pronouns": pronouns,
        "bio": bio,
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
    "campaign_id, character_id, player_id, name, archetype, pronouns, bio, "
    "attributes, skills, momentum_current, momentum_floor, momentum_ceiling, "
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
    pronouns: str,
    attributes: dict[str, str],
    skills: dict[str, str],
    hp_max: int,
    tags: list[str],
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO characters (
                campaign_id, character_id, player_id, name, archetype, pronouns,
                attributes, skills, hp_current, hp_max, tags
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {_CHARACTER_COLUMNS}
            """,
            (
                campaign_id,
                character_id,
                player_id,
                name,
                archetype,
                pronouns,
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
