"""Campaign checkpoints and restore.

Checkpoints are operator-owned snapshots outside the live campaign workspace.
They capture every persistence surface that can affect runtime context:

- campaign filesystem prose/reference artifacts
- embedded campaign rows, including continuity facts and search vectors

Checkpoint archives live under campaigns/.checkpoints/ so discarded/restored
state stays outside normal runtime discovery.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import os
import re
import shutil

from . import permissions
from .config import AogConfig, config_env_value


STORAGE_TABLES: tuple[tuple[str, str], ...] = (
    (
        "characters",
        "character_id",
    ),
    (
        "campaign_runtime_states",
        "campaign_id",
    ),
    (
        "turns",
        "turn_id",
    ),
    (
        "messages",
        "created_at, id",
    ),
    (
        "message_reads",
        "agent_id, message_id",
    ),
    (
        "rolls",
        "created_at, id",
    ),
    (
        "xp_awards",
        "created_at, id",
    ),
    (
        "level_ups",
        "created_at, id",
    ),
    ("signature_moves", "created_at, id"),
    (
        "character_consequences",
        "created_at, id",
    ),
    (
        "clocks",
        "clock_id",
    ),
    (
        "clock_events",
        "created_at, id",
    ),
    (
        "events",
        "created_at, event_id",
    ),
    (
        "scene_trackers",
        "scene_id, tracker_id",
    ),
    (
        "scene_clocks",
        "scene_id, clock_id",
    ),
    (
        "scene_beats",
        "scene_id, beat_id",
    ),
    (
        "action_orders",
        "scene_id, mode",
    ),
    (
        "search_chunks",
        "source_type, source_id, chunk_id",
    ),
    (
        "tarot_influences",
        "actor, starts_turn, id",
    ),
    ("facts", "scope_id, salience_rank DESC, updated_at, uid"),
    ("lore_entries", "namespace, updated_at, uid"),
)

_RUNTIME_JSON_FILES = {
    ".glass-grants.json",
    "aog-state.json",
    "state.json",
}


@dataclass(frozen=True)
class CheckpointResult:
    checkpoint_id: str
    path: Path
    manifest: dict[str, Any]


def checkpoints_root(config: AogConfig, campaign_id: str) -> Path:
    return config.campaigns_dir / ".checkpoints" / campaign_id


def create_checkpoint(
    config: AogConfig,
    campaign_id: str,
    *,
    label: str | None = None,
) -> CheckpointResult:
    campaign_dir = config.campaigns_dir / campaign_id
    if not campaign_dir.exists():
        raise FileNotFoundError(f"campaign workspace not found: {campaign_dir}")

    checkpoint_id = _checkpoint_id(label)
    root = checkpoints_root(config, campaign_id)
    final_path = root / checkpoint_id
    tmp_path = root / f".{checkpoint_id}.tmp"
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    if final_path.exists():
        raise FileExistsError(f"checkpoint already exists: {final_path}")
    tmp_path.mkdir(parents=True, exist_ok=False)

    try:
        fs_path = tmp_path / "filesystem"
        shutil.copytree(
            campaign_dir,
            fs_path,
            symlinks=True,
            ignore=_checkpoint_ignore,
        )

        storage = export_storage(config, campaign_id)
        _write_json(tmp_path / "storage.json", storage)

        manifest = {
            "checkpoint_id": checkpoint_id,
            "campaign_id": campaign_id,
            "label": label or "",
            "created_at": _now(),
            "paths": {
                "filesystem": "filesystem",
                "storage": "storage.json",
            },
            "counts": {
                "storage": {
                    table: len(rows)
                    for table, rows in storage.get("tables", {}).items()
                },
            },
        }
        _write_json(tmp_path / "manifest.json", manifest)
        tmp_path.rename(final_path)
    except Exception:
        if tmp_path.exists():
            shutil.rmtree(tmp_path, ignore_errors=True)
        raise

    return CheckpointResult(
        checkpoint_id=checkpoint_id,
        path=final_path,
        manifest=manifest,
    )


def list_checkpoints(config: AogConfig, campaign_id: str) -> list[dict[str, Any]]:
    root = checkpoints_root(config, campaign_id)
    if not root.exists():
        return []
    checkpoints: list[dict[str, Any]] = []
    for child in sorted(root.iterdir()):
        manifest_path = child / "manifest.json"
        if not child.is_dir() or not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        checkpoints.append(
            {
                "checkpoint_id": manifest.get("checkpoint_id", child.name),
                "label": manifest.get("label", ""),
                "created_at": manifest.get("created_at", ""),
                "path": str(child),
                "counts": manifest.get("counts", {}),
            }
        )
    return checkpoints


def restore_checkpoint(
    config: AogConfig,
    campaign_id: str,
    checkpoint_id: str,
) -> dict[str, Any]:
    root = checkpoints_root(config, campaign_id)
    checkpoint_path = root / checkpoint_id
    manifest_path = checkpoint_path / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"checkpoint not found: {checkpoint_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fs_snapshot = checkpoint_path / manifest["paths"]["filesystem"]
    storage_snapshot = checkpoint_path / manifest["paths"]["storage"]
    if not fs_snapshot.exists():
        raise FileNotFoundError(f"checkpoint filesystem snapshot missing: {fs_snapshot}")
    if not storage_snapshot.exists():
        raise FileNotFoundError(f"checkpoint storage snapshot missing: {storage_snapshot}")

    restore_id = _checkpoint_id(f"restore-{checkpoint_id}")
    discarded_root = root / "_discarded" / restore_id
    discarded_root.mkdir(parents=True, exist_ok=False)

    # Safety snapshot of the current live state before any destructive restore.
    current_dir = config.campaigns_dir / campaign_id
    if current_dir.exists():
        shutil.copytree(current_dir, discarded_root / "filesystem", symlinks=True)
    try:
        _write_json(discarded_root / "storage.json", export_storage(config, campaign_id))
    except Exception:
        # Do not mutate if we cannot archive all live persistence surfaces.
        raise

    storage = json.loads(storage_snapshot.read_text(encoding="utf-8"))
    restore_storage(config, campaign_id, storage)

    live_archive = discarded_root / "live-workspace-before-restore"
    if current_dir.exists():
        current_dir.rename(live_archive)
    shutil.copytree(fs_snapshot, current_dir, symlinks=True)
    _remove_runtime_json_files(current_dir)
    permissions.apply_campaign_permissions(current_dir)

    return {
        "campaign_id": campaign_id,
        "checkpoint_id": checkpoint_id,
        "checkpoint_path": str(checkpoint_path),
        "discarded_archive": str(discarded_root),
        "restored_counts": manifest.get("counts", {}),
    }


def export_storage(config: AogConfig, campaign_id: str) -> dict[str, Any]:
    from cli import db as _glass_db
    from cli.config import load_config as _load_glass_config

    previous = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = config_env_value(config)
    try:
        toml_data = _load_glass_config()
        storage_config = _glass_db.load_storage_config(toml_data)
        with _glass_db.connect(storage_config) as conn:
            tables: dict[str, list[dict[str, Any]]] = {}
            table_columns: dict[str, list[str]] = {}
            with conn.cursor() as cur:
                for table, order_by in STORAGE_TABLES:
                    columns = _table_columns(cur, table)
                    table_columns[table] = columns
                    column_sql = ", ".join(columns)
                    if table == "message_reads":
                        query = (
                            f"SELECT {column_sql} "
                            "FROM message_reads r "
                            "JOIN messages m ON m.id = r.message_id "
                            "WHERE m.campaign_id = %s "
                            f"ORDER BY {order_by}"
                        )
                    else:
                        query = (
                            f"SELECT {column_sql} "
                            f"FROM {table} WHERE campaign_id = %s "
                            f"ORDER BY {order_by}"
                        )
                    cur.execute(query, (campaign_id,))
                    tables[table] = [
                        dict(zip(columns, row, strict=True)) for row in cur.fetchall()
                    ]
        return {
            "campaign_id": campaign_id,
            "exported_at": _now(),
            "target": storage_config.describe(),
            "columns": table_columns,
            "tables": tables,
        }
    finally:
        if previous is None:
            os.environ.pop("GLASS_CONFIG", None)
        else:
            os.environ["GLASS_CONFIG"] = previous


def restore_storage(
    config: AogConfig,
    campaign_id: str,
    snapshot: dict[str, Any],
) -> dict[str, int]:
    from cli import db as _glass_db
    from cli.config import load_config as _load_glass_config

    tables = snapshot.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("invalid storage checkpoint: missing tables")
    snapshot_columns = snapshot.get("columns")
    if not isinstance(snapshot_columns, dict):
        raise ValueError("invalid storage checkpoint: missing columns")

    previous = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = config_env_value(config)
    try:
        toml_data = _load_glass_config()
        storage_config = _glass_db.load_storage_config(toml_data)
        restored: dict[str, int] = {}
        with _glass_db.connect(storage_config) as conn:
            with conn.cursor() as cur:
                _delete_storage_campaign(cur, campaign_id)
                for table, _order_by in STORAGE_TABLES:
                    rows = tables.get(table, [])
                    if not isinstance(rows, list):
                        raise ValueError(f"invalid storage checkpoint table: {table}")
                    columns = _table_columns(cur, table)
                    if snapshot_columns.get(table) != columns:
                        raise ValueError(f"storage checkpoint schema mismatch: {table}")
                    column_sql = ", ".join(columns)
                    placeholders = ", ".join("%s" for _column in columns)
                    for row in rows:
                        if not isinstance(row, dict) or set(row) != set(columns):
                            raise ValueError(f"invalid storage checkpoint row: {table}")
                        if str(row.get("campaign_id", campaign_id)) != campaign_id:
                            if table != "message_reads":
                                raise ValueError(
                                    f"checkpoint row campaign mismatch in {table}"
                                )
                        cur.execute(
                            f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})",
                            tuple(row[column] for column in columns),
                        )
                    restored[table] = len(rows)
            conn.commit()
        return restored
    finally:
        if previous is None:
            os.environ.pop("GLASS_CONFIG", None)
        else:
            os.environ["GLASS_CONFIG"] = previous


def _table_columns(cur: Any, table: str) -> list[str]:
    cur.execute(f"PRAGMA table_info({table})")
    columns = [str(row[1]) for row in cur.fetchall()]
    if not columns:
        raise RuntimeError(f"embedded storage table is missing: {table}")
    return columns


def _delete_storage_campaign(cur: Any, campaign_id: str) -> None:
    for table, _order_by in reversed(STORAGE_TABLES):
        if table == "message_reads":
            cur.execute(
                "DELETE FROM message_reads WHERE message_id IN "
                "(SELECT id FROM messages WHERE campaign_id = %s)",
                (campaign_id,),
            )
        else:
            cur.execute(f"DELETE FROM {table} WHERE campaign_id = %s", (campaign_id,))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _checkpoint_ignore(directory: str, names: list[str]) -> set[str]:
    return set(names).intersection(_RUNTIME_JSON_FILES)


def _remove_runtime_json_files(root: Path) -> None:
    for name in _RUNTIME_JSON_FILES:
        path = root / name
        if path.exists() and path.is_file():
            path.unlink()


def _checkpoint_id(label: str | None = None) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    suffix = _slug(label or "checkpoint")
    return f"{stamp}-{suffix}"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "checkpoint"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
