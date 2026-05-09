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


if __name__ == "__main__":
    unittest.main()
