"""Entry point for the `aog` operator CLI."""

from __future__ import annotations

from pathlib import Path
import json
import os

import click


# umask 002 so subdirs the orchestrator creates inside the campaign
# workspace (notably per-turn artifact dirs under <agent>/turns/) are
# group-writable. Combined with setgid + group=aog-<player> on the
# parent turns/, this lets the player Unix user write their out.md
# into a subdir the orchestrator (running as operator) created.
os.umask(0o002)

from .campaign import (
    CampaignManager,
    CampaignSpace,
    PHASE_ACTIVE,
    PHASE_CHARACTER_CREATION,
    PHASE_PLANNING,
)
from .config import load_config
from .runner import Orchestrator, TurnFailure
from .store import SessionStore, summarize_states


class CliState:
    def __init__(self, config_path: str | None):
        self.config = load_config(config_path)
        self.store = SessionStore(self.config)
        self.orchestrator = Orchestrator(self.config, self.store)
        self.campaign_manager = CampaignManager(self.config)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    help="Path to agents-of-glass.toml. Defaults to repo config files.",
)
@click.pass_context
def main(ctx: click.Context, config_path: Path | None) -> None:
    """Operate Agents of Glass campaigns."""
    ctx.obj = CliState(str(config_path) if config_path else None)


@main.group()
def campaign() -> None:
    """Manage campaigns: bootstrap, list, show, run, resume, clear."""


@campaign.command("bootstrap")
@click.argument("campaign_id")
@click.option(
    "--max-planning-turns",
    type=int,
    default=15,
    show_default=True,
    help="Safety net only. The DM ends the planning mode when they're done.",
)
@click.option(
    "--max-creation-turns",
    type=int,
    default=30,
    show_default=True,
    help="Safety net only. The DM ends character_creation when both rounds are done.",
)
@click.option(
    "--skip-character-creation",
    is_flag=True,
    help="Stop after campaign planning. Useful when you want to inspect the planning output.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Build context and commit synthetic turns without invoking Claude.",
)
@click.pass_obj
def campaign_bootstrap(
    cli: CliState,
    campaign_id: str,
    max_planning_turns: int,
    max_creation_turns: int,
    skip_character_creation: bool,
    dry_run: bool,
) -> None:
    """Bootstrap a campaign end-to-end.

    Steps:
      1. Create campaigns/<id>/ from templates/.
      2. Invoke DM in campaign-planning mode.
      3. Character creation (skip with --skip-character-creation).
      4. [STUB] Active scene play.
    """
    click.secho(f"[1/4] Creating campaign workspace: {campaign_id}", fg="cyan")
    try:
        space = cli.campaign_manager.create(campaign_id)
    except (FileExistsError, FileNotFoundError) as exc:
        raise click.ClickException(str(exc))
    click.echo(f"      workspace: {space.campaign_dir}")
    click.echo(f"      state:     {space.state_path}")

    click.secho(
        f"[2/4] Invoking DM for campaign planning (max {max_planning_turns} turns)",
        fg="cyan",
    )
    cli.campaign_manager.advance_phase(campaign_id, PHASE_PLANNING)
    state = cli.store.create_session(
        campaign=campaign_id,
        initial_mode="campaign-planning",
        initial_scene="planning",
    )
    click.echo(f"      campaign: {state.campaign}")
    try:
        turns_run = cli.orchestrator.run_loop(
            state,
            max_turns=max_planning_turns,
            dry_run=dry_run,
            resume_failed=False,
        )
    except TurnFailure as exc:
        detail = json.dumps(exc.failure, indent=2, sort_keys=True)
        raise click.ClickException(f"campaign planning failed: {exc}\n{detail}") from exc

    click.echo(f"      DM produced {turns_run} planning turn(s)")
    click.echo(f"      transcript: {cli.store.transcript_path(state.campaign)}")
    click.echo(f"      DM workspace: {space.campaign_dir / 'dm'}")

    if skip_character_creation:
        cli.campaign_manager.advance_phase(campaign_id, PHASE_CHARACTER_CREATION)
        click.secho("[3/4] Character creation skipped (--skip-character-creation).",
                    fg="yellow")
    else:
        cli.campaign_manager.advance_phase(campaign_id, PHASE_CHARACTER_CREATION)
        click.secho(
            f"[3/4] Invoking players + DM for character creation "
            f"(max {max_creation_turns} turns)",
            fg="cyan",
        )
        creation_state = cli.store.create_session(
            campaign=campaign_id,
            initial_mode="character-creation",
            initial_scene="character-creation",
        )
        try:
            creation_turns = cli.orchestrator.run_loop(
                creation_state,
                max_turns=max_creation_turns,
                dry_run=dry_run,
                resume_failed=False,
            )
        except TurnFailure as exc:
            detail = json.dumps(exc.failure, indent=2, sort_keys=True)
            raise click.ClickException(
                f"character creation failed: {exc}\n{detail}"
            ) from exc
        click.echo(f"      ran {creation_turns} character-creation turn(s)")
        click.echo(f"      transcript: {cli.store.transcript_path(creation_state.campaign)}")

    cli.campaign_manager.advance_phase(campaign_id, PHASE_ACTIVE)
    click.secho("[4/4] [STUB] Active scene play", fg="yellow")
    click.echo("              (DM creates scenes via glass scene create;")
    click.echo("               operator drives via aog campaign run)")

    click.echo()
    click.secho(
        f"Campaign '{campaign_id}' bootstrapped through "
        f"{'campaign_planning' if skip_character_creation else 'character_creation'}.",
        fg="green",
    )
    click.echo(f"State file: {space.state_path}")


