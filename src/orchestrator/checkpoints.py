"""Campaign checkpoints and restore.

Checkpoints are operator-owned snapshots outside the live campaign workspace.
They capture every persistence surface that can affect agent context:

- campaign filesystem prose/projections
- Postgres campaign rows, including search chunks and embeddings
- FalkorDB campaign graph nodes and edges

The live campaign workspace remains the path agents read. Checkpoint archives
live under campaigns/.checkpoints/ so discarded/restored state is not projected
into agent CWDs.
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


POSTGRES_TABLES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "characters",
        (
            "campaign_id", "character_id", "player_id", "name", "archetype",
            "pronouns", "bio", "attributes", "skills", "momentum_current",
            "momentum_floor", "momentum_ceiling", "hp_current", "hp_max",
            "inventory", "tags", "created_at", "updated_at", "xp", "level",
            "skill_xp", "species", "culture", "organization_role", "goals",
        ),
        "character_id",
    ),
    (
        "campaign_runtime_states",
        (
            "campaign_id", "status", "created_at", "updated_at", "wrapped_at",
            "summary", "turn_counter", "mode_stack", "pending_events",
            "note_intake", "entities", "threads", "next_speakers",
            "scene_closing_turns", "active_turn_id", "active_turn_number",
            "active_turn_actor", "active_turn_role", "active_turn_mode",
            "active_turn_scene_id", "active_turn_character_id",
            "active_turn_kind", "active_turn_turn_type_required",
            "active_turn_allow_player_scene_close",
            "active_turn_beat_checked_at", "active_turn_audit_ran_at",
            "closeout_summary", "closeout_next_speaker",
            "closeout_scene_status", "closeout_state_changes",
            "closeout_rolls", "closeout_open_questions",
            "closeout_position", "closeout_pressure", "closeout_turn_type",
            "closeout_valid", "closeout_problems", "closeout_updated_at",
            "state_extra",
        ),
        "campaign_id",
    ),
    (
        "turns",
        (
            "campaign_id", "turn_id", "session_id", "scene_id", "mode",
            "speaker", "role", "character_id", "source_path", "prose",
            "event_summaries", "events", "markdown", "created_at", "arc_id",
            "scene_type", "turn_number_in_scene", "visibility",
            "turn_summary", "next_speaker", "scene_status", "state_changes",
            "rolls", "turn_type", "open_questions", "position", "pressure",
            "turn_end",
        ),
        "turn_id",
    ),
    (
        "messages",
        (
            "id", "campaign_id", "session_id", "sender", "recipient", "type",
            "body", "created_at",
        ),
        "created_at, id",
    ),
    (
        "message_reads",
        ("agent_id", "message_id", "read_at"),
        "agent_id, message_id",
    ),
    (
        "rolls",
        (
            "id", "campaign_id", "session_id", "scene_id", "character_id",
            "actor", "skill", "attribute", "risk", "dice", "skill_tier",
            "skill_modifier", "attribute_tier", "attribute_modifier",
            "momentum_in", "total", "target", "margin", "outcome",
            "momentum_delta", "momentum_out", "target_id", "metadata",
            "created_at",
        ),
        "created_at, id",
    ),
    (
        "xp_awards",
        (
            "id", "campaign_id", "character_id", "actor", "delta",
            "xp_before", "xp_after", "reason", "session_id", "scene_id",
            "created_at",
        ),
        "created_at, id",
    ),
    (
        "level_ups",
        (
            "id", "campaign_id", "character_id", "actor", "from_level",
            "to_level", "hp_roll", "hp_max_before", "hp_max_after",
            "attribute_bumped", "attribute_to_tier", "momentum_ceiling_before",
            "momentum_ceiling_after", "session_id", "scene_id", "created_at",
        ),
        "created_at, id",
    ),
    (
        "character_consequences",
        (
            "id", "campaign_id", "character_id", "label", "description",
            "severity", "scope", "visibility", "status", "created_by",
            "resolved_by", "resolution_note", "created_at", "resolved_at",
        ),
        "created_at, id",
    ),
    (
        "clocks",
        (
            "campaign_id", "clock_id", "scope", "anchor_id", "label",
            "description", "value", "max_value", "direction", "visibility",
            "status", "created_by", "updated_by", "created_at", "updated_at",
            "resolved_at", "resolution_note",
        ),
        "clock_id",
    ),
    (
        "clock_events",
        (
            "id", "campaign_id", "clock_id", "actor", "event_type", "delta",
            "value_before", "value_after", "note", "created_at",
        ),
        "created_at, id",
    ),
    (
        "events",
        (
            "event_id", "campaign_id", "scene_id", "turn_id", "actor",
            "event_type", "visibility", "summary", "payload", "created_at",
            "claimed_at",
        ),
        "created_at, event_id",
    ),
    (
        "scene_trackers",
        (
            "campaign_id", "tracker_id", "scene_id", "label", "value",
            "max_value", "resistance", "impact_resistance", "visibility",
            "status", "updated_by", "created_at", "updated_at",
        ),
        "scene_id, tracker_id",
    ),
    (
        "scene_clocks",
        (
            "campaign_id", "scene_id", "clock_id", "label", "goal", "value",
            "max_value", "direction", "visibility", "status", "created_by",
            "created_turn_id", "resolved_turn_id", "outcome", "created_at",
            "updated_at", "resolved_at",
        ),
        "scene_id, clock_id",
    ),
    (
        "scene_beats",
        (
            "campaign_id", "scene_id", "beat_id", "clock_id", "label",
            "question", "status", "non_pass_turns", "created_by",
            "created_turn_id", "closed_by", "closed_turn_id", "outcome",
            "converted_to_clock_id", "created_at", "updated_at", "closed_at",
        ),
        "scene_id, beat_id",
    ),
    (
        "action_orders",
        (
            "campaign_id", "mode", "scene_id", "label", "round", "cursor",
            "order_agents", "rolls", "active", "created_by", "created_at",
            "updated_at",
        ),
        "scene_id, mode",
    ),
    (
        "search_chunks",
        (
            "chunk_id", "campaign_id", "source_type", "source_id",
            "visibility", "owner_actor", "path", "title", "body", "metadata",
            "embedding_vector", "embedding_model", "embedding_provider",
            "embedding_dim", "embedded_at", "updated_at",
        ),
        "source_type, source_id, chunk_id",
    ),
    (
        "tarot_influences",
        (
            "id", "campaign_id", "actor", "deck_id", "deck_name", "card_id",
            "card_name", "influence", "source_note", "starts_turn",
            "expires_turn", "active", "created_at",
        ),
        "actor, starts_turn, id",
    ),
)


RESTORE_DELETE_ORDER = (
    "message_reads",
    "events",
    "scene_beats",
    "scene_clocks",
    "scene_trackers",
    "action_orders",
    "search_chunks",
    "tarot_influences",
    "turns",
    "campaign_runtime_states",
    "clock_events",
    "clocks",
    "rolls",
    "xp_awards",
    "level_ups",
    "character_consequences",
    "messages",
    "characters",
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

        postgres = export_postgres(config, campaign_id)
        _write_json(tmp_path / "postgres.json", postgres)

        graph = export_falkor(config, campaign_id)
        _write_json(tmp_path / "falkor.json", graph)

        manifest = {
            "checkpoint_id": checkpoint_id,
            "campaign_id": campaign_id,
            "label": label or "",
            "created_at": _now(),
            "paths": {
                "filesystem": "filesystem",
                "postgres": "postgres.json",
                "falkor": "falkor.json",
            },
            "counts": {
                "postgres": {
                    table: len(rows)
                    for table, rows in postgres.get("tables", {}).items()
                },
                "falkor": graph.get("counts", {}),
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
    postgres_snapshot = checkpoint_path / manifest["paths"]["postgres"]
    falkor_snapshot = checkpoint_path / manifest["paths"]["falkor"]
    if not fs_snapshot.exists():
        raise FileNotFoundError(f"checkpoint filesystem snapshot missing: {fs_snapshot}")
    if not postgres_snapshot.exists():
        raise FileNotFoundError(f"checkpoint postgres snapshot missing: {postgres_snapshot}")
    if not falkor_snapshot.exists():
        raise FileNotFoundError(f"checkpoint falkor snapshot missing: {falkor_snapshot}")

    restore_id = _checkpoint_id(f"restore-{checkpoint_id}")
    discarded_root = root / "_discarded" / restore_id
    discarded_root.mkdir(parents=True, exist_ok=False)

    # Safety snapshot of the current live state before any destructive restore.
    current_dir = config.campaigns_dir / campaign_id
    if current_dir.exists():
        shutil.copytree(current_dir, discarded_root / "filesystem", symlinks=True)
    try:
        _write_json(discarded_root / "postgres.json", export_postgres(config, campaign_id))
        _write_json(discarded_root / "falkor.json", export_falkor(config, campaign_id))
    except Exception:
        # Do not mutate if we cannot archive all live persistence surfaces.
        raise

    postgres = json.loads(postgres_snapshot.read_text(encoding="utf-8"))
    falkor = json.loads(falkor_snapshot.read_text(encoding="utf-8"))
    restore_postgres(config, campaign_id, postgres)
    restore_falkor(config, campaign_id, falkor)

    live_archive = discarded_root / "live-workspace-before-restore"
    if current_dir.exists():
        current_dir.rename(live_archive)
    shutil.copytree(fs_snapshot, current_dir, symlinks=True)
    _remove_runtime_json_files(current_dir)
    permissions.apply_campaign_permissions(current_dir)

    projection_root = config.repo_root / ".glass-cwd" / campaign_id
    if projection_root.exists():
        shutil.rmtree(projection_root, ignore_errors=True)

    return {
        "campaign_id": campaign_id,
        "checkpoint_id": checkpoint_id,
        "checkpoint_path": str(checkpoint_path),
        "discarded_archive": str(discarded_root),
        "restored_counts": manifest.get("counts", {}),
    }


def export_postgres(config: AogConfig, campaign_id: str) -> dict[str, Any]:
    from cli import db as _glass_db
    from cli.config import load_config as _load_glass_config

    previous = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = config_env_value(config)
    try:
        toml_data = _load_glass_config()
        if not _glass_db.postgres_configured(toml_data):
            raise RuntimeError("Postgres is not configured; cannot checkpoint campaign state")
        pg_config = _glass_db.load_pg_config(toml_data)
        with _glass_db.connect(pg_config) as conn:
            tables: dict[str, list[dict[str, Any]]] = {}
            with conn.cursor() as cur:
                for table, columns, order_by in POSTGRES_TABLES:
                    column_sql = ", ".join(columns)
                    if table == "message_reads":
                        query = (
                            f"SELECT to_jsonb(t) FROM (SELECT {column_sql} "
                            "FROM message_reads r "
                            "JOIN messages m ON m.id = r.message_id "
                            "WHERE m.campaign_id = %s "
                            f"ORDER BY {order_by}) t"
                        )
                    else:
                        query = (
                            f"SELECT to_jsonb(t) FROM (SELECT {column_sql} "
                            f"FROM {table} WHERE campaign_id = %s "
                            f"ORDER BY {order_by}) t"
                        )
                    cur.execute(query, (campaign_id,))
                    tables[table] = [dict(row[0]) for row in cur.fetchall()]
        return {
            "campaign_id": campaign_id,
            "exported_at": _now(),
            "target": pg_config.describe(),
            "tables": tables,
        }
    finally:
        if previous is None:
            os.environ.pop("GLASS_CONFIG", None)
        else:
            os.environ["GLASS_CONFIG"] = previous


def restore_postgres(
    config: AogConfig,
    campaign_id: str,
    snapshot: dict[str, Any],
) -> dict[str, int]:
    from cli import db as _glass_db
    from cli.config import load_config as _load_glass_config

    tables = snapshot.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("invalid postgres checkpoint: missing tables")

    previous = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = config_env_value(config)
    try:
        toml_data = _load_glass_config()
        if not _glass_db.postgres_configured(toml_data):
            raise RuntimeError("Postgres is not configured; cannot restore campaign state")
        pg_config = _glass_db.load_pg_config(toml_data)
        restored: dict[str, int] = {}
        with _glass_db.connect(pg_config) as conn:
            with conn.cursor() as cur:
                _delete_postgres_campaign(cur, campaign_id)
                for table, columns, _order_by in POSTGRES_TABLES:
                    rows = tables.get(table, [])
                    if not isinstance(rows, list):
                        raise ValueError(f"invalid postgres checkpoint table: {table}")
                    column_sql = ", ".join(columns)
                    select_sql = ", ".join(columns)
                    for row in rows:
                        if str(row.get("campaign_id", campaign_id)) != campaign_id:
                            if table != "message_reads":
                                raise ValueError(
                                    f"checkpoint row campaign mismatch in {table}"
                                )
                        cur.execute(
                            f"""
                            INSERT INTO {table} ({column_sql})
                            SELECT {select_sql}
                            FROM json_populate_record(NULL::{table}, %s::json)
                            """,
                            (json.dumps(row),),
                        )
                    restored[table] = len(rows)
            conn.commit()
        return restored
    finally:
        if previous is None:
            os.environ.pop("GLASS_CONFIG", None)
        else:
            os.environ["GLASS_CONFIG"] = previous


def export_falkor(config: AogConfig, campaign_id: str) -> dict[str, Any]:
    from cli import graph as _graph
    from cli.config import load_config as _load_glass_config

    previous = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = config_env_value(config)
    try:
        falkor_config = _graph.load_falkor_config(_load_glass_config())
        if not _graph.is_available(falkor_config):
            raise RuntimeError(f"FalkorDB is not reachable at {falkor_config.describe()}")
        with _graph.connect(falkor_config) as g:
            return _graph.export_campaign_graph(g, campaign_id)
    finally:
        if previous is None:
            os.environ.pop("GLASS_CONFIG", None)
        else:
            os.environ["GLASS_CONFIG"] = previous


def restore_falkor(
    config: AogConfig,
    campaign_id: str,
    snapshot: dict[str, Any],
) -> dict[str, int]:
    from cli import graph as _graph
    from cli.config import load_config as _load_glass_config

    previous = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = config_env_value(config)
    try:
        falkor_config = _graph.load_falkor_config(_load_glass_config())
        if not _graph.is_available(falkor_config):
            raise RuntimeError(f"FalkorDB is not reachable at {falkor_config.describe()}")
        with _graph.connect(falkor_config) as g:
            return _graph.import_campaign_graph(g, campaign_id, snapshot)
    finally:
        if previous is None:
            os.environ.pop("GLASS_CONFIG", None)
        else:
            os.environ["GLASS_CONFIG"] = previous


def _delete_postgres_campaign(cur: Any, campaign_id: str) -> None:
    for table in RESTORE_DELETE_ORDER:
        if table == "message_reads":
            cur.execute(
                "DELETE FROM message_reads r USING messages m "
                "WHERE r.message_id = m.id AND m.campaign_id = %s",
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
