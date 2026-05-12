import tempfile
import unittest
import json
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch

from click.testing import CliRunner

from orchestrator import permissions
from orchestrator.config import AogConfig, CapsConfig, ClaudeConfig
from orchestrator.main import main as aog_main
from orchestrator.main import _consume_review_stop
from orchestrator.main import _next_mode_after_no_active_mode
from orchestrator.main import _validate_campaign_planning_complete
from orchestrator.main import _validate_organization_bootstrap_complete
from orchestrator.projection import PLAYER_SURFACE_CHARACTER
from orchestrator.runner import (
    Orchestrator,
    TurnFailure,
    TurnResult,
    _assert_actor_workspace_ready,
    _tool_transcript_lines,
)
from orchestrator.projection import refresh_projection_from_canonical, unsynced_workspace_changes
from orchestrator.state import AGENTS_BY_ID, SessionState, speaker_order_for
from orchestrator.store import SessionStore


def make_config(
    root: Path,
    *,
    use_session_id: bool = False,
    agent_provider: str = "claude",
    skip_player_persona: bool = False,
) -> AogConfig:
    return AogConfig(
        repo_root=root,
        config_path=None,
        templates_dir=root / "templates",
        campaigns_dir=root / "campaigns",
        lore_path=root / "lore",
        agent_provider=agent_provider,
        skip_player_persona=skip_player_persona,
        claude=ClaudeConfig(
            model=None,
            turn_timeout_seconds=60,
            use_session_id=use_session_id,
        ),
        caps=CapsConfig(
            session_max_turns=200,
            mode_default_max_turns=12,
            mode_scene_play_max_turns=120,
            mode_combat_max_turns=8,
            mode_travel_max_turns=4,
        ),
    )


def attach_runtime_mocks(
    orchestrator: Orchestrator,
    *,
    next_speaker: dict | None = None,
    action_order: dict | None = None,
) -> None:
    orchestrator._peek_next_speaker_entry_from_postgres = Mock(return_value=next_speaker)
    orchestrator._load_action_order_from_postgres = Mock(return_value=action_order)
    orchestrator.context_builder._public_trackers_from_postgres = Mock(return_value=[])


class OrchestratorQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self._provisioned_patch = patch.object(
            permissions,
            "has_provisioned_users",
            return_value=False,
        )
        self._provisioned_patch.start()

    def tearDown(self) -> None:
        self._provisioned_patch.stop()

    def test_dm_agent_uses_mara_unix_user_when_provisioned(self) -> None:
        with patch.object(permissions, "has_provisioned_users", return_value=True):
            self.assertEqual(permissions.player_user_for("dm"), "aog-mara")

    def test_projection_permission_helper_receives_actor_user(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(permissions, "has_provisioned_users", return_value=True),
            patch.object(permissions, "_run_helper") as run_helper,
        ):
            root = Path(tmp)
            projection = root / ".glass-cwd" / "c1" / "dm"
            projection.mkdir(parents=True)

            self.assertTrue(
                permissions.apply_projection_permissions(
                    projection,
                    actor_user="aog-mara",
                )
            )

            run_helper.assert_called_once_with(
                ["projection", str(projection.resolve()), "aog-mara"]
            )

    def test_campaign_execution_surface_is_run_only(self) -> None:
        result = CliRunner().invoke(aog_main, ["campaign", "--help"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("run", result.output)
        self.assertNotIn("bootstrap", result.output)
        self.assertNotIn("resume", result.output)

    def test_campaign_run_exposes_review_stop_controls(self) -> None:
        result = CliRunner().invoke(aog_main, ["campaign", "run", "--help"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("--max-organization-turns", result.output)
        self.assertIn("--skip-stops", result.output)
        self.assertIn("--no-review-stops", result.output)
        self.assertIn("--use-codex", result.output)
        self.assertIn("--skip-player-persona", result.output)
        self.assertIn("--use-session-id", result.output)
        self.assertIn("--no-use-session-id", result.output)

    def test_campaign_run_defaults_prelude_cap_to_120(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "templates").mkdir()
            (root / "campaigns").mkdir()
            config_path = root / "agents-of-glass.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        'templates = "templates"',
                        'campaigns = "campaigns"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            seen: list[int] = []

            def fake_lifecycle(cli, *_args, **kwargs):
                seen.append(int(kwargs["max_prelude_turns"]))

            with patch(
                "orchestrator.main._run_campaign_lifecycle",
                side_effect=fake_lifecycle,
            ):
                result = CliRunner().invoke(
                    aog_main,
                    [
                        "--config",
                        str(config_path),
                        "campaign",
                        "run",
                        "c1",
                        "--dry-run",
                    ],
                )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(seen, [120])

    def test_campaign_run_session_id_flags_override_toml(self) -> None:
        for toml_enabled, option, expected in (
            (False, "--use-session-id", True),
            (True, "--no-use-session-id", False),
            (True, None, True),
        ):
            with (
                self.subTest(option=option, toml_enabled=toml_enabled),
                tempfile.TemporaryDirectory() as tmp,
            ):
                root = Path(tmp)
                (root / "templates").mkdir()
                (root / "campaigns").mkdir()
                config_path = root / "agents-of-glass.toml"
                config_path.write_text(
                    "\n".join(
                        [
                            "[paths]",
                            'templates = "templates"',
                            'campaigns = "campaigns"',
                            "",
                            "[claude]",
                            f"use_session_id = {str(toml_enabled).lower()}",
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )
                args = [
                    "--config",
                    str(config_path),
                    "campaign",
                    "run",
                    "c1",
                    "--dry-run",
                ]
                if option:
                    args.append(option)
                seen: list[bool] = []

                def fake_lifecycle(cli, *_args, **_kwargs):
                    seen.append(cli.config.claude.use_session_id)

                with patch(
                    "orchestrator.main._run_campaign_lifecycle",
                    side_effect=fake_lifecycle,
                ):
                    result = CliRunner().invoke(aog_main, args)

                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(seen, [expected])

    def test_campaign_run_provider_and_persona_flags_override_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "templates").mkdir()
            (root / "campaigns").mkdir()
            config_path = root / "agents-of-glass.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        'templates = "templates"',
                        'campaigns = "campaigns"',
                        "",
                        "[agent]",
                        'provider = "claude"',
                        "skip_player_persona = false",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            seen: list[tuple[str, bool]] = []

            def fake_lifecycle(cli, *_args, **_kwargs):
                seen.append(
                    (cli.config.agent_provider, cli.config.skip_player_persona)
                )

            with patch(
                "orchestrator.main._run_campaign_lifecycle",
                side_effect=fake_lifecycle,
            ):
                result = CliRunner().invoke(
                    aog_main,
                    [
                        "--config",
                        str(config_path),
                        "campaign",
                        "run",
                        "c1",
                        "--dry-run",
                        "--use-codex",
                        "--skip-player-persona",
                    ],
                )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(seen, [("codex", True)])

    def test_web_stack_commands_are_exposed(self) -> None:
        result = CliRunner().invoke(aog_main, ["web", "--help"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("start", result.output)
        self.assertIn("stop", result.output)
        self.assertIn("restart", result.output)

    def test_prelude_coordinator_mode_is_dm_only(self) -> None:
        self.assertEqual(speaker_order_for("prelude"), ("dm",))

    def test_organization_bootstrap_mode_is_dm_only(self) -> None:
        self.assertEqual(speaker_order_for("organization-bootstrap"), ("dm",))

    def test_scene_prep_coordinator_mode_is_dm_only(self) -> None:
        self.assertEqual(speaker_order_for("scene-prep"), ("dm",))

    def test_intermission_mode_starts_with_full_table_order(self) -> None:
        self.assertEqual(
            speaker_order_for("intermission"),
            ("dm", "tev", "sumi", "renno", "kit"),
        )

    def test_no_mode_active_lifecycle_uses_intermission_only_at_act_boundaries(self) -> None:
        self.assertEqual(_next_mode_after_no_active_mode(None), "intermission")
        self.assertEqual(
            _next_mode_after_no_active_mode(
                "scene-play",
                active_arc="caulden-rack",
                has_prior_intermission=False,
            ),
            "intermission",
        )
        self.assertEqual(
            _next_mode_after_no_active_mode(
                "scene-play",
                active_arc="caulden-rack",
                has_prior_intermission=True,
            ),
            "scene-prep",
        )
        self.assertEqual(
            _next_mode_after_no_active_mode(
                "action",
                active_arc="caulden-rack",
                has_prior_intermission=True,
            ),
            "scene-prep",
        )
        self.assertEqual(_next_mode_after_no_active_mode("intermission"), "scene-prep")

    def test_review_stop_budget_consumes_finite_or_unlimited_stops(self) -> None:
        self.assertEqual(_consume_review_stop(0), (False, 0))
        self.assertEqual(_consume_review_stop(2), (True, 1))
        self.assertEqual(_consume_review_stop(None), (True, None))

    def test_scene_play_has_expanded_default_budget(self) -> None:
        config = make_config(Path("/tmp/aog-test"))

        self.assertEqual(config.caps.budget_for("scene-play"), 120)
        self.assertEqual(config.caps.budget_for("intermission"), 15)
        self.assertEqual(config.caps.budget_for("character-creation"), 12)

    def test_prepare_turn_peeks_next_speaker_without_consuming(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-play",
                initial_scene="opening",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(
                orchestrator,
                next_speaker={"agent": "sumi", "rapid_prompt": "react now"},
            )

            package = orchestrator.prepare_turn(state)

            self.assertIn("players/sumi/turns/0001", str(package.turn_dir))
            turn_start = package.turn_start_path.read_text(encoding="utf-8")
            self.assertIn("Turn type: **rapid-response-player**", turn_start)
            self.assertIn("methodologies/rapid-response-player.md", turn_start)
            self.assertIn("## RAPID-RESPONSE TURN", turn_start)
            self.assertNotIn("methodologies/scene-play-player.md", turn_start)
            orchestrator._peek_next_speaker_entry_from_postgres.assert_called_once_with("c1")

    def test_prepare_turn_builds_player_projection_with_writable_own_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            (campaign_root / "table").mkdir()
            (campaign_root / "table" / "scene.md").write_text("visible scene\n")
            (campaign_root / "players" / "tev" / "public").mkdir(parents=True)
            (campaign_root / "players" / "tev" / "public" / "intro.md").write_text(
                "tev intro\n"
            )
            (campaign_root / "players" / "tev" / "secrets").mkdir(parents=True)
            (campaign_root / "players" / "tev" / "secrets" / "debt.md").write_text(
                "tev secret\n"
            )
            (campaign_root / "players" / "sumi" / "public").mkdir(parents=True)
            (campaign_root / "players" / "sumi" / "public" / "intro.md").write_text(
                "sumi intro\n"
            )
            (campaign_root / "players" / "sumi" / "secrets").mkdir(parents=True)
            (campaign_root / "players" / "sumi" / "secrets" / "debt.md").write_text(
                "sumi secret\n"
            )
            (campaign_root / "dm" / "secret").mkdir(parents=True)
            (campaign_root / "dm" / "secret" / "truth.md").write_text("dm secret\n")
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-play",
                initial_scene="opening",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator, next_speaker={"agent": "tev"})

            package = orchestrator.prepare_turn(state)

            self.assertEqual(package.spawn_cwd, root / ".glass-cwd" / "c1" / "tev")
            self.assertEqual(
                package.agent_turn_start_path,
                package.spawn_cwd / "turns" / "TURN_START.md",
            )
            self.assertEqual(
                package.agent_turn_closeout_path,
                package.spawn_cwd / "turns" / "turn-closeout.json",
            )
            self.assertEqual(package.agent_turn_dir, package.spawn_cwd / "turns")
            self.assertFalse((package.spawn_cwd / "players" / "tev" / "turns").exists())
            self.assertTrue((package.spawn_cwd / "table" / "scene.md").exists())
            self.assertTrue(
                (package.spawn_cwd / "players" / "tev" / "secrets" / "debt.md").exists()
            )
            self.assertTrue(
                (package.spawn_cwd / "players" / "sumi" / "public" / "intro.md").exists()
            )
            self.assertFalse(
                (package.spawn_cwd / "players" / "sumi" / "secrets" / "debt.md").exists()
            )
            self.assertFalse((package.spawn_cwd / "dm" / "secret" / "truth.md").exists())
            self.assertFalse((package.spawn_cwd / "scratch").exists())
            self.assertEqual((package.spawn_cwd.stat().st_mode & 0o777), 0o550)
            self.assertEqual(
                (
                    (package.spawn_cwd / "players" / "tev")
                    .stat()
                    .st_mode
                    & 0o777
                ),
                0o770,
            )
            self.assertEqual(
                (
                    (package.spawn_cwd / "players" / "tev" / "secrets")
                    .stat()
                    .st_mode
                    & 0o7777
                ),
                0o2770,
            )
            self.assertEqual(
                (
                    (package.spawn_cwd / "players" / "tev" / "secrets" / "debt.md")
                    .stat()
                    .st_mode
                    & 0o777
                ),
                0o660,
            )
            self.assertEqual(((package.spawn_cwd / "table").stat().st_mode & 0o777), 0o550)
            self.assertEqual(((root / ".glass-cwd").stat().st_mode & 0o777), 0o710)
            self.assertEqual(((root / ".glass-cwd" / "c1").stat().st_mode & 0o777), 0o710)
            self.assertEqual(((package.spawn_cwd / ".claude").stat().st_mode & 0o7777), 0o2770)
            self.assertEqual(((package.spawn_cwd / ".mcp.json").stat().st_mode & 0o777), 0o660)
            turn_start = package.turn_start_path.read_text(encoding="utf-8")
            self.assertIn("## Authoring Surface", turn_start)
            self.assertIn("glass turn end", turn_start)
            self.assertIn("methodologies/scene-play-player.md", turn_start)
            _assert_actor_workspace_ready(package, target_user=None)

    def test_prepare_turn_character_surface_hides_player_persona_and_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root, skip_player_persona=True)
            templates = root / "templates"
            (templates / "instructions").mkdir(parents=True)
            (templates / "methodologies").mkdir(parents=True)
            for rel in (
                "instructions/index-character.md",
                "instructions/message-bus-character.md",
                "instructions/workspace-authoring-character.md",
                "methodologies/scene-play-character.md",
                "methodologies/action-scene-character.md",
                "methodologies/rapid-response-character.md",
            ):
                path = templates / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"{rel}\n", encoding="utf-8")
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            (campaign_root / "table").mkdir()
            (campaign_root / "table" / "scene.md").write_text("visible scene\n")
            (campaign_root / "players" / "tev" / "public").mkdir(parents=True)
            (campaign_root / "players" / "tev" / "public" / "character.md").write_text(
                "character mirror\n",
                encoding="utf-8",
            )
            (campaign_root / "players" / "tev" / "public" / "intro.md").write_text(
                "player intro\n",
                encoding="utf-8",
            )
            (campaign_root / "players" / "tev" / "persona.md").write_text(
                "player persona\n",
                encoding="utf-8",
            )
            (campaign_root / "players" / "tev" / "notes").mkdir(parents=True)
            (campaign_root / "players" / "tev" / "notes" / "private.md").write_text(
                "private note\n",
                encoding="utf-8",
            )
            (campaign_root / "players" / "tev" / "secrets").mkdir(parents=True)
            (campaign_root / "players" / "tev" / "secrets" / "debt.md").write_text(
                "secret\n",
                encoding="utf-8",
            )
            (campaign_root / "players" / "tev" / "signature-moves.md").write_text(
                "moves\n",
                encoding="utf-8",
            )
            (campaign_root / "players" / "sumi" / "public").mkdir(parents=True)
            (campaign_root / "players" / "sumi" / "public" / "character.md").write_text(
                "other character\n",
                encoding="utf-8",
            )
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-play",
                initial_scene="opening",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator, next_speaker={"agent": "tev"})

            package = orchestrator.prepare_turn(state)

            self.assertEqual(package.player_surface, PLAYER_SURFACE_CHARACTER)
            self.assertTrue(
                (package.spawn_cwd / "players" / "tev" / "public" / "character.md").exists()
            )
            self.assertTrue(
                (package.spawn_cwd / "players" / "tev" / "secrets" / "debt.md").exists()
            )
            self.assertTrue(
                (package.spawn_cwd / "players" / "tev" / "signature-moves.md").exists()
            )
            self.assertFalse((package.spawn_cwd / "players" / "tev" / "persona.md").exists())
            self.assertFalse(
                (package.spawn_cwd / "players" / "tev" / "public" / "intro.md").exists()
            )
            self.assertFalse(
                (package.spawn_cwd / "players" / "tev" / "notes" / "private.md").exists()
            )
            self.assertFalse(
                (package.spawn_cwd / "players" / "sumi" / "public" / "character.md").exists()
            )
            self.assertEqual(
                (
                    (package.spawn_cwd / "players" / "tev" / "secrets")
                    .stat()
                    .st_mode
                    & 0o7777
                ),
                0o2770,
            )
            self.assertEqual(
                (
                    (package.spawn_cwd / "players" / "tev" / "public")
                    .stat()
                    .st_mode
                    & 0o777
                ),
                0o550,
            )
            self.assertTrue(
                (package.spawn_cwd / "instructions" / "index-character.md").exists()
            )
            self.assertTrue(
                (package.spawn_cwd / "methodologies" / "scene-play-character.md").exists()
            )
            turn_start = package.turn_start_path.read_text(encoding="utf-8")
            self.assertIn("Turn type: **scene-play-character**", turn_start)
            self.assertIn("methodologies/scene-play-character.md", turn_start)
            self.assertIn("instructions/index-character.md", turn_start)
            self.assertIn("instructions/message-bus-character.md", turn_start)
            self.assertNotIn("players/tev/persona.md", turn_start)

    def test_skip_player_persona_keeps_housekeeping_on_player_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root, skip_player_persona=True)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-play",
                initial_scene="second-scene",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(
                orchestrator,
                next_speaker={
                    "agent": "tev",
                    "housekeeping": True,
                    "previous_scene": "first-scene",
                    "next_scene": "second-scene",
                },
            )

            package = orchestrator.prepare_turn(state)

            self.assertEqual(package.player_surface, "player")
            turn_start = package.turn_start_path.read_text(encoding="utf-8")
            self.assertIn("Turn type: **scene-housekeeping-player**", turn_start)
            self.assertIn("players/tev/persona.md", turn_start)

    def test_prepare_turn_character_surface_uses_rapid_response_character_methodology(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root, skip_player_persona=True)
            templates = root / "templates"
            (templates / "instructions").mkdir(parents=True)
            (templates / "methodologies").mkdir(parents=True)
            for rel in (
                "instructions/index-character.md",
                "instructions/message-bus-character.md",
                "instructions/workspace-authoring-character.md",
                "methodologies/scene-play-character.md",
                "methodologies/action-scene-character.md",
                "methodologies/rapid-response-character.md",
            ):
                path = templates / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"{rel}\n", encoding="utf-8")
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-play",
                initial_scene="opening",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(
                orchestrator,
                next_speaker={"agent": "sumi", "rapid_prompt": "Answer now."},
            )

            package = orchestrator.prepare_turn(state)

            turn_start = package.turn_start_path.read_text(encoding="utf-8")
            self.assertEqual(package.player_surface, PLAYER_SURFACE_CHARACTER)
            self.assertIn("Turn type: **rapid-response-character**", turn_start)
            self.assertIn("methodologies/rapid-response-character.md", turn_start)

    def test_prepare_turn_uses_stable_actor_projection_cwd_across_turns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-play",
                initial_scene="opening",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator, next_speaker={"agent": "tev"})

            first = orchestrator.prepare_turn(state)
            state.turn_number = 4
            second = orchestrator.prepare_turn(state)

            expected = root / ".glass-cwd" / "c1" / "tev"
            self.assertEqual(first.spawn_cwd, expected)
            self.assertEqual(second.spawn_cwd, expected)
            self.assertEqual(
                second.agent_turn_start_path,
                expected / "turns" / "TURN_START.md",
            )

    def test_claude_session_ids_are_tracked_but_flag_controls_cli_arg(self) -> None:
        for enabled in (False, True):
            with self.subTest(enabled=enabled), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                config = make_config(root, use_session_id=enabled)
                campaign_root = config.campaigns_dir / "c1"
                campaign_root.mkdir(parents=True)
                state = SessionState.new(
                    campaign="c1",
                    initial_mode="scene-play",
                    initial_scene="opening",
                    initial_budget=None,
                )
                orchestrator = Orchestrator(config, SessionStore(config))
                orchestrator.store.save = Mock()
                attach_runtime_mocks(orchestrator, next_speaker={"agent": "tev"})
                package = orchestrator.prepare_turn(state)
                current_package = package
                turn_start = package.turn_start_path.read_text(encoding="utf-8")
                if enabled:
                    self.assertIn("## Persistent Claude Session", turn_start)
                    self.assertIn(
                        "Before acting, inspect the current workspace and turn "
                        "context instead of relying on remembered conversation state.",
                        turn_start,
                    )
                    self.assertIn("Required startup checks:", turn_start)
                else:
                    self.assertNotIn("## Persistent Claude Session", turn_start)
                commands: list[list[str]] = []

                def fake_stream(command, **_kwargs):
                    commands.append(command)
                    current_package.agent_turn_prose_path.write_text(
                        "Public turn.\n",
                        encoding="utf-8",
                    )
                    current_package.agent_turn_closeout_path.write_text(
                        json.dumps(
                            {
                                "summary": "closed",
                                "state": ["no state change"],
                                "rolls": "none",
                                "next": "default",
                            }
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    return "", "", 0, False

                with (
                    patch("orchestrator.runner.ensure_background_server", return_value="http://api"),
                    patch("orchestrator.runner.mint_grant", return_value="grant"),
                    patch("orchestrator.runner._stream_subprocess", side_effect=fake_stream),
                ):
                    orchestrator._invoke_agent(
                        state,
                        AGENTS_BY_ID["tev"],
                        package,
                        queued_entry=None,
                        action_entry=None,
                    )

                session = state.claude_sessions["tev"]
                self.assertIn("session_id", session)
                self.assertEqual(session["cwd"], str(package.spawn_cwd))
                self.assertEqual(session["last_session_id_flag_enabled"], enabled)
                command = commands[0]
                prompt = command[command.index("-p") + 1]
                self.assertIn("Read turns/TURN_START.md", prompt)
                self.assertIn("turns/TURN.md", prompt)
                self.assertNotIn("players/tev/turns", prompt)
                if enabled:
                    self.assertIn("--session-id", command)
                    self.assertEqual(
                        command[command.index("--session-id") + 1],
                        session["session_id"],
                    )
                    self.assertIn("session_materialized_at", session)

                    state.turn_number = 1
                    current_package = orchestrator.prepare_turn(state)
                    with (
                        patch("orchestrator.runner.ensure_background_server", return_value="http://api"),
                        patch("orchestrator.runner.mint_grant", return_value="grant"),
                        patch("orchestrator.runner._stream_subprocess", side_effect=fake_stream),
                    ):
                        orchestrator._invoke_agent(
                            state,
                            AGENTS_BY_ID["tev"],
                            current_package,
                            queued_entry=None,
                            action_entry=None,
                        )

                    resumed = commands[1]
                    self.assertIn("--resume", resumed)
                    self.assertEqual(
                        resumed[resumed.index("--resume") + 1],
                        session["session_id"],
                    )
                    self.assertNotIn("--session-id", resumed)
                else:
                    self.assertNotIn("--session-id", command)
                    self.assertNotIn("--resume", command)

    def test_codex_provider_uses_codex_exec_without_claude_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root, agent_provider="codex", use_session_id=True)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            state = SessionState.new(
                campaign="c1",
                initial_mode="campaign-planning",
                initial_scene="planning",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            orchestrator.store.save = Mock()
            attach_runtime_mocks(orchestrator, next_speaker={"agent": "dm"})
            package = orchestrator.prepare_turn(state)
            turn_start = package.turn_start_path.read_text(encoding="utf-8")
            self.assertNotIn("## Persistent Claude Session", turn_start)

            commands: list[list[str]] = []

            def fake_stream(command, **_kwargs):
                commands.append(command)
                package.agent_turn_prose_path.write_text(
                    "Public turn.\n",
                    encoding="utf-8",
                )
                package.agent_turn_closeout_path.write_text(
                    json.dumps(
                        {
                            "summary": "closed",
                            "state": ["no state change"],
                            "rolls": "none",
                            "next": "default",
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return "", "", 0, False

            with (
                patch("orchestrator.runner.ensure_background_server", return_value="http://api"),
                patch("orchestrator.runner.mint_grant", return_value="grant"),
                patch("orchestrator.runner._resolve_provider_executable", return_value="/tmp/codex"),
                patch("orchestrator.runner._stream_subprocess", side_effect=fake_stream),
            ):
                orchestrator._invoke_agent(
                    state,
                    AGENTS_BY_ID["dm"],
                    package,
                    queued_entry=None,
                    action_entry=None,
                )

            self.assertEqual(state.claude_sessions, {})
            command = commands[0]
            self.assertEqual(command[0], "/tmp/codex")
            self.assertEqual(command[1], "exec")
            self.assertIn("--dangerously-bypass-approvals-and-sandbox", command)
            self.assertNotIn("--session-id", command)
            self.assertNotIn("--resume", command)

    def test_legacy_attached_claude_session_records_resume_by_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root, use_session_id=True)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            session_id = "11111111-2222-4333-8444-555555555555"
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-play",
                initial_scene="opening",
                initial_budget=None,
            )
            state.claude_sessions["tev"] = {
                "actor": "tev",
                "role": "player",
                "session_id": session_id,
                "cwd": str(root / ".glass-cwd" / "c1" / "tev"),
                "last_session_id_flag_enabled": True,
                "last_returncode": 0,
            }
            orchestrator = Orchestrator(config, SessionStore(config))
            orchestrator.store.save = Mock()
            attach_runtime_mocks(orchestrator, next_speaker={"agent": "tev"})
            package = orchestrator.prepare_turn(state)
            commands: list[list[str]] = []

            def fake_stream(command, **_kwargs):
                commands.append(command)
                package.agent_turn_prose_path.write_text(
                    "Public turn.\n",
                    encoding="utf-8",
                )
                package.agent_turn_closeout_path.write_text(
                    json.dumps(
                        {
                            "summary": "closed",
                            "state": ["no state change"],
                            "rolls": "none",
                            "next": "default",
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return "", "", 0, False

            with (
                patch("orchestrator.runner.ensure_background_server", return_value="http://api"),
                patch("orchestrator.runner.mint_grant", return_value="grant"),
                patch("orchestrator.runner._stream_subprocess", side_effect=fake_stream),
            ):
                orchestrator._invoke_agent(
                    state,
                    AGENTS_BY_ID["tev"],
                    package,
                    queued_entry=None,
                    action_entry=None,
                )

            command = commands[0]
            self.assertIn("--resume", command)
            self.assertEqual(command[command.index("--resume") + 1], session_id)
            self.assertNotIn("--session-id", command)

    def test_prepare_turn_dm_projection_includes_dm_arc_prep(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            arc_root = campaign_root / "arcs" / "opening"
            scene_root = arc_root / "scenes" / "first-room"
            scene_root.mkdir(parents=True)
            (arc_root / "plan.md").write_text("dm arc plan\n")
            (scene_root / "prep.md").write_text("dm scene prep\n")
            state = SessionState.new(
                campaign="c1",
                initial_mode="campaign-planning",
                initial_scene="planning",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator, next_speaker={"agent": "dm"})

            package = orchestrator.prepare_turn(state)

            self.assertIn("dm/turns/0001", str(package.turn_dir))
            self.assertTrue((package.spawn_cwd / "arcs" / "opening" / "plan.md").exists())
            self.assertEqual((package.spawn_cwd.stat().st_mode & 0o777), 0o770)
            self.assertEqual(((package.spawn_cwd / "dm").stat().st_mode & 0o777), 0o770)
            self.assertEqual(
                ((package.spawn_cwd / "arcs" / "opening").stat().st_mode & 0o777),
                0o770,
            )
            self.assertEqual(
                (
                    (package.spawn_cwd / "arcs" / "opening" / "plan.md")
                    .stat()
                    .st_mode
                    & 0o777
                ),
                0o660,
            )
            self.assertTrue(
                (
                    package.spawn_cwd
                    / "arcs"
                    / "opening"
                    / "scenes"
                    / "first-room"
                    / "prep.md"
                ).exists()
            )
            turn_start = package.turn_start_path.read_text(encoding="utf-8")
            self.assertIn("methodologies/` holds required ordered workflows", turn_start)
            self.assertIn("TURN_START selects the one methodology", turn_start)
            self.assertNotIn("optional current-turn working memory", turn_start)
            self.assertIn("methodologies/closeout.md", turn_start)

    def test_projection_refresh_preserves_unsynced_projected_edits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            (campaign_root / "table").mkdir()
            (campaign_root / "table" / "index.md").write_text("legacy index\n")
            (campaign_root / "table" / "visible-artifact.md").write_text(
                "canonical old\n"
            )
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-play",
                initial_scene="opening",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator, next_speaker={"agent": "dm"})
            package = orchestrator.prepare_turn(state)

            projected_table = package.spawn_cwd / "table" / "visible-artifact.md"
            projected_table.write_text("local projected edit\n")
            (campaign_root / "table" / "visible-artifact.md").write_text(
                "canonical new\n"
            )

            refresh_projection_from_canonical(
                config=config,
                campaign_root=campaign_root,
                agent=AGENTS_BY_ID["dm"],
                turn_number=1,
                projection_root=package.spawn_cwd,
            )

            self.assertEqual(projected_table.read_text(), "local projected edit\n")
            self.assertFalse((package.spawn_cwd / "table" / "index.md").exists())

    def test_character_creation_turn_omits_recent_turn_excerpts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            (campaign_root / "transcript.md").write_text(
                "Sumi builds directly around Tev's hook.",
                encoding="utf-8",
            )
            state = SessionState.new(
                campaign="c1",
                initial_mode="character-creation",
                initial_scene="character-creation",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator, next_speaker={"agent": "tev"})

            package = orchestrator.prepare_turn(state)

            turn_start = package.turn_start_path.read_text(encoding="utf-8")
            self.assertIn(
                "Prior character-creation turns are intentionally not embedded",
                turn_start,
            )
            self.assertIn("character-design turns", turn_start)
            self.assertNotIn("Sumi builds directly around Tev's hook", turn_start)
            self.assertIn(
                "Turn type: **character-creation-player-build**",
                turn_start,
            )
            self.assertIn("--table-presence", turn_start)
            self.assertIn("--non-work-want", turn_start)
            self.assertIn("--opening-social-action", turn_start)
            self.assertNotIn("players/tev/secrets", turn_start)
            self.assertNotIn("glass msg secret dm", turn_start)

    def test_character_creation_turn_type_follows_authored_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            for player_id in ("kit", "renno", "sumi", "tev"):
                public = campaign_root / "players" / player_id / "public"
                public.mkdir(parents=True)
                (public / "intro.md").write_text("intro\n", encoding="utf-8")
                (public / "character.md").write_text("character\n", encoding="utf-8")
            state = SessionState.new(
                campaign="c1",
                initial_mode="character-creation",
                initial_scene="character-creation",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator, next_speaker={"agent": "dm"})

            package = orchestrator.prepare_turn(state)
            turn_start = package.turn_start_path.read_text(encoding="utf-8")

            self.assertIn(
                "Turn type: **character-creation-dm-relationship-setup**",
                turn_start,
            )
            self.assertIn(
                "methodologies/character-creation-dm-relationship-setup.md",
                turn_start,
            )

            orchestrator._peek_next_speaker_entry_from_postgres.return_value = {
                "agent": "tev"
            }
            package = orchestrator.prepare_turn(state)
            turn_start = package.turn_start_path.read_text(encoding="utf-8")

            self.assertIn(
                "Turn type: **character-creation-player-relationship**",
                turn_start,
            )
            self.assertIn(
                "methodologies/character-creation-player-relationship.md",
                turn_start,
            )

            for player_id in ("kit", "renno", "sumi", "tev"):
                (
                    campaign_root
                    / "players"
                    / player_id
                    / "public"
                    / "relationships.md"
                ).write_text("relationship\n", encoding="utf-8")
            orchestrator._peek_next_speaker_entry_from_postgres.return_value = {
                "agent": "dm"
            }
            package = orchestrator.prepare_turn(state)
            turn_start = package.turn_start_path.read_text(encoding="utf-8")

            self.assertIn(
                "Turn type: **character-creation-dm-ratification**",
                turn_start,
            )
            self.assertIn(
                "methodologies/character-creation-dm-ratification.md",
                turn_start,
            )

    def test_scene_play_turn_uses_scene_summary_not_recent_turn_prose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            scene_root = campaign_root / "arcs" / "first-arc" / "scenes" / "opening"
            scene_root.mkdir(parents=True)
            (scene_root / "summary.md").write_text(
                "- Turn 3: Drova logged the packet as year-mark form.\n",
                encoding="utf-8",
            )
            (campaign_root / "transcript.md").write_text(
                "Full recent narration should not be pasted into TURN_START.",
                encoding="utf-8",
            )
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-play",
                initial_scene="opening",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator, next_speaker={"agent": "tev"})

            package = orchestrator.prepare_turn(state)

            turn_start = package.turn_start_path.read_text(encoding="utf-8")
            self.assertIn("## Scene Summary", turn_start)
            self.assertIn("Drova logged the packet as year-mark form", turn_start)
            self.assertIn("## Recent Turn Summaries", turn_start)
            self.assertIn("Recent full turn narration is intentionally not embedded", turn_start)
            self.assertIn("glass turns find --scene opening", turn_start)
            self.assertNotIn("Full recent narration should not be pasted", turn_start)

    def test_housekeeping_turn_uses_non_plot_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-play",
                initial_scene="second-scene",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(
                orchestrator,
                next_speaker={
                    "agent": "tev",
                    "housekeeping": True,
                    "previous_scene": "first-scene",
                    "next_scene": "second-scene",
                },
            )

            package = orchestrator.prepare_turn(state)

            turn_start = package.turn_start_path.read_text(encoding="utf-8")
            self.assertIn("## HOUSEKEEPING TURN", turn_start)
            self.assertIn("Do not advance plot", turn_start)
            self.assertIn("Scene just closed: `first-scene`", turn_start)
            self.assertIn("Next scene staged: `second-scene`", turn_start)
            self.assertIn("Turn type: **scene-housekeeping-player**", turn_start)
            self.assertIn("methodologies/scene-housekeeping-player.md", turn_start)
            self.assertNotIn("## Creative Influence", turn_start)

    def test_dm_closing_turn_uses_transition_methodology(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-play",
                initial_scene="first-scene",
                initial_budget=None,
            )
            state.scene_closing_turns = 0
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator, next_speaker={"agent": "dm"})

            package = orchestrator.prepare_turn(state)

            turn_start = package.turn_start_path.read_text(encoding="utf-8")
            self.assertIn("Turn type: **scene-transition-dm**", turn_start)
            self.assertIn("## SCENE TRANSITION TURN", turn_start)
            self.assertIn("methodologies/scene-transition-dm.md", turn_start)
            self.assertNotIn("methodologies/scene-play-dm.md", turn_start)
            self.assertNotIn("## Creative Influence", turn_start)

    def test_prepare_turn_uses_action_order_when_queue_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            state = SessionState.new(
                campaign="c1",
                initial_mode="action",
                initial_scene="ambush",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(
                orchestrator,
                action_order={
                    "mode": "action",
                    "scene_id": "ambush",
                    "round": 1,
                    "cursor": 0,
                    "order": ["kit", "dm", "tev"],
                },
            )

            package = orchestrator.prepare_turn(state)

            self.assertIn("players/kit/turns/0001", str(package.turn_dir))
            turn_start = package.turn_start_path.read_text(encoding="utf-8")
            self.assertIn(
                "You are **Kit**, a player in a Glass Frontier TTRPG session.",
                turn_start,
            )
            self.assertIn("You are playing the character summarized", turn_start)
            self.assertIn("## ACTION-SCENE TURN", turn_start)
            self.assertIn("`kit -> dm -> tev`", turn_start)
            self.assertIn("Turn type: **action-scene-player**", turn_start)
            self.assertIn("methodologies/action-scene-player.md", turn_start)
            self.assertIn("## Creative Influence", turn_start)
            self.assertIn("Verse phrase:", turn_start)
            self.assertIn("Tarot:", turn_start)

    def test_dm_action_turn_without_order_uses_opening_methodology(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            state = SessionState.new(
                campaign="c1",
                initial_mode="action",
                initial_scene="ambush",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator, next_speaker={"agent": "dm"})

            package = orchestrator.prepare_turn(state)

            turn_start = package.turn_start_path.read_text(encoding="utf-8")
            self.assertIn("Turn type: **action-scene-opening-dm**", turn_start)
            self.assertIn("methodologies/action-scene-opening-dm.md", turn_start)
            self.assertNotIn("methodologies/action-scene-dm.md", turn_start)

    def test_creative_influence_omitted_during_bootstrap_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            state = SessionState.new(
                campaign="c1",
                initial_mode="organization-bootstrap",
                initial_scene="organization-bootstrap",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator)

            package = orchestrator.prepare_turn(state)

            turn_start = package.turn_start_path.read_text(encoding="utf-8")
            self.assertIn("Turn type: **organization-bootstrap**", turn_start)
            self.assertIn("methodologies/organization-bootstrap.md", turn_start)
            self.assertNotIn("## Creative Influence", turn_start)
            self.assertNotIn("Verse phrase:", turn_start)

    def test_organization_bootstrap_validation_accepts_org_only_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            (campaign_root / "shared" / "lore").mkdir(parents=True)
            (campaign_root / "dm" / "notes").mkdir(parents=True)
            (campaign_root / "table").mkdir(parents=True)
            (campaign_root / "shared" / "lore" / "organization.md").write_text(
                "org public\n",
                encoding="utf-8",
            )
            (campaign_root / "dm" / "notes" / "organization.md").write_text(
                "org private\n",
                encoding="utf-8",
            )
            (campaign_root / "table" / "scene.md").write_text(
                "character creation brief\n",
                encoding="utf-8",
            )

            with (
                patch("cli.config.load_config", return_value={}),
                patch("cli.db.load_pg_config", return_value=object()),
                patch("cli.db.clock_list", return_value=[]),
                patch("cli.db.connect") as connect,
            ):
                connect.return_value.__enter__.return_value = object()
                _validate_organization_bootstrap_complete(
                    SimpleNamespace(config=config),
                    "c1",
                )

    def test_campaign_planning_validation_requires_main_arc_and_prelude(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            (campaign_root / "dm").mkdir(parents=True)
            (campaign_root / "shared").mkdir(parents=True)
            (campaign_root / "arcs" / "opening").mkdir(parents=True)
            (campaign_root / "arcs" / "prelude").mkdir(parents=True)
            (campaign_root / "dm" / "foundation.md").write_text(
                "foundation\n",
                encoding="utf-8",
            )
            (campaign_root / "context.md").write_text("context\n", encoding="utf-8")
            (campaign_root / "shared" / "campaign-framing.md").write_text(
                "framing\n",
                encoding="utf-8",
            )

            _validate_campaign_planning_complete(
                SimpleNamespace(config=config),
                "c1",
            )

    def test_creative_influence_omitted_during_prelude_coordinator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            state = SessionState.new(
                campaign="c1",
                initial_mode="prelude",
                initial_scene="prelude",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator)

            package = orchestrator.prepare_turn(state)

            turn_start = package.turn_start_path.read_text(encoding="utf-8")
            self.assertIn(
                "You are **Mara**, the DM for a Glass Frontier TTRPG campaign.",
                turn_start,
            )
            self.assertNotIn("operator", turn_start)
            self.assertNotIn("shakedown", turn_start)
            self.assertIn("methodologies/prelude-arc.md", turn_start)
            self.assertNotIn("## Creative Influence", turn_start)

    def test_public_prose_detects_glass_command_lines(self) -> None:
        prose = (
            "The door opens.\n\n"
            "> glass scene create ambush --type action\n"
            "glass shards scatter across the floor.\n"
            "glass turn rapid-round \"react\"\n"
        )

        self.assertEqual(
            _tool_transcript_lines(prose),
            [
                "> glass scene create ambush --type action",
                'glass turn rapid-round "react"',
            ],
        )

    def test_commit_turn_warns_on_glass_command_lines_without_failing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            turn_dir = campaign_root / "players" / "tev" / "turns" / "0001"
            turn_dir.mkdir(parents=True)
            turn_file = turn_dir / "TURN.md"
            turn_file.write_text(
                "Done.\n\nglass sync apply players/tev/public/intro.md\n",
                encoding="utf-8",
            )
            state = SessionState.new(
                campaign="c1",
                initial_mode="character-creation",
                initial_scene="character-creation",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            orchestrator.store.glass.invoke = Mock()
            orchestrator.store.sync_from_glass = Mock(return_value=state)
            orchestrator._tick_closing_countdown = Mock()
            orchestrator._validate_prelude_dm_handoff = Mock()
            result = TurnResult(
                turn_id="c1-t0001",
                agent=AGENTS_BY_ID["tev"],
                turn_dir=turn_dir,
                spawn_cwd=campaign_root,
                prose="Done.\n\nglass sync apply players/tev/public/intro.md\n",
                dry_run=False,
                turn_prose_path=turn_file,
                duration_seconds=12.3456,
            )

            orchestrator.commit_turn(state, result)

            events = [
                json.loads(line)
                for line in (campaign_root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            warning = next(event for event in events if event["event"] == "turn.warning")
            self.assertEqual(warning["reason"], "turn_prose_contains_glass_command_lines")
            self.assertEqual(
                warning["lines"],
                ["glass sync apply players/tev/public/intro.md"],
            )
            committed = next(event for event in events if event["event"] == "turn.committed")
            self.assertEqual(committed["duration_seconds"], 12.346)
            orchestrator.store.glass.invoke.assert_called_once()

    def test_unsynced_workspace_changes_detects_new_and_modified_authoring_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            (campaign_root / "players" / "tev" / "public").mkdir(parents=True)
            (campaign_root / "players" / "tev" / "public" / "intro.md").write_text(
                "old intro\n",
                encoding="utf-8",
            )
            state = SessionState.new(
                campaign="c1",
                initial_mode="character-creation",
                initial_scene="character-creation",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator, next_speaker={"agent": "tev"})
            package = orchestrator.prepare_turn(state)

            (package.spawn_cwd / "players" / "tev" / "public" / "intro.md").write_text(
                "changed intro\n",
                encoding="utf-8",
            )
            (package.spawn_cwd / "players" / "tev" / "public" / "extra.md").write_text(
                "new file\n",
                encoding="utf-8",
            )
            (package.agent_turn_dir / "draft.md").write_text(
                "turn artifacts are intentionally ignored\n",
                encoding="utf-8",
            )

            self.assertEqual(
                unsynced_workspace_changes(package.spawn_cwd, AGENTS_BY_ID["tev"]),
                [
                    {"path": "players/tev/public/extra.md", "status": "new"},
                    {"path": "players/tev/public/intro.md", "status": "modified"},
                ],
            )

    def test_prelude_dm_turn_without_handoff_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            state = SessionState.new(
                campaign="c1",
                initial_mode="prelude",
                initial_scene="prelude",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator)
            result = TurnResult(
                turn_id="c1-t0001",
                agent=AGENTS_BY_ID["dm"],
                turn_dir=campaign_root / "dm" / "turns" / "0001",
                spawn_cwd=campaign_root,
                prose="What do you do?",
                dry_run=False,
            )

            with self.assertRaises(TurnFailure) as caught:
                orchestrator._validate_prelude_dm_handoff(
                    state,
                    result,
                    state.active_mode,
                )
            self.assertEqual(caught.exception.failure["reason"], "prelude_dm_no_handoff")

    def test_prelude_dm_turn_with_queued_player_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            state = SessionState.new(
                campaign="c1",
                initial_mode="prelude",
                initial_scene="prelude",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator, next_speaker={"agent": "tev"})
            result = TurnResult(
                turn_id="c1-t0001",
                agent=AGENTS_BY_ID["dm"],
                turn_dir=campaign_root / "dm" / "turns" / "0001",
                spawn_cwd=campaign_root,
                prose="Tev, what do you do?",
                dry_run=False,
            )

            orchestrator._validate_prelude_dm_handoff(
                state,
                result,
                state.active_mode,
            )

    def test_scene_prep_dm_turn_without_play_mode_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-prep",
                initial_scene="opening-setup",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator)
            result = TurnResult(
                turn_id="c1-t0001",
                agent=AGENTS_BY_ID["dm"],
                turn_dir=campaign_root / "dm" / "turns" / "0001",
                spawn_cwd=campaign_root,
                prose="Prep notes only.",
                dry_run=False,
            )

            with self.assertRaises(TurnFailure) as caught:
                orchestrator._validate_scene_prep_dm_handoff(
                    state,
                    result,
                    state.active_mode,
                )
            self.assertEqual(caught.exception.failure["reason"], "scene_prep_no_handoff")

    def test_scene_prep_dm_turn_with_play_mode_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-prep",
                initial_scene="opening-setup",
                initial_budget=None,
            )
            previous = state.active_mode
            state.mode_stack.append(
                state.mode_stack[0].__class__(
                    mode="scene-play",
                    scene_id="opening",
                    started_at=state.mode_stack[0].started_at,
                    turn_budget_remaining=None,
                )
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator)
            result = TurnResult(
                turn_id="c1-t0001",
                agent=AGENTS_BY_ID["dm"],
                turn_dir=campaign_root / "dm" / "turns" / "0001",
                spawn_cwd=campaign_root,
                prose="Scene starts.",
                dry_run=False,
            )

            orchestrator._validate_scene_prep_dm_handoff(state, result, previous)

    def test_scene_close_inside_open_arc_without_next_mode_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-play",
                initial_scene="first-scene",
                initial_budget=None,
            )
            previous = state.active_mode
            state.mode_stack = []
            orchestrator = Orchestrator(config, SessionStore(config))
            orchestrator.store._load_glass_state = Mock(
                return_value={"active_arc": "caulden-rack", "closed_arcs": []}
            )
            result = TurnResult(
                turn_id="c1-t0001",
                agent=AGENTS_BY_ID["dm"],
                turn_dir=campaign_root / "dm" / "turns" / "0001",
                spawn_cwd=campaign_root,
                prose="Scene closes.",
                dry_run=False,
            )

            with self.assertRaises(TurnFailure) as caught:
                orchestrator._validate_scene_boundary_dm_handoff(
                    state,
                    result,
                    previous,
                )
            self.assertEqual(
                caught.exception.failure["reason"],
                "scene_boundary_no_next_scene",
            )

    def test_advance_action_order_delegates_to_postgres(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            orchestrator = Orchestrator(config, SessionStore(config))
            orchestrator._advance_action_order_in_postgres = Mock(return_value=True)
            expected = {
                "agent": "dm",
                "mode": "action",
                "scene_id": "ambush",
                "cursor": 1,
                "order": ["kit", "dm"],
            }

            orchestrator._advance_action_order("c1", expected)

            orchestrator._advance_action_order_in_postgres.assert_called_once_with(
                "c1", expected
            )


if __name__ == "__main__":
    unittest.main()
