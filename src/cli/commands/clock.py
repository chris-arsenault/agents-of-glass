"""Durable clock commands."""

from __future__ import annotations

from typing import Any

import click

from .. import db as _db
from .. import workspace as _workspace
from ..campaign import active_campaign_id, pg_connection, resolve_active_campaign_workspace
from ..config import get_paths
from ..errors import GlassError
from ..ids import slugify
from ..role import current_role, require_dm
from ..state import append_audit, commit, load_state, queue_event
from ..yaml_io import command_params, emit


@click.group()
def clock() -> None:
    """Durable cross-scene clocks and long-running pressure."""


@clock.command("set")
@click.argument("clock_id")
@click.option("--scope", default="campaign", show_default=True,
              help="Freeform scope: campaign, arc, scene, faction, thread, npc, custom.")
@click.option("--anchor", "anchor_id", default=None,
              help="Optional id the clock belongs to, such as an arc or faction id.")
@click.option("--label", default=None, help="Player-facing label. Defaults to clock id.")
@click.option("--description", default="", help="Freeform clock description.")
@click.option("--value", type=int, default=0, show_default=True)
@click.option("--max", "max_value", type=int, required=True)
@click.option(
    "--direction",
    type=click.Choice(["fills", "drains"]),
    default="fills",
    show_default=True,
)
@click.option(
    "--public/--hidden",
    "public",
    default=False,
    show_default=True,
    help="Whether players can see this durable clock.",
)
@click.pass_context
def clock_set(
    ctx: click.Context,
    clock_id: str,
    scope: str,
    anchor_id: str | None,
    label: str | None,
    description: str,
    value: int,
    max_value: int,
    direction: str,
    public: bool,
) -> None:
    """DM-only: create or replace a durable clock."""
    role = require_dm()
    if max_value <= 0:
        raise GlassError("--max must be greater than zero")
    if value < 0 or value > max_value:
        raise GlassError("--value must be between 0 and --max")
    clock_key = slugify(clock_id)
    scope_key = slugify(scope)
    anchor_key = slugify(anchor_id) if anchor_id else None
    visibility = "public" if public else "dm"

    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    workspace = resolve_active_campaign_workspace()
    with pg_connection() as conn:
        record = _db.clock_upsert(
            conn,
            campaign_id=campaign_id,
            clock_id=clock_key,
            scope=scope_key,
            anchor_id=anchor_key,
            label=label or clock_key,
            description=description,
            value=value,
            max_value=max_value,
            direction=direction,
            visibility=visibility,
            actor=role.actor,
        )
        _write_public_clock_projections(conn, workspace)

    queue_event(
        state,
        role.actor,
        f"clock set {record['label']}: {record['value']}/{record['max']} ({visibility})",
    )
    commit(
        paths,
        state,
        ctx,
        "clock.set",
        command_params(
            clock_id=clock_key,
            scope=scope_key,
            anchor=anchor_key,
            label=label,
            value=value,
            max=max_value,
            direction=direction,
            visibility=visibility,
        ),
        {"clock": record},
    )


@clock.command("tick")
@click.argument("clock_id")
@click.argument("delta", type=int, default=1, required=False)
@click.option("--note", default="", help="Why the clock changed.")
@click.pass_context
def clock_tick(ctx: click.Context, clock_id: str, delta: int, note: str) -> None:
    """DM-only: advance or reduce a durable clock."""
    role = require_dm()
    clock_key = slugify(clock_id)
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    workspace = resolve_active_campaign_workspace()
    with pg_connection() as conn:
        try:
            record, before, after = _db.clock_tick(
                conn,
                campaign_id=campaign_id,
                clock_id=clock_key,
                delta=delta,
                actor=role.actor,
                note=note,
            )
        except LookupError:
            raise GlassError(f"unknown clock {clock_key!r}") from None
        _write_public_clock_projections(conn, workspace)

    sign = f"{delta:+d}"
    queue_event(
        state,
        role.actor,
        f"clock {record['label']} {sign} ({before}/{record['max']} -> {after}/{record['max']})",
    )
    commit(
        paths,
        state,
        ctx,
        "clock.tick",
        command_params(clock_id=clock_key, delta=delta, note=note),
        {"clock": record, "before": before, "after": after},
    )


@clock.command("list")
@click.option("--scope", default=None)
@click.option("--anchor", "anchor_id", default=None)
@click.option("--public", "public_only", is_flag=True, help="Show only public clocks.")
@click.option("--all", "include_archived", is_flag=True, help="Include archived clocks.")
@click.pass_context
def clock_list(
    ctx: click.Context,
    scope: str | None,
    anchor_id: str | None,
    public_only: bool,
    include_archived: bool,
) -> None:
    """List durable clocks visible to the current role."""
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    visibility = "public" if role.kind == "player" or public_only else None
    with pg_connection() as conn:
        clocks = _db.clock_list(
            conn,
            campaign_id=campaign_id,
            scope=slugify(scope) if scope else None,
            anchor_id=slugify(anchor_id) if anchor_id else None,
            visibility=visibility,
            include_archived=include_archived,
        )
    result = {"clocks": clocks, "count": len(clocks)}
    append_audit(
        paths,
        state,
        ctx,
        "clock.list",
        command_params(
            scope=scope,
            anchor=anchor_id,
            public=public_only,
            all=include_archived,
        ),
        result,
    )
    emit(result)


