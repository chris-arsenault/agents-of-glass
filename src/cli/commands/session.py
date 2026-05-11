"""Campaign-state lifecycle commands.

Historically named "session" — kept for backward compat with the
orchestrator's GlassBridge invocation. Each campaign now has exactly
one runtime state record in Postgres. `state.json` is not a supported
runtime cache. The "session" concept is gone; what these commands manage
is the campaign's runtime state.
"""

from __future__ import annotations

import click

from ..campaign import resolve_active_campaign_workspace
from ..config import get_paths
from ..errors import GlassError
from ..paths_resolve import display_path
from ..role import require_dm
from ..state import (
    append_audit,
    campaign_runtime_dir,
    commit,
    default_state,
    load_state,
    save_state,
    scene_framing_path,
    state_exists,
    state_path,
    state_summary,
    transcript_path,
)
from ..yaml_io import command_params, emit, read_body


@click.group()
def session() -> None:
    """Campaign runtime state lifecycle (legacy name)."""


@session.command("new")
@click.option("--campaign", required=True, help="Campaign id (must match the campaigns/<id>/ workspace).")
@click.option("--session-id", "session_id_unused", default=None, hidden=True,
              help="Ignored; kept for backward compat with the orchestrator's invocation.")
@click.pass_context
def session_new(ctx: click.Context, campaign: str, session_id_unused: str | None) -> None:
    """Initialize the campaign's runtime state.

    Writes the default runtime state, transcript.md export header, and an
    empty legacy scene-framing.md. The live public table is created/reset by
    `glass scene create`. Errors if the workspace doesn't exist (use
    `aog campaign run <id>` first).
    """
    paths = get_paths()
    runtime_dir = campaign_runtime_dir(paths, campaign)
    if not runtime_dir.exists():
        raise GlassError(
            f"campaign workspace does not exist at {runtime_dir}; "
            "run `aog campaign run <id>` first"
        )

    existed = state_exists(paths, campaign)
    state = load_state(paths, campaign) if existed else default_state(campaign)
    save_state(paths, state)

    transcript_file = transcript_path(paths, campaign)
    if not transcript_file.exists():
        transcript_file.write_text(
            f"# {campaign}\n\n", encoding="utf-8"
        )
    framing_file = scene_framing_path(paths, campaign)
    if not framing_file.exists():
        framing_file.write_text("# Scene Framing\n\n", encoding="utf-8")

    result = {
        "campaign": campaign,
        "status": "active",
        "path": display_path(runtime_dir),
        "existing": existed,
    }
    append_audit(paths, state, ctx, "session.new", command_params(campaign=campaign), result)
    emit(result)


@session.command("show")
@click.option("--campaign", "campaign_id", default=None,
              help="Campaign id. Defaults to GLASS_CAMPAIGN_ID or the active campaign.")
@click.pass_context
def session_show(ctx: click.Context, campaign_id: str | None) -> None:
    """Show summary of the campaign's current runtime state."""
    paths = get_paths()
    if not campaign_id:
        campaign_id = resolve_active_campaign_workspace().campaign_id
    state = load_state(paths, campaign_id)
    result = state_summary(state)
    append_audit(paths, state, ctx, "session.show", command_params(campaign=campaign_id), result)
    emit(result)


@session.command("wrap")
@click.option("--summary", help="Wrap-up summary text.")
@click.option("--from", "from_file", help="Read summary from this file, or '-' for stdin.")
@click.pass_context
def session_wrap(ctx: click.Context, summary: str | None, from_file: str | None) -> None:
    """Mark the campaign's runtime state as wrapped (DM-only)."""
    from ..ids import now_iso
    from ..campaign import active_campaign_id

    require_dm()
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    body = read_body(summary, from_file).strip()
    state["status"] = "wrapped"
    state["wrapped_at"] = now_iso()
    state["summary"] = body
    result = {
        "campaign": state["campaign"],
        "status": "wrapped",
        "wrapped_at": state["wrapped_at"],
        "summary": body,
    }
    commit(paths, state, ctx, "session.wrap", command_params(summary=body), result)
