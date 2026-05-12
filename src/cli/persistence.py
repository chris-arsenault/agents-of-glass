"""Shared persistence facades for CLI mutations.

Durable markdown is the agent-readable surface, but a successful mutation may
also need to update Postgres search chunks, the runtime entity cache, and the
FalkorDB graph mirror. Keeping those side effects behind one facade prevents
command implementations from updating only the filesystem and forgetting the
other persistence layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import db as _db
from . import embeddings as _embeddings
from .campaign import pg_connection
from .config import Paths, load_config
from .entities import markdown_title, parse_frontmatter, upsert_entity_from_path
from .errors import GlassError, agent_instruction
from .ids import slugify
from .paths_resolve import display_path


@dataclass(frozen=True)
class MarkdownPersistenceResult:
    path: str
    bytes: int
    search: dict[str, Any]
    entity: dict[str, Any] | None
    graph: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "bytes": self.bytes,
            "search": self.search,
            "entity": self.entity,
            "graph": self.graph,
        }


class CampaignPersistence:
    def __init__(self, *, paths: Paths, campaign_id: str, campaign_root: Path):
        self.paths = paths
        self.campaign_id = campaign_id
        self.campaign_root = campaign_root

    def write_markdown(
        self,
        destination: Path,
        text: str,
        *,
        state: dict[str, Any],
        graph: bool | str = "auto",
        search: bool = True,
    ) -> MarkdownPersistenceResult:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
        return self.register_markdown(
            destination,
            state=state,
            graph=graph,
            search=search,
        )

    def register_markdown(
        self,
        path: Path,
        *,
        state: dict[str, Any],
        graph: bool | str = "auto",
        search: bool = True,
    ) -> MarkdownPersistenceResult:
        text = path.read_text(encoding="utf-8")
        entity_record: dict[str, Any] | None = None
        graph_status: dict[str, Any] | None = None

        if graph is True or (graph == "auto" and self._is_entity_markdown(path, text)):
            entity_record = upsert_entity_from_path(self.paths, state, path)
            graph_status = self._mirror_entity_to_graph(entity_record, path)

        search_status = self._index_markdown(path, text) if search else {"status": "skipped"}
        return MarkdownPersistenceResult(
            path=display_path(path),
            bytes=len(text.encode("utf-8")),
            search=search_status,
            entity=entity_record,
            graph=graph_status,
        )

    def _mirror_entity_to_graph(
        self, record: dict[str, Any], path: Path
    ) -> dict[str, Any]:
        from .commands.entity import _mirror_entity_to_graph

        return _mirror_entity_to_graph(record, path, self.campaign_id)

    def _index_markdown(self, path: Path, text: str) -> dict[str, Any]:
        if not _db.postgres_configured(load_config()):
            raise GlassError(
                agent_instruction(
                    "Postgres search index is required",
                    "Configure `[postgres]` in `agents-of-glass.toml` or set libpq environment variables.",
                    "Then run `glass db migrate` before syncing durable markdown.",
                )
            )
        try:
            rel = path.resolve().relative_to(self.campaign_root.resolve())
        except ValueError:
            return {"status": "skipped", "reason": "outside-campaign"}
        if _skip_markdown(rel):
            return {"status": "skipped", "reason": "not-indexable"}

        visibility, owner = _visibility_for_path(rel)
        title = _markdown_title(text, str(rel))
        embedded = _embeddings.embed_text(
            _embeddings.embedding_text(title=title, body=text),
            kind="document",
        )
        with pg_connection() as conn:
            _db.search_chunk_upsert(
                conn,
                chunk_id=f"{self.campaign_id}:markdown:{rel}",
                campaign_id=self.campaign_id,
                source_type="markdown",
                source_id=str(rel),
                visibility=visibility,
                owner_actor=owner,
                path=str(rel),
                title=title,
                body=text,
                metadata={"path": str(rel)},
                embedding=embedded.vectors[0],
                embedding_model=embedded.model,
                embedding_provider=embedded.provider,
            )
            conn.commit()
        return {
            "status": "indexed",
            "source_type": "markdown",
            "path": str(rel),
            "visibility": visibility,
            "owner_actor": owner,
            "embedding_model": embedded.model,
            "embedding_dim": embedded.dimensions,
        }

    def _is_entity_markdown(self, path: Path, text: str) -> bool:
        try:
            rel = path.resolve().relative_to(self.campaign_root.resolve())
        except ValueError:
            return False
        fm = parse_frontmatter(text)
        if any(key in fm for key in ("id", "type", "title")):
            return True
        if len(rel.parts) >= 2 and rel.parts[0] == "shared" and rel.parts[1] == "lore":
            return True
        if len(rel.parts) >= 3 and rel.parts[0] == "dm" and rel.parts[1] == "notes":
            return rel.parts[2] in {
                "npcs",
                "factions",
                "locales",
                "creatures",
                "artifacts",
                "ships",
                "events",
                "threads",
            }
        return False


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
    fm = parse_frontmatter(text)
    if fm.get("title"):
        return fm["title"]
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return markdown_title(text, slugify(Path(fallback).stem).replace("-", " ").title())
