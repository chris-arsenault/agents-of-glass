import json
import tempfile
import unittest
from pathlib import Path

from orchestrator.config import AogConfig, CapsConfig, ClaudeConfig
from orchestrator.runner import (
    Orchestrator,
    TurnFailure,
    TurnResult,
    _tool_transcript_lines,
)
from orchestrator.state import AGENTS_BY_ID, SessionState, speaker_order_for
from orchestrator.store import SessionStore


def make_config(root: Path) -> AogConfig:
    return AogConfig(
        repo_root=root,
        config_path=None,
        templates_dir=root / "templates",
        campaigns_dir=root / "campaigns",
        lore_path=root / "lore",
        claude=ClaudeConfig(model=None, turn_timeout_seconds=60),
        caps=CapsConfig(
            session_max_turns=200,
            mode_default_max_turns=12,
            mode_combat_max_turns=8,
            mode_travel_max_turns=4,
        ),
    )


class OrchestratorQueueTests(unittest.TestCase):
    def test_prelude_coordinator_mode_is_dm_only(self) -> None:
        self.assertEqual(speaker_order_for("prelude"), ("dm",))

    def test_prepare_turn_peeks_next_speaker_without_consuming(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            (campaign_root / "state.json").write_text(
                json.dumps(
                    {
                        "campaign": "c1",
                        "next_speakers": [
                            {"agent": "sumi", "rapid_prompt": "react now"}
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            state = SessionState.new(
                campaign="c1",
                initial_mode="scene-play",
                initial_scene="opening",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))

            package = orchestrator.prepare_turn(state)

            self.assertIn("players/sumi/turns/0001", str(package.turn_dir))
            raw = json.loads((campaign_root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["next_speakers"][0]["agent"], "sumi")

    def test_prepare_turn_builds_readonly_player_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            (campaign_root / "state.json").write_text(
                json.dumps({"campaign": "c1", "next_speakers": [{"agent": "tev"}]})
                + "\n",
                encoding="utf-8",
            )
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

            package = orchestrator.prepare_turn(state)

            self.assertEqual(package.spawn_cwd, root / ".glass-cwd" / "c1" / "0001-tev")
            self.assertEqual(
                package.agent_turn_start_path,
                package.spawn_cwd / "players" / "tev" / "turns" / "0001" / "in.md",
            )
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
            self.assertTrue((package.spawn_cwd / "scratch").is_dir())
            self.assertEqual((package.spawn_cwd.stat().st_mode & 0o777), 0o555)
            self.assertEqual(((package.spawn_cwd / "scratch").stat().st_mode & 0o777), 0o777)
            self.assertEqual(((root / ".glass-cwd").stat().st_mode & 0o777), 0o710)
            self.assertEqual(((root / ".glass-cwd" / "c1").stat().st_mode & 0o777), 0o710)
            self.assertEqual(((package.spawn_cwd / ".claude").stat().st_mode & 0o777), 0o777)
            self.assertEqual(((package.spawn_cwd / ".mcp.json").stat().st_mode & 0o777), 0o666)
            turn_start = package.turn_start_path.read_text(encoding="utf-8")
            self.assertIn("read-only projection of the campaign workspace", turn_start)

    def test_prepare_turn_dm_projection_includes_dm_arc_prep(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            (campaign_root / "state.json").write_text(
                json.dumps({"campaign": "c1"}) + "\n",
                encoding="utf-8",
            )
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

            package = orchestrator.prepare_turn(state)

            self.assertIn("dm/turns/0001", str(package.turn_dir))
            self.assertTrue((package.spawn_cwd / "arcs" / "opening" / "plan.md").exists())
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

    def test_character_creation_turn_omits_recent_turn_excerpts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            (campaign_root / "state.json").write_text(
                json.dumps({"campaign": "c1", "next_speakers": [{"agent": "tev"}]})
                + "\n",
                encoding="utf-8",
            )
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

            package = orchestrator.prepare_turn(state)

            turn_start = package.turn_start_path.read_text(encoding="utf-8")
            self.assertIn("Prior character-creation turns are intentionally not embedded", turn_start)
            self.assertIn("character concepts independent", turn_start)
            self.assertNotIn("Sumi builds directly around Tev's hook", turn_start)

    def test_prepare_turn_uses_action_order_when_queue_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            (campaign_root / "state.json").write_text(
                json.dumps(
                    {
                        "campaign": "c1",
                        "next_speakers": [],
                        "action_order": {
                            "mode": "action",
                            "scene_id": "ambush",
                            "round": 1,
                            "cursor": 0,
                            "order": ["kit", "dm", "tev"],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            state = SessionState.new(
                campaign="c1",
                initial_mode="action",
                initial_scene="ambush",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))

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
            self.assertIn("## Creative Influence", turn_start)
            self.assertIn("Verse phrase:", turn_start)
            self.assertIn("Tarot:", turn_start)

    def test_creative_influence_omitted_during_bootstrap_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            (campaign_root / "state.json").write_text(
                json.dumps({"campaign": "c1"}) + "\n",
                encoding="utf-8",
            )
            state = SessionState.new(
                campaign="c1",
                initial_mode="campaign-planning",
                initial_scene="planning",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))

            package = orchestrator.prepare_turn(state)

            turn_start = package.turn_start_path.read_text(encoding="utf-8")
            self.assertNotIn("## Creative Influence", turn_start)
            self.assertNotIn("Verse phrase:", turn_start)

    def test_creative_influence_omitted_during_prelude_coordinator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            (campaign_root / "state.json").write_text(
                json.dumps({"campaign": "c1"}) + "\n",
                encoding="utf-8",
            )
            state = SessionState.new(
                campaign="c1",
                initial_mode="prelude",
                initial_scene="prelude",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))

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

    def test_public_prose_rejects_glass_command_transcripts(self) -> None:
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

    def test_prelude_dm_turn_without_handoff_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            (campaign_root / "state.json").write_text(
                json.dumps({"campaign": "c1", "next_speakers": []}) + "\n",
                encoding="utf-8",
            )
            state = SessionState.new(
                campaign="c1",
                initial_mode="prelude",
                initial_scene="prelude",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
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
            (campaign_root / "state.json").write_text(
                json.dumps({"campaign": "c1", "next_speakers": [{"agent": "tev"}]})
                + "\n",
                encoding="utf-8",
            )
            state = SessionState.new(
                campaign="c1",
                initial_mode="prelude",
                initial_scene="prelude",
                initial_budget=None,
            )
            orchestrator = Orchestrator(config, SessionStore(config))
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

    def test_advance_action_order_wraps_round(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = make_config(root)
            campaign_root = config.campaigns_dir / "c1"
            campaign_root.mkdir(parents=True)
            (campaign_root / "state.json").write_text(
                json.dumps(
                    {
                        "campaign": "c1",
                        "action_order": {
                            "mode": "action",
                            "scene_id": "ambush",
                            "round": 1,
                            "cursor": 1,
                            "order": ["kit", "dm"],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            orchestrator = Orchestrator(config, SessionStore(config))

            orchestrator._advance_action_order(
                "c1",
                {
                    "agent": "dm",
                    "mode": "action",
                    "scene_id": "ambush",
                    "cursor": 1,
                    "order": ["kit", "dm"],
                },
            )

            raw = json.loads((campaign_root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["action_order"]["cursor"], 0)
            self.assertEqual(raw["action_order"]["round"], 2)


if __name__ == "__main__":
    unittest.main()
