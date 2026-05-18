"""Note commands."""

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
def note() -> None:
    """Lore draft and journal commands."""


@note.command("write")
@click.argument("path_text")
@click.option("--body", help="Markdown body to write.")
@click.option("--from", "from_file", help="Read body from this file, or '-' for stdin.")
@click.pass_context
def note_write(
    ctx: click.Context, path_text: str, body: str | None, from_file: str | None
) -> None:
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    destination = resolve_note_write_path(paths, path_text, campaign_id=campaign_id)
    text = read_body(body, from_file)
    persistence = CampaignPersistence(
        paths=paths,
        campaign_id=campaign_id,
        campaign_root=active_campaign_root(),
    )
    persisted = persistence.write_markdown(destination, text, state=state)
    result = persisted.to_dict()
    commit(
        paths,
        state,
        ctx,
        "note.write",
        command_params(path=path_text, bytes=result["bytes"]),
        result,
    )


@note.command("propose")
@click.argument("path_text")
@click.pass_context
def note_propose(ctx: click.Context, path_text: str) -> None:
    role = require_player()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    source = resolve_content_path(paths, path_text)
    workspace_root = active_campaign_root()

    def _player_drafts_root(workspace: Path, player: str) -> Path:
        return (workspace / "players" / player / "drafts").resolve()

    if role.kind == "player":
        # Source must be under <campaign or templates>/players/<actor>/drafts/
        candidates = [_player_drafts_root(workspace_root, role.actor)]
        if workspace_root != paths.content:
            candidates.append(_player_drafts_root(paths.content, role.actor))
        if not any(
            str(source.resolve()).startswith(str(root) + os.sep) or source.resolve() == root
            for root in candidates
        ):
            raise GlassError(
                agent_instruction(
                    "players can propose only their own drafts",
                    f"Write the draft under `players/{role.actor}/drafts/`, then run `glass note propose <that-path>`.",
                )
            )
        player_id = role.actor
    else:
        player_id = infer_player_from_path(paths, source)
        if not player_id and workspace_root != paths.content:
            try:
                rel = source.resolve().relative_to(workspace_root.resolve())
                if len(rel.parts) >= 3 and rel.parts[0] == "players" and rel.parts[2] == "drafts":
                    player_id = rel.parts[1]
            except ValueError:
                pass
        if not player_id:
            raise GlassError(
                agent_instruction(
                    "operator note propose needs a player draft path",
                    "Use a path under `players/<id>/drafts/` so Glass knows which player authored the proposal.",
                )
            )
    if not source.exists():
        raise GlassError(
            agent_instruction(
                f"draft does not exist: {display_path(source)}",
                "Create the draft markdown file first, then run `glass note propose <path>`.",
            )
        )
    intake_id = new_id("intake")
    destination_name = f"{intake_id}--{player_id}--{source.name}"
    destination = workspace_root / "dm" / "intake" / destination_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    record = {
        "intake_id": intake_id,
        "player_id": player_id,
        "source_path": display_path(source),
        "intake_path": display_path(destination),
        "status": "pending",
        "created_at": now_iso(),
        "resolved_at": None,
        "ratified_path": None,
    }
    state["note_intake"].append(record)
    result = {"intake": record}
    commit(
        paths,
        state,
        ctx,
        "note.propose",
        command_params(path=path_text),
        result,
    )


def require_intake(state: dict[str, Any], intake_id: str) -> dict[str, Any]:
    for item in state.get("note_intake", []):
        if item["intake_id"] == intake_id:
            return item
    pending = ", ".join(item["intake_id"] for item in state.get("note_intake", [])) or "none"
    raise GlassError(
        agent_instruction(
            f"unknown intake id {intake_id!r}",
            f"Use one of the known intake ids: {pending}.",
            "Read the campaign intake list before ratifying or rejecting a note.",
        )
    )


@note.command("ratify")
@click.argument("intake_id")
@click.option("--to", "target_path",
              help="Target path relative to shared/lore/. Defaults to "
                   "shared/lore/<original-filename>.")
@click.pass_context
def note_ratify(
    ctx: click.Context,
    intake_id: str,
    target_path: str | None,
) -> None:
    """DM-only: ratify an intake (e.g. a public journal entry) into shared lore.

    propose/ratify is intended for public journal entries — text the player
    wants to publish to the party. Character sheets, intros, and relationships
    are written by the player directly into their own dirs without going
    through this loop.
    """
    require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    item = require_intake(state, intake_id)
    if item["status"] != "pending":
        raise GlassError(
            agent_instruction(
                f"intake {intake_id} is already {item['status']}",
                "Do not ratify it again; choose a pending intake id.",
            )
        )
    source = REPO_ROOT / item["intake_path"]
    workspace_root = active_campaign_root()
    lore_root = workspace_root / "shared" / "lore"

    if target_path:
        rel = clean_relative_path(target_path)
        while rel.parts and rel.parts[0] in {"content", "shared", "lore"}:
            rel = Path(*rel.parts[1:])
        destination = lore_root / rel
    else:
        # Strip the "<intake_id>--<player_id>--" prefix off the intake filename.
        original_name = source.name.split("--", 2)[-1]
        destination = lore_root / original_name

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    item["status"] = "ratified"
    item["resolved_at"] = now_iso()
    item["ratified_path"] = display_path(destination)
    persistence = CampaignPersistence(
        paths=paths,
        campaign_id=campaign_id,
        campaign_root=workspace_root,
    )
    persisted = persistence.register_markdown(destination, state=state, graph=True)
    result = {"intake": item, **persisted.to_dict()}
    commit(
        paths,
        state,
        ctx,
        "note.ratify",
        command_params(intake_id=intake_id, target_path=target_path),
        result,
    )


@note.command("reject")
@click.argument("intake_id")
@click.option("--reason", default="")
@click.pass_context
def note_reject(ctx: click.Context, intake_id: str, reason: str) -> None:
    require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    item = require_intake(state, intake_id)
    if item["status"] != "pending":
        raise GlassError(
            agent_instruction(
                f"intake {intake_id} is already {item['status']}",
                "Do not reject it again; choose a pending intake id.",
            )
        )
    item["status"] = "rejected"
    item["resolved_at"] = now_iso()
    item["reason"] = reason
    result = {"intake": item}
    commit(
        paths,
        state,
        ctx,
        "note.reject",
        command_params(intake_id=intake_id, reason=reason),
        result,
    )
