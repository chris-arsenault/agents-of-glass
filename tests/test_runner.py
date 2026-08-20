import tempfile
import unittest
import json
import subprocess
import tomllib
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch

import click
from click.testing import CliRunner

from orchestrator import permissions
from orchestrator.config import (
    AogConfig,
    CapsConfig,
    ClaudeConfig,
    OrchestratorConfig,
    PromptsConfig,
    config_env_value,
    provider_for_actor,
)
from orchestrator.context import ContextBuilder, PLAYER_SURFACE_CHARACTER
from orchestrator.main import main as aog_main
from orchestrator.main import _consume_review_stop
from orchestrator.main import _next_mode_after_no_active_mode
from orchestrator.main import _recover_bootstrap_phase_after_budget_exhaustion
from orchestrator.main import _store_operator_org_direction
from orchestrator.main import _validate_campaign_planning_complete
from orchestrator.main import _validate_character_creation_complete
from orchestrator.main import _validate_organization_bootstrap_complete
from orchestrator.runner import (
    Orchestrator,
    TurnFailure,
    TurnResult,
    _glass_mcp_command,
    _live_stream_policy_for_provider,
    _stderr_prefix_for_provider,
    _tool_transcript_lines,
)
from orchestrator.state import AGENTS_BY_ID, SessionState, next_agent_for, speaker_order_for
from orchestrator.store import SessionStore
from orchestrator.system_prompt import assemble_system_prompt, materialize_system_prompt


def committed_turn(prose: str = "Public turn.") -> dict:
    return {
        "prose": prose,
        "turn_end": {
            "summary": "closed",
            "state": ["no state change"],
            "rolls": "none",
            "next": "default",
            "valid": True,
            "problems": [],
        },
    }


