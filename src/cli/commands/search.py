"""Search commands over the campaign corpus and markdown surface."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import click

from .. import db as _db
from ..campaign import active_campaign_id, pg_connection, resolve_active_campaign_workspace
from ..config import get_paths
from ..errors import GlassError
from ..ids import slugify
from ..role import current_role, require_dm
from ..state import append_audit, load_state
from ..yaml_io import command_params, emit


@click.group(name="search")
def search_group() -> None:
    """Search the campaign corpus and indexed prose."""


@search_group.command("text")
@click.argument("query")
@click.option("--type", "source_type", default=None, help="Filter by source type.")
@click.option("--limit", type=int, default=10, show_default=True)
@click.pass_context
def search_text(
    ctx: click.Context,
    query: str,
    source_type: str | None,
    limit: int,
) -> None:
    """Plain text / full-text search over indexed visible content."""
    _run_search(ctx, query, source_type=source_type, limit=limit, semantic=False)


@search_group.command("semantic")
@click.argument("query")
@click.option("--type", "source_type", default=None, help="Filter by source type.")
@click.option("--limit", type=int, default=10, show_default=True)
@click.pass_context
def search_semantic(
    ctx: click.Context,
    query: str,
    source_type: str | None,
    limit: int,
) -> None:
    """Semantic-search surface.

    The backing table has an embedding column, but embeddings are not populated
    until an embedding provider is configured. Until then this command uses the
    same bounded full-text index and labels the result as lexical fallback.
    """
    _run_search(ctx, query, source_type=source_type, limit=limit, semantic=True)


@search_group.command("reindex")
@click.option(
    "--turns-only",
    is_flag=True,
    help="Only refresh the public turn corpus chunks.",
)
@click.pass_context
def search_reindex(ctx: click.Context, turns_only: bool) -> None:
    """DM-only: rebuild the Postgres search index for this campaign."""
    require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    workspace = resolve_active_campaign_workspace()
    with pg_connection() as conn:
        deleted_turns = _db.search_chunks_delete_source(
            conn,
            campaign_id=campaign_id,
            source_type="turn",
        )
        turns = _db.turn_list(conn, campaign_id=campaign_id, limit=100000)
        for turn in turns:
            _db.search_chunk_upsert(
                conn,
                chunk_id=f"{campaign_id}:turn:{turn['turn_id']}",
                campaign_id=campaign_id,
                source_type="turn",
                source_id=str(turn["turn_id"]),
                visibility=turn.get("visibility") or "public",
                owner_actor=None,
                path=turn.get("source_path"),
                title=(
                    f"Turn {turn['turn_id']} - {turn['speaker']} "
                    f"({turn['mode']}, {turn['scene_id']})"
                ),
                body=turn.get("prose") or "",
                metadata={
                    "turn_id": turn["turn_id"],
                    "speaker": turn.get("speaker"),
                    "role": turn.get("role"),
                    "mode": turn.get("mode"),
                    "scene_id": turn.get("scene_id"),
                    "arc_id": turn.get("arc_id"),
                },
            )
        deleted_files = 0
        indexed_files = 0
        if not turns_only:
            deleted_files = _db.search_chunks_delete_source(
                conn,
                campaign_id=campaign_id,
                source_type="markdown",
            )
            for item in _iter_indexable_markdown(workspace.root):
                text = item["path"].read_text(encoding="utf-8")
                _db.search_chunk_upsert(
                    conn,
                    chunk_id=f"{campaign_id}:markdown:{item['rel']}",
                    campaign_id=campaign_id,
                    source_type="markdown",
                    source_id=str(item["rel"]),
                    visibility=item["visibility"],
                    owner_actor=item["owner_actor"],
                    path=str(item["rel"]),
                    title=_markdown_title(text, str(item["rel"])),
                    body=text,
                    metadata={"path": str(item["rel"])},
                )
                indexed_files += 1
        conn.commit()
    result = {
        "campaign_id": campaign_id,
        "turns_indexed": len(turns),
        "markdown_indexed": indexed_files,
        "deleted": {"turn": deleted_turns, "markdown": deleted_files},
        "semantic_embeddings": "not-populated",
    }
    append_audit(
        paths,
        state,
        ctx,
        "search.reindex",
        command_params(turns_only=turns_only),
        result,
    )
    emit(result)


def _run_search(
    ctx: click.Context,
    query: str,
    *,
    source_type: str | None,
    limit: int,
    semantic: bool,
) -> None:
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    with pg_connection() as conn:
        matches = _db.search_query(
            conn,
            campaign_id=campaign_id,
            query=query,
            role_kind=role.kind,
            actor=role.actor,
            source_type=source_type,
            limit=limit,
        )
    result = {
        "campaign_id": campaign_id,
        "query": query,
        "mode": "semantic" if semantic else "text",
        "semantic_embeddings": "lexical-fallback" if semantic else None,
        "matches": matches,
        "count": len(matches),
    }
    append_audit(
        paths,
        state,
        ctx,
        "search.semantic" if semantic else "search.text",
        command_params(query=query, type=source_type, limit=limit),
        result,
    )
    emit(result)


def _iter_indexable_markdown(root: Path) -> Iterable[dict[str, Any]]:
    if not root.exists():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if _skip_markdown(rel):
            continue
        visibility, owner = _visibility_for_path(rel)
        out.append(
            {
                "path": path,
                "rel": rel,
                "visibility": visibility,
                "owner_actor": owner,
            }
        )
    return out


def _skip_markdown(rel: Path) -> bool:
    parts = rel.parts
    if "turns" in parts:
        return True
    if rel.name in {"transcript.md", "audit.jsonl"}:
        return True
    if len(parts) >= 3 and parts[0] == "arcs" and rel.name in {"prep.md", "plan.md"}:
        return True
    return False


def _visibility_for_path(rel: Path) -> tuple[str, str | None]:
    parts = rel.parts
    if not parts:
        return "public", None
    if parts[0] == "dm":
        return "dm", None
    if parts[0] == "players" and len(parts) >= 2:
        player = parts[1]
        if len(parts) >= 3 and parts[2] == "public":
            return "public", None
        return "private", player
    return "public", None


def _markdown_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return slugify(Path(fallback).stem).replace("-", " ").title()
