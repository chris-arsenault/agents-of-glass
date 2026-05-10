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

    def test_turn_append_exports_file_and_structured_feed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["mode", "start", "scene-play", "opening"], dm_env)
            turn_file = tmp_path / "turn.md"
            turn_file.write_text("Mara frames the scene.", encoding="utf-8")

            appended = invoke_ok(
                runner,
                ["turn", "append", str(turn_file), "--speaker", "dm"],
                dm_env,
            )
            self.assertIn("turn_id: 1", appended.output)
            self.assertIn("transcript_export_path:", appended.output)

            found = invoke_ok(runner, ["turns", "find", "--limit", "1"], dm_env)
            self.assertIn("Mara frames the scene.", found.output)
            text_found = invoke_ok(
                runner,
                ["turns", "find", "--text", "frames", "--limit", "1"],
                dm_env,
            )
            self.assertIn("Mara frames the scene.", text_found.output)

            feed = invoke_ok(runner, ["turns", "feed", "--after-turn", "0"], dm_env)
            self.assertIn("event_type: turn.committed", feed.output)
            self.assertIn('prose: "Mara frames the scene."', feed.output)

            transcript = (tmp_path / "campaigns" / "c1" / "transcript.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## Turn 1 - dm (dm) - scene-play, opening", transcript)
            self.assertIn("Mara frames the scene.", transcript)

    def test_turn_initiative_persists_action_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["mode", "start", "action", "ambush"], dm_env)

            result = invoke_ok(
                runner,
                ["turn", "initiative", "--participants", "tev,dm,kit"],
                dm_env,
            )

            self.assertIn("action_order:", result.output)
            state = json.loads((tmp_path / "campaigns" / "c1" / "state.json").read_text())
            action_order = state["action_order"]
            self.assertEqual(action_order["mode"], "action")
            self.assertEqual(action_order["scene_id"], "ambush")
            self.assertEqual(action_order["round"], 1)
            self.assertEqual(action_order["cursor"], 0)
            self.assertEqual(set(action_order["order"]), {"tev", "dm", "kit"})
            self.assertEqual(len(action_order["rolls"]), 3)

    def test_scene_create_accepts_custom_type_and_trackers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["arc", "create", "first-arc"], dm_env)

            scene = invoke_ok(
                runner,
                ["scene", "create", "duke-gate", "--type", "courtroom-standoff"],
                dm_env,
            )
            self.assertIn("scene_type: courtroom-standoff", scene.output)
            root = tmp_path / "campaigns" / "c1"
            table_root = root / "table"
            self.assertTrue((table_root / "index.md").exists())
            self.assertTrue((table_root / "scene.md").exists())
            self.assertTrue((table_root / "handouts").is_dir())
            self.assertIn("table_path:", scene.output)

            invoke_ok(
                runner,
                [
                    "table",
                    "write",
                    "npc-korth.md",
                    "--body",
                    "Korth is visibly rattled.",
                ],
                dm_env,
            )
            table_read = invoke_ok(
                runner,
                ["table", "show", "npc-korth.md"],
                {**env, "GLASS_ROLE": "player:tev"},
            )
            self.assertIn("Korth is visibly rattled.", table_read.output)
            denied = runner.invoke(
                main,
                ["table", "write", "player-note.md", "--body", "not allowed"],
                env={**env, "GLASS_ROLE": "player:tev"},
            )
            self.assertNotEqual(denied.exit_code, 0)
            self.assertIn("DM-only", denied.output)

            invoke_ok(runner, ["mode", "start", "action", "duke-gate"], dm_env)
            turn_file = tmp_path / "scene-turn.md"
            turn_file.write_text("Mara points to the castle gate.", encoding="utf-8")
            invoke_ok(
                runner,
                ["turn", "append", str(turn_file), "--speaker", "dm"],
                dm_env,
            )
            scene_transcript = (
                root / "arcs" / "first-arc" / "scenes" / "duke-gate" / "transcript.md"
            ).read_text(encoding="utf-8")
            self.assertIn("Mara points to the castle gate.", scene_transcript)

            tracker = invoke_ok(
                runner,
                [
                    "scene",
                    "tracker",
                    "set",
                    "duke-permission",
                    "--label",
                    "Duke lets the party into the castle",
                    "--max",
                    "4",
                    "--resistance",
                    "2",
                    "--impact-resistance",
                    "1",
                ],
                dm_env,
            )
            self.assertIn("Duke lets the party into the castle", tracker.output)
            ticked = invoke_ok(
                runner,
                ["scene", "tracker", "tick", "duke-permission", "2"],
                dm_env,
            )
            self.assertIn("after: 2", ticked.output)

            state = json.loads((tmp_path / "campaigns" / "c1" / "state.json").read_text())
            self.assertEqual(state["active_scene_type"], "courtroom-standoff")
            self.assertEqual(state["scene_trackers"]["duke-permission"]["value"], 2)
            self.assertEqual(state["scene_trackers"]["duke-permission"]["resistance"], 2)
            self.assertEqual(
                state["scene_trackers"]["duke-permission"]["impact_resistance"],
                1,
            )

            snapshot = invoke_ok(
                runner,
                ["table", "snapshot", "--label", "after-korth"],
                dm_env,
            )
            self.assertIn("after-korth", snapshot.output)

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
            invoke_ok(
                runner,
                [
                    "table",
                    "append",
                    "index.md",
                    "--body",
                    "\n- The warrant clock is visible on the table.\n",
                ],
                dm_env,
            )

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
            shown_summary = invoke_ok(
                runner,
                ["summary", "show", "scene", "opening", "--arc", "first-arc"],
                dm_env,
            )
            self.assertIn("The scene closes.", shown_summary.output)
            invoke_ok(
                runner,
                ["summary", "write", "campaign", "--body", "The campaign has begun."],
                dm_env,
            )
            campaign_summary = invoke_ok(
                runner,
                ["summary", "show", "campaign"],
                {**env, "GLASS_ROLE": "player:tev"},
            )
            self.assertIn("The campaign has begun.", campaign_summary.output)
            archived_table = root / "arcs" / "first-arc" / "scenes" / "opening" / "table" / "final"
            self.assertTrue((archived_table / "index.md").exists())
            self.assertIn(
                "The warrant clock is visible",
                (archived_table / "index.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "No scene is currently active",
                (root / "table" / "index.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
