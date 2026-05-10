import json
import tempfile
import unittest
from pathlib import Path

from orchestrator.config import AogConfig, CapsConfig, ClaudeConfig
from orchestrator.runner import Orchestrator
from orchestrator.state import SessionState
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
            self.assertIn("## ACTION-SCENE TURN", turn_start)
            self.assertIn("`kit -> dm -> tev`", turn_start)

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
