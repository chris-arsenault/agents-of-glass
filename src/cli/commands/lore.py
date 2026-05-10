"""Lore commands."""

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
from ..persistence import CampaignPersistence
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


_campaign_workspace = resolve_active_campaign_workspace


def _mirror_entity_to_graph(
    record: "dict[str, Any]", path: "Path", campaign_id_override: "str | None"
) -> "dict[str, Any]":
    from .entity import _mirror_entity_to_graph as _impl
    return _impl(record, path, campaign_id_override)


@click.group()
def lore() -> None:
    """Lore curation: import / list / search."""


@lore.command("import")
@click.argument("source_path")
@click.option("--as", "alias", default=None, help="Override destination filename.")
@click.pass_context
def lore_import(ctx: click.Context, source_path: str, alias: str | None) -> None:
    """Import an entry from the world bible into the campaign's curated lore.

    SOURCE_PATH is interpreted relative to the lore root (`lore.path` in config),
    or as an absolute path. Examples:
      glass lore import player/concepts/ringglass.md
      glass lore import dm/themes/builders-gone.md
    """
    require_dm()
    workspace = _campaign_workspace()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    if paths.lore is None:
        raise GlassError("lore.path is not configured")

    source = Path(source_path)
    if not source.is_absolute():
        source = (paths.lore / source).resolve()
    try:
        dest = _workspace.import_lore(workspace, source, paths.lore, alias=alias)
    except (FileExistsError, FileNotFoundError) as exc:
        raise GlassError(str(exc)) from exc

    persistence = CampaignPersistence(
        paths=paths,
        campaign_id=workspace.campaign_id,
        campaign_root=workspace.root,
    )
    persisted = persistence.register_markdown(dest, state=state, graph=True)

    result = {
        "campaign_id": workspace.campaign_id,
        "source": str(source),
        "destination": str(dest),
        **persisted.to_dict(),
    }
    commit(
        paths,
        state,
        ctx,
        "lore.import",
        command_params(source_path=source_path, alias=alias),
        result,
    )


def _record_for_lore_import(path: Path) -> dict[str, Any]:
    """Build the same record shape as upsert_entity_from_path, but without the
    paths-must-be-under-content guard (lore lands in campaigns/<id>/shared/lore/).
    """
    text = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    entity_id = fm.get("id") or slugify(path.stem)
    return {
        "entity_id": entity_id,
        "title": fm.get("title") or markdown_title(text, path.stem),
        "path": str(path),
        "updated_at": now_iso(),
        "sections": parse_sections(text, entity_id),
        "frontmatter": fm,
        "edges": [],
    }


@lore.command("list")
@click.pass_context
def lore_list(ctx: click.Context) -> None:
    workspace = _campaign_workspace()
    entries = _workspace.list_lore(workspace)
    emit({"campaign_id": workspace.campaign_id, "lore": entries, "count": len(entries)})


@lore.command("search")
@click.argument("query")
@click.option("--limit", type=int, default=20, show_default=True)
@click.pass_context
def lore_search(ctx: click.Context, query: str, limit: int) -> None:
    """Search the world bible (DM only) — for finding candidates to import."""
    require_dm()
    paths = get_paths()
    if paths.lore is None:
        raise GlassError("lore.path is not configured")
    matches = _workspace.search_lore(paths.lore, query, limit=limit)
    emit({"query": query, "lore_root": str(paths.lore), "matches": matches, "count": len(matches)})


