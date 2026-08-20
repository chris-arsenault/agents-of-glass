"""Embedded neutral continuity facts.

This module is deliberately not a markdown mirror. It owns the tabular shape used
for agent-readable continuity: current neutral facts with loose predicates,
source turn metadata, and scoped retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
import re
from typing import Any

from . import db as _db
from .config import load_config
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
    """Persist a current fact in the embedded store and return its identity."""

    scoped_spec = spec if spec.scope_id else replace(
        spec,
        scope_id=default_fact_scope_for_mode(mode, scene_id),
    )
    config = _db.load_storage_config(load_config())
    with _db.connect(config) as conn:
        stored = _set_fact_storage(
            conn,
            campaign_id=campaign_id,
            spec=scoped_spec,
            actor=actor,
            turn_id=turn_id,
            mode=mode,
            scene_id=scene_id,
        )
        conn.commit()
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
    """Persist many facts in one embedded transaction."""

    if not specs:
        return {"status": "skipped", "facts": [], "count": 0}
    scoped_specs = _scope_fact_specs(specs, mode=mode, scene_id=scene_id)
    config = _db.load_storage_config(load_config())
    facts: list[dict[str, Any]] = []
    with _db.connect(config) as conn:
        for spec in scoped_specs:
            facts.append(
                _set_fact_storage(
                    conn,
                    campaign_id=campaign_id,
                    spec=spec,
                    actor=actor,
                    turn_id=turn_id,
                    mode=mode,
                    scene_id=scene_id,
                )
            )
        conn.commit()
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
    audience = normalize_fact_audience(audience, allow_all=True)
    config = _db.load_storage_config(load_config())
    with _db.connect(config) as conn:
        rows = _fact_pack_storage(
            conn,
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
    facts = list(pack.get("facts") or [])
    audience = str(pack.get("audience") or DEFAULT_AUDIENCE)
    lines = [
        "## Continuity Facts"
        if audience == DEFAULT_AUDIENCE
        else f"## Continuity Facts ({audience})",
        "",
        "This is the continuity source for agent decisions. Prose files are viewer/archive material; do not use them as the state layer.",
        "",
    ]
    if not facts:
        lines.append("_No active facts matched this turn scope yet._")
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


def _set_fact_storage(
    conn: Any,
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
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO facts (
                uid, id, campaign_id, scope_id, subject_id, predicate,
                object_id, claim_text, visibility, status, salience,
                salience_rank, audience, source_turn_id, actor, mode, scene_id,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s,
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT(uid) DO UPDATE SET
                object_id = excluded.object_id,
                claim_text = excluded.claim_text,
                visibility = excluded.visibility,
                status = 'active',
                salience = excluded.salience,
                salience_rank = excluded.salience_rank,
                audience = excluded.audience,
                source_turn_id = excluded.source_turn_id,
                actor = excluded.actor,
                mode = excluded.mode,
                scene_id = excluded.scene_id,
                updated_at = excluded.updated_at
            """,
            (
                fact_uid,
                fact_id,
                campaign_id,
                scope_id,
                spec.subject_id,
                spec.predicate,
                spec.object_id,
                spec.text,
                spec.visibility,
                salience,
                salience_rank,
                spec.audience,
                turn_id,
                actor,
                mode,
                scene_id,
                now,
                now,
            ),
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


def _fact_pack_storage(
    conn: Any,
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
    scopes = list(dict.fromkeys(scopes))
    visibilities = _visible_fact_levels(visibility)
    scope_params = ", ".join("%s" for _scope in scopes)
    visibility_params = ", ".join("%s" for _visibility in visibilities)
    query_limit = limit if audience == "all" else max(limit * 5, limit + 50)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT scope_id, subject_id, predicate, object_id, claim_text,
                   source_turn_id, salience, salience_rank, updated_at, audience
            FROM facts
            WHERE campaign_id = %s
              AND status = 'active'
              AND visibility IN ({visibility_params})
              AND (scope_id IN ({scope_params}) OR scene_id = %s OR actor = %s)
            ORDER BY scope_id, salience_rank DESC, updated_at DESC
            LIMIT %s
            """,
            [campaign_id, *visibilities, *scopes, scene_id, actor, query_limit],
        )
        rows = cur.fetchall()
    facts: list[dict[str, Any]] = []
    for row in rows:
        row_audience = normalize_fact_audience(row[9], allow_missing=True)
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
