"""Entry point for the `aog` operator CLI."""

from __future__ import annotations

from pathlib import Path
import json
import os
import shutil

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
    PHASE_PRELUDE,
)
from .config import config_env_value, load_config
from .runner import Orchestrator, TurnFailure
from .state import PLAYER_IDS
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
def api() -> None:
    """Manage the local glass API daemon."""


@api.command("start")
@click.option("--url", default=None, help="API URL. Defaults to GLASS_API_URL or localhost.")
@click.pass_obj
def api_start(cli: CliState, url: str | None) -> None:
    """Start the detached local glass API daemon."""
    from cli.api_daemon import start_daemon

    _echo_api_daemon(
        start_daemon(url=_api_url(url), config_path=config_env_value(cli.config))
    )


@api.command("restart")
@click.option("--url", default=None, help="API URL. Defaults to GLASS_API_URL or localhost.")
@click.pass_obj
def api_restart(cli: CliState, url: str | None) -> None:
    """Restart the detached local glass API daemon with current code/config."""
    from cli.api_daemon import restart_daemon

    _echo_api_daemon(
        restart_daemon(url=_api_url(url), config_path=config_env_value(cli.config))
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
    "--max-prelude-turns",
    type=int,
    default=35,
    show_default=True,
    help="Safety net only. The DM ends prelude after the two-scene shakedown.",
)
@click.option(
    "--skip-character-creation",
    is_flag=True,
    help="Stop after campaign planning. Useful when you want to inspect the planning output.",
)
@click.option(
    "--skip-prelude",
    is_flag=True,
    help="Stop after character creation without running the bootstrap prelude.",
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
    max_prelude_turns: int,
    skip_character_creation: bool,
    skip_prelude: bool,
    dry_run: bool,
) -> None:
    """Bootstrap a campaign end-to-end.

    Idempotent: if the workspace already exists, resume from the current
    phase. Phases that have already completed (have a completed_at in
    phase_history) are skipped. Phases that started but didn't finish
    are picked up where they left off (the orchestrator's create_session
    is idempotent w.r.t. mode-stack pushes).

    Steps:
      1. Create or resume campaigns/<id>/.
      2. Invoke DM in campaign-planning mode.
      3. Character creation (skip with --skip-character-creation).
      4. Prelude shakedown: one normal scene, one action scene.
      5. Advance to active play.
    """
    from .campaign import CampaignSpace

    _ensure_operator_groups_active()
    _ensure_db_migrated(cli)
    _restart_api_daemon_for_run(cli)

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
    click.echo(f"      state:     {space.state_path}")

    # Phase 2: campaign planning
    if _phase_completed(cm_state, PHASE_PLANNING):
        click.secho(
            f"[2/5] Campaign planning already complete; skipping.", fg="yellow"
        )
    else:
        click.secho(
            f"[2/5] Invoking DM for campaign planning (max {max_planning_turns} turns)",
            fg="cyan",
        )
        if cm_state["phase"] != PHASE_PLANNING:
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
            raise click.ClickException(
                f"campaign planning failed: {exc}\n{detail}"
            ) from exc
        _require_bootstrap_mode_ended(
            cli,
            campaign_id=campaign_id,
            mode_name="campaign-planning",
            scene_id="planning",
            phase_label="campaign planning",
            turns_run=turns_run,
        )
        click.echo(f"      DM produced {turns_run} planning turn(s)")
        click.echo(f"      transcript: {cli.store.transcript_path(state.campaign)}")
        click.echo(f"      DM workspace: {space.campaign_dir / 'dm'}")
        cm_state = cli.campaign_manager.load_state(campaign_id)  # refresh

    # Phase 3: character creation
    if skip_character_creation:
        if cm_state["phase"] != PHASE_CHARACTER_CREATION:
            cli.campaign_manager.advance_phase(campaign_id, PHASE_CHARACTER_CREATION)
        click.secho("[3/5] Character creation skipped (--skip-character-creation).",
                    fg="yellow")
        click.echo()
        click.secho(
            f"Campaign '{campaign_id}' bootstrapped through campaign_planning.",
            fg="green",
        )
        click.echo(f"Next phase: {PHASE_CHARACTER_CREATION}")
        click.echo(f"State file: {space.state_path}")
        return
    elif _phase_completed(cm_state, PHASE_CHARACTER_CREATION):
        click.secho(
            f"[3/5] Character creation already complete; skipping.", fg="yellow"
        )
    else:
        click.secho(
            f"[3/5] Invoking players + DM for character creation "
            f"(max {max_creation_turns} turns)",
            fg="cyan",
        )
        if cm_state["phase"] != PHASE_CHARACTER_CREATION:
            cli.campaign_manager.advance_phase(campaign_id, PHASE_CHARACTER_CREATION)
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
        _require_bootstrap_mode_ended(
            cli,
            campaign_id=campaign_id,
            mode_name="character-creation",
            scene_id="character-creation",
            phase_label="character creation",
            turns_run=creation_turns,
        )
        if not dry_run:
            _validate_character_creation_complete(cli, campaign_id)
        click.echo(f"      ran {creation_turns} character-creation turn(s)")
        click.echo(f"      transcript: {cli.store.transcript_path(creation_state.campaign)}")
        cm_state = cli.campaign_manager.load_state(campaign_id)

    # Phase 4: prelude shakedown
    if skip_prelude:
        if cm_state["phase"] != PHASE_PRELUDE:
            cli.campaign_manager.advance_phase(campaign_id, PHASE_PRELUDE)
        click.secho("[4/5] Prelude skipped (--skip-prelude).", fg="yellow")
        click.echo()
        click.secho(
            f"Campaign '{campaign_id}' bootstrapped through character_creation.",
            fg="green",
        )
        click.echo(f"Next phase: {PHASE_PRELUDE}")
        click.echo(f"State file: {space.state_path}")
        return
    if _phase_completed(cm_state, PHASE_PRELUDE):
        click.secho(f"[4/5] Prelude already complete; skipping.", fg="yellow")
    else:
        click.secho(
            f"[4/5] Running bootstrap prelude (max {max_prelude_turns} turns)",
            fg="cyan",
        )
        if cm_state["phase"] != PHASE_PRELUDE:
            cli.campaign_manager.advance_phase(campaign_id, PHASE_PRELUDE)
        prelude_state = cli.store.create_session(
            campaign=campaign_id,
            initial_mode="prelude",
            initial_scene="prelude",
        )
        try:
            prelude_turns = cli.orchestrator.run_loop(
                prelude_state,
                max_turns=max_prelude_turns,
                dry_run=dry_run,
                resume_failed=False,
            )
        except TurnFailure as exc:
            detail = json.dumps(exc.failure, indent=2, sort_keys=True)
            raise click.ClickException(
                f"prelude failed: {exc}\n{detail}"
            ) from exc
        _require_bootstrap_mode_ended(
            cli,
            campaign_id=campaign_id,
            mode_name="prelude",
            scene_id="prelude",
            phase_label="prelude",
            turns_run=prelude_turns,
        )
        click.echo(f"      ran {prelude_turns} prelude turn(s)")
        click.echo(f"      transcript: {cli.store.transcript_path(prelude_state.campaign)}")
        cm_state = cli.campaign_manager.load_state(campaign_id)

    # Phase 5: active campaign handoff
    if cm_state["phase"] != PHASE_ACTIVE:
        cli.campaign_manager.advance_phase(campaign_id, PHASE_ACTIVE)
    click.secho("[5/5] Campaign ready for active play", fg="green")
    click.echo("      DM creates the next scene via glass scene create;")
    click.echo("      operator drives via aog campaign run.")

    click.echo()
    click.secho(
        f"Campaign '{campaign_id}' bootstrapped through prelude.",
        fg="green",
    )
    click.echo(f"State file: {space.state_path}")


