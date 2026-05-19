"""Entry point for the `aog` operator CLI."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import os
import shutil

import click

from .campaign import (
    CampaignManager,
    CampaignSpace,
    PHASE_ACTIVE,
    PHASE_CHARACTER_CREATION,
    PHASE_ORGANIZATION_BOOTSTRAP,
    PHASE_PLANNING,
)
from .config import config_env_value, load_config
from .runner import Orchestrator, TurnFailure
from .state import PLAYER_IDS
from .store import SessionStore

MODE_INTERMISSION = "intermission"
MODE_SCENE_PREP = "scene-prep"


# umask 002 so subdirs the orchestrator creates inside the campaign
# workspace (notably per-turn artifact dirs under <agent>/turns/) are
# group-writable. Combined with setgid + group=aog-<player> on the
# parent turns/, this lets the player Unix user write their TURN.md
# into a subdir the orchestrator (running as operator) created.
os.umask(0o002)


class CliState:
    def __init__(self, config_path: str | None):
        from cli.local_env import load_repo_env

        load_repo_env()
        self.config = load_config(config_path)
        self.store = SessionStore(self.config)
        self.orchestrator = Orchestrator(self.config, self.store)
        self.campaign_manager = CampaignManager(self.config)


def _rebuild_cli_state(cli: CliState) -> None:
    cli.store = SessionStore(cli.config)
    cli.orchestrator = Orchestrator(cli.config, cli.store)
    cli.campaign_manager = CampaignManager(cli.config)


def _apply_cli_overrides(
    cli: CliState,
    *,
    use_session_id: bool | None = None,
    use_codex: bool | None = None,
    skip_player_persona: bool | None = None,
    turn_minimum_seconds: int | None = None,
) -> None:
    if (
        use_session_id is None
        and use_codex is None
        and skip_player_persona is None
        and turn_minimum_seconds is None
    ):
        return
    provider = cli.config.agent_provider
    if use_codex is not None:
        provider = "mixed-codex" if use_codex else "claude"
    session_flag = (
        cli.config.claude.use_session_id
        if use_session_id is None
        else use_session_id
    )
    cli.config = replace(
        cli.config,
        agent_provider=provider,
        skip_player_persona=(
            cli.config.skip_player_persona
            if skip_player_persona is None
            else skip_player_persona
        ),
        claude=replace(cli.config.claude, use_session_id=session_flag),
        orchestrator=(
            cli.config.orchestrator
            if turn_minimum_seconds is None
            else replace(
                cli.config.orchestrator,
                turn_minimum_seconds=max(int(turn_minimum_seconds), 0),
            )
        ),
    )
    _rebuild_cli_state(cli)


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
def api() -> None:
    """Manage the local glass API daemon."""


@api.command("start")
@click.option("--url", default=None, help="API URL. Defaults to GLASS_API_URL or localhost.")
@click.option("--host", "bind_host", default=None, help="Bind host for the daemon.")
@click.pass_obj
def api_start(cli: CliState, url: str | None, bind_host: str | None) -> None:
    """Start the detached local glass API daemon."""
    from cli.api_daemon import start_daemon

    _echo_api_daemon(
        start_daemon(
            url=_api_url(url),
            config_path=config_env_value(cli.config),
            bind_host=bind_host,
        )
    )


@api.command("restart")
@click.option("--url", default=None, help="API URL. Defaults to GLASS_API_URL or localhost.")
@click.option("--host", "bind_host", default=None, help="Bind host for the daemon.")
@click.pass_obj
def api_restart(cli: CliState, url: str | None, bind_host: str | None) -> None:
    """Restart the detached local glass API daemon with current code/config."""
    from cli.api_daemon import restart_daemon

    _echo_api_daemon(
        restart_daemon(
            url=_api_url(url),
            config_path=config_env_value(cli.config),
            bind_host=bind_host,
        )
    )


@api.command("stop")
@click.option("--url", default=None, help="API URL. Defaults to GLASS_API_URL or localhost.")
def api_stop(url: str | None) -> None:
    """Stop the detached local glass API daemon."""
    from cli.api_daemon import stop_daemon

    _echo_api_daemon(stop_daemon(url=_api_url(url)))


@api.command("status")
@click.option("--url", default=None, help="API URL. Defaults to GLASS_API_URL or localhost.")
def api_status(url: str | None) -> None:
    """Show local glass API daemon status."""
    from cli.api_daemon import status_daemon

    _echo_api_daemon(status_daemon(url=_api_url(url)))


@main.group("web-api")
def web_api() -> None:
    """Manage the local read-only web API daemon."""


@web_api.command("start")
@click.option("--url", default=None, help="Web API URL. Defaults to AOG_WEB_API_URL or localhost.")
@click.option("--host", "bind_host", default=None, help="Bind host for the daemon.")
@click.pass_obj
def web_api_start(cli: CliState, url: str | None, bind_host: str | None) -> None:
    """Start the detached read-only web API daemon."""
    from cli.web_api_daemon import start_daemon

    _echo_service_daemon(
        start_daemon(
            url=_web_api_url(url),
            config_path=config_env_value(cli.config),
            bind_host=bind_host,
        ),
        "web API",
    )


@web_api.command("restart")
@click.option("--url", default=None, help="Web API URL. Defaults to AOG_WEB_API_URL or localhost.")
@click.option("--host", "bind_host", default=None, help="Bind host for the daemon.")
@click.pass_obj
def web_api_restart(cli: CliState, url: str | None, bind_host: str | None) -> None:
    """Restart the detached read-only web API daemon."""
    from cli.web_api_daemon import restart_daemon

    _echo_service_daemon(
        restart_daemon(
            url=_web_api_url(url),
            config_path=config_env_value(cli.config),
            bind_host=bind_host,
        ),
        "web API",
    )


@web_api.command("stop")
@click.option("--url", default=None, help="Web API URL. Defaults to AOG_WEB_API_URL or localhost.")
def web_api_stop(url: str | None) -> None:
    """Stop the detached read-only web API daemon."""
    from cli.web_api_daemon import stop_daemon

    _echo_service_daemon(stop_daemon(url=_web_api_url(url)), "web API")


@web_api.command("status")
@click.option("--url", default=None, help="Web API URL. Defaults to AOG_WEB_API_URL or localhost.")
def web_api_status(url: str | None) -> None:
    """Show local read-only web API daemon status."""
    from cli.web_api_daemon import status_daemon

    _echo_service_daemon(status_daemon(url=_web_api_url(url)), "web API")


@main.group()
def web() -> None:
    """Manage the local web UI and read-only web API."""


@web.command("start")
@click.argument("campaign_id", required=False)
@click.option("--url", default=None, help="Web UI URL. Defaults to localhost:26000.")
@click.pass_obj
def web_start(cli: CliState, campaign_id: str | None, url: str | None) -> None:
    """Start the local web UI and read-only web API if needed."""

    if campaign_id:
        click.echo("campaign selection is handled in the web UI; ignoring start argument")
    _echo_webui_daemon(_start_webui(cli, url=url))


@web.command("restart")
@click.argument("campaign_id", required=False)
@click.option("--url", default=None, help="Web UI URL. Defaults to localhost:26000.")
@click.pass_obj
def web_restart(cli: CliState, campaign_id: str | None, url: str | None) -> None:
    """Restart the local web UI process."""

    from .webui_daemon import restart_webui

    if campaign_id:
        click.echo("campaign selection is handled in the web UI; ignoring restart argument")
    _echo_webui_daemon(
        restart_webui(
            repo_root=cli.config.repo_root,
            config_path=config_env_value(cli.config),
            url=url or _webui_url(None),
            web_api_url=_web_api_url(None),
        )
    )


@web.command("stop")
@click.option("--url", default=None, help="Web UI URL. Defaults to localhost:26000.")
@click.pass_obj
def web_stop(cli: CliState, url: str | None) -> None:
    """Stop managed local web UI processes."""

    from .webui_daemon import stop_webui

    _echo_webui_daemon(
        stop_webui(
            repo_root=cli.config.repo_root,
            url=url or _webui_url(None),
            web_api_url=_web_api_url(None),
        )
    )


@web.command("status")
@click.option("--url", default=None, help="Web UI URL. Defaults to localhost:26000.")
@click.pass_obj
def web_status(cli: CliState, url: str | None) -> None:
    """Show local web UI status."""

    from .webui_daemon import status_webui

    _echo_webui_daemon(
        status_webui(
            repo_root=cli.config.repo_root,
            url=url or _webui_url(None),
            web_api_url=_web_api_url(None),
        )
    )


@main.group()
def campaign() -> None:
    """Manage campaigns: run, inspect, checkpoint, and clear."""


def _run_campaign_lifecycle(
    cli: CliState,
    campaign_id: str | None,
    *,
    max_organization_turns: int,
    max_planning_turns: int,
    max_creation_turns: int,
    max_active_turns: int | None,
    review_stop_budget: int | None,
    skip_character_creation: bool,
    dry_run: bool,
) -> None:
    """Create or continue a campaign from durable phase/mode state."""

    from .campaign import CampaignSpace

    _ensure_operator_groups_active()
    _ensure_db_migrated(cli)
    _ensure_falkor_reachable(cli)

    if campaign_id is None:
        campaign_id = cli.store.latest_campaign()
        if campaign_id is None:
            raise click.ClickException(
                "campaign id required when no campaign exists; "
                "run `aog campaign run <campaign-id>`"
            )
    _ensure_glass_api_for_run(cli)

    space = CampaignSpace.from_config(cli.config, campaign_id)
    if space.exists():
        click.secho(f"[1/5] Resuming existing campaign: {campaign_id}", fg="cyan")
        try:
            cm_state = cli.campaign_manager.load_state(campaign_id)
        except FileNotFoundError as exc:
            raise click.ClickException(str(exc))
        # Re-apply permissions on resume in case the perms helper has
        # been updated since this workspace was provisioned.
        from . import permissions as _permissions
        _permissions.apply_campaign_permissions(space.campaign_dir)
    else:
        click.secho(f"[1/5] Creating campaign workspace: {campaign_id}", fg="cyan")
        try:
            space = cli.campaign_manager.create(campaign_id)
            cm_state = cli.campaign_manager.load_state(campaign_id)
        except (FileExistsError, FileNotFoundError) as exc:
            raise click.ClickException(str(exc))
    click.echo(f"      workspace: {space.campaign_dir}")
    click.echo("      state:     Postgres runtime row")

    # Phase 2: organization bootstrap
    cm_state = _run_bootstrap_phase(
        cli,
        campaign_id=campaign_id,
        cm_state=cm_state,
        phase_name=PHASE_ORGANIZATION_BOOTSTRAP,
        mode_name="organization-bootstrap",
        scene_id="organization-bootstrap",
        phase_label="organization bootstrap",
        step_label="[2/6] Organization bootstrap",
        start_message=(
            "[2/6] Invoking Mara for organization bootstrap "
            f"(max {max_organization_turns} turn)"
        ),
        max_turns=max_organization_turns,
        checkpoint_label="after-organization-bootstrap",
        next_phase=PHASE_CHARACTER_CREATION,
        dry_run=dry_run,
        validate=_validate_organization_bootstrap_complete,
    )
    # Phase 3: character creation
    if skip_character_creation:
        click.secho("[3/6] Character creation skipped (--skip-character-creation).",
                    fg="yellow")
        click.echo()
        click.secho(
            f"Campaign '{campaign_id}' advanced through organization_bootstrap.",
            fg="green",
        )
        click.echo(f"Next phase: {PHASE_CHARACTER_CREATION}")
        click.echo("Runtime state: Postgres runtime row")
        return
    cm_state = _run_bootstrap_phase(
        cli,
        campaign_id=campaign_id,
        cm_state=cm_state,
        phase_name=PHASE_CHARACTER_CREATION,
        mode_name="character-creation",
        scene_id="character-creation",
        phase_label="character creation",
        step_label="[3/6] Character creation",
        start_message=(
            f"[3/6] Invoking players + DM for character creation "
            f"(max {max_creation_turns} turns)"
        ),
        max_turns=max_creation_turns,
        checkpoint_label="after-character-creation",
        next_phase=PHASE_PLANNING,
        dry_run=dry_run,
        validate=_validate_character_creation_complete,
    )
    # Phase 4: campaign planning
    cm_state = _run_bootstrap_phase(
        cli,
        campaign_id=campaign_id,
        cm_state=cm_state,
        phase_name=PHASE_PLANNING,
        mode_name="campaign-planning",
        scene_id="planning",
        phase_label="campaign planning",
        step_label="[4/5] Campaign planning",
        start_message=(
            f"[4/5] Invoking Mara for campaign planning "
            f"(max {max_planning_turns} turns)"
        ),
        max_turns=max_planning_turns,
        checkpoint_label="after-campaign-planning",
        next_phase=PHASE_ACTIVE,
        dry_run=dry_run,
        validate=_validate_campaign_planning_complete,
    )
    # Phase 5: active campaign handoff
    if cm_state.get("phase") != PHASE_ACTIVE:
        cm_state = cli.campaign_manager.advance_phase(campaign_id, PHASE_ACTIVE)
    click.secho("[5/5] Active campaign", fg="green")
    active_state = cli.store.load(campaign_id)
    turns_remaining = max_active_turns
    while True:
        if turns_remaining is not None and turns_remaining <= 0:
            click.echo("      active turn cap reached")
            return

        if not active_state.has_active_mode:
            started = _start_next_active_mode(cli, campaign_id=campaign_id)
            if started:
                active_state = cli.store.load(campaign_id)
            else:
                active_state.mark_ready()
                cli.store.save(active_state)
                click.echo("      no active mode; no arc is available for automatic setup")
                click.echo()
                click.secho(
                    f"Campaign '{campaign_id}' is ready.",
                    fg="green",
                )
                click.echo("Runtime state: Postgres runtime row")
                return

        mode_at_start = active_state.active_mode.mode
        run_limit = turns_remaining
        auto_end_intermission = False
        if mode_at_start == MODE_INTERMISSION:
            remaining = active_state.active_mode.turn_budget_remaining
            if remaining is None:
                remaining = cli.config.caps.budget_for(MODE_INTERMISSION) or 15
            if turns_remaining is None:
                run_limit = remaining
                auto_end_intermission = True
            else:
                run_limit = min(turns_remaining, remaining)
                auto_end_intermission = turns_remaining >= remaining
        turns = _run_or_raise(
            cli,
            active_state,
            max_turns=run_limit,
            dry_run=dry_run,
            resume_failed=True,
        )
        if turns_remaining is not None:
            turns_remaining -= turns

        after = cli.store.load(campaign_id)
        if mode_at_start == MODE_INTERMISSION:
            if (
                auto_end_intermission
                and after.has_active_mode
                and after.active_mode.mode == MODE_INTERMISSION
                and not dry_run
            ):
                _end_current_mode(
                    cli,
                    campaign_id=campaign_id,
                    expected_mode=MODE_INTERMISSION,
                    reason="intermission turn cap reached",
                )
                after = cli.store.load(campaign_id)
            click.echo(f"      ran {turns} intermission turn(s)")
            if turns_remaining is not None and turns_remaining <= 0:
                click.echo("      active turn cap reached")
                return
            if after.has_active_mode:
                return
            if not after.has_active_mode:
                should_continue, review_stop_budget = _consume_review_stop(
                    review_stop_budget
                )
                if should_continue:
                    click.echo("      skipped review stop after intermission")
                    active_state = after
                    continue
                click.echo("      intermission complete; next run will start scene prep")
                return

        click.echo(f"      ran {turns} active-play turn(s)")
        if turns_remaining is not None and turns_remaining <= 0:
            click.echo("      active turn cap reached")
            return
        if after.has_active_mode:
            return
        should_continue, review_stop_budget = _consume_review_stop(review_stop_budget)
        if should_continue:
            click.echo("      skipped active-play review stop")
            active_state = after
            continue
        return


def _phase_completed(cm_state: dict, phase_name: str) -> bool:
    """True if any phase_history entry for this phase has a completed_at."""
    for entry in cm_state.get("phase_history", []):
        if entry.get("phase") == phase_name and "completed_at" in entry:
            return True
    return False


def _start_next_active_mode(cli: CliState, *, campaign_id: str) -> str | None:
    """Start the next no-intervention active-play bridge mode.

    A no-mode active campaign is an intentional pause surface. Intermission is
    an act boundary, not a scene boundary: after intermission closes we
    open scene prep; inside an already-active act we recover into scene prep
    rather than opening another intermission.
    """

    latest_mode = _latest_turn_mode(cli, campaign_id)
    try:
        cm_state = cli.campaign_manager.load_state(campaign_id)
    except Exception:
        cm_state = {}
    arc_id = _active_main_arc_id(cm_state)
    next_mode = _next_mode_after_no_active_mode(
        latest_mode,
        active_arc=arc_id,
        has_prior_intermission=_has_intermission_turns(cli, campaign_id),
    )
    if next_mode == MODE_INTERMISSION:
        scene_id = _next_intermission_scene_id(cli, campaign_id)
        _dm_glass(cli, campaign_id, ["mode", "start", MODE_INTERMISSION, scene_id])
        _queue_mara_next(cli, campaign_id)
        click.echo(
            f"      started intermission: {scene_id} "
            "(Mara queued first, 15-turn cap)"
        )
        return MODE_INTERMISSION

    if next_mode == MODE_SCENE_PREP:
        arc_id = arc_id or _ensure_main_arc_active(cli, campaign_id)
        scene_id = f"{arc_id or 'next-act'}-setup"
        _dm_glass(cli, campaign_id, ["mode", "start", MODE_SCENE_PREP, scene_id])
        _queue_mara_next(cli, campaign_id)
        click.echo(f"      started scene prep: {scene_id} (Mara queued first)")
        return MODE_SCENE_PREP

    return None


def _next_mode_after_no_active_mode(
    latest_turn_mode: str | None,
    *,
    active_arc: str | None = None,
    has_prior_intermission: bool = False,
) -> str:
    latest = (latest_turn_mode or "").lower()
    active_play_modes = {"scene-play", "action"}
    if latest == MODE_INTERMISSION:
        return MODE_SCENE_PREP
    if active_arc and latest not in active_play_modes:
        return MODE_SCENE_PREP
    if active_arc and has_prior_intermission:
        return MODE_SCENE_PREP
    return MODE_INTERMISSION


def _active_main_arc_id(cm_state: dict) -> str | None:
    closed = {str(arc_id) for arc_id in cm_state.get("closed_arcs", [])}
    active_arc = str(cm_state.get("active_arc") or "")
    if active_arc and active_arc not in closed:
        return active_arc
    return None


def _has_intermission_turns(cli: CliState, campaign_id: str) -> bool:
    from cli import db as _glass_db
    from cli.config import load_config as _load_glass_config

    previous_config = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = config_env_value(cli.config)
    try:
        toml_data = _load_glass_config()
        pg_config = _glass_db.load_pg_config(toml_data)
        with _glass_db.connect(pg_config) as conn:
            return bool(
                _glass_db.turn_list(
                    conn,
                    campaign_id=campaign_id,
                    mode=MODE_INTERMISSION,
                    limit=1,
                )
            )
    finally:
        if previous_config is None:
            os.environ.pop("GLASS_CONFIG", None)
        else:
            os.environ["GLASS_CONFIG"] = previous_config


def _consume_review_stop(review_stop_budget: int | None) -> tuple[bool, int | None]:
    """Return whether to continue past this review stop and the new budget.

    `None` means unlimited review-stop skipping for this run. Non-negative
    integers are consumed one stop at a time.
    """
    if review_stop_budget is None:
        return True, None
    if review_stop_budget <= 0:
        return False, review_stop_budget
    return True, review_stop_budget - 1


def _latest_turn_mode(cli: CliState, campaign_id: str) -> str | None:
    from cli import db as _glass_db
    from cli.config import load_config as _load_glass_config

    previous_config = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = config_env_value(cli.config)
    try:
        toml_data = _load_glass_config()
        pg_config = _glass_db.load_pg_config(toml_data)
        with _glass_db.connect(pg_config) as conn:
            turns = _glass_db.turn_list(
                conn,
                campaign_id=campaign_id,
                limit=1,
                latest=True,
            )
    finally:
        if previous_config is None:
            os.environ.pop("GLASS_CONFIG", None)
        else:
            os.environ["GLASS_CONFIG"] = previous_config
    if not turns:
        return None
    return str(turns[0].get("mode") or "")


def _next_intermission_scene_id(cli: CliState, campaign_id: str) -> str:
    from cli import db as _glass_db
    from cli.config import load_config as _load_glass_config

    previous_config = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = config_env_value(cli.config)
    try:
        toml_data = _load_glass_config()
        pg_config = _glass_db.load_pg_config(toml_data)
        with _glass_db.connect(pg_config) as conn:
            turns = _glass_db.turn_list(
                conn,
                campaign_id=campaign_id,
                mode=MODE_INTERMISSION,
                limit=100000,
            )
    finally:
        if previous_config is None:
            os.environ.pop("GLASS_CONFIG", None)
        else:
            os.environ["GLASS_CONFIG"] = previous_config

    seen = {
        str(turn.get("scene_id"))
        for turn in turns
        if str(turn.get("scene_id") or "").startswith("intermission-")
    }
    return f"intermission-{len(seen) + 1:02d}"


def _ensure_main_arc_active(cli: CliState, campaign_id: str) -> str | None:
    try:
        cm_state = cli.campaign_manager.load_state(campaign_id)
    except Exception:
        return None
    closed = {str(arc_id) for arc_id in cm_state.get("closed_arcs", [])}
    active_arc = str(cm_state.get("active_arc") or "")
    if active_arc and active_arc not in closed:
        return active_arc
    candidates = [
        str(arc_id)
        for arc_id in cm_state.get("arcs", [])
        if str(arc_id) and str(arc_id) not in closed
    ]
    if not candidates:
        return None
    chosen = candidates[0]
    _dm_glass(cli, campaign_id, ["arc", "activate", chosen])
    click.echo(f"      active arc: {chosen}")
    return chosen


def _queue_mara_next(cli: CliState, campaign_id: str) -> None:
    try:
        _dm_glass(cli, campaign_id, ["turn", "clear-handoff"])
    except click.ClickException:
        # Clearing is best-effort; the handoff below is what makes Mara next.
        pass
    _dm_glass(cli, campaign_id, ["turn", "handoff", "dm"])


def _end_current_mode(
    cli: CliState,
    *,
    campaign_id: str,
    expected_mode: str,
    reason: str,
) -> None:
    state = cli.store.load(campaign_id)
    if not state.has_active_mode or state.active_mode.mode != expected_mode:
        return
    _dm_glass(cli, campaign_id, ["mode", "end"])
    click.echo(f"      ended {expected_mode}: {reason}")


def _dm_glass(cli: CliState, campaign_id: str, args: list[str]) -> None:
    try:
        cli.store.glass.invoke(args, role="dm", campaign=campaign_id)
    except Exception as exc:
        joined = " ".join(args)
        raise click.ClickException(f"glass {joined} failed: {exc}") from exc


def _run_bootstrap_phase(
    cli: CliState,
    *,
    campaign_id: str,
    cm_state: dict,
    phase_name: str,
    mode_name: str,
    scene_id: str,
    phase_label: str,
    step_label: str,
    start_message: str,
    max_turns: int,
    checkpoint_label: str,
    next_phase: str,
    dry_run: bool,
    validate,
) -> dict:
    if _phase_completed(cm_state, phase_name):
        click.secho(f"{step_label} already complete; skipping.", fg="yellow")
        return cm_state

    finalized = _finalize_ended_bootstrap_phase(
        cli,
        campaign_id=campaign_id,
        cm_state=cm_state,
        phase_name=phase_name,
        mode_name=mode_name,
        scene_id=scene_id,
        phase_label=phase_label,
        checkpoint_label=checkpoint_label,
        next_phase=next_phase,
        dry_run=dry_run,
        validate=validate,
    )
    if finalized is not None:
        return finalized

    click.secho(start_message, fg="cyan")
    if cm_state.get("phase") != phase_name:
        cm_state = cli.campaign_manager.advance_phase(campaign_id, phase_name)
    state = cli.store.create_session(
        campaign=campaign_id,
        initial_mode=mode_name,
        initial_scene=scene_id,
    )
    try:
        turns_run = cli.orchestrator.run_loop(
            state,
            max_turns=max_turns,
            dry_run=dry_run,
            resume_failed=True,
        )
    except TurnFailure as exc:
        if _recover_bootstrap_phase_after_budget_exhaustion(
            cli,
            campaign_id=campaign_id,
            mode_name=mode_name,
            phase_label=phase_label,
            checkpoint_label=checkpoint_label,
            next_phase=next_phase,
            dry_run=dry_run,
            validate=validate,
            failure=exc.failure,
        ):
            return cli.campaign_manager.load_state(campaign_id)
        detail = json.dumps(exc.failure, indent=2, sort_keys=True)
        raise click.ClickException(f"{phase_label} failed: {exc}\n{detail}") from exc
    runtime_state = cli.store.load(campaign_id)
    _require_bootstrap_mode_ended(
        cli,
        campaign_id=campaign_id,
        mode_name=mode_name,
        scene_id=scene_id,
        phase_label=phase_label,
        turns_run=turns_run,
    )
    if validate is not None and not dry_run:
        validate(cli, campaign_id)
    click.echo(f"      ran {turns_run} {phase_label} turn(s)")
    click.echo(f"      transcript: {cli.store.transcript_path(state.campaign)}")
    return _checkpoint_and_advance_bootstrap_phase(
        cli,
        campaign_id=campaign_id,
        checkpoint_label=checkpoint_label,
        next_phase=next_phase,
    )


def _recover_bootstrap_phase_after_budget_exhaustion(
    cli: CliState,
    *,
    campaign_id: str,
    mode_name: str,
    phase_label: str,
    checkpoint_label: str,
    next_phase: str,
    dry_run: bool,
    validate,
    failure: dict,
) -> bool:
    if str(failure.get("reason") or "") != "mode_budget_exhausted":
        return False
    if dry_run or validate is None:
        return False
    try:
        validate(cli, campaign_id)
    except click.ClickException:
        return False
    click.secho(
        f"{phase_label} validated after mode budget exhaustion; ending mode and finalizing phase.",
        fg="yellow",
    )
    _end_current_mode(
        cli,
        campaign_id=campaign_id,
        expected_mode=mode_name,
        reason="phase validation already passes",
    )
    _checkpoint_and_advance_bootstrap_phase(
        cli,
        campaign_id=campaign_id,
        checkpoint_label=checkpoint_label,
        next_phase=next_phase,
    )
    return True


def _finalize_ended_bootstrap_phase(
    cli: CliState,
    *,
    campaign_id: str,
    cm_state: dict,
    phase_name: str,
    mode_name: str,
    scene_id: str,
    phase_label: str,
    checkpoint_label: str,
    next_phase: str,
    dry_run: bool,
    validate,
) -> dict | None:
    """Recover after a bootstrap mode ended but phase finalization stopped."""

    if cm_state.get("phase") != phase_name:
        return None
    if _phase_completed(cm_state, phase_name):
        return None

    try:
        runtime_state = cli.store.load(campaign_id)
    except Exception:
        return None
    if any(
        frame.mode == mode_name and frame.scene_id == scene_id
        for frame in runtime_state.mode_stack
    ):
        return None
    if not _bootstrap_mode_has_turns(
        cli,
        campaign_id=campaign_id,
        mode_name=mode_name,
        scene_id=scene_id,
    ):
        return None

    if validate is not None and not dry_run:
        try:
            validate(cli, campaign_id)
        except click.ClickException:
            return None

    click.secho(
        f"{phase_label} mode already ended; finalizing phase.",
        fg="yellow",
    )
    return _checkpoint_and_advance_bootstrap_phase(
        cli,
        campaign_id=campaign_id,
        checkpoint_label=checkpoint_label,
        next_phase=next_phase,
    )


def _checkpoint_and_advance_bootstrap_phase(
    cli: CliState,
    *,
    campaign_id: str,
    checkpoint_label: str,
    next_phase: str,
) -> dict:
    runtime_state = cli.store.load(campaign_id)
    runtime_state.mark_ready()
    cli.store.save(runtime_state)
    checkpoint = _checkpoint_or_raise(
        cli,
        campaign_id,
        label=checkpoint_label,
    )
    click.echo(f"      checkpoint: {checkpoint['checkpoint_id']}")
    return cli.campaign_manager.advance_phase(campaign_id, next_phase)


def _bootstrap_mode_has_turns(
    cli: CliState,
    *,
    campaign_id: str,
    mode_name: str,
    scene_id: str,
) -> bool:
    from cli import db as _glass_db
    from cli.config import load_config as _load_glass_config

    previous_config = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = config_env_value(cli.config)
    try:
        toml_data = _load_glass_config()
        pg_config = _glass_db.load_pg_config(toml_data)
        with _glass_db.connect(pg_config) as conn:
            turns = _glass_db.turn_list(
                conn,
                campaign_id=campaign_id,
                scene=scene_id,
                mode=mode_name,
                limit=1,
                latest=True,
            )
    finally:
        if previous_config is None:
            os.environ.pop("GLASS_CONFIG", None)
        else:
            os.environ["GLASS_CONFIG"] = previous_config
    return bool(turns)


def _require_bootstrap_mode_ended(
    cli: CliState,
    *,
    campaign_id: str,
    mode_name: str,
    scene_id: str,
    phase_label: str,
    turns_run: int,
) -> None:
    state = cli.store.load(campaign_id)
    still_active = any(
        frame.mode == mode_name and frame.scene_id == scene_id
        for frame in state.mode_stack
    )
    if not still_active:
        return
    state.mark_paused(
        f"{phase_label} incomplete after {turns_run} turn(s); "
        f"DM must call glass mode end"
    )
    cli.store.save(state)
    raise click.ClickException(
        f"{phase_label} did not explicitly complete after {turns_run} turn(s); "
        f"`{mode_name}` is still on the mode stack. Not advancing bootstrap phase."
    )


def _validate_organization_bootstrap_complete(
    cli: CliState,
    campaign_id: str,
) -> None:
    from cli import db as _db
    from cli.config import load_config as _load_glass_config

    campaign_root = cli.config.campaigns_dir / campaign_id
    failures: list[str] = []

    organization_public = campaign_root / "shared" / "lore" / "organization.md"
    organization_private = campaign_root / "dm" / "notes" / "organization.md"
    table_scene = campaign_root / "table" / "scene.md"

    for path, label in (
        (organization_public, "shared/lore/organization.md"),
        (organization_private, "dm/notes/organization.md"),
        (table_scene, "table/scene.md"),
    ):
        try:
            body = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            failures.append(f"missing {label}")
            continue
        if not body:
            failures.append(f"empty {label}")

    try:
        scene_body = table_scene.read_text(encoding="utf-8")
    except OSError:
        scene_body = ""
    if "No scene is currently active." in scene_body:
        failures.append("table/scene.md still has the inactive table stub")

    if (campaign_root / "dm" / "foundation.md").exists():
        failures.append("dm/foundation.md exists; campaign planning started too early")

    arcs_root = campaign_root / "arcs"
    if arcs_root.exists() and any(path.is_dir() for path in arcs_root.iterdir()):
        failures.append("arcs/ exists; organization bootstrap must not create arcs")

    for rel in (
        Path("dm/notes/factions"),
        Path("dm/notes/npcs"),
        Path("dm/notes/locales"),
        Path("dm/notes/creatures"),
        Path("dm/notes/ships"),
        Path("dm/notes/artifacts"),
        Path("dm/notes/hooks.md"),
        Path("dm/notes/secrets.md"),
        Path("dm/notes/philosophy"),
    ):
        if (campaign_root / rel).exists():
            failures.append(f"{rel} exists; org bootstrap must stay org-only")

    previous_config = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = config_env_value(cli.config)
    try:
        pg_config = _db.load_pg_config(_load_glass_config())
        with _db.connect(pg_config) as conn:
            clocks = _db.clock_list(
                conn,
                campaign_id=campaign_id,
                include_archived=True,
            )
    finally:
        if previous_config is None:
            os.environ.pop("GLASS_CONFIG", None)
        else:
            os.environ["GLASS_CONFIG"] = previous_config
    if clocks:
        failures.append("durable clocks exist; org bootstrap must not create pressures")

    if failures:
        detail = "\n".join(f"- {failure}" for failure in failures)
        raise click.ClickException(
            "organization bootstrap validation failed; not advancing bootstrap "
            f"phase:\n{detail}"
        )


def _validate_campaign_planning_complete(cli: CliState, campaign_id: str) -> None:
    campaign_root = cli.config.campaigns_dir / campaign_id
    failures: list[str] = []

    foundation = campaign_root / "dm" / "foundation.md"
    context = campaign_root / "context.md"
    framing = campaign_root / "shared" / "campaign-framing.md"

    for path, label in (
        (foundation, "dm/foundation.md"),
        (context, "context.md"),
        (framing, "shared/campaign-framing.md"),
    ):
        try:
            body = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            failures.append(f"missing {label}")
            continue
        if not body:
            failures.append(f"empty {label}")
            continue
        if label == "shared/campaign-framing.md" and "**Stub.**" in body:
            failures.append("shared/campaign-framing.md still has the stub content")

    arcs_root = campaign_root / "arcs"
    arc_dirs = (
        sorted(path.name for path in arcs_root.iterdir() if path.is_dir())
        if arcs_root.exists()
        else []
    )
    if not arc_dirs:
        failures.append("no opening arc was created during campaign planning")

    if failures:
        detail = "\n".join(f"- {failure}" for failure in failures)
        raise click.ClickException(
            "campaign planning validation failed; not advancing bootstrap phase:\n"
            f"{detail}"
        )


def _validate_character_creation_complete(cli: CliState, campaign_id: str) -> None:
    from cli import db as _db
    from cli.config import load_config as _load_glass_config

    previous_config = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = config_env_value(cli.config)
    try:
        pg_config = _db.load_pg_config(_load_glass_config())
        with _db.connect(pg_config) as conn:
            characters = _db.character_list(conn, campaign_id)
    finally:
        if previous_config is None:
            os.environ.pop("GLASS_CONFIG", None)
        else:
            os.environ["GLASS_CONFIG"] = previous_config

    by_player: dict[str, list[dict]] = {player_id: [] for player_id in PLAYER_IDS}
    for character in characters:
        player_id = str(character.get("player_id") or "")
        if player_id in by_player:
            by_player[player_id].append(character)

    failures: list[str] = []
    campaign_root = cli.config.campaigns_dir / campaign_id
    for player_id in PLAYER_IDS:
        player_characters = by_player[player_id]
        if len(player_characters) != 1:
            failures.append(
                f"{player_id}: expected exactly one character row, "
                f"found {len(player_characters)}"
            )
            continue
        character = player_characters[0]
        for field_name in ("name", "species", "culture", "archetype", "organization_role", "bio"):
            if not str(character.get(field_name) or "").strip():
                failures.append(f"{player_id}: missing character field {field_name}")
        goals = list(character.get("goals") or [])
        if not (2 <= len([goal for goal in goals if str(goal).strip()]) <= 3):
            failures.append(
                f"{player_id}: expected 2-3 canonical goals, found {len(goals)}"
            )
        # Starting inventory shape is prompt guidance, not a bootstrap invariant.
        # Do not fail the operator process after relationship-building because a
        # player picked imperfect items during their build turn.
        for rel_path in (
            Path("players") / player_id / "public" / "character.md",
            Path("players") / player_id / "public" / "intro.md",
            Path("players") / player_id / "public" / "relationships.md",
        ):
            path = campaign_root / rel_path
            try:
                has_text = path.read_text(encoding="utf-8").strip()
            except FileNotFoundError:
                failures.append(f"{player_id}: missing {rel_path}")
                continue
            except PermissionError as exc:
                failures.append(
                    f"{player_id}: cannot read {rel_path}: {exc.strerror or exc}"
                )
                continue
            except OSError:
                failures.append(f"{player_id}: cannot read {rel_path}")
                continue
            if not has_text:
                failures.append(f"{player_id}: missing or empty {rel_path}")

    if failures:
        detail = "\n".join(f"- {failure}" for failure in failures)
        raise click.ClickException(
            "character creation hard-state validation failed; not advancing "
            f"bootstrap phase:\n{detail}"
        )


def _ensure_operator_groups_active() -> None:
    from . import permissions as _permissions

    missing = _permissions.missing_operator_groups()
    if not missing:
        return
    operator = _permissions.operator_user()
    aog_bin = shutil.which("aog") or "aog"
    raise click.ClickException(
        "Unix isolation is provisioned, but this operator process has not "
        "picked up all required supplementary groups. Missing: "
        f"{', '.join(missing)}.\n"
        "Start a fresh login shell, or run through sudo so groups are "
        "recomputed, for example:\n"
        f"  sudo -n -u {operator} -g {operator} {aog_bin} campaign run "
        "<campaign-id>"
    )


def _ensure_glass_api_for_run(cli: CliState) -> None:
    try:
        from cli.api_daemon import restart_daemon

        info = restart_daemon(
            url=_api_url(None),
            config_path=config_env_value(cli.config),
        )
    except Exception as exc:
        raise click.ClickException(f"failed to restart glass API: {exc}") from exc
    click.echo(
        f"      glass API: {info.message} {info.url} "
        f"pid={info.pid or '-'} (log: {info.log_path})"
    )


def _start_webui(
    cli: CliState,
    *,
    url: str | None = None,
):
    from .webui_daemon import start_webui

    return start_webui(
        repo_root=cli.config.repo_root,
        config_path=config_env_value(cli.config),
        url=url or _webui_url(None),
        web_api_url=_web_api_url(None),
    )


def _ensure_db_migrated(cli: CliState) -> None:
    from cli import db as _glass_db
    from cli.config import load_config as _load_glass_config

    previous_config = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = config_env_value(cli.config)
    try:
        toml_data = _load_glass_config()
        if not _glass_db.postgres_configured(toml_data):
            raise click.ClickException(
                "Postgres runtime is required. Configure [postgres] in "
                "agents-of-glass.toml or set libpq environment variables."
            )
        pg_config = _glass_db.load_pg_config(toml_data)
        try:
            with _glass_db.connect(pg_config) as conn:
                actions = _glass_db.migrate(conn)
        except Exception as exc:
            raise click.ClickException(
                f"failed to migrate Postgres runtime schema at "
                f"{pg_config.describe()}: {exc}"
            ) from exc
        applied = [name for name, action in actions if action == "applied"]
        if applied:
            click.echo(f"      db: applied migrations {', '.join(applied)}")
    finally:
        if previous_config is None:
            os.environ.pop("GLASS_CONFIG", None)
        else:
            os.environ["GLASS_CONFIG"] = previous_config


def _ensure_falkor_reachable(cli: CliState) -> None:
    from cli import graph as _glass_graph
    from cli.config import load_config as _load_glass_config

    previous_config = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = config_env_value(cli.config)
    try:
        toml_data = _load_glass_config()
        falkor_config = _glass_graph.load_falkor_config(toml_data)
        if not _glass_graph.is_available(falkor_config):
            raise click.ClickException(
                f"FalkorDB graph is required and is not reachable at "
                f"{falkor_config.describe()}."
            )
    finally:
        if previous_config is None:
            os.environ.pop("GLASS_CONFIG", None)
        else:
            os.environ["GLASS_CONFIG"] = previous_config


def _api_url(value: str | None) -> str:
    from cli.api_grants import DEFAULT_API_URL

    return value or os.environ.get("GLASS_API_URL", DEFAULT_API_URL)


def _webui_url(value: str | None) -> str:
    from .webui_daemon import DEFAULT_WEBUI_URL

    return value or os.environ.get("AOG_WEBUI_URL", DEFAULT_WEBUI_URL)


def _web_api_url(value: str | None) -> str:
    from cli.web_api_server import DEFAULT_WEB_API_URL

    return value or os.environ.get("AOG_WEB_API_URL", DEFAULT_WEB_API_URL)


def _echo_api_daemon(info) -> None:
    _echo_service_daemon(info, "glass API")


def _echo_service_daemon(info, label: str) -> None:
    bind = f" bind={info.bind_host}" if getattr(info, "bind_host", None) else ""
    click.echo(
        f"{label} {info.message}: url={info.url} "
        f"pid={info.pid or '-'} running={str(info.running).lower()}{bind}"
    )
    click.echo(f"log: {info.log_path}")


def _echo_webui_daemon(info) -> None:
    click.echo(
        f"web UI {info.message}: url={info.url} web_api={info.api_url} "
        f"pid={info.pid or '-'} running={str(info.running).lower()}"
    )
    click.echo(f"log: {info.log_path}")


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


@campaign.command("checkpoint")
@click.argument("campaign_id")
@click.option("--label", default=None, help="Human-readable checkpoint label.")
@click.pass_obj
def campaign_checkpoint(cli: CliState, campaign_id: str, label: str | None) -> None:
    """Snapshot filesystem, Postgres, search vectors, and FalkorDB graph."""
    checkpoint = _checkpoint_or_raise(cli, campaign_id, label=label)
    click.echo(f"checkpoint: {checkpoint['checkpoint_id']}")
    click.echo(f"path: {checkpoint['path']}")
    click.echo("counts:")
    click.echo(json.dumps(checkpoint["counts"], indent=2, sort_keys=True))


@campaign.command("checkpoints")
@click.argument("campaign_id")
@click.pass_obj
def campaign_checkpoints(cli: CliState, campaign_id: str) -> None:
    """List campaign checkpoints."""
    from .checkpoints import list_checkpoints

    checkpoints = list_checkpoints(cli.config, campaign_id)
    if not checkpoints:
        click.echo("no checkpoints")
        return
    for item in checkpoints:
        click.echo(
            f"{item['checkpoint_id']:<72}  "
            f"{item.get('created_at', ''):<25}  {item.get('label', '')}"
        )


@campaign.command("restore")
@click.argument("campaign_id")
@click.argument("checkpoint_id")
@click.option("--yes", is_flag=True, help="Do not prompt for confirmation.")
@click.pass_obj
def campaign_restore(
    cli: CliState,
    campaign_id: str,
    checkpoint_id: str,
    yes: bool,
) -> None:
    """Restore campaign state from a checkpoint."""
    from .checkpoints import restore_checkpoint

    if not yes and not click.confirm(
        f"Restore campaign {campaign_id!r} to checkpoint {checkpoint_id!r}? "
        "Current live state will be archived outside agent discovery."
    ):
        raise click.Abort()
    try:
        result = restore_checkpoint(cli.config, campaign_id, checkpoint_id)
    except Exception as exc:
        raise click.ClickException(f"checkpoint restore failed: {exc}") from exc
    click.echo(f"restored: {campaign_id} <- {checkpoint_id}")
    click.echo(f"discarded archive: {result['discarded_archive']}")
    click.echo("restored counts:")
    click.echo(json.dumps(result["restored_counts"], indent=2, sort_keys=True))


@campaign.command("reconcile")
@click.argument("campaign_id")
@click.option("--repair", is_flag=True, help="Rewrite disposable projections and permissions.")
@click.pass_obj
def campaign_reconcile(cli: CliState, campaign_id: str, repair: bool) -> None:
    """Check campaign state surfaces and optionally refresh projections."""
    result = _reconcile_campaign(cli, campaign_id, repair=repair)
    click.echo(json.dumps(result, indent=2, sort_keys=True))


@campaign.command("prepare-turn")
@click.argument("campaign_id", required=False)
@click.option(
    "--use-codex/--use-claude",
    "use_codex",
    default=None,
    help="Switch between the mixed Codex table preset and the all-Claude baseline for this prepared turn.",
)
@click.option(
    "--skip-player-persona/--no-skip-player-persona",
    "skip_player_persona",
    default=None,
    help="Override [agent].skip_player_persona for this prepared turn.",
)
@click.option(
    "--use-session-id/--no-use-session-id",
    "use_session_id",
    default=None,
    help="Override [claude].use_session_id for this prepared turn.",
)
@click.pass_obj
def campaign_prepare_turn(
    cli: CliState,
    campaign_id: str | None,
    use_codex: bool | None,
    skip_player_persona: bool | None,
    use_session_id: bool | None,
) -> None:
    """Build the next turn's TURN_START context without invoking the agent."""
    _apply_cli_overrides(
        cli,
        use_session_id=use_session_id,
        use_codex=use_codex,
        skip_player_persona=skip_player_persona,
    )
    _ensure_db_migrated(cli)
    _ensure_falkor_reachable(cli)
    state = cli.store.load(campaign_id)
    package = cli.orchestrator.prepare_turn(state)
    click.echo(f"prepared {package.turn_id}")
    click.echo(f"cwd: {package.spawn_cwd}")
    click.echo(f"start:    {package.turn_start_path}")
    click.echo(f"prose:    {package.turn_prose_path}")
    click.echo(f"closeout: {package.turn_closeout_path}")


