"""Entity commands."""

from __future__ import annotations

import json
import os
import random
import re
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
from ..errors import GlassError, agent_instruction
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
    state_path,
    state_summary,
    transcript_path,)
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


def _graph_unavailable_message(target: str) -> str:
    return agent_instruction(
        f"FalkorDB is not reachable at {target}",
        "Use the markdown/table/lore files that are already in TURN_START or the campaign workspace for this turn.",
        "If graph data is required, ask the operator to start FalkorDB and rerun the graph command.",
    )


def _graph_failure_message(action: str, detail: Exception) -> str:
    return agent_instruction(
        f"FalkorDB {action} failed",
        "Do not keep retrying this graph command in the same turn.",
        "Use visible table/lore files for immediate play, and ask the operator to inspect the graph service if the relationship query is required.",
        f"Graph detail: {detail}",
    )


@entity.command("upsert")
@click.argument("path_text")
@click.option("--campaign-id", default=None, help="Override campaign id (default: GLASS_CAMPAIGN_ID).")
@click.pass_context
def entity_upsert(ctx: click.Context, path_text: str, campaign_id: str | None) -> None:
    require_dm()
    paths = get_paths()
    target_campaign = campaign_id or active_campaign_id()
    state = load_state(paths, target_campaign)
    path = resolve_content_path(paths, path_text)
    record = upsert_entity_from_path(paths, state, path)

    # Mirror the entity into FalkorDB. Best-effort: if the graph is
    # unreachable, the JSON state still has the data and the operation
    # remains useful — but we surface the error so the operator knows.
    graph_status = _mirror_entity_to_graph(record, path, target_campaign)

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
    from .. import graph as _graph

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
    """Show an entity's outgoing edges, incoming edges, and sections."""
    from .. import graph as _graph

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(_graph_unavailable_message(config.describe()))
    try:
        with _graph.connect(config) as g:
            payload = _graph.neighborhood(
                g, entity_id, campaign_id=campaign_id
            )
    except Exception as exc:
        raise GlassError(_graph_failure_message("neighborhood lookup", exc)) from exc
    if not payload.get("found"):
        raise GlassError(
            agent_instruction(
                f"unknown entity {entity_id!r} in graph",
                "Search first with `glass entity find --query <text>` or use a lore/table file path you know exists.",
            )
        )
    result = {**payload, "source": "falkordb", "target": config.describe()}
    append_audit(
        paths, state, ctx, "entity.neighborhood",
        command_params(entity_id=entity_id), result,
    )
    emit(result)


@entity.command("relations")
@click.argument("entity_id")
@click.option("--type", "edge_type", default=None, help="Filter by edge type.")
@click.option(
    "--direction",
    type=click.Choice(["out", "in", "both"]),
    default="both",
    show_default=True,
)
@click.option("--target-type", default=None, help="Filter by related entity type.")
@click.option("--limit", type=int, default=50, show_default=True)
@click.pass_context
def entity_relations(
    ctx: click.Context,
    entity_id: str,
    edge_type: str | None,
    direction: str,
    target_type: str | None,
    limit: int,
) -> None:
    """Show typed relationships touching an entity."""
    from .. import graph as _graph

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(_graph_unavailable_message(config.describe()))
    try:
        with _graph.connect(config) as g:
            rows = _graph.relations(
                g,
                entity_id,
                campaign_id=campaign_id,
                edge_type=edge_type,
                direction=direction,
                target_type=target_type,
                limit=limit,
            )
    except Exception as exc:
        raise GlassError(_graph_failure_message("relations lookup", exc)) from exc
    result = {
        "target": config.describe(),
        "entity_id": entity_id,
        "relationships": rows,
        "count": len(rows),
    }
    append_audit(
        paths,
        state,
        ctx,
        "entity.relations",
        command_params(entity_id=entity_id, type=edge_type, direction=direction),
        result,
    )
    emit(result)


