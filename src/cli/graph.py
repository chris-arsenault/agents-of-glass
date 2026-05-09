"""FalkorDB connection + entity graph helpers for the glass CLI.

The graph mirrors campaign lore and DM notes. Each markdown entity becomes
one `(:Entity)` node with zero-or-more `(:Section)` child nodes for its
prose subsections. Typed edges between entities (`LOCATED_IN`, `MEMBER_OF`,
`ADVANCES_BEAT`, etc.) describe relationships.

Connection params come from `[falkordb]` in the active TOML, with env
fallbacks. Note the user's LAN FalkorDB runs on **port 16379** (not the
default Redis 6379).
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterator
import logging
import os
import re

try:
    from falkordb import FalkorDB
except ImportError:
    FalkorDB = None  # type: ignore[assignment]


log = logging.getLogger(__name__)

DEFAULT_PORT = 16379
DEFAULT_GRAPH = "agents_of_glass"


@dataclass(frozen=True)
class FalkorConfig:
    host: str
    port: int
    graph: str
    password: str | None

    def describe(self) -> str:
        creds = "<pw>@" if self.password else ""
        return f"falkordb://{creds}{self.host}:{self.port}/{self.graph}"


def load_falkor_config(toml_data: dict[str, Any] | None = None) -> FalkorConfig:
    section = (toml_data or {}).get("falkordb", {}) if toml_data else {}
    host = (
        (section.get("host") if section else None)
        or os.environ.get("AOG_FALKOR_HOST")
        or "localhost"
    )
    raw_port = (
        (section.get("port") if section else None)
        or os.environ.get("AOG_FALKOR_PORT")
        or DEFAULT_PORT
    )
    graph = (
        (section.get("graph") if section else None)
        or os.environ.get("AOG_FALKOR_GRAPH")
        or DEFAULT_GRAPH
    )
    password = os.environ.get("AOG_FALKOR_PASSWORD") or os.environ.get("REDIS_PASSWORD")
    return FalkorConfig(host=host, port=int(raw_port), graph=graph, password=password)


@contextmanager
def connect(config: FalkorConfig) -> Iterator[Any]:
    """Open a FalkorDB graph handle. Caller manages transactions."""
    if FalkorDB is None:
        raise RuntimeError(
            "falkordb is not installed; install with `pip install falkordb`"
        )
    client = FalkorDB(host=config.host, port=config.port, password=config.password)
    g = client.select_graph(config.graph)
    try:
        yield g
    finally:
        try:
            client.close()
        except Exception:
            pass


def is_available(config: FalkorConfig) -> bool:
    """Probe — can we connect and run a trivial query?"""
    if FalkorDB is None:
        return False
    try:
        with connect(config) as g:
            g.query("RETURN 1")
        return True
    except Exception as exc:
        log.debug("falkordb probe failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Entity upsert
# ---------------------------------------------------------------------------


def upsert_entity(
    g: Any,
    *,
    entity_id: str,
    campaign_id: str,
    title: str,
    entity_type: str,
    file_path: str,
    tags: list[str] | None = None,
    prominence: str | None = None,
    status: str | None = None,
    source: str | None = None,
    sections: list[dict[str, Any]] | None = None,
    mentions: list[str] | None = None,
) -> None:
    """Create or update an Entity node and its Sections.

    Replaces existing sections (delete + recreate) and refreshes any
    auto-derived `MENTIONS` edges. Manually-added typed edges (via
    `link_entities`) are preserved.
    """
    now = _now_iso()
    props: dict[str, Any] = {
        "id": entity_id,
        "campaign_id": campaign_id,
        "title": title,
        "type": entity_type,
        "file_path": file_path,
        "updated_at": now,
    }
    if tags is not None:
        props["tags"] = list(tags)
    if prominence is not None:
        props["prominence"] = prominence
    if status is not None:
        props["status"] = status
    if source is not None:
        props["source"] = source

    # Upsert the entity itself.
    set_assignments = ", ".join(f"e.{k} = ${k}" for k in props if k != "id")
    g.query(
        f"""
        MERGE (e:Entity {{id: $id}})
        ON CREATE SET e.created_at = $created_at
        SET {set_assignments}
        RETURN e
        """,
        {**props, "created_at": now},
    )

    # Replace sections.
    g.query(
        "MATCH (e:Entity {id: $id})-[r:HAS_SECTION]->(s:Section) DELETE r, s",
        {"id": entity_id},
    )
    for section in sections or []:
        section_id = section.get("section_id") or section.get("id")
        if not section_id:
            continue
        s_props = {
            "id": section_id,
            "entity_id": entity_id,
            "title": section.get("title", ""),
            "heading": section.get("heading", section.get("title", "")),
            "text": section.get("text", ""),
        }
        set_clause = ", ".join(f"s.{k} = ${k}" for k in s_props if k != "id")
        g.query(
            f"""
            MATCH (e:Entity {{id: $entity_id}})
            CREATE (e)-[:HAS_SECTION]->(s:Section {{id: $id}})
            SET {set_clause}
            """,
            {**s_props, "entity_id": entity_id},
        )

    # Refresh auto-detected MENTIONS edges.
    g.query(
        "MATCH (a:Entity {id: $id})-[r:MENTIONS]->(:Entity) DELETE r",
        {"id": entity_id},
    )
    for target_id in dict.fromkeys(mentions or []):
        if target_id == entity_id:
            continue
        g.query(
            """
            MATCH (a:Entity {id: $src})
            MERGE (b:Entity {id: $dst})
              ON CREATE SET b.title = $dst, b.status = 'shell'
            MERGE (a)-[:MENTIONS]->(b)
            """,
            {"src": entity_id, "dst": target_id},
        )


def remove_entity(g: Any, entity_id: str) -> int:
    """Delete an entity, its sections, and any edges touching it. Returns number of nodes affected."""
    res = g.query(
        """
        MATCH (e:Entity {id: $id})
        OPTIONAL MATCH (e)-[:HAS_SECTION]->(s:Section)
        DETACH DELETE e, s
        RETURN count(e) AS n
        """,
        {"id": entity_id},
    )
    if res.result_set:
        return int(res.result_set[0][0])
    return 0


def delete_campaign_graph(g: Any, campaign_id: str) -> dict[str, int]:
    """Drop every node + edge that belongs to this campaign.

    All entities (and their sections) tagged with `campaign_id` are
    DETACH DELETEd, which also removes any edges touching them. Returns
    counts so the caller can report them.
    """
    deleted: dict[str, int] = {"sections": 0, "entities": 0}

    sec = g.query(
        """
        MATCH (e:Entity {campaign_id: $campaign})-[:HAS_SECTION]->(s:Section)
        DETACH DELETE s
        RETURN count(s) AS n
        """,
        {"campaign": campaign_id},
    )
    if sec.result_set:
        deleted["sections"] = int(sec.result_set[0][0])

    ent = g.query(
        """
        MATCH (e:Entity {campaign_id: $campaign})
        DETACH DELETE e
        RETURN count(e) AS n
        """,
        {"campaign": campaign_id},
    )
    if ent.result_set:
        deleted["entities"] = int(ent.result_set[0][0])

    return deleted


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def neighborhood(g: Any, entity_id: str) -> dict[str, Any]:
    """Return entity + its outgoing edges + incoming edges + sections."""
    res = g.query(
        """
        MATCH (e:Entity {id: $id})
        OPTIONAL MATCH (e)-[r_out]->(t:Entity)
        OPTIONAL MATCH (s:Entity)-[r_in]->(e)
        OPTIONAL MATCH (e)-[:HAS_SECTION]->(sec:Section)
        RETURN e,
               collect(DISTINCT {type: type(r_out), target: t.id, target_title: t.title}) AS outgoing,
               collect(DISTINCT {type: type(r_in), source: s.id, source_title: s.title}) AS incoming,
               collect(DISTINCT {id: sec.id, heading: sec.heading}) AS sections
        """,
        {"id": entity_id},
    )
    if not res.result_set:
        return {"found": False, "entity_id": entity_id}
    row = res.result_set[0]
    entity = _node_to_dict(row[0])
    if not entity:
        return {"found": False, "entity_id": entity_id}
    return {
        "found": True,
        "entity": entity,
        "outgoing": [r for r in row[1] if r and r.get("target")],
        "incoming": [r for r in row[2] if r and r.get("source")],
        "sections": [s for s in row[3] if s and s.get("id")],
    }


def find_entities(
    g: Any,
    *,
    query: str | None = None,
    type_filter: str | None = None,
    campaign_id: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Find entities by id/title substring or type."""
    where_clauses: list[str] = []
    params: dict[str, Any] = {"limit": limit}
    if query:
        where_clauses.append(
            "(toLower(e.title) CONTAINS toLower($q) OR toLower(e.id) CONTAINS toLower($q))"
        )
        params["q"] = query
    if type_filter:
        where_clauses.append("e.type = $type")
        params["type"] = type_filter
    if campaign_id:
        where_clauses.append("e.campaign_id = $campaign")
        params["campaign"] = campaign_id
    where = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    cypher = f"MATCH (e:Entity) {where} RETURN e ORDER BY e.title LIMIT $limit"
    res = g.query(cypher, params)
    return [_node_to_dict(row[0]) or {} for row in res.result_set]


