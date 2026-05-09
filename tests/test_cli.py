import json
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from cli.main import main


def make_env(tmp_path: Path, campaign_id: str = "c1") -> dict[str, str]:
    templates = tmp_path / "templates"
    campaigns = tmp_path / "campaigns"
    templates.mkdir()
    campaign = campaigns / campaign_id
    campaign.mkdir(parents=True)
    config = tmp_path / "agents-of-glass.toml"
    config.write_text(
        f"""
[paths]
templates = "{templates}"
campaigns = "{campaigns}"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return {"GLASS_CONFIG": str(config), "GLASS_CAMPAIGN_ID": campaign_id}


def invoke_ok(runner: CliRunner, args: list[str], env: dict[str, str]):
    result = runner.invoke(main, args, env=env)
    if result.exit_code != 0:
        raise AssertionError(result.output)
    return result


class GlassCliTests(unittest.TestCase):
    def test_session_and_mode_use_campaign_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)

            session = invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            self.assertIn("campaign: c1", session.output)

            mode = invoke_ok(
                runner,
                ["mode", "start", "scene-play", "opening"],
                {**env, "GLASS_ROLE": "dm"},
            )
            self.assertIn("current_mode: scene-play", mode.output)

            state = json.loads((tmp_path / "campaigns" / "c1" / "state.json").read_text())
            self.assertEqual(state["mode_stack"][-1]["mode"], "scene-play")

            ended = invoke_ok(runner, ["mode", "end"], {**env, "GLASS_ROLE": "dm"})
            self.assertIn("ended:", ended.output)

    def test_player_note_write_targets_campaign_not_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)

            result = invoke_ok(
                runner,
                ["note", "write", "journal/field-note.md", "--body", "Observed."],
                {**env, "GLASS_ROLE": "player:tev"},
            )
            self.assertIn("players/tev/journal/field-note.md", result.output)
            campaign_note = (
                tmp_path / "campaigns" / "c1" / "players" / "tev"
                / "journal" / "field-note.md"
            )
            template_note = (
                tmp_path / "templates" / "players" / "tev"
                / "journal" / "field-note.md"
            )
            self.assertEqual(campaign_note.read_text(encoding="utf-8"), "Observed.")
            self.assertFalse(template_note.exists())

    def test_arc_scene_quest_and_scene_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)

            arc = invoke_ok(runner, ["arc", "create", "first-arc"], dm_env)
            self.assertIn("arc_id: first-arc", arc.output)

            scene = invoke_ok(
                runner,
                ["scene", "create", "opening", "--type", "social"],
                dm_env,
            )
            self.assertIn("scene_id: opening", scene.output)

            beat = invoke_ok(
                runner,
                ["quest", "beat", "The warrant clock starts."],
                dm_env,
            )
            self.assertIn("The warrant clock starts.", beat.output)

            ended = invoke_ok(
                runner,
                [
                    "scene",
                    "end",
                    "--summary",
                    "The scene closes.",
                    "--beats",
                    "The party commits to the warrant.",
                ],
                dm_env,
            )
            self.assertIn("ended_scene: opening", ended.output)

            root = tmp_path / "campaigns" / "c1"
            quest_log = (root / "shared" / "quest-log.md").read_text(encoding="utf-8")
            self.assertIn("The warrant clock starts.", quest_log)
            self.assertIn("The party commits to the warrant.", quest_log)
            summary = (
                root / "arcs" / "first-arc" / "scenes" / "opening" / "summary.md"
            ).read_text(encoding="utf-8")
            self.assertIn("The scene closes.", summary)


if __name__ == "__main__":
    unittest.main()