def make_config(
    root: Path,
    *,
    use_session_id: bool = False,
    agent_provider: str = "claude",
    codex_players: tuple[str, ...] = ("tev", "sumi"),
    skip_player_persona: bool = False,
    turn_minimum_seconds: int = 0,
) -> AogConfig:
    return AogConfig(
        repo_root=root,
        config_path=None,
        templates_dir=root / "templates",
        campaigns_dir=root / "campaigns",
        lore_path=root / "lore",
        agent_provider=agent_provider,
        codex_players=codex_players,
        skip_player_persona=skip_player_persona,
        claude=ClaudeConfig(
            model=None,
            turn_timeout_seconds=60,
            use_session_id=use_session_id,
        ),
        prompts=PromptsConfig(
            dm_base=root / "templates" / "prompts" / "dm-base.md",
            player_base=root / "templates" / "prompts" / "player-base.md",
        ),
        caps=CapsConfig(
            session_max_turns=200,
            mode_default_max_turns=12,
            mode_scene_play_max_turns=120,
            mode_action_max_turns=120,
        ),
        orchestrator=OrchestratorConfig(
            turn_minimum_seconds=turn_minimum_seconds,
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

    def _render_turn_start_text(
        self,
        root: Path,
        *,
        state: SessionState,
        agent_id: str,
        turn_meta: dict | None = None,
        glass_state: dict | None = None,
    ) -> str:
        config = make_config(root)
        campaign_root = config.campaigns_dir / state.campaign
        campaign_root.mkdir(parents=True, exist_ok=True)
        spawn_cwd = config.templates_dir
        spawn_cwd.mkdir(parents=True, exist_ok=True)
        builder = ContextBuilder(config, SessionStore(config))
        builder.store._recent_turn_records = Mock(return_value=[])
        builder._glass_runtime_state = Mock(return_value=glass_state or {})
        return builder._render_turn_start(
            state,
            AGENTS_BY_ID[agent_id],
            "c1-t0001",
            spawn_cwd,
            turn_meta=turn_meta or {},
        )

    def test_dm_agent_uses_mara_unix_user_when_provisioned(self) -> None:
        with patch.object(permissions, "has_provisioned_users", return_value=True):
            self.assertEqual(permissions.player_user_for("dm"), "aog-mara")

    def test_provider_specific_stderr_prefixes(self) -> None:
        self.assertEqual(_stderr_prefix_for_provider("claude", "[dm] "), "[dm] (err) ")
        self.assertEqual(_stderr_prefix_for_provider("codex", "[dm] "), "[dm] (log) ")
        self.assertEqual(_live_stream_policy_for_provider("claude"), (True, True))
        self.assertEqual(_live_stream_policy_for_provider("codex"), (False, False))

    def test_provider_routing_uses_mixed_codex_roster(self) -> None:
        config = make_config(
            Path("/tmp/aog-test"),
            agent_provider="mixed-codex",
            codex_players=("tev", "sumi"),
        )

        self.assertEqual(
            provider_for_actor(config, actor_id="dm", role="dm"),
            "codex",
        )
        self.assertEqual(
            provider_for_actor(config, actor_id="tev", role="player"),
            "codex",
        )
        self.assertEqual(
            provider_for_actor(config, actor_id="sumi", role="player"),
            "codex",
        )
        self.assertEqual(
            provider_for_actor(config, actor_id="renno", role="player"),
            "claude",
        )
        self.assertEqual(
            provider_for_actor(config, actor_id="kit", role="player"),
            "claude",
        )

    def test_campaign_permissions_do_not_grant_agent_filesystem_authority(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(permissions, "has_provisioned_users", return_value=True),
            patch.object(permissions, "_run_helper") as run_helper,
        ):
            root = Path(tmp)
            campaign = root / "campaigns" / "c1"
            campaign.mkdir(parents=True)

            self.assertFalse(permissions.apply_campaign_permissions(campaign))

            run_helper.assert_not_called()

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
        self.assertIn("--turn-minimum-seconds", result.output)

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
                seen.append((cli.config.agent_provider, cli.config.skip_player_persona))

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
            self.assertEqual(seen, [("mixed-codex", True)])

    def test_campaign_run_turn_minimum_flag_overrides_toml(self) -> None:
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
                        "[orchestrator]",
                        "turn_minimum_seconds = 600",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            seen: list[int] = []

            def fake_lifecycle(cli, *_args, **_kwargs):
                seen.append(cli.config.orchestrator.turn_minimum_seconds)

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
                        "--turn-minimum-seconds",
                        "30",
                    ],
                )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(seen, [30])

    def test_org_direction_is_stored_as_dm_fact_not_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            cli = SimpleNamespace(config=config)
            captured = {}

            def fake_set_fact(**kwargs):
                captured.update(kwargs)
                return {"status": "stored"}

            with patch("cli.facts.set_fact", side_effect=fake_set_fact):
                _store_operator_org_direction(
                    cli=cli,
                    campaign_id="c1",
                    phase_state={"phase": "init"},
                    direction="deep sheer monster extermination",
                )

            spec = captured["spec"]
            self.assertEqual(spec.subject_id, "operator")
            self.assertEqual(spec.predicate, "org-direction")
            self.assertEqual(spec.visibility, "dm")
            self.assertEqual(spec.scope_id, "campaign")
            self.assertFalse(
                (
                    config.campaigns_dir / "c1" / "dm" / "notes" / "operator-org-direction.md"
                ).exists()
            )

    def test_web_stack_commands_are_exposed(self) -> None:
        result = CliRunner().invoke(aog_main, ["web", "--help"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("start", result.output)
        self.assertIn("stop", result.output)
        self.assertIn("restart", result.output)

    def test_organization_bootstrap_mode_is_dm_only(self) -> None:
        self.assertEqual(speaker_order_for("organization-bootstrap"), ("dm",))

    def test_scene_prep_coordinator_mode_is_dm_only(self) -> None:
        self.assertEqual(speaker_order_for("scene-prep"), ("dm",))

    def test_scene_play_uses_player_cursor_after_dm_turn(self) -> None:
        state = SessionState.new(
            campaign="c1",
            initial_mode="scene-play",
            initial_scene="opening",
            initial_budget=None,
        )
        state.last_speaker = "dm"
        state.run_metadata["scene_play_next_player"] = "sumi"

        self.assertEqual(next_agent_for(state).id, "sumi")

    def test_scene_play_player_turn_advances_cursor(self) -> None:
        state = SessionState.new(
            campaign="c1",
            initial_mode="scene-play",
            initial_scene="opening",
            initial_budget=None,
        )

        state.record_committed_turn(AGENTS_BY_ID["tev"])

        self.assertEqual(state.run_metadata["scene_play_next_player"], "sumi")

    def test_state_sync_infers_scene_play_cursor_for_existing_campaign(self) -> None:
        store = SessionStore(make_config(Path("/tmp/aog-test")))
        state = store._state_from_glass_state(
            {
                "campaign": "c1",
                "status": "active",
                "turn_counter": 3,
                "mode_stack": [
                    {
                        "mode": "scene-play",
                        "scene_id": "opening",
                        "started_at": "2026-05-15T00:00:00+00:00",
                    }
                ],
                "turns": [
                    {
                        "speaker": "tev",
                        "mode": "scene-play",
                        "scene_id": "opening",
                    },
                    {
                        "speaker": "sumi",
                        "mode": "scene-play",
                        "scene_id": "opening",
                    },
                    {
                        "speaker": "dm",
                        "mode": "scene-play",
                        "scene_id": "opening",
                    },
                ],
            },
            existing=None,
        )

        self.assertEqual(state.run_metadata["scene_play_next_player"], "renno")
        self.assertEqual(next_agent_for(state).id, "renno")

    def test_run_loop_waits_for_turn_minimum_between_turns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root, turn_minimum_seconds=10)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-play",
                initial_scene="opening",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator)
            orchestrator.store.save = Mock()
            orchestrator.run_one_turn = Mock(
                return_value=TurnResult(
                    turn_id="c1-t0001",
                    agent=AGENTS_BY_ID["tev"],
                    turn_dir=campaign_root / "players" / "tev" / "turns" / "0001",
                    spawn_cwd=campaign_root,
                    prose="Tev acts.",
                    dry_run=False,
                )
            )
            orchestrator.commit_turn = Mock()

            with (
                patch("orchestrator.runner.time.monotonic", side_effect=[100.0, 103.0, 200.0]),
                patch("orchestrator.runner.time.sleep") as sleep,
                patch("builtins.print"),
            ):
                turns_run = orchestrator.run_loop(
                    state,
                    max_turns=2,
                    dry_run=False,
                )

            self.assertEqual(turns_run, 2)
            sleep.assert_called_once_with(7.0)

    def test_turn_minimum_sleep_ignores_dry_run(self) -> None:
        config = make_config(Path("/tmp/aog-test"), turn_minimum_seconds=10)
        orchestrator = Orchestrator(config, SessionStore(config))

        with patch("orchestrator.runner.time.sleep") as sleep:
            orchestrator._sleep_for_turn_minimum(100.0, dry_run=True)

        sleep.assert_not_called()

    def test_intermission_mode_starts_with_full_table_order(self) -> None:
        self.assertEqual(
            speaker_order_for("intermission"),
            ("dm", "tev", "sumi", "renno", "kit"),
        )

    def test_no_mode_active_lifecycle_uses_intermission_only_at_act_boundaries(self) -> None:
        self.assertEqual(_next_mode_after_no_active_mode(None), "intermission")
        self.assertEqual(
            _next_mode_after_no_active_mode(
                "campaign-planning",
                active_arc="caulden-rack",
                has_prior_intermission=False,
            ),
            "scene-prep",
        )
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

    def test_scene_and_action_modes_have_expanded_default_budgets(self) -> None:
        config = make_config(Path("/tmp/aog-test"))

        self.assertEqual(config.caps.budget_for("scene-play"), 120)
        self.assertEqual(config.caps.budget_for("action"), 120)
        self.assertEqual(config.caps.budget_for("intermission"), 15)
        self.assertEqual(config.caps.budget_for("character-creation"), 12)
        self.assertEqual(config.caps.budget_for("combat"), 12)

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

            self.assertEqual(package.turn_dir, campaign_root)
            self.assertEqual(package.spawn_cwd, config.templates_dir)
            turn_start = package.prompt
            self.assertIn("Methodology: **rapid-response-player**", turn_start)
            self.assertIn("methodologies/rapid-response-player.md", turn_start)
            self.assertIn("## RAPID-RESPONSE TURN", turn_start)
            self.assertNotIn("methodologies/scene-play-player.md", turn_start)
            orchestrator._peek_next_speaker_entry_from_postgres.assert_called_once_with("c1")

    def test_prepare_turn_injects_single_prompt_without_player_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            (campaign_root / "table").mkdir()
            (campaign_root / "table" / "scene.md").write_text("visible scene\n")
            (campaign_root / "players" / "tev" / "public").mkdir(parents=True)
            (campaign_root / "players" / "tev" / "public" / "intro.md").write_text("tev intro\n")
            (campaign_root / "players" / "tev" / "secrets").mkdir(parents=True)
            (campaign_root / "players" / "tev" / "secrets" / "debt.md").write_text("tev secret\n")
            (campaign_root / "players" / "sumi" / "public").mkdir(parents=True)
            (campaign_root / "players" / "sumi" / "public" / "intro.md").write_text("sumi intro\n")
            (campaign_root / "players" / "sumi" / "secrets").mkdir(parents=True)
            (campaign_root / "players" / "sumi" / "secrets" / "debt.md").write_text("sumi secret\n")
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

            self.assertEqual(package.spawn_cwd, config.templates_dir)
            self.assertEqual(package.turn_dir, campaign_root)
            self.assertFalse((root / ".glass-cwd").exists())
            self.assertFalse(hasattr(package, "agent_turn_start_path"))
            self.assertFalse(hasattr(package, "agent_turn_closeout_path"))
            turn_start = package.prompt
            self.assertIn("## Authoring Surface", turn_start)
            self.assertIn("Do not write files", turn_start)
            self.assertIn('glass_turn_append(body="<public prose>")', turn_start)
            self.assertIn("glass_done(", turn_start)
            self.assertIn("canonical `tools/list`", turn_start)
            self.assertIn('glass_help(command="<glass_tool_name>")', turn_start)
            self.assertNotIn("## Active-Play Roll Momentum", turn_start)
            self.assertIn("methodologies/scene-play-player.md", turn_start)
            self.assertIn("Valid recipients this turn:", turn_start)
            self.assertIn("- `party`", turn_start)
            self.assertIn("- `dm`", turn_start)
            self.assertIn("- `tev`", turn_start)
            self.assertIn("- `sumi`", turn_start)
            self.assertIn("- `renno`", turn_start)
            self.assertIn("- `kit`", turn_start)
            self.assertNotIn("TURN_START", turn_start)
            self.assertNotIn("TURN.md", turn_start)

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
                "---\ncharacter_id: tern-korr\n---\ncharacter mirror\n",
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
            (campaign_root / "players" / "sumi" / "public").mkdir(parents=True)
            (campaign_root / "players" / "sumi" / "public" / "character.md").write_text(
                "---\ncharacter_id: duva-doraleth\n---\nother character\n",
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
            orchestrator.context_builder._campaign_characters_from_postgres = Mock(
                return_value=[
                    {"character_id": "tern-korr", "player_id": "tev"},
                    {"character_id": "duva-doraleth", "player_id": "sumi"},
                ]
            )

            package = orchestrator.prepare_turn(state)

            self.assertEqual(package.player_surface, PLAYER_SURFACE_CHARACTER)
            self.assertEqual(package.spawn_cwd, config.templates_dir)
            self.assertFalse((root / ".glass-cwd").exists())
            turn_start = package.prompt
            self.assertIn("Methodology: **scene-play-character**", turn_start)
            self.assertIn("methodologies/scene-play-character.md", turn_start)
            self.assertIn("instructions/index-character.md", turn_start)
            self.assertIn("instructions/message-bus-character.md", turn_start)
            self.assertIn("Valid recipients this turn:", turn_start)
            self.assertIn("- `party`", turn_start)
            self.assertIn("- `dm`", turn_start)
            self.assertIn("- `tern-korr (tev)`", turn_start)
            self.assertIn("- `duva-doraleth (sumi)`", turn_start)
            self.assertIn(
                "On character surface, prefer character ids for private recipients.",
                turn_start,
            )
            self.assertNotIn("players/tev/persona.md", turn_start)
            self.assertIn("do not rely on persona", turn_start)

    def test_active_system_prompt_slims_turn_prompt(self) -> None:
        def render(root: Path, *, with_base_prompts: bool) -> str:
            config = make_config(root)
            templates = root / "templates"
            (templates / "instructions").mkdir(parents=True, exist_ok=True)
            (templates / "methodologies").mkdir(parents=True, exist_ok=True)
            if with_base_prompts:
                prompts_dir = templates / "prompts"
                prompts_dir.mkdir(parents=True, exist_ok=True)
                (prompts_dir / "dm-base.md").write_text("# DM base\n")
                (prompts_dir / "player-base.md").write_text("# Player base\n")
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True, exist_ok=True)
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-play",
                initial_scene="opening",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator, next_speaker={"agent": "dm"})
            return orchestrator.prepare_turn(state).prompt

        with tempfile.TemporaryDirectory() as tmp:
            legacy = render(Path(tmp), with_base_prompts=False)
        with tempfile.TemporaryDirectory() as tmp:
            slim = render(Path(tmp), with_base_prompts=True)

        self.assertIn("Codified handles vs in-fiction language", legacy)
        self.assertIn("Scene framing discipline", legacy)
        self.assertNotIn("Codified handles vs in-fiction language", slim)
        self.assertNotIn("Scene framing discipline", slim)
        self.assertNotIn("do not rely on persona", slim)
        self.assertIn("are in your system prompt", slim)
        self.assertIn("## Context boundary", slim)
        # The per-turn tool card is load-bearing (exact call shapes) and is
        # deliberately kept; the gate is that every ledger-relocated section is
        # gone (asserted above) and the prompt is at least a third shorter.
        self.assertLessEqual(
            len(slim),
            (len(legacy) * 2) // 3,
            f"slim prompt {len(slim)} chars vs legacy {len(legacy)} chars",
        )

    def test_prepare_turn_character_surface_prompts_pending_level_up(self) -> None:
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
            public_root = campaign_root / "players" / "tev" / "public"
            public_root.mkdir(parents=True)
            (public_root / "character.md").write_text(
                "\n".join(
                    [
                        "---",
                        "character_id: rinavik",
                        "---",
                        "",
                        "# Ri'navik",
                        "",
                        "- **Level:** 1 (14 XP)",
                        "",
                    ]
                ),
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
            orchestrator.context_builder._campaign_characters_from_postgres = Mock(
                return_value=[
                    {
                        "character_id": "rinavik",
                        "player_id": "tev",
                        "level": 1,
                        "xp": 14,
                    }
                ]
            )

            package = orchestrator.prepare_turn(state)

            turn_start = package.prompt
            self.assertIn("## Pending Level-Up", turn_start)
            self.assertIn("`rinavik` is level 1 with 14 XP", turn_start)
            self.assertIn("1 pending level-up", turn_start)
            self.assertIn('glass_character_level_up(character_id="rinavik")', turn_start)
            self.assertIn(
                'glass_character_level_up(character_id="<your-character-id>")', turn_start
            )

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
            turn_start = package.prompt
            self.assertIn("Methodology: **scene-housekeeping-player**", turn_start)
            self.assertIn("Do not write files", turn_start)
            self.assertNotIn("players/tev/persona.md", turn_start)

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

            turn_start = package.prompt
            self.assertEqual(package.player_surface, PLAYER_SURFACE_CHARACTER)
            self.assertIn("Methodology: **rapid-response-character**", turn_start)
            self.assertIn("methodologies/rapid-response-character.md", turn_start)

    def test_prepare_turn_uses_stable_reference_cwd_across_turns(self) -> None:
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

            expected = config.templates_dir
            self.assertEqual(first.spawn_cwd, expected)
            self.assertEqual(second.spawn_cwd, expected)
            self.assertFalse((root / ".glass-cwd").exists())
            self.assertIn('glass_turn_append(body="<public prose>")', second.prompt)

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
                turn_start = package.prompt
                if enabled:
                    self.assertIn("## Persistent Claude Session", turn_start)
                    self.assertIn(
                        "Before acting, use the injected prompt and Glass state "
                        "instead of relying on remembered conversation state.",
                        turn_start,
                    )
                    self.assertIn("Required startup checks:", turn_start)
                else:
                    self.assertNotIn("## Persistent Claude Session", turn_start)
                commands: list[list[str]] = []
                stream_envs: list[dict[str, str]] = []

                def fake_stream(command, **kwargs):
                    commands.append(command)
                    stream_envs.append(kwargs["env"])
                    return "", "", 0, False

                with (
                    patch(
                        "orchestrator.runner.ensure_background_server", return_value="http://api"
                    ),
                    patch("orchestrator.runner.mint_grant", return_value="grant"),
                    patch.object(orchestrator, "_begin_turn_via_glass"),
                    patch.object(
                        orchestrator,
                        "_collect_committed_turn_from_postgres",
                        return_value=committed_turn(),
                    ),
                    patch("orchestrator.runner._stream_subprocess", side_effect=fake_stream),
                ):
                    orchestrator._invoke_agent(
                        state,
                        AGENTS_BY_ID["tev"],
                        package,
                        turn_meta={},
                        queued_entry=None,
                        action_entry=None,
                    )

                session = state.claude_sessions["tev"]
                self.assertIn("session_id", session)
                self.assertEqual(session["cwd"], str(package.spawn_cwd))
                self.assertEqual(session["last_session_id_flag_enabled"], enabled)
                command = commands[0]
                prompt = command[command.index("-p") + 1]
                self.assertIn('glass_turn_append(body="<public prose>")', prompt)
                self.assertIn("Do not write files", prompt)
                self.assertNotIn("TURN_START.md", prompt)
                self.assertNotIn("turns/TURN.md", prompt)
                self.assertNotIn("players/tev/turns", prompt)
                self.assertIn("--mcp-config", command)
                self.assertIn("--strict-mcp-config", command)
                mcp_config = json.loads(command[command.index("--mcp-config") + 1])
                self.assertEqual(
                    mcp_config["mcpServers"]["glass"]["args"],
                    ["-m", "cli.mcp_server"],
                )
                self.assertEqual(
                    mcp_config["mcpServers"]["glass"]["env"],
                    {
                        "GLASS_API_URL": "http://api",
                        "GLASS_API_GRANT": "grant",
                        "GLASS_ROLE": "player:tev",
                        "GLASS_CAMPAIGN_ID": "c1",
                        "GLASS_CONFIG": config_env_value(config),
                        "GLASS_TURN_ID": package.turn_id,
                    },
                )
                self.assertEqual(stream_envs[0]["GLASS_API_URL"], "http://api")
                self.assertEqual(stream_envs[0]["GLASS_API_GRANT"], "grant")
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
                        patch(
                            "orchestrator.runner.ensure_background_server",
                            return_value="http://api",
                        ),
                        patch("orchestrator.runner.mint_grant", return_value="grant"),
                        patch.object(orchestrator, "_begin_turn_via_glass"),
                        patch.object(
                            orchestrator,
                            "_collect_committed_turn_from_postgres",
                            return_value=committed_turn(),
                        ),
                        patch("orchestrator.runner._stream_subprocess", side_effect=fake_stream),
                    ):
                        orchestrator._invoke_agent(
                            state,
                            AGENTS_BY_ID["tev"],
                            current_package,
                            turn_meta={},
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
            config = make_config(root, agent_provider="mixed-codex", use_session_id=True)
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
            turn_start = package.prompt
            self.assertNotIn("## Persistent Claude Session", turn_start)

            commands: list[list[str]] = []
            stream_envs: list[dict[str, str]] = []

            def fake_stream(command, **kwargs):
                commands.append(command)
                stream_envs.append(kwargs["env"])
                return "", "", 0, False

            with (
                patch("orchestrator.runner.ensure_background_server", return_value="http://api"),
                patch("orchestrator.runner.mint_grant", return_value="grant"),
                patch(
                    "orchestrator.runner._resolve_provider_executable", return_value="/tmp/codex"
                ),
                patch.object(orchestrator, "_begin_turn_via_glass"),
                patch.object(
                    orchestrator,
                    "_collect_committed_turn_from_postgres",
                    return_value=committed_turn(),
                ),
                patch("orchestrator.runner._stream_subprocess", side_effect=fake_stream),
            ):
                orchestrator._invoke_agent(
                    state,
                    AGENTS_BY_ID["dm"],
                    package,
                    turn_meta={},
                    queued_entry=None,
                    action_entry=None,
                )

            self.assertEqual(state.claude_sessions, {})
            command = commands[0]
            self.assertEqual(command[0], "/tmp/codex")
            self.assertEqual(command[1], "exec")
            self.assertIn(
                "mcp_servers={glass={command=",
                " ".join(command),
            )
            self.assertIn('args=["-m", "cli.mcp_server"]', " ".join(command))
            mcp_override = tomllib.loads(command[command.index("-c") + 1])
            self.assertEqual(
                mcp_override["mcp_servers"]["glass"]["env"],
                {
                    "GLASS_API_URL": "http://api",
                    "GLASS_API_GRANT": "grant",
                    "GLASS_ROLE": "dm",
                    "GLASS_CAMPAIGN_ID": "c1",
                    "GLASS_CONFIG": config_env_value(config),
                    "GLASS_TURN_ID": package.turn_id,
                },
            )
            self.assertEqual(stream_envs[0]["GLASS_API_URL"], "http://api")
            self.assertEqual(stream_envs[0]["GLASS_API_GRANT"], "grant")
            self.assertIn("--dangerously-bypass-approvals-and-sandbox", command)
            self.assertNotIn("--session-id", command)
            self.assertNotIn("--resume", command)

    def test_glass_mcp_command_runs_from_agent_workspace(self) -> None:
        command, args = _glass_mcp_command()

        result = subprocess.run(
            [command, *args, "--help"],
            check=False,
            cwd=Path(__file__).resolve().parents[1] / "templates",
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Agents of Glass MCP server", result.stdout)

    def test_mixed_codex_keeps_claude_players_on_claude(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(
                root,
                agent_provider="mixed-codex",
                codex_players=("tev", "sumi"),
                use_session_id=True,
            )
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
            attach_runtime_mocks(orchestrator, next_speaker={"agent": "renno"})
            package = orchestrator.prepare_turn(state)
            turn_start = package.prompt

            self.assertIn("## Persistent Claude Session", turn_start)

            commands: list[list[str]] = []

            def fake_stream(command, **_kwargs):
                commands.append(command)
                return "", "", 0, False

            with (
                patch("orchestrator.runner.ensure_background_server", return_value="http://api"),
                patch("orchestrator.runner.mint_grant", return_value="grant"),
                patch(
                    "orchestrator.runner._resolve_provider_executable",
                    side_effect=lambda provider: f"/tmp/{provider}",
                ),
                patch.object(orchestrator, "_begin_turn_via_glass"),
                patch.object(
                    orchestrator,
                    "_collect_committed_turn_from_postgres",
                    return_value=committed_turn(),
                ),
                patch("orchestrator.runner._stream_subprocess", side_effect=fake_stream),
            ):
                orchestrator._invoke_agent(
                    state,
                    AGENTS_BY_ID["renno"],
                    package,
                    turn_meta={},
                    queued_entry=None,
                    action_entry=None,
                )

            self.assertIn("session_id", state.claude_sessions["renno"])
            self.assertEqual(commands[0][0], "/tmp/claude")
            self.assertIn("-p", commands[0])
            self.assertIn("--mcp-config", commands[0])

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
                "cwd": str(config.templates_dir),
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
                return "", "", 0, False

            with (
                patch("orchestrator.runner.ensure_background_server", return_value="http://api"),
                patch("orchestrator.runner.mint_grant", return_value="grant"),
                patch.object(orchestrator, "_begin_turn_via_glass"),
                patch.object(
                    orchestrator,
                    "_collect_committed_turn_from_postgres",
                    return_value=committed_turn(),
                ),
                patch("orchestrator.runner._stream_subprocess", side_effect=fake_stream),
            ):
                orchestrator._invoke_agent(
                    state,
                    AGENTS_BY_ID["tev"],
                    package,
                    turn_meta={},
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

            self.assertEqual(package.turn_dir, campaign_root)
            self.assertEqual(package.spawn_cwd, config.templates_dir)
            self.assertFalse((root / ".glass-cwd").exists())
            turn_start = package.prompt
            self.assertIn("methodologies/` holds required ordered workflows", turn_start)
            self.assertIn("prompt selects the one methodology", turn_start)
            self.assertNotIn("optional current-turn working memory", turn_start)
            self.assertIn("methodologies/closeout.md", turn_start)

    def test_projection_refresh_helper_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            (campaign_root / "table").mkdir()
            (campaign_root / "table" / "index.md").write_text("legacy index\n")
            (campaign_root / "table" / "visible-artifact.md").write_text("canonical old\n")
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-play",
                initial_scene="opening",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator, next_speaker={"agent": "dm"})
            package = orchestrator.prepare_turn(state)

            self.assertEqual(package.spawn_cwd, config.templates_dir)
            self.assertFalse((root / ".glass-cwd").exists())

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

            turn_start = package.prompt
            self.assertIn(
                "Prior character-creation turns are intentionally not embedded",
                turn_start,
            )
            self.assertIn("character-design turns", turn_start)
            self.assertNotIn("Sumi builds directly around Tev's hook", turn_start)
            self.assertIn(
                "Methodology: **character-creation-player-build**",
                turn_start,
            )
            self.assertNotIn("- Turn type:", turn_start)
            self.assertNotIn('turn_type="character-creation-player-build"', turn_start)
            self.assertIn('pull_utilization={"source":', turn_start)
            self.assertIn("starting_items=[", turn_start)
            self.assertIn("facts=[", turn_start)
            self.assertIn("non_work_want=", turn_start)
            self.assertIn("opening_social_action=", turn_start)
            self.assertNotIn("players/tev/secrets", turn_start)
            self.assertNotIn("glass msg secret dm", turn_start)

    def test_character_creation_turn_type_follows_hard_state_and_relationship_facts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            characters = [
                {"player_id": player_id, "character_id": f"{player_id}-hero"}
                for player_id in ("kit", "renno", "sumi", "tev")
            ]
            state = SessionState.new(
                campaign="c1",
                initial_mode="character-creation",
                initial_scene="character-creation",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator, next_speaker={"agent": "dm"})
            orchestrator.context_builder._campaign_characters_from_postgres = Mock(
                return_value=characters
            )

            with patch("orchestrator.context.fact_pack", return_value={"facts": []}):
                package = orchestrator.prepare_turn(state)
            turn_start = package.prompt

            self.assertIn(
                "Methodology: **character-creation-dm-relationship-setup**",
                turn_start,
            )
            self.assertIn(
                "methodologies/character-creation-dm-relationship-setup.md",
                turn_start,
            )

            orchestrator._peek_next_speaker_entry_from_postgres.return_value = {"agent": "tev"}
            package = orchestrator.prepare_turn(state)
            turn_start = package.prompt

            self.assertIn(
                "Methodology: **character-creation-player-relationship**",
                turn_start,
            )
            self.assertIn(
                "methodologies/character-creation-player-relationship.md",
                turn_start,
            )

            facts = {
                "facts": [
                    {"subject_id": f"{player_id}-hero", "predicate": "relationship"}
                    for player_id in ("kit", "renno", "sumi", "tev")
                ]
            }
            orchestrator._peek_next_speaker_entry_from_postgres.return_value = {"agent": "dm"}
            with patch("orchestrator.context.fact_pack", return_value=facts):
                package = orchestrator.prepare_turn(state)
            turn_start = package.prompt

            self.assertIn(
                "Methodology: **character-creation-dm-ratification**",
                turn_start,
            )
            self.assertIn(
                "methodologies/character-creation-dm-ratification.md",
                turn_start,
            )

    def test_scene_play_turn_uses_fact_graph_not_summary_or_recent_prose(self) -> None:
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
                "Full recent narration should not be pasted into injected prompts.",
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

            turn_start = package.prompt
            self.assertIn("## Continuity Facts", turn_start)
            self.assertIn("Continuity facts are the agent-readable state store", turn_start)
            self.assertIn(
                'glass_fact_pack(audience="continuity", output_format="markdown")',
                turn_start,
            )
            self.assertNotIn("## Scene Summary", turn_start)
            self.assertNotIn("Drova logged the packet as year-mark form", turn_start)
            self.assertNotIn("## Recent Turn Summaries", turn_start)
            self.assertIn(
                "Do not use transcript prose, table prose, or summary markdown", turn_start
            )
            self.assertIn('glass_lore_search(query="<query>")', turn_start)
            self.assertNotIn("glass find", turn_start)
            self.assertNotIn("Full recent narration should not be pasted", turn_start)

    def test_player_scene_play_command_surface_is_turn_specific(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-play",
                initial_scene="opening",
                initial_budget=None,
            )

            turn_start = self._render_turn_start_text(
                Path(tmp),
                state=state,
                agent_id="tev",
                glass_state={
                    "active_arc": "caulden-rack",
                    "active_scene": "opening",
                    "active_scene_type": "scene-play",
                },
            )

            self.assertIn("Use this injected MCP tool set for this turn", turn_start)
            self.assertIn('turn_type="<act|answer|support|pass>"', turn_start)
            self.assertIn('glass_beat_close(beat_id="<beat-id>"', turn_start)
            self.assertNotIn("glass arc close-check", turn_start)
            self.assertNotIn("glass scene create <next-scene>", turn_start)
            self.assertNotIn("glass campaign pull-note", turn_start)

    def test_campaign_planning_surface_includes_phase_close_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = SessionState.new(
                campaign="c1",
                initial_mode="campaign-planning",
                initial_scene="planning",
                initial_budget=None,
            )

            turn_start = self._render_turn_start_text(
                Path(tmp),
                state=state,
                agent_id="dm",
            )

            self.assertNotIn("glass campaign pull-note", turn_start)
            self.assertIn('glass_arc_create(arc_id="<arc-id>"', turn_start)
            self.assertNotIn("glass lore list", turn_start)
            self.assertIn(
                'glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "campaign", "predicate": "opening"',
                turn_start,
            )
            self.assertIn(
                '"predicate": "premise|constraint"',
                turn_start,
            )
            self.assertIn(
                '"subject_id": "<arc-id>", "predicate": "focus|direction|status"',
                turn_start,
            )
            self.assertIn("glass_mode_end()", turn_start)

    def test_dm_scene_transition_injects_scene_and_arc_close_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-play",
                initial_scene="dock-raid",
                initial_budget=None,
            )

            turn_start = self._render_turn_start_text(
                Path(tmp),
                state=state,
                agent_id="dm",
                turn_meta={"scene_transition": True},
                glass_state={
                    "active_arc": "caulden-rack",
                    "active_scene": "dock-raid",
                    "active_scene_type": "extraction",
                },
            )

            self.assertIn("Methodology: **scene-transition-dm**", turn_start)
            self.assertIn('glass_scene_end(summary="<scene summary>"', turn_start)
            self.assertIn('glass_arc_close_check(arc_id="caulden-rack")', turn_start)
            self.assertIn(
                'glass_scene_create(scene_id="<next-scene>", scene_type="<problem-family>", arc_id="caulden-rack")',
                turn_start,
            )
            self.assertIn("the opposing will and its move this scene", turn_start)
            self.assertIn("3 interactable scene toys", turn_start)
            self.assertIn('glass_scene_clock_declare(clock_id="<objective-clock-id>"', turn_start)
            self.assertIn('glass_beat_start(beat_id="<beat-id>"', turn_start)
            self.assertIn("glass_thread_current", turn_start)
            self.assertIn('glass_thread_advance(thread_id="<thread-id>"', turn_start)

    def test_dm_scene_prep_injects_arc_check_and_scene_problem_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-prep",
                initial_scene="next-scene",
                initial_budget=None,
            )

            turn_start = self._render_turn_start_text(
                Path(tmp),
                state=state,
                agent_id="dm",
                glass_state={
                    "active_arc": "caulden-rack",
                    "active_scene": "",
                    "active_scene_type": "",
                },
            )

            self.assertIn("glass_arc_current()", turn_start)
            self.assertIn('glass_arc_close_check(arc_id="caulden-rack")', turn_start)
            self.assertIn(
                'glass_scene_create(scene_id="<scene-slug>", scene_type="<problem-family>", arc_id="caulden-rack")',
                turn_start,
            )
            self.assertIn("the opposing will and its move this scene", turn_start)
            self.assertIn("3 interactable scene toys", turn_start)
            self.assertIn('glass_scene_clock_declare(clock_id="<objective-clock-id>"', turn_start)
            self.assertIn("glass_thread_current", turn_start)
            self.assertIn('glass_thread_advance(thread_id="<thread-id>"', turn_start)
            self.assertNotIn("glass_scene_end(summary=", turn_start)

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

            turn_start = package.prompt
            self.assertIn("## HOUSEKEEPING TURN", turn_start)
            self.assertIn("Do not advance plot", turn_start)
            self.assertIn("Scene just closed: `first-scene`", turn_start)
            self.assertIn("Next scene staged: `second-scene`", turn_start)
            self.assertIn("Methodology: **scene-housekeeping-player**", turn_start)
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

            turn_start = package.prompt
            self.assertIn("Methodology: **scene-transition-dm**", turn_start)
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

            self.assertEqual(package.turn_dir, campaign_root)
            self.assertEqual(package.spawn_cwd, config.templates_dir)
            turn_start = package.prompt
            self.assertIn(
                "You are **Kit**, a player in a Glass Frontier TTRPG session.",
                turn_start,
            )
            self.assertIn("embody the character only through facts", turn_start)
            self.assertIn("## ACTION-SCENE TURN", turn_start)
            self.assertIn("`kit -> dm -> tev`", turn_start)
            self.assertIn("Methodology: **action-scene-player**", turn_start)
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

            turn_start = package.prompt
            self.assertIn("Methodology: **action-scene-opening-dm**", turn_start)
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

            turn_start = package.prompt
            self.assertIn("Methodology: **organization-bootstrap**", turn_start)
            self.assertIn("methodologies/organization-bootstrap.md", turn_start)
            self.assertNotIn("## Creative Influence", turn_start)
            self.assertNotIn("Verse phrase:", turn_start)

    def test_organization_bootstrap_embeds_last_five_previous_orgs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            (config.campaigns_dir / "current").mkdir(parents=True)
            patterns = [
                {
                    "campaign_id": f"prior-{index}",
                    "public_org": f"Mission pattern marker-{index}.",
                    "private_org": f"Hidden pressure marker-{index}.",
                    "pull_note": f"Non-adjacent domain marker-{index}.",
                }
                for index in range(3, 8)
            ]

            state = SessionState.new(
                campaign="current",
                initial_mode="organization-bootstrap",
                initial_scene="organization-bootstrap",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
            attach_runtime_mocks(orchestrator)

            with patch.object(
                orchestrator.context_builder,
                "_previous_campaign_organization_patterns",
                return_value=patterns,
            ):
                package = orchestrator.prepare_turn(state)

            turn_start = package.prompt
            self.assertIn("## Previous Campaign Organization Check", turn_start)
            self.assertIn("Avoid repeating their mission", turn_start)
            for index in range(3, 8):
                self.assertIn(f"`prior-{index}`", turn_start)
                self.assertIn(f"marker-{index}", turn_start)
            self.assertNotIn("`prior-1`", turn_start)
            self.assertNotIn("`prior-2`", turn_start)
            self.assertNotIn("- `current`", turn_start)
            self.assertNotIn("current-marker", turn_start)

    def test_organization_bootstrap_validation_accepts_org_fact_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            (campaign_root / "table").mkdir(parents=True)
            (campaign_root / "table" / "scene.md").write_text(
                "retired scaffold; not continuity\n",
                encoding="utf-8",
            )
            fact_pack = {
                "status": "ok",
                "facts": [
                    {"subject_id": "campaign", "predicate": "pull"},
                    {"subject_id": "organization", "predicate": "identity"},
                    {"subject_id": "organization", "predicate": "dangerous-work"},
                    {"subject_id": "organization", "predicate": "character-brief"},
                    {"subject_id": "organization", "predicate": "want"},
                ],
            }

            with (
                patch("cli.config.load_config", return_value={}),
                patch("cli.facts.fact_pack", return_value=fact_pack),
                patch("cli.db.load_storage_config", return_value=object()),
                patch("cli.db.clock_list", return_value=[]),
                patch("cli.db.connect") as connect,
            ):
                connect.return_value.__enter__.return_value = object()
                _validate_organization_bootstrap_complete(
                    SimpleNamespace(config=config),
                    "c1",
                )

    def test_campaign_planning_validation_requires_main_arc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            fact_pack = {
                "status": "ok",
                "facts": [
                    {"subject_id": "campaign", "predicate": "opening"},
                    {"subject_id": "opening", "predicate": "focus"},
                    {"subject_id": "opening", "predicate": "antagonist"},
                    {"subject_id": "opening", "predicate": "inaction-consequence"},
                ],
            }

            with (
                patch("cli.config.get_paths", return_value=object()),
                patch(
                    "cli.state.load_state",
                    return_value={"active_arc": "opening", "arcs": ["opening"]},
                ),
                patch("cli.facts.fact_pack", return_value=fact_pack),
            ):
                _validate_campaign_planning_complete(
                    SimpleNamespace(config=config),
                    "c1",
                )

    def test_campaign_planning_validation_accepts_opening_arc_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            fact_pack = {
                "status": "ok",
                "facts": [
                    {"subject_id": "opening-arc", "predicate": "premise"},
                    {"subject_id": "opening-arc", "predicate": "direction"},
                    {"subject_id": "opening-arc", "predicate": "antagonist"},
                    {"subject_id": "opening-arc", "predicate": "inaction-consequence"},
                ],
            }

            with (
                patch("cli.config.get_paths", return_value=object()),
                patch(
                    "cli.state.load_state",
                    return_value={
                        "active_arc": "greyspill-lockmouth",
                        "arcs": ["greyspill-lockmouth"],
                    },
                ),
                patch("cli.facts.fact_pack", return_value=fact_pack),
            ):
                _validate_campaign_planning_complete(
                    SimpleNamespace(config=config),
                    "c1",
                )

    def test_campaign_planning_validation_ignores_unchanged_checkpoint_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            current = config.campaigns_dir / "c1" / "shared" / "campaign-framing.md"
            current.parent.mkdir(parents=True)
            current.write_text("starter framing\n", encoding="utf-8")
            checkpoint = (
                config.campaigns_dir
                / ".checkpoints"
                / "c1"
                / "20260101T000000000000Z-after-character-creation"
            )
            prior = checkpoint / "filesystem" / "shared" / "campaign-framing.md"
            prior.parent.mkdir(parents=True)
            prior.write_text("starter framing\n", encoding="utf-8")
            (checkpoint / "manifest.json").write_text(
                json.dumps(
                    {
                        "checkpoint_id": checkpoint.name,
                        "campaign_id": "c1",
                        "label": "after-character-creation",
                        "created_at": "2026-01-01T00:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )
            fact_pack = {
                "status": "ok",
                "facts": [
                    {"subject_id": "campaign", "predicate": "opening"},
                    {"subject_id": "opening", "predicate": "focus"},
                    {"subject_id": "opening", "predicate": "antagonist"},
                    {"subject_id": "opening", "predicate": "inaction-consequence"},
                ],
            }

            with (
                patch("cli.config.get_paths", return_value=object()),
                patch(
                    "cli.state.load_state",
                    return_value={"active_arc": "opening", "arcs": ["opening"]},
                ),
                patch("cli.facts.fact_pack", return_value=fact_pack),
            ):
                _validate_campaign_planning_complete(
                    SimpleNamespace(config=config),
                    "c1",
                )

    def test_campaign_planning_validation_rejects_changed_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            current = config.campaigns_dir / "c1" / "shared" / "campaign-framing.md"
            current.parent.mkdir(parents=True)
            current.write_text("new planning prose\n", encoding="utf-8")
            checkpoint = (
                config.campaigns_dir
                / ".checkpoints"
                / "c1"
                / "20260101T000000000000Z-after-character-creation"
            )
            prior = checkpoint / "filesystem" / "shared" / "campaign-framing.md"
            prior.parent.mkdir(parents=True)
            prior.write_text("starter framing\n", encoding="utf-8")
            (checkpoint / "manifest.json").write_text(
                json.dumps(
                    {
                        "checkpoint_id": checkpoint.name,
                        "campaign_id": "c1",
                        "label": "after-character-creation",
                        "created_at": "2026-01-01T00:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )
            fact_pack = {
                "status": "ok",
                "facts": [
                    {"subject_id": "campaign", "predicate": "opening"},
                    {"subject_id": "opening", "predicate": "focus"},
                ],
            }

            with (
                patch("cli.config.get_paths", return_value=object()),
                patch(
                    "cli.state.load_state",
                    return_value={"active_arc": "opening", "arcs": ["opening"]},
                ),
                patch("cli.facts.fact_pack", return_value=fact_pack),
            ):
                with self.assertRaises(click.ClickException) as raised:
                    _validate_campaign_planning_complete(
                        SimpleNamespace(config=config),
                        "c1",
                    )

            self.assertIn("shared/campaign-framing.md exists", str(raised.exception))

    def test_budget_exhaustion_finalizes_bootstrap_when_validation_passes(self) -> None:
        validate = Mock()
        cli = SimpleNamespace(
            campaign_manager=SimpleNamespace(load_state=Mock(return_value={"phase": "active"}))
        )
        failure = {
            "reason": "mode_budget_exhausted",
            "mode": "campaign-planning",
            "scene_id": "planning",
        }

        with (
            patch("orchestrator.main._end_current_mode") as end_mode,
            patch(
                "orchestrator.main._checkpoint_and_advance_bootstrap_phase",
                return_value={"phase": "active"},
            ) as checkpoint,
        ):
            recovered = _recover_bootstrap_phase_after_budget_exhaustion(
                cli,
                campaign_id="c1",
                mode_name="campaign-planning",
                phase_label="campaign planning",
                checkpoint_label="after-campaign-planning",
                next_phase="active",
                dry_run=False,
                validate=validate,
                failure=failure,
            )

        self.assertTrue(recovered)
        validate.assert_called_once_with(cli, "c1")
        end_mode.assert_called_once_with(
            cli,
            campaign_id="c1",
            expected_mode="campaign-planning",
            reason="phase validation already passes",
        )
        checkpoint.assert_called_once()

    def test_character_creation_validation_does_not_hard_fail_inventory_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            players = ("tev", "sumi", "renno", "kit")
            for player_id in players:
                public_root = campaign_root / "players" / player_id / "public"
                public_root.mkdir(parents=True)
                (public_root / "character.md").write_text("character\n", encoding="utf-8")
                (public_root / "intro.md").write_text("intro\n", encoding="utf-8")
                (public_root / "relationships.md").write_text(
                    "relationships\n",
                    encoding="utf-8",
                )
            characters = [
                {
                    "player_id": player_id,
                    "name": f"{player_id.title()} Example",
                    "species": "human",
                    "culture": "Sithari",
                    "archetype": "resonance knight",
                    "organization_role": "field witness",
                    "bio": "Keeps doors open for people who cannot be seen asking.",
                    "goals": ["Find the missing door.", "Pay down the route debt."],
                    "inventory": [
                        {
                            "id": "ledger-token",
                            "qty": 1,
                            "effect_tags": ["proves a local obligation"],
                        }
                    ],
                }
                for player_id in players
            ]

            with (
                patch("cli.config.load_config", return_value={}),
                patch("cli.db.load_storage_config", return_value=object()),
                patch("cli.db.character_list", return_value=characters),
                patch("cli.facts.fact_pack", return_value={"facts": []}),
                patch("cli.db.connect") as connect,
            ):
                connect.return_value.__enter__.return_value = object()
                _validate_character_creation_complete(
                    SimpleNamespace(config=config),
                    "c1",
                )

    def test_public_prose_detects_glass_command_lines(self) -> None:
        prose = (
            "The door opens.\n\n"
            "> glass scene create ambush --type action\n"
            "glass shards scatter across the floor.\n"
            'glass turn rapid-round "react"\n'
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
            campaign_root.mkdir(parents=True)
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
            result = TurnResult(
                turn_id="c1-t0001",
                agent=AGENTS_BY_ID["tev"],
                turn_dir=campaign_root,
                spawn_cwd=campaign_root,
                prose="Done.\n\nglass roll focus --attribute daring\n",
                dry_run=False,
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
                ["glass roll focus --attribute daring"],
            )
            committed = next(event for event in events if event["event"] == "turn.committed")
            self.assertEqual(committed["duration_seconds"], 12.346)
            orchestrator.store.glass.invoke.assert_not_called()

    def test_prepare_turn_does_not_create_unsynced_authoring_workspace(self) -> None:
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

            self.assertEqual(package.spawn_cwd, config.templates_dir)
            self.assertFalse((root / ".glass-cwd").exists())
            self.assertIn("Do not write files", package.prompt)

    def test_scene_prep_dm_turn_without_play_mode_redirects_dm(self) -> None:
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
            orchestrator._peek_next_speaker_entry = Mock(return_value=None)
            orchestrator._prepend_next_speaker_entry = Mock()
            orchestrator._send_system_instruction = Mock()
            result = TurnResult(
                turn_id="c1-t0001",
                agent=AGENTS_BY_ID["dm"],
                turn_dir=campaign_root / "dm" / "turns" / "0001",
                spawn_cwd=campaign_root,
                prose="Prep notes only.",
                dry_run=False,
            )

            orchestrator._validate_scene_prep_dm_handoff(
                state,
                result,
                state.active_mode,
            )
            orchestrator._prepend_next_speaker_entry.assert_called_once()
            orchestrator._send_system_instruction.assert_called_once()
            events = [
                json.loads(line)
                for line in (campaign_root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            redirected = next(event for event in events if event["event"] == "turn.redirected")
            self.assertEqual(redirected["reason"], "scene_prep_no_handoff")
            self.assertEqual(redirected["recipient"], "dm")

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

    def test_scene_prep_handoff_into_active_play_redirects_dm_on_missing_scene_contract(
        self,
    ) -> None:
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
            orchestrator._scene_contract_failures_for_scene = Mock(
                return_value=[
                    "this active scene has 0 scene clocks",
                    "this active scene has 0 active beats",
                ]
            )
            orchestrator._prepend_next_speaker_entry = Mock()
            orchestrator._send_system_instruction = Mock()
            result = TurnResult(
                turn_id="c1-t0001",
                agent=AGENTS_BY_ID["dm"],
                turn_dir=campaign_root / "dm" / "turns" / "0001",
                spawn_cwd=campaign_root,
                prose="Scene starts.",
                dry_run=False,
            )

            orchestrator._validate_active_play_scene_contract_handoff(
                state,
                result,
                previous,
            )
            orchestrator._prepend_next_speaker_entry.assert_called_once_with("c1", {"agent": "dm"})
            orchestrator._send_system_instruction.assert_called_once()
            self.assertEqual(
                orchestrator._send_system_instruction.call_args.kwargs["recipient"],
                "dm",
            )
            self.assertIn(
                "declare a scene clock",
                orchestrator._send_system_instruction.call_args.kwargs["body"],
            )
            events = [
                json.loads(line)
                for line in (campaign_root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            redirected = next(event for event in events if event["event"] == "turn.redirected")
            self.assertEqual(redirected["reason"], "scene_contract_missing")
            self.assertEqual(redirected["recipient"], "dm")

    def test_scene_prep_handoff_with_scene_contract_is_allowed(self) -> None:
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
            orchestrator._scene_contract_failures_for_scene = Mock(return_value=[])
            result = TurnResult(
                turn_id="c1-t0001",
                agent=AGENTS_BY_ID["dm"],
                turn_dir=campaign_root / "dm" / "turns" / "0001",
                spawn_cwd=campaign_root,
                prose="Scene starts.",
                dry_run=False,
            )

            orchestrator._validate_active_play_scene_contract_handoff(
                state,
                result,
                previous,
            )

    def test_active_play_contract_gap_redirects_to_dm_with_closure_nudge(self) -> None:
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
            attach_runtime_mocks(orchestrator)
            orchestrator._scene_contract_snapshot_for_scene = Mock(
                return_value={
                    "active_clock_count": 1,
                    "active_beat_count": 0,
                    "completed_beats": 9,
                    "scene_note": "this scene has ample resolved material.",
                }
            )
            orchestrator._prepend_next_speaker_entry = Mock()
            orchestrator._send_system_instruction = Mock()
            result = TurnResult(
                turn_id="c1-t0049",
                agent=AGENTS_BY_ID["tev"],
                turn_dir=campaign_root / "players" / "tev" / "turns" / "0049",
                spawn_cwd=campaign_root,
                prose="Tev lands the beat.",
                dry_run=False,
            )

            orchestrator._redirect_active_play_contract_gap_to_dm(
                state,
                result,
                state.active_mode,
            )

            orchestrator._prepend_next_speaker_entry.assert_called_once()
            campaign, entry = orchestrator._prepend_next_speaker_entry.call_args.args
            self.assertEqual(campaign, "c1")
            self.assertEqual(entry["agent"], "dm")
            self.assertIn("Strong closure nudge", entry["scene_contract_nudge"])
            orchestrator._send_system_instruction.assert_called_once()
            self.assertEqual(
                orchestrator._send_system_instruction.call_args.kwargs["recipient"],
                "dm",
            )
            self.assertIn(
                "Do not hand this gap to another player",
                orchestrator._send_system_instruction.call_args.kwargs["body"],
            )
            events = [
                json.loads(line)
                for line in (campaign_root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            redirected = next(event for event in events if event["event"] == "turn.redirected")
            self.assertEqual(redirected["reason"], "scene_contract_closure_gap")
            self.assertEqual(redirected["recipient"], "dm")

    def test_run_loop_redirects_dm_on_recoverable_scene_contract_failure(self) -> None:
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
            attach_runtime_mocks(orchestrator)
            orchestrator.store.save = Mock()
            failure = {
                "reason": "invalid_turn_end",
                "turn_id": "c1-t0001",
                "speaker": "tev",
                "error": (
                    "turn closeout is invalid: You MUST still call glass_check().; "
                    "This active scene has 0 scene clocks. The DM MUST declare at least "
                    "one with `glass_scene_clock_declare(...)`.; "
                    "This active scene has 0 active beats. Start one with "
                    '`glass_beat_start(beat_id="<beat-id>", clock_id="<clock-id>", label="...", question="...")`.'
                ),
            }
            orchestrator._load_active_turn_runtime = Mock(
                return_value={
                    "turn_id": "c1-t0001",
                    "scene_id": "opening",
                    "closeout": {
                        "problems": [
                            "You MUST still call glass_check().",
                            "This active scene has 0 scene clocks. The DM MUST declare at least one with `glass_scene_clock_declare(...)`.",
                            'This active scene has 0 active beats. Start one with `glass_beat_start(beat_id="<beat-id>", clock_id="<clock-id>", label="...", question="...")`.',
                        ]
                    },
                }
            )
            orchestrator._prepend_next_speaker_entry = Mock()
            orchestrator._send_system_instruction = Mock()
            repaired = TurnResult(
                turn_id="c1-t0001",
                agent=AGENTS_BY_ID["dm"],
                turn_dir=campaign_root / "dm" / "turns" / "0001",
                spawn_cwd=campaign_root,
                prose="DM repair turn.",
                dry_run=False,
            )
            orchestrator.run_one_turn = Mock(
                side_effect=[TurnFailure("blocked", failure), repaired]
            )
            orchestrator.commit_turn = Mock()

            turns_run = orchestrator.run_loop(
                state,
                max_turns=1,
                dry_run=False,
                resume_failed=True,
            )

            self.assertEqual(turns_run, 1)
            self.assertEqual(state.status, "ready")
            self.assertIsNone(state.failure)
            orchestrator._prepend_next_speaker_entry.assert_called_once_with("c1", {"agent": "dm"})
            orchestrator._send_system_instruction.assert_called_once()
            orchestrator.commit_turn.assert_called_once_with(state, repaired)
            self.assertEqual(
                orchestrator._send_system_instruction.call_args.kwargs["recipient"],
                "dm",
            )
            self.assertIn(
                "close or transition the scene",
                orchestrator._send_system_instruction.call_args.kwargs["body"],
            )
            events = [
                json.loads(line)
                for line in (campaign_root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            redirected = next(event for event in events if event["event"] == "turn.redirected")
            self.assertEqual(redirected["reason"], "invalid_turn_end")
            self.assertEqual(redirected["recipient"], "dm")

    def test_scene_close_inside_open_arc_without_next_mode_redirects_dm(self) -> None:
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
            orchestrator._peek_next_speaker_entry = Mock(return_value=None)
            orchestrator._prepend_next_speaker_entry = Mock()
            orchestrator._send_system_instruction = Mock()
            result = TurnResult(
                turn_id="c1-t0001",
                agent=AGENTS_BY_ID["dm"],
                turn_dir=campaign_root / "dm" / "turns" / "0001",
                spawn_cwd=campaign_root,
                prose="Scene closes.",
                dry_run=False,
            )

            orchestrator._validate_scene_boundary_dm_handoff(
                state,
                result,
                previous,
            )
            orchestrator._prepend_next_speaker_entry.assert_called_once()
            orchestrator._send_system_instruction.assert_called_once()
            self.assertEqual(
                orchestrator._send_system_instruction.call_args.kwargs["recipient"],
                "dm",
            )
            self.assertIn(
                "active arc `caulden-rack` with no active scene mode",
                orchestrator._send_system_instruction.call_args.kwargs["body"],
            )
            events = [
                json.loads(line)
                for line in (campaign_root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            redirected = next(event for event in events if event["event"] == "turn.redirected")
            self.assertEqual(redirected["reason"], "scene_boundary_no_next_scene")
            self.assertEqual(redirected["recipient"], "dm")

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

            orchestrator._advance_action_order_in_postgres.assert_called_once_with("c1", expected)


class SystemPromptAssemblyTests(unittest.TestCase):
    def _write_inputs(self, root: Path) -> None:
        prompts_dir = root / "templates" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "dm-base.md").write_text("# DM base\n\nRun the table.\n")
        (prompts_dir / "player-base.md").write_text("# Player base\n\nPlay the person.\n")
        tev_dir = root / "templates" / "players" / "tev"
        tev_dir.mkdir(parents=True)
        (tev_dir / "persona.md").write_text(
            "---\nname: Tev\nrole: player\nnarrative_style: rules-first-actor\n---\n\n"
            "# Tev\n\nApprentice electrician.\n"
        )
        styles_dir = root / "templates" / "styles"
        styles_dir.mkdir(parents=True)
        (styles_dir / "rules-first-actor.md").write_text(
            "---\ntitle: Rules-First Actor\n---\n\nShort declarative sentences.\n"
        )

    def test_assembles_base_persona_and_style_without_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_inputs(root)
            config = make_config(root)

            content = assemble_system_prompt(config, AGENTS_BY_ID["tev"])

            self.assertIsNotNone(content)
            self.assertIn("Player base", content)
            self.assertIn("Apprentice electrician.", content)
            self.assertIn("Short declarative sentences.", content)
            self.assertIn("Who you are at the table", content)
            self.assertIn("How your prose moves", content)
            self.assertNotIn("narrative_style:", content)
            self.assertNotIn("title: Rules-First Actor", content)

    def test_missing_base_disables_system_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)

            self.assertIsNone(assemble_system_prompt(config, AGENTS_BY_ID["tev"]))
            self.assertIsNone(
                materialize_system_prompt(config, campaign_id="c1", agent=AGENTS_BY_ID["tev"])
            )

    def test_missing_persona_degrades_to_base_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_inputs(root)
            config = make_config(root)

            content = assemble_system_prompt(config, AGENTS_BY_ID["kit"])

            self.assertIsNotNone(content)
            self.assertIn("Player base", content)
            self.assertNotIn("Who you are at the table", content)

    def test_materialize_writes_outside_templates_and_campaign_trees(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_inputs(root)
            config = make_config(root)

            path = materialize_system_prompt(
                config, campaign_id="c1", agent=AGENTS_BY_ID["tev"]
            )

            self.assertEqual(
                path,
                config.campaigns_dir / ".system-prompts" / "c1" / "tev.md",
            )
            self.assertIn("Apprentice electrician.", path.read_text())


if __name__ == "__main__":
    unittest.main()
