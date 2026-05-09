"""Entity commands."""

from __future__ import annotations

import json
import os
import random
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

from .. import db as _db
from .. import workspace as _workspace
from ..campaign import (
    active_campaign_id,
    active_campaign_root,
    lookup_player_character_id,
    pg_connection,
    resolve_active_campaign_workspace,
)
from ..config import REPO_ROOT, Paths, get_paths, load_config
from ..constants import (
    ATTRIBUTE_TIERS,
    ATTRIBUTES,
    RISK_THRESHOLDS,
    SKILL_TIERS,
    STARTER_MESSAGE_TYPES,
)
from ..entities import (
    markdown_title,
    parse_frontmatter,
    parse_sections,
    upsert_entity_from_path,
)
from ..errors import GlassError
from ..ids import new_id, now_iso, slugify
from ..messages import (
    infer_player_from_path,
    load_message_types,
    message_visible_to,
    player_dirs,
    require_message_type,
    require_recipient,
    roster,
)
from ..paths_resolve import (
    clean_relative_path,
    display_path,
    ensure_under,
    ensure_under_any,
    resolve_content_path,
    resolve_note_write_path,
)
from ..role import (
    Role,
    actor_for_turn,
    assert_character_writable,
    current_role,
    require_dm,
    require_player,
    role_label_for_turn,
)
from ..state import (
    active_session_file,
    active_session_id,
    append_audit,
    audit_path,
    commit,
    current_mode_record,
    default_state,
    inline_event_lines,
    load_state,
    normalize_state,
    queue_event,
    save_state,
    session_dir,
    state_path,
    state_summary,
    transcript_path,
    write_active_session,
)
from ..validation import (
    assert_attribute_name,
    clamp,
    outcome_for_margin,
    validate_key_values,
)
from ..yaml_io import (
    command_params,
    emit,
    make_jsonable,
    read_body,
    to_yaml,
    yaml_scalar,
)


@click.group()
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


