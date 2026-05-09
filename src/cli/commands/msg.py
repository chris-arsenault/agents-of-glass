"""Msg commands."""

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
    active_session_file,
    active_session_id,
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
    session_dir,
    state_path,
    state_summary,
    transcript_path,
    write_active_session,
)
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


class MessageGroup(click.Group):
    """Allow both `glass msg read` and spec-shaped `glass msg <type> <to> <body>`."""

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        if args and args[0] in self.commands:
            return super().resolve_command(ctx, args)
        return super().resolve_command(ctx, ["send", *args])


@click.group(cls=MessageGroup, name="msg")
def msg_group() -> None:
    """Typed inter-agent message bus.

    Send with: glass msg <type> <recipient> <body>
    Read with: glass msg read [--since-checkpoint]
    """


@msg_group.command("send", hidden=True)
@click.argument("message_type")
@click.argument("recipient")
@click.argument("body_parts", nargs=-1, required=True)
@click.pass_context
def msg_send(
    ctx: click.Context, message_type: str, recipient: str, body_parts: tuple[str, ...]
) -> None:
    paths = get_paths()
    state = load_state(paths)
    require_message_type(paths, message_type)
    require_recipient(paths, state, recipient)
    role = current_role()
    body = " ".join(body_parts)
    campaign_id = active_campaign_id()
    with pg_connection() as conn:
        message = _db.message_send(
            conn,
            campaign_id=campaign_id,
            session_id=state["session"]["id"],
            sender=role.actor,
            recipient=recipient,
            type_=message_type,
            body=body,
        )
    result = {"message": message}
    commit(
        paths,
        state,
        ctx,
        "msg.send",
        command_params(message_type=message_type, recipient=recipient),
        result,
    )


@msg_group.command("read")
@click.option("--since-checkpoint", is_flag=True,
              help="Show only messages this agent hasn't read yet (recommended at turn start).")
@click.option("--from", "sender")
@click.option("--type", "message_type")
@click.option("--no-mark", is_flag=True,
              help="Do not write read-checkpoints. Useful for spot-checking the bus.")
@click.pass_context
def msg_read(
    ctx: click.Context,
    since_checkpoint: bool,
    sender: str | None,
    message_type: str | None,
    no_mark: bool,
) -> None:
    paths = get_paths()
    state = load_state(paths)
    if message_type:
        require_message_type(paths, message_type)
    role = current_role()
    campaign_id = active_campaign_id()
    with pg_connection() as conn:
        rows = _db.message_list(
            conn,
            campaign_id=campaign_id,
            agent_id=role.actor,
            only_unread=since_checkpoint,
            sender=sender,
            type_=message_type,
            limit=500,
        )
        # Visibility filter at the app layer (DM sees all; players see
        # party broadcasts, addressed-to-them, and self-sent).
        visible = [m for m in rows if message_visible_to(m, role)]
        if not no_mark and visible:
            _db.message_mark_read(
                conn,
                agent_id=role.actor,
                message_ids=[m["id"] for m in visible],
            )
    result = {"messages": visible, "count": len(visible)}
    commit(
        paths,
        state,
        ctx,
        "msg.read",
        command_params(
            since_checkpoint=since_checkpoint,
            sender=sender,
            message_type=message_type,
            no_mark=no_mark,
        ),
        result,
    )


