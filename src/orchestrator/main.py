"""Entry point for the `aog` operator CLI."""

from __future__ import annotations

from pathlib import Path
import json

import click

from .config import load_config
from .runner import Orchestrator, TurnFailure
from .store import SessionStore, summarize_states


class CliState:
    def __init__(self, config_path: str | None):
        self.config = load_config(config_path)
        self.store = SessionStore(self.config)
        self.orchestrator = Orchestrator(self.config, self.store)


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
