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
from pathlib import Path
from typing import Any, Iterator
import hashlib
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