@campaign.command("run")
@click.argument("campaign_id", required=False)
@click.option(
    "--max-turns",
    type=int,
    default=None,
    help="Turns to run in active play once bootstrap phases are complete.",
)
@click.option(
    "--skip-stops",
    "skip_review_stops",
    type=click.IntRange(min=0),
    default=0,
    show_default=True,
    help=(
        "Number of active-play review stops to auto-continue past. "
        "Use 1 to run intermission and continue into the next act."
    ),
)
@click.option(
    "--no-review-stops",
    is_flag=True,
    help=(
        "Do not stop at active-play review boundaries during this run. "
        "Use with --max-turns for a bounded overnight run."
    ),
)
@click.option(
    "--max-organization-turns",
    type=int,
    default=1,
    show_default=True,
    help="Safety net only. Organization bootstrap should finish in a single Mara turn.",
)
@click.option(
    "--max-planning-turns",
    type=int,
    default=15,
    show_default=True,
    help="Safety net only. Mara ends post-character campaign planning when done.",
)
@click.option(
    "--max-creation-turns",
    type=int,
    default=30,
    show_default=True,
    help="Safety net only. The DM ends character creation when done.",
)
@click.option(
    "--skip-character-creation",
    is_flag=True,
    help="Stop after organization bootstrap. Useful for inspecting the party org.",
)
@click.option(
    "--use-codex/--use-claude",
    "use_codex",
    default=None,
    help="Switch between the mixed Codex table preset and the all-Claude baseline for this run.",
)
@click.option(
    "--skip-player-persona/--no-skip-player-persona",
    "skip_player_persona",
    default=None,
    help="Override [agent].skip_player_persona for this run.",
)
@click.option(
    "--use-session-id/--no-use-session-id",
    "use_session_id",
    default=None,
    help="Override [claude].use_session_id for this run.",
)
@click.option(
    "--turn-minimum-seconds",
    type=click.IntRange(min=0),
    default=None,
    help=(
        "Override [orchestrator].turn_minimum_seconds for this run. "
        "Use 0 for no pacing delay."
    ),
)
@click.option("--dry-run", is_flag=True, help="Synthetic turns without Claude.")
@click.pass_obj
def campaign_run(
    cli: CliState,
    campaign_id: str | None,
    max_turns: int | None,
    skip_review_stops: int,
    no_review_stops: bool,
    max_organization_turns: int,
    max_planning_turns: int,
    max_creation_turns: int,
    skip_character_creation: bool,
    use_codex: bool | None,
    skip_player_persona: bool | None,
    use_session_id: bool | None,
    turn_minimum_seconds: int | None,
    dry_run: bool,
) -> None:
    """Create or continue a campaign from its durable phase/mode state."""

    _apply_cli_overrides(
        cli,
        use_session_id=use_session_id,
        use_codex=use_codex,
        skip_player_persona=skip_player_persona,
        turn_minimum_seconds=turn_minimum_seconds,
    )
    _run_campaign_lifecycle(
        cli,
        campaign_id,
        max_organization_turns=max_organization_turns,
        max_planning_turns=max_planning_turns,
        max_creation_turns=max_creation_turns,
        max_active_turns=max_turns,
        review_stop_budget=None if no_review_stops else skip_review_stops,
        skip_character_creation=skip_character_creation,
        dry_run=dry_run,
    )