def _phase_completed(cm_state: dict, phase_name: str) -> bool:
    """True if any phase_history entry for this phase has a completed_at."""
    for entry in cm_state.get("phase_history", []):
        if entry.get("phase") == phase_name and "completed_at" in entry:
            return True
    return False


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
        inventory = list(character.get("inventory") or [])
        if not (3 <= len(inventory) <= 5):
            failures.append(
                f"{player_id}: expected 3-5 inventory entries, found {len(inventory)}"
            )
        for rel_path in (
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
        f"  with-cred -- sudo -n -u {operator} -g {operator} "
        f"{aog_bin} campaign bootstrap <campaign-id>"
    )


def _restart_api_daemon_for_run(cli: CliState) -> None:
    from cli.api_daemon import restart_daemon

    try:
        info = restart_daemon(
            url=_api_url(None),
            config_path=config_env_value(cli.config),
        )
    except Exception as exc:
        raise click.ClickException(f"failed to restart glass API daemon: {exc}") from exc
    click.echo(
        f"      glass API: restarted {info.url} pid={info.pid or '-'} "
        f"(log: {info.log_path})"
    )


def _ensure_db_migrated(cli: CliState) -> None:
    from cli import db as _glass_db
    from cli.config import load_config as _load_glass_config

    previous_config = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = config_env_value(cli.config)
    try:
        toml_data = _load_glass_config()
        if not _glass_db.postgres_configured(toml_data):
            return
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


def _api_url(value: str | None) -> str:
    from cli.api_grants import DEFAULT_API_URL

    return value or os.environ.get("GLASS_API_URL", DEFAULT_API_URL)


def _echo_api_daemon(info) -> None:
    click.echo(
        f"glass API {info.message}: url={info.url} "
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
    _ensure_operator_groups_active()
    _ensure_db_migrated(cli)
    _restart_api_daemon_for_run(cli)
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
    _ensure_operator_groups_active()
    _ensure_db_migrated(cli)
    _restart_api_daemon_for_run(cli)
    state = cli.store.load(campaign_id)
    turns = _run_or_raise(cli, state, max_turns=max_turns, dry_run=dry_run, resume_failed=True)
    click.echo(f"resumed and ran {turns} turn(s)")


@campaign.command("clean")
@click.argument("campaign_id")
@click.option("--state-only", is_flag=True,
              help="Only delete runtime state/cache (runtime DB rows, state.json, "
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


if __name__ == "__main__":
    main()