@entity.command("between")
@click.argument("src_id")
@click.argument("dst_id")
@click.pass_context
def entity_between(ctx: click.Context, src_id: str, dst_id: str) -> None:
    """Show direct typed relationships between two entities."""
    from .. import graph as _graph

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(_graph_unavailable_message(config.describe()))
    try:
        with _graph.connect(config) as g:
            rows = _graph.between(
                g, campaign_id=campaign_id, src_id=src_id, dst_id=dst_id
            )
    except Exception as exc:
        raise GlassError(_graph_failure_message("between lookup", exc)) from exc
    result = {
        "target": config.describe(),
        "source": src_id,
        "destination": dst_id,
        "relationships": rows,
        "count": len(rows),
    }
    append_audit(
        paths,
        state,
        ctx,
        "entity.between",
        command_params(src=src_id, dst=dst_id),
        result,
    )
    emit(result)


@entity.command("edges")
@click.option("--type", "edge_type", required=True, help="Edge type, e.g. AT_WAR_WITH.")
@click.option("--limit", type=int, default=100, show_default=True)
@click.pass_context
def entity_edges(ctx: click.Context, edge_type: str, limit: int) -> None:
    """List graph edges of a given type."""
    from .. import graph as _graph

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(_graph_unavailable_message(config.describe()))
    try:
        with _graph.connect(config) as g:
            rows = _graph.edges_by_type(
                g, campaign_id=campaign_id, edge_type=edge_type, limit=limit
            )
    except Exception as exc:
        raise GlassError(_graph_failure_message("edges lookup", exc)) from exc
    result = {
        "target": config.describe(),
        "edge_type": edge_type,
        "edges": rows,
        "count": len(rows),
    }
    append_audit(
        paths,
        state,
        ctx,
        "entity.edges",
        command_params(type=edge_type, limit=limit),
        result,
    )
    emit(result)


@entity.command("stance")
@click.argument("src_id")
@click.argument("dst_id")
@click.pass_context
def entity_stance(ctx: click.Context, src_id: str, dst_id: str) -> None:
    """Convenience alias for relationship state between two entities.

    No social schema is implied: this returns direct edge facts and their
    freeform properties.
    """
    from .. import graph as _graph

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(_graph_unavailable_message(config.describe()))
    try:
        with _graph.connect(config) as g:
            rows = _graph.between(
                g, campaign_id=campaign_id, src_id=src_id, dst_id=dst_id
            )
    except Exception as exc:
        raise GlassError(_graph_failure_message("stance lookup", exc)) from exc
    result = {
        "target": config.describe(),
        "source": src_id,
        "destination": dst_id,
        "relationships": rows,
        "count": len(rows),
    }
    append_audit(
        paths,
        state,
        ctx,
        "entity.stance",
        command_params(src=src_id, dst=dst_id),
        result,
    )
    emit(result)


@entity.command("similar")
@click.argument("section_id")
@click.option("--limit", type=int, default=5)
@click.pass_context
def entity_similar(ctx: click.Context, section_id: str, limit: int) -> None:
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
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
        raise GlassError(
            agent_instruction(
                f"unknown section {section_id!r}",
                f"Use one of the known section ids: {known}.",
                "Run `glass entity neighborhood <entity-id>` or inspect the lore file before asking for similar sections.",
            )
        )
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
    from .. import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(_graph_unavailable_message(config.describe()))

    role = current_role()
    active_campaign = active_campaign_id()
    if role.kind == "player" and campaign_id and campaign_id != active_campaign:
        raise GlassError(
            agent_instruction(
                "players cannot query another campaign graph",
                "Query the active campaign only; omit `--campaign-id` from player turns.",
            )
        )
    campaign = campaign_id or active_campaign
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
        raise GlassError(_graph_failure_message("find query", exc)) from exc

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
    from .. import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(_graph_unavailable_message(config.describe()))

    properties: dict[str, Any] = {}
    for raw in props:
        if "=" not in raw:
            raise GlassError(
                agent_instruction(
                    f"invalid `--prop` value {raw!r}",
                    "Use `--prop key=value` for each relationship property.",
                )
            )
        k, v = raw.split("=", 1)
        properties[k.strip()] = v.strip()

    try:
        with _graph.connect(config) as g:
            _graph.link_entities(
                g,
                campaign_id=active_campaign_id(),
                src_id=src_id,
                edge_type=edge_type,
                dst_id=dst_id,
                properties=properties,
            )
    except (ValueError, Exception) as exc:
        raise GlassError(_graph_failure_message("link mutation", exc)) from exc

    emit({
        "target": config.describe(),
        "src": src_id,
        "edge_type": edge_type,
        "dst": dst_id,
        "properties": properties,
        "status": "linked",
    })