@campaign.command("clean")
@click.argument("campaign_id")
@click.option("--state-only", is_flag=True,
              help="Only delete runtime state/cache (runtime DB rows, stale JSON state, "
                   "transcript export, audit.jsonl, scene-framing.md, per-agent turns/). "
                   "Keeps the campaign workspace, DM/player content, arcs, lore, "
                   "characters/messages/rolls, and graph nodes.")
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
            "(workspace, DM/player content, arcs, lore, non-runtime DB rows, graph all remain)"
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


def _checkpoint_or_raise(
    cli: CliState,
    campaign_id: str,
    *,
    label: str | None,
) -> dict[str, object]:
    from .checkpoints import create_checkpoint

    try:
        checkpoint = create_checkpoint(cli.config, campaign_id, label=label)
    except Exception as exc:
        raise click.ClickException(f"checkpoint failed: {exc}") from exc
    return {
        "checkpoint_id": checkpoint.checkpoint_id,
        "path": str(checkpoint.path),
        "counts": checkpoint.manifest.get("counts", {}),
    }


def _reconcile_campaign(
    cli: CliState,
    campaign_id: str,
    *,
    repair: bool,
) -> dict[str, object]:
    from . import permissions as _permissions
    from cli import db as _glass_db
    from cli import graph as _glass_graph
    from cli.config import load_config as _load_glass_config

    campaign_dir = cli.config.campaigns_dir / campaign_id
    checks: list[dict[str, object]] = []
    repaired: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    check("workspace", campaign_dir.exists(), str(campaign_dir))
    state_path = campaign_dir / "state.json"
    aog_state_path = campaign_dir / "aog-state.json"
    table_dir = campaign_dir / "table"
    check("table", table_dir.exists(), str(table_dir))

    phase_state: dict[str, object] = {}
    try:
        phase_state = cli.campaign_manager.load_state(campaign_id)
        check("campaign.phase_state", True, "runtime state")
    except Exception as exc:
        check("campaign.phase_state", False, str(exc))

    previous_config = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = config_env_value(cli.config)
    try:
        toml_data = _load_glass_config()
        postgres_configured = _glass_db.postgres_configured(toml_data)
        check("postgres.configured", postgres_configured, "required")
        check("state.json.absent", not state_path.exists(), str(state_path))
        check("aog-state.json.absent", not aog_state_path.exists(), str(aog_state_path))
        if postgres_configured:
            pg_config = _glass_db.load_pg_config(toml_data)
            with _glass_db.connect(pg_config) as conn:
                runtime = _glass_db.runtime_state_get(conn, campaign_id)
                turns = _glass_db.turn_list(
                    conn,
                    campaign_id=campaign_id,
                    limit=100000,
                )
            check("postgres.runtime", runtime is not None, pg_config.describe())
            if runtime is not None:
                pg_turn = int(runtime.get("turn_counter", 0))
                max_turn = max((int(turn["turn_id"]) for turn in turns), default=0)
                check(
                    "postgres.turn_counter",
                    pg_turn >= max_turn,
                    f"turn_counter={pg_turn}, max_turn={max_turn}",
                )
                if repair:
                    state = cli.store.load(campaign_id)
                    cli.store.save(state)
                    repaired.append("orchestrator-runtime-state")
            if repair and turns:
                transcript = "\n\n".join(str(turn["markdown"]).rstrip() for turn in turns)
                (campaign_dir / "transcript.md").write_text(
                    transcript.rstrip() + "\n",
                    encoding="utf-8",
                )
                repaired.append("transcript.md")
        falkor_config = _glass_graph.load_falkor_config(toml_data)
        check("falkordb.reachable", _glass_graph.is_available(falkor_config), falkor_config.describe())
    finally:
        if previous_config is None:
            os.environ.pop("GLASS_CONFIG", None)
        else:
            os.environ["GLASS_CONFIG"] = previous_config

    active_arc = phase_state.get("active_arc")
    active_scene = phase_state.get("active_scene")
    if active_arc:
        check(
            "active_arc_dir",
            (campaign_dir / "arcs" / str(active_arc)).exists(),
            str(active_arc),
        )
    if active_scene:
        arc = str(phase_state.get("active_scene_arc") or active_arc or "")
        check(
            "active_scene_dir",
            bool(arc) and (campaign_dir / "arcs" / arc / "scenes" / str(active_scene)).exists(),
            f"{arc}/{active_scene}",
        )

    if repair and campaign_dir.exists():
        _permissions.apply_campaign_permissions(campaign_dir)
        repaired.append("permissions")

    return {
        "campaign_id": campaign_id,
        "ok": all(bool(item["ok"]) for item in checks),
        "repair": repair,
        "repaired": repaired,
        "checks": checks,
    }


if __name__ == "__main__":
    main()
