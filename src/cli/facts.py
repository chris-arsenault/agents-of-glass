"""FalkorDB-backed neutral continuity facts.

This module is deliberately not a markdown mirror. It owns the graph shape used
for agent-readable continuity: current neutral facts with loose predicates,
source turn metadata, and scoped retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
import re
from typing import Any

from .config import load_config
from .errors import GlassError, agent_instruction
from .ids import slugify


DEFAULT_VISIBILITY = "public"
DEFAULT_SALIENCE = "medium"
DEFAULT_AUDIENCE = "continuity"
FACT_AUDIENCES = ("continuity", "profile", "meta")
FACT_PACK_AUDIENCES = (*FACT_AUDIENCES, "all")
FACT_IMPORTANCE = ("high", "medium", "low", "minor")
LOW_FACT_IMPORTANCE = frozenset({"low", "minor"})

_PROFILE_PREDICATES = frozenset(
    {
        "social-texture",
        "table-presence",
        "voice",
        "tic",
        "mannerism",
        "habit",
        "preference",
        "positive-trait",
        "non-work-want",
        "opening-social-action",
    }
)
_META_TEXT_MARKERS = (
    "not the mission engine",
    "future agents",
    "agent-readable",
    "fact graph",
    "narrative output",
    "prose guidance",
    "writing rule",
    "prompt guidance",
    "prompt instruction",
    "runtime contract",
    "methodology",
    "anti-drift",
)


@dataclass(frozen=True)
class FactSpec:
    subject_id: str
    predicate: str
    text: str
    audience: str
    object_id: str | None = None
    scope_id: str | None = None
    visibility: str = DEFAULT_VISIBILITY
    salience: str = DEFAULT_SALIENCE

    def __post_init__(self) -> None:
        object.__setattr__(self, "audience", normalize_fact_audience(self.audience))
        object.__setattr__(
            self,
            "salience",
            normalize_fact_importance(self.salience, allow_missing=True),
        )


def parse_fact_spec(
    raw: str,
    *,
    default_scope_id: str | None = None,
    visibility: str = DEFAULT_VISIBILITY,
    salience: str = DEFAULT_SALIENCE,
    audience: str,
) -> FactSpec:
    """Parse one agent-facing fact string.

    Accepted forms:

    - ``mox.status = Mox is pinned in the second pipe.``
    - ``mox.status: Mox is pinned in the second pipe.``
    - ``mera.trusts -> mox = Mera trusts Mox after plain speech.``
    - ``mox status = Mox is pinned in the second pipe.``
    """

    if not raw or not raw.strip():
        raise ValueError("fact is empty")
    match = re.match(r"^\s*(?P<lhs>[^:=]+?)\s*(?:=|:)\s*(?P<text>.+?)\s*$", raw)
    if not match:
        raise ValueError(
            "fact must look like `subject.predicate = neutral text` "
            "or `subject.predicate -> object = neutral text`"
        )
    lhs = match.group("lhs").strip()
    text = match.group("text").strip()
    if not text:
        raise ValueError("fact text is empty")

    object_id: str | None = None
    if "->" in lhs:
        lhs, object_part = lhs.split("->", 1)
        object_id = _normalize_entity_id(object_part)

    lhs = lhs.strip()
    subject_id: str
    predicate: str
    if "." in lhs and " " not in lhs:
        subject_part, predicate_part = lhs.rsplit(".", 1)
        subject_id = _normalize_entity_id(subject_part)
        predicate = _normalize_predicate(predicate_part)
    else:
        parts = [part for part in re.split(r"\s+", lhs) if part]
        if len(parts) < 2:
            raise ValueError("fact needs both a subject and predicate")
        subject_id = _normalize_entity_id(" ".join(parts[:-1]))
        predicate = _normalize_predicate(parts[-1])

    if not subject_id:
        raise ValueError("fact subject is empty")
    if not predicate:
        raise ValueError("fact predicate is empty")

    return FactSpec(
        subject_id=subject_id,
        predicate=predicate,
        object_id=object_id,
        text=text,
        audience=normalize_fact_audience(audience),
        scope_id=_normalize_scope_id(default_scope_id),
        visibility=visibility,
        salience=normalize_fact_importance(salience, allow_missing=True),
    )


def normalize_fact_audience(
    value: str | None,
    *,
    allow_all: bool = False,
    allow_missing: bool = False,
) -> str:
    text = (value or "").strip().lower()
    if not text:
        if allow_missing:
            return DEFAULT_AUDIENCE
        raise ValueError("fact audience is required")
    if allow_all and text == "all":
        return "all"
    if text in FACT_AUDIENCES:
        return text
    options = [*FACT_AUDIENCES]
    if allow_all:
        options.append("all")
    raise ValueError(f"fact audience must be one of {', '.join(options)}")


def normalize_fact_importance(value: str | None, *, allow_missing: bool = False) -> str:
    text = (value or "").strip().lower()
    if not text:
        if allow_missing:
            return DEFAULT_SALIENCE
        raise ValueError("fact importance is required")
    if text == "normal":
        return "medium"
    if text in FACT_IMPORTANCE:
        return text
    raise ValueError(f"fact importance must be one of {', '.join(FACT_IMPORTANCE)}")


def infer_fact_audience(
    *,
    predicate: str | None,
    text: str | None,
    explicit: str | None = None,
) -> str:
    if explicit is not None:
        return normalize_fact_audience(explicit)

    normalized_predicate = _normalize_predicate(predicate)
    normalized_text = re.sub(r"\s+", " ", (text or "").strip().lower())
    if any(marker in normalized_text for marker in _META_TEXT_MARKERS):
        return "meta"
    if normalized_predicate in _PROFILE_PREDICATES:
        return "profile"
    return DEFAULT_AUDIENCE


def default_fact_scope_for_mode(mode: str | None, scene_id: str | None) -> str:
    mode_name = str(mode or "").strip()
    active_scene = str(scene_id or "").strip()
    scene_scoped_modes = {"scene-prep", "scene-play", "action"}
    if mode_name in scene_scoped_modes and active_scene:
        return active_scene
    return "campaign"


def _scope_fact_specs(
    specs: list[FactSpec] | tuple[FactSpec, ...],
    *,
    mode: str | None,
    scene_id: str | None,
) -> list[FactSpec]:
    default_scope = default_fact_scope_for_mode(mode, scene_id)
    return [
        spec if spec.scope_id else replace(spec, scope_id=default_scope)
        for spec in specs
    ]


def set_fact(
    *,
    campaign_id: str,
    spec: FactSpec,
    actor: str | None = None,
    turn_id: str | None = None,
    mode: str | None = None,
    scene_id: str | None = None,
) -> dict[str, Any]:
    """Persist a current fact in FalkorDB and return the stored identity."""

    from . import graph as _graph

    scoped_spec = spec if spec.scope_id else replace(
        spec,
        scope_id=default_fact_scope_for_mode(mode, scene_id),
    )
    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        raise GlassError(_graph_unavailable_message(config.describe()))
    with _graph.connect(config) as g:
        stored = _set_fact_graph(
            g,
            campaign_id=campaign_id,
            spec=scoped_spec,
            actor=actor,
            turn_id=turn_id,
            mode=mode,
            scene_id=scene_id,
        )
    return {"target": config.describe(), **stored}


def set_fact_specs(
    *,
    campaign_id: str,
    specs: list[FactSpec],
    actor: str | None = None,
    turn_id: str | None = None,
    mode: str | None = None,
    scene_id: str | None = None,
    require_available: bool = True,
) -> dict[str, Any]:
    """Persist many facts with one FalkorDB connection."""

    if not specs:
        return {"status": "skipped", "facts": [], "count": 0}
    from . import graph as _graph

    scoped_specs = _scope_fact_specs(specs, mode=mode, scene_id=scene_id)
    config = _graph.load_falkor_config(load_config())
    if not _graph.is_available(config):
        if not require_available:
            return {
                "status": "unavailable",
                "target": config.describe(),
                "facts": [],
                "count": 0,
            }
        raise GlassError(_graph_unavailable_message(config.describe()))
    facts: list[dict[str, Any]] = []
    with _graph.connect(config) as g:
        for spec in scoped_specs:
            facts.append(
                _set_fact_graph(
                    g,
                    campaign_id=campaign_id,
                    spec=spec,
                    actor=actor,
                    turn_id=turn_id,
                    mode=mode,
                    scene_id=scene_id,
                )
            )
    return {"status": "stored", "target": config.describe(), "facts": facts, "count": len(facts)}


def fact_pack(
    *,
    campaign_id: str,
    audience: str,
    scene_id: str | None = None,
    actor: str | None = None,
    visibility: str = DEFAULT_VISIBILITY,
    limit: int = 80,
) -> dict[str, Any]:
    from . import graph as _graph

    audience = normalize_fact_audience(audience, allow_all=True)
    try:
        config = _graph.load_falkor_config(load_config())
    except Exception as exc:
        return {
            "status": "unavailable",
            "target": f"unconfigured FalkorDB ({exc})",
            "audience": audience,
            "facts": [],
            "count": 0,
        }
    if not _graph.is_available(config):
        return {
            "status": "unavailable",
            "target": config.describe(),
            "audience": audience,
            "facts": [],
            "count": 0,
        }
    with _graph.connect(config) as g:
        rows = _fact_pack_graph(
            g,
            campaign_id=campaign_id,
            scene_id=scene_id,
            actor=actor,
            visibility=visibility,
            audience=audience,
            limit=limit,
        )
    return {
        "status": "ok",
        "target": config.describe(),
        "audience": audience,
        "facts": rows,
        "count": len(rows),
    }


def render_fact_pack_markdown(pack: dict[str, Any]) -> str:
    status = str(pack.get("status") or "")
    if status == "unavailable":
        return (
            "## Fact Graph Continuity\n\n"
            f"FalkorDB is unavailable at `{pack.get('target')}`. Do not fall back "
            "to prose summaries as continuity; report the blocker in closeout if "
            "the turn needs prior state.\n\n"
        )
    facts = list(pack.get("facts") or [])
    audience = str(pack.get("audience") or DEFAULT_AUDIENCE)
    lines = [
        "## Fact Graph Continuity"
        if audience == DEFAULT_AUDIENCE
        else f"## Fact Graph ({audience})",
        "",
        "This is the continuity source for agent decisions. Prose files are viewer/archive material; do not use them as the state layer.",
        "",
    ]
    if not facts:
        lines.append("_No active graph facts matched this turn scope yet._")
        lines.append("")
        return "\n".join(lines)

    current_scope: str | None = None
    for fact in facts:
        scope = str(fact.get("scope_id") or "campaign")
        if scope != current_scope:
            if current_scope is not None:
                lines.append("")
            lines.append(f"### {scope}")
            current_scope = scope
        subject = fact.get("subject_id") or "unknown"
        predicate = fact.get("predicate") or "fact"
        obj = fact.get("object_id")
        target = f"{subject}.{predicate}"
        if obj:
            target = f"{target} -> {obj}"
        text = str(fact.get("text") or "").strip()
        source = str(fact.get("source_turn_id") or "").strip()
        source_suffix = f" [{source}]" if source else ""
        audience_suffix = ""
        if audience == "all":
            fact_audience = str(fact.get("audience") or DEFAULT_AUDIENCE)
            importance = str(fact.get("importance") or fact.get("salience") or DEFAULT_SALIENCE)
            audience_suffix = f" ({fact_audience}; {importance})"
        lines.append(f"- `{target}`{audience_suffix}: {text}{source_suffix}")
    lines.append("")
    return "\n".join(lines)


def _set_fact_graph(
    g: Any,
    *,
    campaign_id: str,
    spec: FactSpec,
    actor: str | None,
    turn_id: str | None,
    mode: str | None,
    scene_id: str | None,
) -> dict[str, Any]:
    now = _now_iso()
    scope_id = spec.scope_id or scene_id or "campaign"
    salience = normalize_fact_importance(spec.salience, allow_missing=True)
    salience_rank = _salience_rank(salience)
    fact_id = _fact_id(scope_id, spec.subject_id, spec.predicate, spec.object_id)
    fact_uid = f"{campaign_id}:fact:{fact_id}"
    subject_uid = f"{campaign_id}:entity:{spec.subject_id}"
    predicate_uid = f"{campaign_id}:predicate:{spec.predicate}"
    scope_uid = f"{campaign_id}:scope:{scope_id}"
    props = {
        "uid": fact_uid,
        "id": fact_id,
        "campaign_id": campaign_id,
        "subject_id": spec.subject_id,
        "predicate": spec.predicate,
        "object_id": spec.object_id,
        "claim_text": spec.text,
        "scope_id": scope_id,
        "visibility": spec.visibility,
        "status": "active",
        "salience": salience,
        "salience_rank": salience_rank,
        "audience": spec.audience,
        "source_turn_id": turn_id,
        "actor": actor,
        "mode": mode,
        "scene_id": scene_id,
        "updated_at": now,
    }
    g.query(
        """
        MERGE (subject:Entity {uid: $subject_uid})
          ON CREATE SET subject.id = $subject_id,
                        subject.title = $subject_id,
                        subject.type = 'fact-subject',
                        subject.campaign_id = $campaign_id,
                        subject.created_at = $now
        SET subject.updated_at = $now
        MERGE (predicate:Predicate {uid: $predicate_uid})
          ON CREATE SET predicate.id = $predicate,
                        predicate.campaign_id = $campaign_id,
                        predicate.created_at = $now
        SET predicate.updated_at = $now
        MERGE (scope:Scope {uid: $scope_uid})
          ON CREATE SET scope.id = $scope_id,
                        scope.campaign_id = $campaign_id,
                        scope.created_at = $now
        SET scope.updated_at = $now
        MERGE (fact:Fact {uid: $uid})
          ON CREATE SET fact.created_at = $now
        SET fact += $props
        MERGE (subject)-[:SUBJECT_OF]->(fact)
        MERGE (fact)-[:USES_PREDICATE]->(predicate)
        MERGE (fact)-[:IN_SCOPE]->(scope)
        """,
        {
            "uid": fact_uid,
            "subject_uid": subject_uid,
            "subject_id": spec.subject_id,
            "predicate_uid": predicate_uid,
            "predicate": spec.predicate,
            "scope_uid": scope_uid,
            "scope_id": scope_id,
            "campaign_id": campaign_id,
            "now": now,
            "props": props,
        },
    )
    g.query("MATCH (:Fact {uid: $uid})-[r:OBJECT]->() DELETE r", {"uid": fact_uid})
    if spec.object_id:
        object_uid = f"{campaign_id}:entity:{spec.object_id}"
        g.query(
            """
            MERGE (object:Entity {uid: $object_uid})
              ON CREATE SET object.id = $object_id,
                            object.title = $object_id,
                            object.type = 'fact-object',
                            object.campaign_id = $campaign_id,
                            object.created_at = $now
            SET object.updated_at = $now
            WITH object
            MATCH (fact:Fact {uid: $uid})
            MERGE (fact)-[:OBJECT]->(object)
            """,
            {
                "uid": fact_uid,
                "object_uid": object_uid,
                "object_id": spec.object_id,
                "campaign_id": campaign_id,
                "now": now,
            },
        )
    return {
        "id": fact_id,
        "uid": fact_uid,
        "subject_id": spec.subject_id,
        "predicate": spec.predicate,
        "object_id": spec.object_id,
        "scope_id": scope_id,
        "text": spec.text,
        "audience": spec.audience,
        "importance": salience,
        "salience": salience,
        "salience_rank": salience_rank,
    }


def _fact_pack_graph(
    g: Any,
    *,
    campaign_id: str,
    scene_id: str | None,
    actor: str | None,
    visibility: str,
    audience: str,
    limit: int,
) -> list[dict[str, Any]]:
    scopes = ["campaign", "party", "organization"]
    if scene_id:
        scopes.extend([scene_id, f"scene.{scene_id}"])
    if actor:
        scopes.extend([actor, f"character.{actor}", f"player.{actor}"])
    query_limit = limit if audience == "all" else max(limit * 5, limit + 50)
    res = g.query(
        """
        MATCH (fact:Fact {campaign_id: $campaign_id, status: 'active'})
        WHERE fact.visibility IN $visibilities
          AND (fact.scope_id IN $scopes OR fact.scene_id = $scene_id OR fact.actor = $actor)
        RETURN fact.scope_id,
               fact.subject_id,
               fact.predicate,
               fact.object_id,
               fact.claim_text,
               fact.source_turn_id,
               fact.salience,
               fact.salience_rank,
               fact.updated_at,
               fact.audience
        ORDER BY fact.scope_id, fact.salience_rank DESC, fact.updated_at DESC
        LIMIT $limit
        """,
        {
            "campaign_id": campaign_id,
            "visibilities": _visible_fact_levels(visibility),
            "scopes": list(dict.fromkeys(scope for scope in scopes if scope)),
            "scene_id": scene_id,
            "actor": actor,
            "limit": query_limit,
        },
    )
    facts: list[dict[str, Any]] = []
    for row in res.result_set:
        try:
            row_audience = normalize_fact_audience(
                row[9] if len(row) > 9 else None,
                allow_missing=True,
            )
        except ValueError:
            row_audience = infer_fact_audience(predicate=row[2], text=row[4])
        if len(row) <= 9 or row[9] is None:
            row_audience = infer_fact_audience(predicate=row[2], text=row[4])
        row_importance = normalize_fact_importance(row[6], allow_missing=True)
        if audience != "all" and row_audience != audience:
            continue
        if row_importance in LOW_FACT_IMPORTANCE:
            continue
        facts.append(
            {
                "scope_id": row[0],
                "subject_id": row[1],
                "predicate": row[2],
                "object_id": row[3],
                "text": row[4],
                "source_turn_id": row[5],
                "importance": row_importance,
                "salience": row_importance,
                "salience_rank": _salience_rank(row_importance),
                "updated_at": row[8],
                "audience": row_audience,
            }
        )
        if len(facts) >= limit:
            break
    return facts


def _visible_fact_levels(visibility: str) -> list[str]:
    if visibility == "dm":
        return ["public", "dm"]
    if visibility == "private":
        return ["private"]
    return [DEFAULT_VISIBILITY]


def _fact_id(scope_id: str, subject_id: str, predicate: str, object_id: str | None) -> str:
    raw = f"{scope_id}.{subject_id}.{predicate}"
    if object_id:
        raw += f".{object_id}"
    return slugify(raw)


def _normalize_entity_id(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^a-z0-9_.-]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-.")
    return text


def _normalize_predicate(value: str | None) -> str:
    return slugify((value or "").strip()).replace("_", "-")


def _normalize_scope_id(value: str | None) -> str | None:
    if value is None:
        return None
    return _normalize_entity_id(value) or None


def _salience_rank(value: str | None) -> int:
    normalized = normalize_fact_importance(value, allow_missing=True)
    return {"minor": 0, "low": 1, "medium": 2, "high": 3}[normalized]


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _graph_unavailable_message(target: str) -> str:
    return agent_instruction(
        f"FalkorDB is not reachable at {target}",
        "Do not create a markdown fact file as a substitute.",
        'Use `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<entity-id>", "predicate": "<predicate>", "text": "<neutral fact>"}])` only when the graph is available, or report the graph blocker in closeout.',
    )