def link_entities(
    g: Any,
    *,
    src_id: str,
    edge_type: str,
    dst_id: str,
    properties: dict[str, Any] | None = None,
) -> None:
    """Create (or merge) a typed edge between two entities."""
    if not _valid_edge_type(edge_type):
        raise ValueError(
            f"edge type must be UPPERCASE_SNAKE_CASE: {edge_type!r}"
        )
    properties = properties or {}
    cypher = f"""
        MERGE (a:Entity {{id: $src}})
          ON CREATE SET a.title = $src, a.status = 'shell'
        MERGE (b:Entity {{id: $dst}})
          ON CREATE SET b.title = $dst, b.status = 'shell'
        MERGE (a)-[r:{edge_type}]->(b)
        SET r += $props
        RETURN r
    """
    g.query(cypher, {"src": src_id, "dst": dst_id, "props": properties})


def unlink_entities(g: Any, *, src_id: str, edge_type: str, dst_id: str) -> int:
    if not _valid_edge_type(edge_type):
        raise ValueError(f"invalid edge type: {edge_type!r}")
    res = g.query(
        f"""
        MATCH (:Entity {{id: $src}})-[r:{edge_type}]->(:Entity {{id: $dst}})
        DELETE r
        RETURN count(r) AS n
        """,
        {"src": src_id, "dst": dst_id},
    )
    if res.result_set:
        return int(res.result_set[0][0])
    return 0


