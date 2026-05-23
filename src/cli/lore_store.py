"""FalkorDB-backed reference lore.

Reference lore is prose source material. It is not campaign continuity. Agents
may use injected excerpts for color or specificity, but anything that becomes
true in the campaign must be committed as neutral facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re
from typing import Any

from .config import load_config
from .errors import GlassError, agent_instruction
from .ids import slugify


REFERENCE_NAMESPACE = "reference"
DEFAULT_VISIBILITY = "public"
DEFAULT_KIND = "reference"
_MAX_EXCERPT_CHARS = 420
_STOP_TERMS = {
    "about",
    "active",
    "after",
    "campaign",
    "character",
    "current",
    "during",
    "first",
    "graph",
    "needs",
    "party",
    "scene",
    "status",
    "their",
    "there",
    "these",
    "turn",
    "visible",
    "with",
}


@dataclass(frozen=True)
class LoreEntrySpec:
    lore_id: str
    title: str
    body: str
    kind: str = DEFAULT_KIND
    namespace: str = REFERENCE_NAMESPACE
    visibility: str = DEFAULT_VISIBILITY
    source: str | None = None
    tags: tuple[str, ...] = ()


def normalize_lore_id(raw: str) -> str:
    lore_id = slugify(raw)
    if not lore_id:
        raise ValueError("lore id is empty")
    return lore_id


def namespace_for_scope(scope: str, *, campaign_id: str) -> str:
    normalized = (scope or REFERENCE_NAMESPACE).strip().lower()
    if normalized == "reference":
        return REFERENCE_NAMESPACE
    if normalized == "campaign":
        return campaign_id
    raise ValueError("lore scope must be `reference` or `campaign`")


def upsert_lore_entry(*, campaign_id: str, spec: LoreEntrySpec) -> dict[str, Any]:
    """Persist prose reference material in FalkorDB."""

    from . import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(_unavailable_message(config.describe()))
    with _graph.connect(config) as g:
        stored = _upsert_lore_entry_graph(g, campaign_id=campaign_id, spec=spec)
    return {"target": config.describe(), **stored}


def search_lore_entries(
    *,
    campaign_id: str,
    query: str,
    limit: int = 20,
    include_dm: bool = False,
) -> dict[str, Any]:
    """Search reference/campaign lore prose in FalkorDB."""

    from . import graph as _graph

    terms = _query_terms(query)
    if not terms:
        raise GlassError("lore search query is empty")
    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(_unavailable_message(config.describe()))
    with _graph.connect(config) as g:
        rows = _search_lore_graph(
            g,
            campaign_id=campaign_id,
            terms=terms,
            limit=limit,
            include_dm=include_dm,
        )
    return {
        "status": "ok",
        "target": config.describe(),
        "query": query,
        "terms": terms,
        "entries": rows,
        "count": len(rows),
    }


def read_lore_entry(
    *,
    campaign_id: str,
    lore_id: str,
    include_dm: bool = False,
) -> dict[str, Any]:
    """Read one lore entry from FalkorDB."""

    from . import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(_unavailable_message(config.describe()))
    with _graph.connect(config) as g:
        row = _read_lore_graph(
            g,
            campaign_id=campaign_id,
            lore_id=normalize_lore_id(lore_id),
            include_dm=include_dm,
        )
    if row is None:
        raise GlassError(f"lore entry not found: {lore_id}")
    return {"status": "ok", "target": config.describe(), "entry": row}


def list_lore_entries(
    *,
    campaign_id: str,
    limit: int = 50,
    include_dm: bool = False,
) -> dict[str, Any]:
    """List DB-backed lore entries available to this campaign."""

    from . import graph as _graph

    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(_unavailable_message(config.describe()))
    with _graph.connect(config) as g:
        rows = _list_lore_graph(
            g,
            campaign_id=campaign_id,
            limit=limit,
            include_dm=include_dm,
        )
    return {"status": "ok", "target": config.describe(), "entries": rows, "count": len(rows)}


def reference_lore_pack(
    *,
    campaign_id: str,
    fact_pack: dict[str, Any],
    role: str,
    limit: int = 6,
) -> dict[str, Any]:
    """Return deterministic reference lore matches for the injected prompt.

    The selector uses current fact subjects, objects, and concrete words from
    fact text. Agents do not choose the initial lore search.
    """

    from . import graph as _graph

    terms = _terms_from_fact_pack(fact_pack)
    if not terms:
        return {"status": "empty", "entries": [], "count": 0, "terms": []}
    try:
        config = _graph.load_falkor_config(load_config())
    except Exception as exc:
        return {
            "status": "unavailable",
            "target": f"unconfigured FalkorDB ({exc})",
            "entries": [],
            "count": 0,
            "terms": terms,
        }
    if not _graph.is_available(config):
        return {
            "status": "unavailable",
            "target": config.describe(),
            "entries": [],
            "count": 0,
            "terms": terms,
        }
    with _graph.connect(config) as g:
        rows = _search_lore_graph(
            g,
            campaign_id=campaign_id,
            terms=terms,
            limit=limit,
            include_dm=role == "dm",
        )
    return {
        "status": "ok",
        "target": config.describe(),
        "entries": rows,
        "count": len(rows),
        "terms": terms,
    }


def render_reference_lore_markdown(pack: dict[str, Any]) -> str:
    """Render prompt-safe reference lore.

    Unavailable or empty packs render nothing. Missing reference lore should not
    push agents toward filesystem fallback.
    """

    entries = list(pack.get("entries") or [])
    if not entries:
        return ""
    lines = [
        "## Reference Lore",
        "",
        "These excerpts are source prose, not campaign continuity. Use them for",
        "specificity only. If an excerpt becomes true or visible in this",
        "campaign, commit the usable portion as a neutral fact.",
        "",
    ]
    for entry in entries:
        title = str(entry.get("title") or entry.get("id") or "untitled").strip()
        lore_id = str(entry.get("id") or "").strip()
        kind = str(entry.get("kind") or DEFAULT_KIND).strip()
        source = str(entry.get("source") or "").strip()
        header = f"- `{lore_id}` ({kind})" if lore_id else f"- {title} ({kind})"
        if title and lore_id and title != lore_id:
            header += f": {title}"
        if source:
            header += f" [{source}]"
        lines.append(header)
        excerpt = str(entry.get("excerpt") or "").strip()
        if excerpt:
            lines.append(f"  {excerpt}")
    lines.append("")
    return "\n".join(lines)


def _upsert_lore_entry_graph(
    g: Any,
    *,
    campaign_id: str,
    spec: LoreEntrySpec,
) -> dict[str, Any]:
    now = _now_iso()
    lore_id = normalize_lore_id(spec.lore_id)
    namespace = spec.namespace or REFERENCE_NAMESPACE
    uid = f"lore:{namespace}:{lore_id}"
    tags = [tag.strip() for tag in spec.tags if tag.strip()]
    body = spec.body.strip()
    if not body:
        raise ValueError("lore body is empty")
    props = {
        "uid": uid,
        "id": lore_id,
        "campaign_id": campaign_id if namespace == campaign_id else None,
        "namespace": namespace,
        "title": spec.title.strip() or lore_id,
        "kind": spec.kind.strip() or DEFAULT_KIND,
        "visibility": spec.visibility.strip() or DEFAULT_VISIBILITY,
        "source": spec.source,
        "tags": tags,
        "tags_text": " ".join(tags),
        "body_text": body,
        "updated_at": now,
    }
    g.query(
        """
        MERGE (entry:LoreEntry {uid: $uid})
          ON CREATE SET entry.created_at = $now
        SET entry += $props
        RETURN entry.uid
        """,
        {"uid": uid, "now": now, "props": props},
    )
    return {
        "uid": uid,
        "id": lore_id,
        "namespace": namespace,
        "title": props["title"],
        "kind": props["kind"],
        "visibility": props["visibility"],
        "source": spec.source,
    }


def _search_lore_graph(
    g: Any,
    *,
    campaign_id: str,
    terms: list[str],
    limit: int,
    include_dm: bool,
) -> list[dict[str, Any]]:
    namespaces = [REFERENCE_NAMESPACE, campaign_id]
    visibilities = ["public", "dm"] if include_dm else ["public"]
    res = g.query(
        """
        MATCH (entry:LoreEntry)
        WHERE entry.namespace IN $namespaces
          AND entry.visibility IN $visibilities
          AND any(term IN $terms WHERE
            toLower(coalesce(entry.id, '')) CONTAINS term OR
            toLower(coalesce(entry.title, '')) CONTAINS term OR
            toLower(coalesce(entry.kind, '')) CONTAINS term OR
            toLower(coalesce(entry.tags_text, '')) CONTAINS term OR
            toLower(coalesce(entry.source, '')) CONTAINS term OR
            toLower(coalesce(entry.body_text, '')) CONTAINS term)
        RETURN entry.id,
               entry.title,
               entry.kind,
               entry.namespace,
               entry.visibility,
               entry.source,
               entry.body_text,
               entry.updated_at
        ORDER BY entry.namespace DESC, entry.updated_at DESC, entry.title
        LIMIT $limit
        """,
        {
            "namespaces": namespaces,
            "visibilities": visibilities,
            "terms": terms,
            "limit": limit,
        },
    )
    return [_row_to_lore_entry(row, terms=terms, include_body=False) for row in res.result_set]


def _read_lore_graph(
    g: Any,
    *,
    campaign_id: str,
    lore_id: str,
    include_dm: bool,
) -> dict[str, Any] | None:
    namespaces = [REFERENCE_NAMESPACE, campaign_id]
    visibilities = ["public", "dm"] if include_dm else ["public"]
    res = g.query(
        """
        MATCH (entry:LoreEntry {id: $id})
        WHERE entry.namespace IN $namespaces
          AND entry.visibility IN $visibilities
        RETURN entry.id,
               entry.title,
               entry.kind,
               entry.namespace,
               entry.visibility,
               entry.source,
               entry.body_text,
               entry.updated_at
        ORDER BY entry.namespace DESC
        LIMIT 1
        """,
        {"id": lore_id, "namespaces": namespaces, "visibilities": visibilities},
    )
    if not res.result_set:
        return None
    return _row_to_lore_entry(res.result_set[0], terms=[], include_body=True)


def _list_lore_graph(
    g: Any,
    *,
    campaign_id: str,
    limit: int,
    include_dm: bool,
) -> list[dict[str, Any]]:
    namespaces = [REFERENCE_NAMESPACE, campaign_id]
    visibilities = ["public", "dm"] if include_dm else ["public"]
    res = g.query(
        """
        MATCH (entry:LoreEntry)
        WHERE entry.namespace IN $namespaces
          AND entry.visibility IN $visibilities
        RETURN entry.id,
               entry.title,
               entry.kind,
               entry.namespace,
               entry.visibility,
               entry.source,
               entry.body_text,
               entry.updated_at
        ORDER BY entry.namespace DESC, entry.title
        LIMIT $limit
        """,
        {"namespaces": namespaces, "visibilities": visibilities, "limit": limit},
    )
    return [_row_to_lore_entry(row, terms=[], include_body=False) for row in res.result_set]


def _row_to_lore_entry(
    row: list[Any] | tuple[Any, ...],
    *,
    terms: list[str],
    include_body: bool,
) -> dict[str, Any]:
    body = str(row[6] or "")
    entry = {
        "id": row[0],
        "title": row[1],
        "kind": row[2],
        "namespace": row[3],
        "visibility": row[4],
        "source": row[5],
        "updated_at": row[7],
        "excerpt": _excerpt(body, terms=terms),
    }
    if include_body:
        entry["body"] = body
    return entry


def _terms_from_fact_pack(pack: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for fact in list(pack.get("facts") or []):
        if not isinstance(fact, dict):
            continue
        for key in ("subject_id", "object_id"):
            terms.extend(_query_terms(str(fact.get(key) or "")))
        text = str(fact.get("text") or "")
        terms.extend(_query_terms(text, max_terms=8))
    return _dedupe_terms(terms, limit=32)


def _query_terms(raw: str, *, max_terms: int = 16) -> list[str]:
    normalized = raw.replace("_", " ").replace("-", " ").lower()
    candidates = re.findall(r"[a-z0-9][a-z0-9']{2,}", normalized)
    return _dedupe_terms(candidates, limit=max_terms)


def _dedupe_terms(terms: list[str], *, limit: int) -> list[str]:
    result: list[str] = []
    for term in terms:
        term = term.strip().lower()
        if len(term) < 3 or term in _STOP_TERMS or term in result:
            continue
        result.append(term)
        if len(result) >= limit:
            break
    return result


def _excerpt(body: str, *, terms: list[str]) -> str:
    compact = re.sub(r"\s+", " ", body).strip()
    if len(compact) <= _MAX_EXCERPT_CHARS:
        return compact
    lower = compact.lower()
    index = -1
    for term in terms:
        index = lower.find(term)
        if index >= 0:
            break
    if index < 0:
        return compact[: _MAX_EXCERPT_CHARS - 1].rstrip() + "..."
    start = max(0, index - 120)
    end = min(len(compact), start + _MAX_EXCERPT_CHARS)
    prefix = "..." if start else ""
    suffix = "..." if end < len(compact) else ""
    return prefix + compact[start:end].strip() + suffix


def _unavailable_message(target: str) -> str:
    return agent_instruction(
        f"FalkorDB is unavailable at {target}",
        "Reference lore is stored in FalkorDB, not campaign files.",
        "Fix FalkorDB configuration or continue from injected facts without lore lookup.",
    )


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
