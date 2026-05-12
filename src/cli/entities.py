"""Markdown frontmatter + entity-from-path helpers.

The entity record is the in-state cache for a graph node — id, title,
sections, frontmatter, edges. The graph (FalkorDB) is canonical;
this dict in state["entities"] is a fast local lookup.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Paths
from .errors import GlassError, agent_instruction
from .ids import now_iso, slugify
from .paths_resolve import display_path, ensure_under_any


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    raw = text[4:end]
    data: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


def markdown_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def parse_sections(text: str, entity_id: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current_title = "body"
    current_lines: list[str] = []

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if body:
            section_id = f"{entity_id}:{slugify(current_title)}"
            sections.append(
                {
                    "section_id": section_id,
                    "title": current_title,
                    "text": body,
                }
            )

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            current_title = line[3:].strip() or "section"
            current_lines = []
        else:
            current_lines.append(line)
    flush()
    return sections


def upsert_entity_from_path(paths: Paths, state: dict[str, Any], path: Path) -> dict[str, Any]:
    allowed_roots = [paths.content]
    if paths.campaigns is not None:
        allowed_roots.append(paths.campaigns)
    path = ensure_under_any(
        path,
        allowed_roots,
        f"entity paths must stay under templates/ or campaigns/; got {path}",
    )
    if not path.exists():
        raise GlassError(
            agent_instruction(
                f"entity source does not exist: {display_path(path)}",
                "Pass an existing markdown lore/entity file, usually under `shared/lore/` or an arc/scene document.",
            )
        )
    text = path.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(text)
    entity_id = frontmatter.get("id") or slugify(path.stem)
    record = {
        "entity_id": entity_id,
        "title": frontmatter.get("title") or markdown_title(text, path.stem),
        "path": display_path(path),
        "updated_at": now_iso(),
        "sections": parse_sections(text, entity_id),
        "frontmatter": frontmatter,
        "edges": [],
    }
    state["entities"][entity_id] = record
    return record