def run_query(
    g: Any, cypher: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Run an arbitrary Cypher query (DM-only escape hatch).

    Returns a dict with `header` (column names) and `rows` (serialized cells).
    """
    res = g.query(cypher, params or {})
    rows: list[list[Any]] = []
    for row in res.result_set:
        rows.append([_serialize_value(v) for v in row])
    header = [str(h) for h in (res.header or [])] if hasattr(res, "header") else []
    return {"header": header, "rows": rows, "rowcount": len(rows)}


def graph_stats(g: Any) -> dict[str, Any]:
    """Useful at-a-glance stats."""
    counts: dict[str, Any] = {}
    res = g.query("MATCH (e:Entity) RETURN count(e)")
    counts["entities"] = int(res.result_set[0][0]) if res.result_set else 0
    res = g.query("MATCH (s:Section) RETURN count(s)")
    counts["sections"] = int(res.result_set[0][0]) if res.result_set else 0
    res = g.query("MATCH ()-[r]->() RETURN count(r)")
    counts["edges"] = int(res.result_set[0][0]) if res.result_set else 0
    res = g.query("MATCH ()-[r]->() RETURN type(r) AS t, count(r) AS n ORDER BY n DESC LIMIT 25")
    counts["edge_types"] = [{"type": str(row[0]), "count": int(row[1])} for row in res.result_set]
    res = g.query("MATCH (e:Entity) RETURN e.type AS t, count(e) AS n ORDER BY n DESC LIMIT 25")
    counts["entity_types"] = [{"type": str(row[0]), "count": int(row[1])} for row in res.result_set]
    return counts


# ---------------------------------------------------------------------------
# Markdown -> graph helpers
# ---------------------------------------------------------------------------


_FUTURE_RE = re.compile(r"\[future:([^\]]+)\]")
_LINK_RE = re.compile(r"\]\(([^)]+\.md)\)")  # markdown links to .md files


def extract_mentions(text: str) -> list[str]:
    """Pull mention ids from `[future:Name]` markers and markdown links to .md files.

    Each id is slugified (kebab-case ASCII).
    """
    raw: list[str] = []
    raw.extend(_FUTURE_RE.findall(text))
    for href in _LINK_RE.findall(text):
        # strip directory + extension
        stem = href.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if stem:
            raw.append(stem)
    return list(dict.fromkeys(_slugify(token) for token in raw if token))


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unnamed"


def _valid_edge_type(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][A-Z0-9_]*", name))


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _node_to_dict(node: Any) -> dict[str, Any] | None:
    if node is None:
        return None
    if hasattr(node, "properties"):
        return dict(node.properties)
    if isinstance(node, dict):
        return node
    return None


def _serialize_value(value: Any) -> Any:
    """Convert FalkorDB Node/Edge/Path objects into plain dicts for emit()."""
    if value is None:
        return None
    if hasattr(value, "properties"):
        kind = "node"
        if hasattr(value, "relation"):
            kind = "edge"
        out: dict[str, Any] = {"_kind": kind, **dict(value.properties)}
        if hasattr(value, "labels") and value.labels:
            out["_labels"] = list(value.labels)
        if hasattr(value, "relation") and value.relation:
            out["_relation"] = value.relation
        return out
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    return value