@entity.command("claim")
@click.argument("src_id")
@click.argument("edge_type")
@click.argument("dst_id")
@click.option("--summary", required=True, help="Why this relationship should exist.")
@click.option("--prop", "props", multiple=True, help="key=value edge property; repeatable.")
@click.pass_context
def entity_claim(
    ctx: click.Context,
    src_id: str,
    edge_type: str,
    dst_id: str,
    summary: str,
    props: tuple[str, ...],
) -> None:
    """Propose a graph relationship without mutating the canonical graph."""
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", edge_type):
        raise GlassError(
            agent_instruction(
                f"edge type must be UPPERCASE_SNAKE_CASE: {edge_type!r}",
                "Use a relationship type like `ALLIED_WITH`, `OWES`, `LOCATED_IN`, or another uppercase snake-case verb phrase.",
            )
        )
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    properties = _parse_edge_props(props)
    claim_id = new_id("claim")
    workspace_root = active_campaign_root()
    destination = workspace_root / "dm" / "intake" / f"{claim_id}--{role.actor}--relationship.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "---\n"
        "kind: relationship-claim\n"
        f"claim_id: {claim_id}\n"
        f"actor: {role.actor}\n"
        f"src: {src_id}\n"
        f"edge_type: {edge_type}\n"
        f"dst: {dst_id}\n"
        "---\n\n"
        "# Relationship Claim\n\n"
        f"- Source: `{src_id}`\n"
        f"- Edge: `{edge_type}`\n"
        f"- Target: `{dst_id}`\n"
        f"- Properties: `{json.dumps(properties, sort_keys=True)}`\n\n"
        f"{summary.strip()}\n"
    )
    destination.write_text(body, encoding="utf-8")
    record = {
        "intake_id": claim_id,
        "kind": "relationship-claim",
        "player_id": role.actor if role.kind == "player" else None,
        "actor": role.actor,
        "source_path": None,
        "intake_path": display_path(destination),
        "status": "pending",
        "created_at": now_iso(),
        "resolved_at": None,
        "src": src_id,
        "edge_type": edge_type,
        "dst": dst_id,
        "properties": properties,
        "summary": summary.strip(),
    }
    state["note_intake"].append(record)
    result = {"claim": record}
    commit(
        paths,
        state,
        ctx,
        "entity.claim",
        command_params(src=src_id, edge_type=edge_type, dst=dst_id),
        result,
    )


@entity.command("ratify-claim")
@click.argument("claim_id")
@click.pass_context
def entity_ratify_claim(ctx: click.Context, claim_id: str) -> None:
    """DM-only: ratify a relationship claim into a canonical graph edge."""
    require_dm()
    from .. import graph as _graph

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    claim = _relationship_claim(state, claim_id)
    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(_graph_unavailable_message(config.describe()))
    try:
        with _graph.connect(config) as g:
            _graph.link_entities(
                g,
                campaign_id=campaign_id,
                src_id=claim["src"],
                edge_type=claim["edge_type"],
                dst_id=claim["dst"],
                properties=claim.get("properties", {}),
            )
    except Exception as exc:
        raise GlassError(_graph_failure_message("claim ratification", exc)) from exc
    claim["status"] = "ratified"
    claim["resolved_at"] = now_iso()
    result = {"claim": claim, "target": config.describe(), "status": "ratified"}
    commit(
        paths,
        state,
        ctx,
        "entity.ratify-claim",
        command_params(claim_id=claim_id),
        result,
    )