@lore.command("new")
@click.argument("entity_type")
@click.argument("slug")
@click.option("--title", default=None, help="Entry title (defaults to slug, title-cased).")
@click.option("--tags", default="", help="Comma-separated tag list.")
@click.option(
    "--prominence",
    type=click.Choice(["forgotten", "marginal", "recognized", "renowned", "mythic"]),
    default=None,
)
@click.option(
    "--category",
    default=None,
    help="Subdirectory under shared/lore/ (e.g. 'npcs', 'factions', 'locales'). "
    "Defaults to the plural of <entity_type> when sensible.",
)
@click.pass_context
def lore_new(
    ctx: click.Context,
    entity_type: str,
    slug: str,
    title: str | None,
    tags: str,
    prominence: str | None,
    category: str | None,
) -> None:
    """Scaffold a new lore entry under campaigns/<id>/shared/lore/.

    Creates a file with valid frontmatter, ready for the DM to fill in. Does
    NOT upsert to the graph — the DM edits the body, then runs `glass lore
    upsert <path>` once the entry is real. Run with empty body, fill in
    afterward.

    Example:
      glass lore new npc patrol-leader-verra --title "Patrol Leader Verra" \\
                     --tags "patrol,accord" --prominence marginal
    """
    require_dm()
    workspace = _campaign_workspace()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    slug_clean = _workspace.slugify(slug)
    cat = category or _default_category_for(entity_type)
    dest_dir = workspace.lore_dir / cat
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{slug_clean}.md"
    if dest.exists():
        raise GlassError(f"lore entry already exists: {dest}")

    title_value = title or slug_clean.replace("-", " ").title()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    fm_lines = [
        "---",
        f"title: {title_value}",
        f"type: {entity_type}",
        f"id: {slug_clean}",
    ]
    if tag_list:
        fm_lines.append("tags: [" + ", ".join(tag_list) + "]")
    if prominence:
        fm_lines.append(f"prominence: {prominence}")
    fm_lines.extend(["status: draft", "---", "", f"# {title_value}", "", "_Body to be authored._", ""])
    dest.write_text("\n".join(fm_lines), encoding="utf-8")
    persistence = CampaignPersistence(
        paths=paths,
        campaign_id=workspace.campaign_id,
        campaign_root=workspace.root,
    )
    persisted = persistence.register_markdown(dest, state=state, graph=True)

    result = {
        "campaign_id": workspace.campaign_id,
        "id": slug_clean,
        "type": entity_type,
        "title": title_value,
        "path": str(dest),
        "persistence": persisted.to_dict(),
        "next": [
            f"edit {dest} to fill in the body",
            f"glass lore upsert {dest.relative_to(workspace.root)} to register in the graph",
        ],
    }
    commit(
        paths,
        state,
        ctx,
        "lore.new",
        command_params(
            entity_type=entity_type,
            slug=slug,
            title=title,
            tags=tags,
            prominence=prominence,
            category=category,
        ),
        result,
    )


def _default_category_for(entity_type: str) -> str:
    plurals = {
        "npc": "npcs",
        "faction": "factions",
        "location": "locales",
        "locale": "locales",
        "creature": "creatures",
        "artifact": "artifacts",
        "ship": "ships",
        "transport": "ships",
        "event": "events",
        "occurrence": "events",
        "concept": "concepts",
        "thread": "threads",
        "loop": "loops",
        "theme": "themes",
        "hook": "hooks",
        "secret": "secrets",
    }
    return plurals.get(entity_type.lower(), entity_type.lower() + "s")


@lore.command("upsert")
@click.argument("path_text")
@click.pass_context
def lore_upsert(ctx: click.Context, path_text: str) -> None:
    """Register an authored lore entry in the FalkorDB graph.

    Use this after writing a lore file (either with `glass lore new` then
    your editor, or directly with the agent's Write tool). The path can be
    relative to the campaign workspace or absolute.

    Example:
      glass lore upsert shared/lore/npcs/patrol-leader-verra.md
    """
    require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)

    raw = Path(path_text).expanduser()
    if not raw.is_absolute():
        # Resolve relative to cwd (typically the campaign workspace).
        raw = (Path.cwd() / raw).resolve()

    if not raw.exists():
        raise GlassError(f"file not found: {raw}")

    persistence = CampaignPersistence(
        paths=paths,
        campaign_id=campaign_id,
        campaign_root=active_campaign_root(),
    )
    persisted = persistence.register_markdown(raw, state=state, graph=True)
    result = persisted.to_dict()
    commit(paths, state, ctx, "lore.upsert", command_params(path=path_text), result)


if __name__ == "__main__":
    main()
