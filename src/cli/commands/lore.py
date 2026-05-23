"""DB-backed lore reference commands."""

from __future__ import annotations

from pathlib import Path
import sys

import click

from ..campaign import active_campaign_id
from ..config import get_paths
from ..errors import GlassError, agent_instruction
from ..ids import slugify
from .. import lore_store
from ..lore_store import LoreEntrySpec
from ..role import current_role, require_dm
from ..yaml_io import emit


@click.group()
def lore() -> None:
    """Reference lore stored in FalkorDB, not campaign files."""


@lore.command("put")
@click.argument("lore_id")
@click.option("--title", default=None, help="Human-readable title.")
@click.option("--kind", default="reference", show_default=True)
@click.option(
    "--scope",
    type=click.Choice(["reference", "campaign"]),
    default="campaign",
    show_default=True,
    help="Reference corpus or current-campaign prose reference namespace.",
)
@click.option(
    "--visibility",
    type=click.Choice(["public", "dm"]),
    default="public",
    show_default=True,
)
@click.option("--source", default=None, help="Source/provenance label.")
@click.option("--tag", "tags", multiple=True, help="Repeatable search tag.")
@click.option("--body", default=None, help="Prose body. Use --body-stdin for long text.")
@click.option("--body-stdin", is_flag=True, help="Read the prose body from stdin.")
def lore_put(
    lore_id: str,
    title: str | None,
    kind: str,
    scope: str,
    visibility: str,
    source: str | None,
    tags: tuple[str, ...],
    body: str | None,
    body_stdin: bool,
) -> None:
    """Create or update a lore prose entry in FalkorDB.

    This does not create campaign files. If the entry becomes campaign reality,
    commit the usable portion with `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<entity-id>", "predicate": "<predicate>", "text": "<neutral fact>"}])`.
    """

    require_dm()
    body_text = sys.stdin.read() if body_stdin else body
    if not body_text or not body_text.strip():
        raise GlassError(
            agent_instruction(
                "lore body is empty",
                "Pass --body for short entries or --body-stdin for long prose.",
                "Do not create a markdown lore file as a workaround.",
            )
        )
    campaign_id = active_campaign_id()
    namespace = lore_store.namespace_for_scope(scope, campaign_id=campaign_id)
    spec = LoreEntrySpec(
        lore_id=lore_store.normalize_lore_id(lore_id),
        title=title or lore_id.replace("-", " ").title(),
        kind=kind,
        namespace=namespace,
        visibility=visibility,
        source=source,
        tags=tags,
        body=body_text,
    )
    emit(lore_store.upsert_lore_entry(campaign_id=campaign_id, spec=spec))


@lore.command("ingest")
@click.argument("source_path")
@click.option(
    "--scope",
    type=click.Choice(["reference", "campaign"]),
    default="reference",
    show_default=True,
)
@click.option("--kind", default="reference", show_default=True)
@click.option(
    "--visibility",
    type=click.Choice(["public", "dm"]),
    default="public",
    show_default=True,
)
@click.option("--tag", "tags", multiple=True, help="Repeatable search tag.")
@click.option("--limit", type=int, default=200, show_default=True)
def lore_ingest(
    source_path: str,
    scope: str,
    kind: str,
    visibility: str,
    tags: tuple[str, ...],
    limit: int,
) -> None:
    """Load markdown prose into the DB reference store.

    This is an operator/DM ingestion path. It reads existing reference files and
    writes FalkorDB lore entries; it never copies them into the campaign.
    """

    require_dm()
    paths = get_paths()
    source = Path(source_path).expanduser()
    if not source.is_absolute():
        base = paths.lore if paths.lore is not None else Path.cwd()
        source = (base / source).resolve()
    if not source.exists():
        raise GlassError(f"lore source does not exist: {source}")

    files = [source] if source.is_file() else sorted(source.rglob("*.md"))
    if len(files) > limit:
        raise GlassError(
            f"lore ingest matched {len(files)} files, above --limit {limit}"
        )

    campaign_id = active_campaign_id()
    namespace = lore_store.namespace_for_scope(scope, campaign_id=campaign_id)
    stored = []
    for path in files:
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        body = path.read_text(encoding="utf-8")
        rel = _safe_relative(path, source if source.is_dir() else source.parent)
        lore_id = slugify(str(rel.with_suffix("")))
        title = _markdown_title(body) or path.stem.replace("-", " ").title()
        result = lore_store.upsert_lore_entry(
            campaign_id=campaign_id,
            spec=LoreEntrySpec(
                lore_id=lore_id,
                title=title,
                body=body,
                kind=kind,
                namespace=namespace,
                visibility=visibility,
                source=str(path),
                tags=tags,
            ),
        )
        stored.append(result)

    emit(
        {
            "campaign_id": campaign_id,
            "scope": scope,
            "namespace": namespace,
            "source": str(source),
            "stored": stored,
            "count": len(stored),
        }
    )


@lore.command("search")
@click.argument("query")
@click.option("--limit", type=int, default=20, show_default=True)
def lore_search(query: str, limit: int) -> None:
    """Search DB-backed reference lore.

    Results are source material, not continuity. Promote any load-bearing
    detail with `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<entity-id>", "predicate": "<predicate>", "text": "<neutral fact>"}])`.
    """

    emit(lore_search_service(query=query, limit=limit))


def lore_search_service(*, query: str, limit: int = 20) -> dict:
    """Search DB-backed reference lore visible to the current role."""

    role = current_role()
    return lore_store.search_lore_entries(
        campaign_id=active_campaign_id(),
        query=query,
        limit=limit,
        include_dm=role.kind in {"dm", "operator"},
    )


@lore.command("read")
@click.argument("lore_id")
def lore_read(lore_id: str) -> None:
    """Read one DB-backed lore entry."""

    emit(lore_read_service(lore_id=lore_id))


def lore_read_service(*, lore_id: str) -> dict:
    """Read one DB-backed lore entry visible to the current role."""

    role = current_role()
    return lore_store.read_lore_entry(
        campaign_id=active_campaign_id(),
        lore_id=lore_id,
        include_dm=role.kind in {"dm", "operator"},
    )


@lore.command("list")
@click.option("--limit", type=int, default=50, show_default=True)
def lore_list(limit: int) -> None:
    """List DB-backed lore entries available to this campaign."""

    emit(lore_list_service(limit=limit))


def lore_list_service(*, limit: int = 50) -> dict:
    """List DB-backed lore entries visible to the current role."""

    role = current_role()
    return lore_store.list_lore_entries(
        campaign_id=active_campaign_id(),
        limit=limit,
        include_dm=role.kind in {"dm", "operator"},
    )


def _markdown_title(body: str) -> str | None:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or None
    return None


def _safe_relative(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return Path(path.name)
