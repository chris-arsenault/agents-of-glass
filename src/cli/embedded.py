"""Embedded SQLite connection and Postgres-SQL compatibility helpers.

The game has one authoritative mutation surface (``glass``) and modest,
campaign-sized data.  SQLite provides the transactions and concurrent viewer
reads that surface needs without a database service, credentials, or network
availability.

``cli.db`` still contains the domain queries.  This module translates the
small Postgres syntax subset those queries use while that code is made
storage-neutral.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from contextlib import AbstractContextManager
from datetime import date, datetime
from pathlib import Path
from typing import Any
import json
import math
import re
import sqlite3
import uuid


def _decode_json(raw: bytes) -> Any:
    text = raw.decode("utf-8")
    if not text:
        return None
    return json.loads(text)


sqlite3.register_converter("JSON", _decode_json)


def _greatest(*values: Any) -> Any:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _least(*values: Any) -> Any:
    present = [value for value in values if value is not None]
    return min(present) if present else None


def _json_merge(left: Any, right: Any) -> str:
    def as_object(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if not value:
            return {}
        decoded = json.loads(str(value))
        return dict(decoded) if isinstance(decoded, dict) else {}

    merged = as_object(left)
    merged.update(as_object(right))
    return json.dumps(merged, separators=(",", ":"), sort_keys=True)


def _cosine_similarity(left: Any, right: Any) -> float | None:
    def as_vector(value: Any) -> list[float]:
        if isinstance(value, list):
            return [float(item) for item in value]
        if not value:
            return []
        decoded = json.loads(str(value))
        return [float(item) for item in decoded] if isinstance(decoded, list) else []

    a = as_vector(left)
    b = as_vector(right)
    if not a or len(a) != len(b):
        return None
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return None
    return dot / (norm_a * norm_b)


def _adapt_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, separators=(",", ":"), sort_keys=True)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bool):
        return int(value)
    return value


_CAST_RE = re.compile(r"::(?:jsonb|timestamptz|text|vector)\b", re.IGNORECASE)
_FOR_UPDATE_RE = re.compile(r"\s+FOR\s+UPDATE\b", re.IGNORECASE)
_NOW_RE = re.compile(r"\bnow\(\)", re.IGNORECASE)
_ILIKE_RE = re.compile(r"\bILIKE\b", re.IGNORECASE)


def translate_sql(sql: str) -> str:
    """Translate the deliberately small Postgres subset used by ``cli.db``."""

    translated = _CAST_RE.sub("", sql)
    translated = _FOR_UPDATE_RE.sub("", translated)
    translated = _NOW_RE.sub("CURRENT_TIMESTAMP", translated)
    translated = _ILIKE_RE.sub("LIKE", translated)
    translated = translated.replace("state_extra = state_extra || %s", "state_extra = json_merge(state_extra, %s)")
    translated = translated.replace("%s", "?")
    translated = translated.replace("%%", "%")
    return translated


class EmbeddedCursor(AbstractContextManager["EmbeddedCursor"]):
    def __init__(self, cursor: sqlite3.Cursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> "EmbeddedCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def close(self) -> None:
        self._cursor.close()

    def execute(
        self,
        sql: str,
        params: Sequence[Any] | None = None,
    ) -> "EmbeddedCursor":
        values = tuple(_adapt_value(value) for value in (params or ()))
        self._cursor.execute(translate_sql(sql), values)
        return self

    def executemany(
        self,
        sql: str,
        rows: Iterable[Sequence[Any]],
    ) -> "EmbeddedCursor":
        values = [tuple(_adapt_value(value) for value in row) for row in rows]
        self._cursor.executemany(translate_sql(sql), values)
        return self

    def fetchone(self) -> tuple[Any, ...] | None:
        row = self._cursor.fetchone()
        return tuple(row) if row is not None else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return [tuple(row) for row in self._cursor.fetchall()]

    def __iter__(self) -> Iterator[tuple[Any, ...]]:
        for row in self._cursor:
            yield tuple(row)


class EmbeddedConnection:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            path,
            timeout=30,
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
        )
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute("PRAGMA busy_timeout = 30000")
        self._connection.create_function("greatest", -1, _greatest)
        self._connection.create_function("least", -1, _least)
        self._connection.create_function("json_merge", 2, _json_merge)
        self._connection.create_function("cosine_similarity", 2, _cosine_similarity)

    def cursor(self) -> EmbeddedCursor:
        return EmbeddedCursor(self._connection.cursor())

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()

    def execute_script(self, sql: str) -> None:
        self._connection.executescript(sql)

