"""Tarot influence commands."""

from __future__ import annotations

import click

from .. import creative
from .. import db as _db
from ..campaign import active_campaign_id, pg_connection
from ..config import get_paths
from ..errors import GlassError
from ..role import current_role, require_dm
from ..state import append_audit, load_state
from ..yaml_io import command_params, emit


@click.group()
def tarot() -> None:
    """Actual-play tarot influences."""


@tarot.command("current")
@click.argument("actor", required=False)
@click.pass_context
def tarot_current(ctx: click.Context, actor: str | None) -> None:
    """Show an actor's current persisted tarot influence."""
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    resolved_actor = actor or ("dm" if role.kind == "operator" else role.actor)
    turn_number = _current_prompt_turn(state)
    with pg_connection() as conn:
        influence = _db.tarot_current(
            conn,
            campaign_id=campaign_id,
            actor=resolved_actor,
            turn_number=turn_number,
        )
    result = {
        "campaign_id": campaign_id,
        "actor": resolved_actor,
        "turn_number": turn_number,
        "tarot": influence,
    }
    append_audit(
        paths,
        state,
        ctx,
        "tarot.current",
        command_params(actor=resolved_actor),
        result,
    )
    emit(result)


@tarot.command("list")
@click.option("--actor", default=None, help="Filter by actor id.")
@click.option("--all", "include_inactive", is_flag=True, help="Include expired/deactivated draws.")
@click.option("--limit", type=int, default=25, show_default=True)
@click.pass_context
def tarot_list(
    ctx: click.Context,
    actor: str | None,
    include_inactive: bool,
    limit: int,
) -> None:
    """List persisted tarot influences for the campaign."""
    if limit <= 0:
        raise GlassError("--limit must be greater than zero")
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    turn_number = _current_prompt_turn(state)
    with pg_connection() as conn:
        influences = _db.tarot_list(
            conn,
            campaign_id=campaign_id,
            actor=actor,
            active_only=not include_inactive,
            turn_number=None if include_inactive else turn_number,
            limit=limit,
        )
    result = {
        "campaign_id": campaign_id,
        "actor": actor,
        "turn_number": turn_number,
        "influences": influences,
        "count": len(influences),
    }
    append_audit(
        paths,
        state,
        ctx,
        "tarot.list",
        command_params(actor=actor, all=include_inactive, limit=limit),
        result,
    )
    emit(result)


@tarot.command("draw")
@click.argument("actor")
@click.option(
    "--turns",
    "duration_turns",
    type=int,
    default=creative.DEFAULT_TAROT_DURATION_TURNS,
    show_default=True,
    help="How many global agent turns this draw lasts.",
)
@click.pass_context
def tarot_draw(ctx: click.Context, actor: str, duration_turns: int) -> None:
    """DM-only: draw and persist a new tarot influence for an actor."""
    require_dm()
    if duration_turns <= 0:
        raise GlassError("--turns must be greater than zero")
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    starts_turn = _current_prompt_turn(state)
    expires_turn = starts_turn + duration_turns - 1
    draw = creative.tarot_for_seed(
        campaign_id=campaign_id,
        actor=actor,
        turn_number=starts_turn,
    )
    with pg_connection() as conn:
        influence = _db.tarot_draw(
            conn,
            campaign_id=campaign_id,
            actor=actor,
            deck_id=draw["deck_id"],
            deck_name=draw["deck_name"],
            card_id=draw["card_id"],
            card_name=draw["card_name"],
            influence=draw["influence"],
            source_note=draw["source_note"],
            starts_turn=starts_turn,
            expires_turn=expires_turn,
        )
    result = {
        "campaign_id": campaign_id,
        "actor": actor,
        "duration_turns": duration_turns,
        "tarot": influence,
    }
    append_audit(
        paths,
        state,
        ctx,
        "tarot.draw",
        command_params(actor=actor, turns=duration_turns),
        result,
    )
    emit(result)


def _current_prompt_turn(state: dict) -> int:
    return int(state.get("turn_counter", 0)) + 1
