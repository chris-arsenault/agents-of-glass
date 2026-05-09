"""Entry point for the `aog` operator CLI."""

from __future__ import annotations

from pathlib import Path
import json

import click

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
    """Operate Agents of Glass sessions."""

    ctx.obj = CliState(str(config_path) if config_path else None)


@main.group()
def campaign() -> None:
    """Manage campaigns: bootstrap, list, clear."""


@campaign.command("bootstrap")
@click.argument("campaign_id")
@click.option(
    "--max-planning-turns",
    type=int,
    default=5,
    show_default=True,
    help="Hard cap on DM invocations during campaign planning.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Build context packages and commit synthetic turns without invoking Claude.",
)
@click.option(
    "--keep-cwd",
    is_flag=True,
    help="Keep successful per-turn ephemeral CWDs for inspection.",
)
@click.pass_obj
def campaign_bootstrap(
    cli: CliState,
    campaign_id: str,
    max_planning_turns: int,
    dry_run: bool,
    keep_cwd: bool,
) -> None:
    """Bootstrap a campaign end-to-end.

    Steps:
      1. Create campaigns/<id>/ from templates/.
      2. Invoke DM in campaign-planning mode (foundation + opening arc).
      3. [STUB] Character creation.
      4. [STUB] Active scene play.
    """

    # 1. Create campaign workspace
    click.secho(f"[1/4] Creating campaign workspace: {campaign_id}", fg="cyan")
    try:
        space = cli.campaign_manager.create(campaign_id)
    except FileExistsError as exc:
        raise click.ClickException(str(exc))
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc))
    click.echo(f"      workspace: {space.campaign_dir}")
    click.echo(f"      state:     {space.state_path}")

    # 2. Invoke DM for campaign planning
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
    click.echo(f"      session: {state.session_id}")

    try:
        turns_run = cli.orchestrator.run_loop(
            state,
            max_turns=max_planning_turns,
            dry_run=dry_run,
            keep_cwd=keep_cwd,
            resume_failed=False,
        )
    except TurnFailure as exc:
        detail = json.dumps(exc.failure, indent=2, sort_keys=True)
        raise click.ClickException(
            f"campaign planning failed: {exc}\n{detail}"
        ) from exc

    click.echo(f"      DM produced {turns_run} planning turn(s)")
    click.echo(f"      transcript: {cli.store.transcript_path(state.session_id)}")
    click.echo(f"      DM workspace: {space.campaign_dir / 'dm'}")

    # 3. STUB — character creation
    cli.campaign_manager.advance_phase(campaign_id, PHASE_CHARACTER_CREATION)
    click.secho("[3/4] [STUB] Character creation", fg="yellow")
    click.echo("              this is where the PCs are created")
    click.echo("              (DM writes campaign-intro; each player authors")
    click.echo("               character.md + intro entry; DM ratifies)")

    # 4. STUB — active scene play
    cli.campaign_manager.advance_phase(campaign_id, PHASE_ACTIVE)
    click.secho("[4/4] [STUB] Active scene play", fg="yellow")
    click.echo("              this is where regular scene play would begin")
    click.echo("              (DM creates scenes via glass scene create;")
    click.echo("               orchestrator runs scene loops)")

    click.echo()
    click.secho(
        f"Campaign '{campaign_id}' bootstrapped through campaign_planning.",
        fg="green",
    )
    click.echo(f"State file: {space.state_path}")


@campaign.command("list")
@click.pass_obj
def campaign_list(cli: CliState) -> None:
    campaigns = cli.campaign_manager.list_campaigns()
    if not campaigns:
        click.echo("no campaigns")
        return
    for campaign_id in campaigns:
        try:
            state = cli.campaign_manager.load_state(campaign_id)
            phase = state.get("phase", "?")
        except Exception:
            phase = "?"
        click.echo(f"{campaign_id:<32} phase: {phase}")


@campaign.command("show")
@click.argument("campaign_id")
@click.pass_obj
def campaign_show(cli: CliState, campaign_id: str) -> None:
    space = CampaignSpace.from_config(cli.config, campaign_id)
    if not space.exists():
        raise click.ClickException(f"Campaign {campaign_id!r} does not exist")
    state = cli.campaign_manager.load_state(campaign_id)
    click.echo(json.dumps(state, indent=2, sort_keys=True))
    click.echo(f"\nworkspace: {space.campaign_dir}")


@campaign.command("clear")
@click.argument("campaign_id")
@click.option("--yes", is_flag=True, help="Do not prompt for confirmation.")
@click.pass_obj
def campaign_clear(cli: CliState, campaign_id: str, yes: bool) -> None:
    space = CampaignSpace.from_config(cli.config, campaign_id)
    if not space.exists():
        raise click.ClickException(f"Campaign {campaign_id!r} does not exist")
    if not yes and not click.confirm(
        f"Delete campaign {campaign_id!r} at {space.campaign_dir}?"
    ):
        raise click.Abort()
    cli.campaign_manager.clear(campaign_id)
    click.echo(f"cleared campaign {campaign_id}")


@main.group()
def session() -> None:
    """Create, inspect, and run sessions."""


@session.command("new")
@click.option("--campaign", required=True, help="Campaign name.")
@click.option("--mode", default="worldbuilding", show_default=True, help="Initial mode.")
@click.option("--scene", default="session-zero", show_default=True, help="Initial scene id.")
@click.pass_obj
def session_new(cli: CliState, campaign: str, mode: str, scene: str) -> None:
    state = cli.store.create_session(campaign, mode, scene)
    click.echo(f"created session {state.session_id}")
    click.echo(f"path: {cli.store.session_dir(state.session_id)}")