@campaign.command("list")
@click.pass_obj
def campaign_list(cli: CliState) -> None:
    """List campaigns and their phase + runtime status."""
    workspace_ids = set(cli.campaign_manager.list_campaigns())
    states = {state.campaign: state for state in cli.store.list_campaigns()}
    if not workspace_ids and not states:
        click.echo("no campaigns")
        return
    for campaign_id in sorted(workspace_ids | set(states)):
        try:
            phase_state = cli.campaign_manager.load_state(campaign_id)
            phase = phase_state.get("phase", "?")
        except Exception:
            phase = "?"
        runtime = states.get(campaign_id)
        if runtime is not None:
            try:
                active = runtime.active_mode
                mode_str = f"{active.mode}:{active.scene_id}"
            except ValueError:
                mode_str = "(no mode)"
            click.echo(
                f"{campaign_id:<32}  phase: {phase:<22}  "
                f"status: {runtime.status:<10}  turn={runtime.turn_number}  {mode_str}"
            )
        else:
            click.echo(f"{campaign_id:<32}  phase: {phase:<22}  (no runtime state)")


@campaign.command("show")
@click.argument("campaign_id", required=False)
@click.option("--json", "as_json", is_flag=True, help="Print raw runtime state JSON.")
@click.pass_obj
def campaign_show(cli: CliState, campaign_id: str | None, as_json: bool) -> None:
    """Show a campaign's runtime state. Defaults to the latest campaign."""
    state = cli.store.load(campaign_id)
    if as_json:
        click.echo(json.dumps(state.to_dict(), indent=2, sort_keys=True))
        return
    try:
        active = state.active_mode
    except ValueError:
        active = None
    click.echo(f"campaign: {state.campaign}")
    click.echo(f"status: {state.status}")
    click.echo(f"turn: {state.turn_number}")
    if active is not None:
        click.echo(f"active mode: {active.mode}")
        click.echo(f"scene: {active.scene_id}")
        click.echo(f"mode budget remaining: {active.turn_budget_remaining}")
    else:
        click.echo("active mode: (none)")
    click.echo(f"last speaker: {state.last_speaker or '-'}")
    if state.failure:
        click.echo("failure:")
        click.echo(json.dumps(state.failure, indent=2, sort_keys=True))


@campaign.command("prepare-turn")
@click.argument("campaign_id", required=False)
@click.pass_obj
def campaign_prepare_turn(cli: CliState, campaign_id: str | None) -> None:
    """Build the next turn's TURN_START context without invoking the agent."""
    state = cli.store.load(campaign_id)
    package = cli.orchestrator.prepare_turn(state)
    click.echo(f"prepared {package.turn_id}")
    click.echo(f"cwd: {package.spawn_cwd}")
    click.echo(f"in:  {package.turn_start_path}")
    click.echo(f"out: {package.turn_output_path}")


@campaign.command("run")
@click.argument("campaign_id", required=False)
@click.option("--max-turns", type=int, default=None, help="Turns to run in this invocation.")
@click.option("--dry-run", is_flag=True, help="Synthetic turns without Claude.")
@click.pass_obj
def campaign_run(
    cli: CliState,
    campaign_id: str | None,
    max_turns: int | None,
    dry_run: bool,
) -> None:
    """Run the orchestration loop for a campaign."""
    state = cli.store.load(campaign_id)
    turns = _run_or_raise(cli, state, max_turns=max_turns, dry_run=dry_run, resume_failed=False)
    click.echo(f"ran {turns} turn(s)")


@campaign.command("resume")
@click.argument("campaign_id", required=False)
@click.option("--max-turns", type=int, default=None, help="Turns to run in this invocation.")
@click.option("--dry-run", is_flag=True, help="Synthetic turns without Claude.")
@click.pass_obj
def campaign_resume(
    cli: CliState,
    campaign_id: str | None,
    max_turns: int | None,
    dry_run: bool,
) -> None:
    """Resume a failed/paused/interrupted campaign."""
    state = cli.store.load(campaign_id)
    turns = _run_or_raise(cli, state, max_turns=max_turns, dry_run=dry_run, resume_failed=True)
    click.echo(f"resumed and ran {turns} turn(s)")