@entity.command("unlink")
@click.argument("src_id")
@click.argument("edge_type")
@click.argument("dst_id")
@click.pass_context
def entity_unlink(ctx: click.Context, src_id: str, edge_type: str, dst_id: str) -> None:
    """Remove a typed edge between two entities (DM-only)."""
    require_dm()
    from .. import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(_graph_unavailable_message(config.describe()))
    try:
        with _graph.connect(config) as g:
            removed = _graph.unlink_entities(
                g,
                campaign_id=active_campaign_id(),
                src_id=src_id,
                edge_type=edge_type,
                dst_id=dst_id,
            )
    except Exception as exc:
        raise GlassError(_graph_failure_message("unlink mutation", exc)) from exc
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
    from .. import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(_graph_unavailable_message(config.describe()))

    parameters: dict[str, Any] = {}
    for raw in params:
        if "=" not in raw:
            raise GlassError(
                agent_instruction(
                    f"invalid `--param` value {raw!r}",
                    "Use `--param key=value` for each Cypher parameter.",
                )
            )
        k, v = raw.split("=", 1)
        parameters[k.strip()] = v.strip()

    try:
        with _graph.connect(config) as g:
            payload = _graph.run_query(g, cypher, parameters)
    except Exception as exc:
        raise GlassError(_graph_failure_message("Cypher query", exc)) from exc

    emit({"target": config.describe(), "cypher": cypher, "params": parameters, **payload})


@entity.command("stats")
@click.pass_context
def entity_stats(ctx: click.Context) -> None:
    """Show graph counts: entities, sections, edges, top edge types, top entity types."""
    from .. import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(_graph_unavailable_message(config.describe()))
    try:
        with _graph.connect(config) as g:
            stats = _graph.graph_stats(g)
    except Exception as exc:
        raise GlassError(_graph_failure_message("stats query", exc)) from exc
    emit({"target": config.describe(), **stats})


def _parse_edge_props(props: tuple[str, ...]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for raw in props:
        if "=" not in raw:
            raise GlassError(
                agent_instruction(
                    f"invalid `--prop` value {raw!r}",
                    "Use `--prop key=value` for each relationship property.",
                )
            )
        k, v = raw.split("=", 1)
        properties[k.strip()] = v.strip()
    return properties


def _relationship_claim(state: dict[str, Any], claim_id: str) -> dict[str, Any]:
    for item in state.get("note_intake", []):
        if item.get("intake_id") != claim_id:
            continue
        if item.get("kind") != "relationship-claim":
            raise GlassError(
                agent_instruction(
                    f"intake {claim_id!r} is not a relationship claim",
                    "Use an intake id created by `glass entity claim`, not a note intake id.",
                )
            )
        if item.get("status") != "pending":
            raise GlassError(
                agent_instruction(
                    f"relationship claim {claim_id!r} is already {item.get('status')}",
                    "Do not ratify it again; choose a pending relationship claim.",
                )
            )
        return item
    known = ", ".join(
        item.get("intake_id", "")
        for item in state.get("note_intake", [])
        if item.get("kind") == "relationship-claim"
    ) or "none"
    raise GlassError(
        agent_instruction(
            f"unknown relationship claim {claim_id!r}",
            f"Use one of the known relationship claims: {known}.",
            "Create a new claim with `glass entity claim <src> <EDGE_TYPE> <dst> --summary <why>` if needed.",
        )
    )