@session.command("list")
@click.pass_obj
def session_list(cli: CliState) -> None:
    states = cli.store.list_sessions()
    if not states:
        click.echo("no sessions")
        return
    click.echo(summarize_states(states))


@session.command("show")
@click.argument("session_id", required=False)
@click.option("--json", "as_json", is_flag=True, help="Print raw state JSON.")
@click.pass_obj
def session_show(cli: CliState, session_id: str | None, as_json: bool) -> None:
    state = cli.store.load(session_id)
    if as_json:
        click.echo(json.dumps(state.to_dict(), indent=2, sort_keys=True))
        return
    active = state.active_mode
    click.echo(f"session: {state.session_id}")
    click.echo(f"campaign: {state.campaign}")
    click.echo(f"status: {state.status}")
    click.echo(f"turn: {state.turn_number}")
    click.echo(f"active mode: {active.mode}")
    click.echo(f"scene: {active.scene_id}")
    click.echo(f"mode budget remaining: {active.turn_budget_remaining}")
    click.echo(f"last speaker: {state.last_speaker or '-'}")
    if state.failure:
        click.echo("failure:")
        click.echo(json.dumps(state.failure, indent=2, sort_keys=True))


@session.command("prepare-turn")
@click.argument("session_id", required=False)
@click.pass_obj
def session_prepare_turn(cli: CliState, session_id: str | None) -> None:
    state = cli.store.load(session_id)
    package = cli.orchestrator.prepare_turn(state)
    click.echo(f"prepared {package.turn_id}")
    click.echo(f"cwd: {package.cwd}")


@session.command("run")
@click.argument("session_id", required=False)
@click.option("--max-turns", type=int, default=None, help="Turns to run in this invocation.")
@click.option("--dry-run", is_flag=True, help="Build and commit synthetic turns without Claude.")
@click.option("--keep-cwd", is_flag=True, help="Keep successful per-turn CWDs for inspection.")
@click.pass_obj
def session_run(
    cli: CliState,
    session_id: str | None,
    max_turns: int | None,
    dry_run: bool,
    keep_cwd: bool,
) -> None:
    state = cli.store.load(session_id)
    turns = _run_or_raise(
        cli,
        state,
        max_turns=max_turns,
        dry_run=dry_run,
        keep_cwd=keep_cwd,
        resume_failed=False,
    )
    click.echo(f"ran {turns} turn(s)")


@session.command("resume")
@click.argument("session_id", required=False)
@click.option("--max-turns", type=int, default=None, help="Turns to run in this invocation.")
@click.option("--dry-run", is_flag=True, help="Build and commit synthetic turns without Claude.")
@click.option("--keep-cwd", is_flag=True, help="Keep successful per-turn CWDs for inspection.")
@click.pass_obj
def session_resume(
    cli: CliState,
    session_id: str | None,
    max_turns: int | None,
    dry_run: bool,
    keep_cwd: bool,
) -> None:
    state = cli.store.load(session_id)
    turns = _run_or_raise(
        cli,
        state,
        max_turns=max_turns,
        dry_run=dry_run,
        keep_cwd=keep_cwd,
        resume_failed=True,
    )
    click.echo(f"resumed and ran {turns} turn(s)")


@main.group()
def clear() -> None:
    """Clear operator-managed session state."""


@clear.command("session")
@click.argument("session_id", required=False)
@click.option("--yes", is_flag=True, help="Do not prompt for confirmation.")
@click.pass_obj
def clear_session(cli: CliState, session_id: str | None, yes: bool) -> None:
    state = cli.store.load(session_id)
    if not yes and not click.confirm(f"Delete session {state.session_id}?"):
        raise click.Abort()
    cli.store.clear_session(state.session_id)
    click.echo(f"cleared session {state.session_id}")


@clear.command("campaign")
@click.argument("campaign")
@click.option("--yes", is_flag=True, help="Do not prompt for confirmation.")
@click.pass_obj
def clear_campaign(cli: CliState, campaign: str, yes: bool) -> None:
    matching = [
        state.session_id
        for state in cli.store.list_sessions()
        if state.campaign == campaign
    ]
    if not matching:
        click.echo(f"no sessions found for campaign {campaign!r}")
        return
    if not yes and not click.confirm(f"Delete {len(matching)} session(s) for {campaign!r}?"):
        raise click.Abort()
    removed = cli.store.clear_campaign(campaign)
    click.echo(f"cleared {len(removed)} session(s)")


@clear.command("scene")
@click.argument("scene_id", required=False)
@click.option("--session-id", default=None, help="Session id. Defaults to latest session.")
@click.option("--yes", is_flag=True, help="Do not prompt for confirmation.")
@click.pass_obj
def clear_scene(
    cli: CliState,
    scene_id: str | None,
    session_id: str | None,
    yes: bool,
) -> None:
    state = cli.store.load(session_id)
    target = scene_id or state.active_mode.scene_id
    if not yes and not click.confirm(f"Clear scene state for {state.session_id}:{target}?"):
        raise click.Abort()
    cleared = cli.store.clear_scene(state.session_id, target)
    click.echo(f"cleared scene state for {state.session_id}:{cleared}")


def _run_or_raise(
    cli: CliState,
    state,
    *,
    max_turns: int | None,
    dry_run: bool,
    keep_cwd: bool,
    resume_failed: bool,
) -> int:
    try:
        return cli.orchestrator.run_loop(
            state,
            max_turns=max_turns,
            dry_run=dry_run,
            keep_cwd=keep_cwd,
            resume_failed=resume_failed,
        )
    except TurnFailure as exc:
        detail = json.dumps(exc.failure, indent=2, sort_keys=True)
        raise click.ClickException(f"{exc}\n{detail}") from exc


if __name__ == "__main__":
    main()
