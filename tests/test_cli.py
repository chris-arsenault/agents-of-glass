import json
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from cli.main import main


def make_env(tmp_path: Path, role: str | None = None) -> dict[str, str]:
    content = tmp_path / "content"
    sessions = content / "sessions"
    for player in ("tev", "sumi", "renno", "kit"):
        (content / "players" / player).mkdir(parents=True, exist_ok=True)
    (content / "shared" / "vocabulary").mkdir(parents=True, exist_ok=True)
    (content / "shared" / "vocabulary" / "message-types.md").write_text(
        "- table-talk\n- banter\n- instruction\n- plot-hint\n- secret\n",
        encoding="utf-8",
    )
    config = tmp_path / "agents-of-glass.toml"
    config.write_text(
        f"""
[paths]
content = "{content}"
sessions = "{sessions}"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    env = {"GLASS_CONFIG": str(config)}
    if role is not None:
        env["GLASS_ROLE"] = role
    return env


def invoke_ok(runner: CliRunner, args: list[str], env: dict[str, str]):
    result = runner.invoke(main, args, env=env)
    if result.exit_code != 0:
        raise AssertionError(result.output)
    return result


def session_state(tmp_path: Path, session_id: str = "test-campaign") -> dict:
    state_path = tmp_path / "content" / "sessions" / session_id / "state.json"
    return json.loads(state_path.read_text(encoding="utf-8"))


class GlassCliTests(unittest.TestCase):
    def test_session_character_roll_and_turn_append(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)

            invoke_ok(
                runner,
                [
                    "session",
                    "new",
                    "--campaign",
                    "Test Campaign",
                    "--session-id",
                    "test-campaign",
                ],
                env,
            )
            invoke_ok(
                runner,
                [
                    "character",
                    "new",
                    "karrith",
                    "--player",
                    "tev",
                    "--skill",
                    "climbing=artisan",
                    "--attribute",
                    "finesse=advanced",
                ],
                env,
            )
            roll = invoke_ok(
                runner,
                ["roll", "climbing", "finesse", "--risk", "risky", "--character", "karrith"],
                {**env, "GLASS_ROLE": "player:tev"},
            )
            self.assertIn("roll_id:", roll.output)
            self.assertIn("outcome:", roll.output)

            turn_file = tmp_path / "turn.md"
            turn_file.write_text("Karrith climbs the gantry.", encoding="utf-8")
            turn = invoke_ok(
                runner,
                ["turn", "append", str(turn_file)],
                {**env, "GLASS_ROLE": "player:tev"},
            )
            self.assertIn("turn_id: 1", turn.output)

            state = session_state(tmp_path)
            self.assertEqual(len(state["dice_events"]), 1)
            self.assertEqual(state["turns"][0]["speaker"], "tev")
            transcript = (
                tmp_path / "content" / "sessions" / "test-campaign" / "transcript.md"
            ).read_text(encoding="utf-8")
            self.assertIn("Karrith climbs the gantry.", transcript)
            self.assertIn("> roll climbing", transcript)

    def test_player_cannot_start_mode_or_mutate_other_character(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            invoke_ok(
                runner,
                [
                    "session",
                    "new",
                    "--campaign",
                    "Test Campaign",
                    "--session-id",
                    "test-campaign",
                ],
                env,
            )
            invoke_ok(runner, ["character", "new", "karrith", "--player", "tev"], env)

            denied_mode = runner.invoke(
                main,
                ["mode", "start", "combat", "market"],
                env={**env, "GLASS_ROLE": "player:tev"},
            )
            self.assertNotEqual(denied_mode.exit_code, 0)
            self.assertIn("DM-only", denied_mode.output)

            denied_hp = runner.invoke(
                main,
                ["character", "set-hp", "karrith", "-1"],
                env={**env, "GLASS_ROLE": "player:sumi"},
            )
            self.assertNotEqual(denied_hp.exit_code, 0)
            self.assertIn("players may mutate only their own character", denied_hp.output)

    def test_messages_are_role_visible_and_checkpointed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            invoke_ok(
                runner,
                [
                    "session",
                    "new",
                    "--campaign",
                    "Test Campaign",
                    "--session-id",
                    "test-campaign",
                ],
                env,
            )

            invoke_ok(
                runner,
                ["msg", "secret", "tev", "watch", "the", "stairs"],
                {**env, "GLASS_ROLE": "dm"},
            )

            sumi_read = invoke_ok(
                runner,
                ["msg", "read", "--since-checkpoint"],
                {**env, "GLASS_ROLE": "player:sumi"},
            )
            self.assertIn("count: 0", sumi_read.output)

            tev_read = invoke_ok(
                runner,
                ["msg", "read", "--since-checkpoint"],
                {**env, "GLASS_ROLE": "player:tev"},
            )
            self.assertIn("count: 1", tev_read.output)
            self.assertIn("watch the stairs", tev_read.output)

            tev_second_read = invoke_ok(
                runner,
                ["msg", "read", "--since-checkpoint"],
                {**env, "GLASS_ROLE": "player:tev"},
            )
            self.assertIn("count: 0", tev_second_read.output)

    def test_note_propose_and_ratify_upserts_entity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            invoke_ok(
                runner,
                [
                    "session",
                    "new",
                    "--campaign",
                    "Test Campaign",
                    "--session-id",
                    "test-campaign",
                ],
                env,
            )

            draft_body = (
                "---\nid: glass-market\ntitle: Glass Market\n---\n"
                "# Glass Market\n\n## Look\nBright."
            )
            invoke_ok(
                runner,
                ["note", "write", "drafts/glass-market.md", "--body", draft_body],
                {**env, "GLASS_ROLE": "player:tev"},
            )
            propose = invoke_ok(
                runner,
                ["note", "propose", "players/tev/drafts/glass-market.md"],
                {**env, "GLASS_ROLE": "player:tev"},
            )
            intake_line = next(line for line in propose.output.splitlines() if "intake_id:" in line)
            intake_id = intake_line.split(":", 1)[1].strip()

            ratify = invoke_ok(
                runner,
                ["note", "ratify", intake_id],
                {**env, "GLASS_ROLE": "dm"},
            )
            self.assertIn("entity_id: glass-market", ratify.output)

            state = session_state(tmp_path)
            self.assertEqual(state["note_intake"][0]["status"], "ratified")
            self.assertIn("glass-market", state["entities"])


if __name__ == "__main__":
    unittest.main()