@campaign.command("clean")
@click.argument("campaign_id")
@click.option("--state-only", is_flag=True,
              help="Only delete runtime state files (state.json, transcript.md, "
                   "audit.jsonl, scene-framing.md, per-agent turns/). Keeps the "
                   "campaign workspace, DM/player content, arcs, lore, AND all "
                   "DB rows + graph nodes.")
@click.option("--keep-workspace", is_flag=True,
              help="Drop DB rows + graph nodes but leave the filesystem campaign "
                   "workspace intact. For when you want to wipe persistence but "
                   "keep authored content for re-import.")
@click.option("--yes", is_flag=True, help="Do not prompt for confirmation.")
@click.pass_obj
def campaign_clean(
    cli: CliState,
    campaign_id: str,
    state_only: bool,
    keep_workspace: bool,
    yes: bool,
) -> None:
    """Remove a campaign: filesystem + Postgres rows + FalkorDB graph.

    Default: drop EVERYTHING (workspace dir, DB rows for the campaign,
    graph entities for the campaign). Use --state-only to wipe just the
    runtime state files (no DB/graph touch). Use --keep-workspace to
    drop DB+graph but keep the filesystem.
    """
    if state_only and keep_workspace:
        raise click.ClickException("--state-only and --keep-workspace are mutually exclusive")

    space = CampaignSpace.from_config(cli.config, campaign_id)
    workspace_exists = space.exists()
    if state_only and not workspace_exists:
        raise click.ClickException(f"Campaign {campaign_id!r} does not exist")

    if state_only:
        if not yes and not click.confirm(
            f"Clear runtime state for campaign {campaign_id!r}? "
            "(workspace, DM/player content, arcs, lore, DB, graph all remain)"
        ):
            raise click.Abort()
        cli.store.clear_state(campaign_id)
        click.echo(f"cleared runtime state for {campaign_id}")
        return

    actions = ["DB rows", "graph nodes"]
    if not keep_workspace:
        actions.append("filesystem workspace")
    if not yes and not click.confirm(
        f"Delete {', '.join(actions)} for campaign {campaign_id!r}?"
    ):
        raise click.Abort()

    # 1. Postgres
    try:
        from cli import db as _glass_db
        from cli.config import load_config as _load_glass_config

        toml_data = _load_glass_config()
        pg_config = _glass_db.load_pg_config(toml_data)
        with _glass_db.connect(pg_config) as conn:
            deleted_db = _glass_db.delete_campaign_data(conn, campaign_id)
        nonzero = {k: v for k, v in deleted_db.items() if v}
        click.echo(f"  db: {nonzero or 'no rows'}")
    except Exception as exc:
        click.secho(f"  db cleanup failed: {exc}", fg="yellow")

    # 2. FalkorDB
    try:
        from cli import graph as _glass_graph
        from cli.config import load_config as _load_glass_config

        toml_data = _load_glass_config()
        falkor_config = _glass_graph.load_falkor_config(toml_data)
        if _glass_graph.is_available(falkor_config):
            with _glass_graph.connect(falkor_config) as g:
                deleted_graph = _glass_graph.delete_campaign_graph(g, campaign_id)
            click.echo(f"  graph: {deleted_graph}")
        else:
            click.secho(
                f"  graph: skipped (FalkorDB not reachable at {falkor_config.describe()})",
                fg="yellow",
            )
    except Exception as exc:
        click.secho(f"  graph cleanup failed: {exc}", fg="yellow")

    # 3. Filesystem
    if keep_workspace:
        click.echo("  workspace: kept (--keep-workspace)")
    elif workspace_exists:
        cli.campaign_manager.clear(campaign_id)
        click.echo(f"  workspace: removed ({space.campaign_dir})")
    else:
        click.echo("  workspace: not present")


@campaign.command("clear-scene")
@click.argument("scene_id", required=False)
@click.option("--campaign", "campaign_id", default=None,
              help="Campaign id. Defaults to the latest.")
@click.option("--yes", is_flag=True, help="Do not prompt for confirmation.")
@click.pass_obj
def campaign_clear_scene(
    cli: CliState,
    scene_id: str | None,
    campaign_id: str | None,
    yes: bool,
) -> None:
    """Reset scene-framing.md so the DM has to reframe."""
    state = cli.store.load(campaign_id)
    target = scene_id or state.active_mode.scene_id
    if not yes and not click.confirm(f"Clear scene state for {state.campaign}:{target}?"):
        raise click.Abort()
    cleared = cli.store.clear_scene(state.campaign, target)
    click.echo(f"cleared scene state for {state.campaign}:{cleared}")


def _run_or_raise(
    cli: CliState,
    state,
    *,
    max_turns: int | None,
    dry_run: bool,
    resume_failed: bool,
) -> int:
    try:
        return cli.orchestrator.run_loop(
            state,
            max_turns=max_turns,
            dry_run=dry_run,
            resume_failed=resume_failed,
        )
    except TurnFailure as exc:
        detail = json.dumps(exc.failure, indent=2, sort_keys=True)
        raise click.ClickException(f"{exc}\n{detail}") from exc


if __name__ == "__main__":
    main()