@clock.command("show")
@click.argument("clock_id")
@click.pass_context
def clock_show(ctx: click.Context, clock_id: str) -> None:
    """Show one durable clock."""
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    role = current_role()
    clock_key = slugify(clock_id)
    with pg_connection() as conn:
        record = _db.clock_get(conn, campaign_id=campaign_id, clock_id=clock_key)
    if record is None:
        raise GlassError(f"unknown clock {clock_key!r}")
    if role.kind == "player" and record["visibility"] != "public":
        raise GlassError("permission denied: players cannot read hidden clocks")
    result = {"clock": record}
    append_audit(
        paths,
        state,
        ctx,
        "clock.show",
        command_params(clock_id=clock_key),
        result,
    )
    emit(result)


@clock.command("resolve")
@click.argument("clock_id")
@click.option("--note", default="", help="What happened when the clock resolved.")
@click.pass_context
def clock_resolve(ctx: click.Context, clock_id: str, note: str) -> None:
    """DM-only: mark a durable clock resolved."""
    _set_clock_status(ctx, clock_id, status="resolved", note=note)


@clock.command("archive")
@click.argument("clock_id")
@click.option("--note", default="", help="Why the clock is being archived.")
@click.pass_context
def clock_archive(ctx: click.Context, clock_id: str, note: str) -> None:
    """DM-only: archive a durable clock so it no longer appears by default."""
    _set_clock_status(ctx, clock_id, status="archived", note=note)


def _set_clock_status(
    ctx: click.Context,
    clock_id: str,
    *,
    status: str,
    note: str,
) -> None:
    role = require_dm()
    clock_key = slugify(clock_id)
    paths = get_paths()
    campaign_id = active_campaign_id()
    state = load_state(paths, campaign_id)
    workspace = resolve_active_campaign_workspace()
    with pg_connection() as conn:
        try:
            record = _db.clock_set_status(
                conn,
                campaign_id=campaign_id,
                clock_id=clock_key,
                status=status,
                actor=role.actor,
                note=note,
            )
        except LookupError:
            raise GlassError(f"unknown clock {clock_key!r}") from None
        _write_public_clock_projections(conn, workspace)

    queue_event(state, role.actor, f"clock {status} {record['label']}")
    commit(
        paths,
        state,
        ctx,
        f"clock.{status}",
        command_params(clock_id=clock_key, note=note),
        {"clock": record},
    )


def _write_public_clock_projections(
    conn: Any, workspace: _workspace.CampaignWorkspace
) -> None:
    """Project public durable clocks to markdown.

    Postgres remains canonical. These files are player-facing reference
    surfaces so agents can inspect public pressure without asking the DM.
    """
    clocks = _db.clock_list(
        conn,
        campaign_id=workspace.campaign_id,
        visibility="public",
        include_archived=False,
    )
    shared_path = workspace.root / "shared" / "clocks.md"
    shared_path.parent.mkdir(parents=True, exist_ok=True)
    shared_path.write_text(_render_clock_markdown(clocks, "Public Clocks"), encoding="utf-8")

    arc_groups: dict[str, list[dict[str, Any]]] = {}
    for item in clocks:
        if item["scope"] in {"arc", "act"} and item.get("anchor_id"):
            arc_groups.setdefault(str(item["anchor_id"]), []).append(item)
    if workspace.arcs_dir.exists():
        for arc_dir in workspace.arcs_dir.iterdir():
            if not arc_dir.is_dir():
                continue
            arc_clocks = arc_groups.get(arc_dir.name, [])
            (arc_dir / "clocks.md").write_text(
                _render_clock_markdown(arc_clocks, f"Public Clocks - {arc_dir.name}"),
                encoding="utf-8",
            )


def _render_clock_markdown(clocks: list[dict[str, Any]], title: str) -> str:
    active = [clock for clock in clocks if clock["status"] == "active"]
    resolved = [clock for clock in clocks if clock["status"] == "resolved"]
    lines = [
        "---",
        "generated_by: glass clock",
        "---",
        "",
        f"# {title}",
        "",
        "Postgres is canonical. This file is a player-facing projection of public durable clocks.",
        "",
    ]
    _append_clock_section(lines, "Active", active)
    _append_clock_section(lines, "Resolved", resolved)
    return "\n".join(lines).rstrip() + "\n"


def _append_clock_section(
    lines: list[str],
    title: str,
    clocks: list[dict[str, Any]],
) -> None:
    lines.extend([f"## {title}", ""])
    if not clocks:
        lines.extend(["_None._", ""])
        return
    for clock in clocks:
        scope = clock["scope"]
        anchor = f":{clock['anchor_id']}" if clock.get("anchor_id") else ""
        description = f" - {clock['description']}" if clock.get("description") else ""
        resolution = (
            f" Resolved: {clock['resolution_note']}"
            if clock.get("resolution_note") and clock["status"] == "resolved"
            else ""
        )
        lines.append(
            f"- **{clock['label']}** (`{clock['clock_id']}`, {scope}{anchor}): "
            f"{clock['value']}/{clock['max']} ({clock['direction']})"
            f"{description}{resolution}"
        )
    lines.append("")
