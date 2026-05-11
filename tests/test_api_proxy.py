import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cli import db as _db
from cli.api_grants import mint_grant, validate_grant
from cli.api_server import (
    _current_turn_output_payload,
    _file_content_payload,
    _file_entry_matches_section,
    _file_section_counts,
    _file_tree_payload,
    _invoke_glass,
    _parse_created_id_cursor,
    ensure_background_server,
)
from cli.config import get_paths, load_config
from cli.errors import GlassError
from cli.local_env import load_repo_env
from cli.state import default_state, save_state
from orchestrator import permissions


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def initialize_postgres_state(config: Path, campaign_id: str) -> None:
    load_repo_env()
    previous = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = str(config)
    try:
        toml_data = load_config()
        pg_config = _db.load_pg_config(toml_data)
        with _db.connect(pg_config) as conn:
            _db.migrate(conn)
            _db.delete_campaign_data(conn, campaign_id)
        save_state(get_paths(), default_state(campaign_id))
    finally:
        if previous is None:
            os.environ.pop("GLASS_CONFIG", None)
        else:
            os.environ["GLASS_CONFIG"] = previous


class GlassApiProxyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._provisioned_patch = patch.object(
            permissions,
            "has_provisioned_users",
            return_value=False,
        )
        self._provisioned_patch.start()

    def tearDown(self) -> None:
        self._provisioned_patch.stop()

    def test_readonly_file_tree_includes_narrative_private_notes_not_grants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign_root = Path(tmp) / "campaigns" / "c1"
            (campaign_root / "dm" / "notes").mkdir(parents=True)
            (campaign_root / "players" / "tev" / "private").mkdir(parents=True)
            (campaign_root / "dm" / "notes" / "secret.md").write_text(
                "# Secret Notes\n\nvisible to the debug surface\n",
                encoding="utf-8",
            )
            (campaign_root / "players" / "tev" / "private" / "journal.md").write_text(
                "# Tev Journal\n\nalso visible\n",
                encoding="utf-8",
            )
            (campaign_root / ".glass-grants.json").write_text("{}", encoding="utf-8")

            files = _file_tree_payload(campaign_root)
            paths = {entry["path"] for entry in files}

            self.assertIn("dm/notes/secret.md", paths)
            self.assertIn("players/tev/private/journal.md", paths)
            self.assertNotIn(".glass-grants.json", paths)
            sections = {entry["section"]: entry["count"] for entry in _file_section_counts(files)}
            self.assertGreaterEqual(sections["dm"], 1)
            self.assertTrue(
                _file_entry_matches_section(
                    next(entry for entry in files if entry["path"] == "dm/notes/secret.md"),
                    "dm",
                )
            )

    def test_readonly_file_content_rejects_campaign_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign_root = root / "campaigns" / "c1"
            campaign_root.mkdir(parents=True)
            (campaign_root / "context.md").write_text("hello\n", encoding="utf-8")
            (root / "outside.md").write_text("nope\n", encoding="utf-8")

            payload = _file_content_payload(campaign_root, "context.md")
            self.assertEqual(payload["content"], "hello\n")
            with self.assertRaises(GlassError):
                _file_content_payload(campaign_root, "../outside.md")

    def test_created_id_cursor_parsing_rejects_invalid_cursor(self) -> None:
        self.assertEqual(
            _parse_created_id_cursor("2026-05-11T00:00:00Z::abc"),
            ("2026-05-11T00:00:00Z", "abc"),
        )
        with self.assertRaises(GlassError):
            _parse_created_id_cursor("not-a-cursor")

    def test_current_turn_output_returns_only_running_turn_capture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign_root = Path(tmp) / "campaigns" / "c1"
            turn_dir = campaign_root / "players" / "tev" / "turns" / "0005"
            turn_dir.mkdir(parents=True)
            (turn_dir / "agent-stdout.txt").write_text(
                "thinking line one\nthinking line two\n",
                encoding="utf-8",
            )
            (turn_dir / "agent-stderr.txt").write_text("warning line\n", encoding="utf-8")

            running = _current_turn_output_payload(
                campaign_root,
                runtime_state={
                    "aog_status": "running",
                    "turn_counter": 4,
                },
                max_bytes=512,
            )

            self.assertTrue(running["active"])
            self.assertEqual(running["turn_id"], "c1-t0005")
            self.assertEqual(running["turn_number"], 5)
            self.assertEqual(running["speaker"], "tev")
            self.assertEqual(running["role"], "player")
            self.assertEqual(running["turn_dir"], "players/tev/turns/0005")
            self.assertEqual(
                running["stdout"],
                "thinking line one\nthinking line two\n",
            )
            self.assertEqual(running["stderr"], "warning line\n")

            ready = _current_turn_output_payload(
                campaign_root,
                runtime_state={
                    "aog_status": "ready",
                    "turn_counter": 5,
                },
                max_bytes=512,
            )

            self.assertFalse(ready["active"])
            self.assertIsNone(ready["turn_id"])
            self.assertEqual(ready["stdout"], "")
            self.assertEqual(ready["stderr"], "")

    def test_player_grant_allows_player_surface_and_rejects_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaigns = Path(tmp) / "campaigns"
            (campaigns / "c1").mkdir(parents=True)
            token = mint_grant(
                campaigns,
                campaign_id="c1",
                role="player",
                actor="tev",
                glass_role="player:tev",
                turn_id="c1-t0001",
                ttl_seconds=60,
            )

            claim = validate_grant(campaigns, token, ["msg", "read"])
            self.assertEqual(claim["actor"], "tev")
            validate_grant(campaigns, token, ["search", "text", "duke"])
            validate_grant(campaigns, token, ["tarot", "current"])
            validate_grant(campaigns, token, ["tarot", "list"])
            validate_grant(campaigns, token, ["entity", "relations", "duke"])
            validate_grant(campaigns, token, ["sync", "apply", "--from", "scratch/sync.json"])
            validate_grant(
                campaigns,
                token,
                ["entity", "claim", "duke", "ATTITUDE_TOWARD", "party", "--summary", "heard it"],
            )

            with self.assertRaises(GlassError):
                validate_grant(campaigns, token, ["db", "init"])
            with self.assertRaises(GlassError):
                validate_grant(campaigns, token, ["tarot", "draw", "tev"])
            with self.assertRaises(GlassError):
                validate_grant(campaigns, token, ["entity", "query", "MATCH (n) RETURN n"])

    def test_standalone_client_proxies_to_local_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaigns = root / "campaigns"
            (campaigns / "c1").mkdir(parents=True)
            config = root / "agents-of-glass.toml"
            config.write_text(
                f"""
[postgres]
host = "192.168.66.3"
port = 5432
database = "agents_of_glass"
user = "agents_of_glass_app"

[falkordb]
host = "192.168.66.3"
port = 16379
graph = "agents_of_glass"

[paths]
content = "{root / "templates"}"
campaigns = "{campaigns}"
""".lstrip(),
                encoding="utf-8",
            )
            url = ensure_background_server(
                url=f"http://127.0.0.1:{free_port()}",
                config_path=str(config),
            )
            grant = mint_grant(
                campaigns,
                campaign_id="c1",
                role="player",
                actor="tev",
                glass_role="player:tev",
                turn_id="c1-t0001",
                ttl_seconds=60,
            )
            grant_file = root / "grant.json"
            grant_file.write_text(
                json.dumps({"api_url": url, "grant": grant}) + "\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.pop("GLASS_API_URL", None)
            env.pop("GLASS_API_GRANT", None)
            env["GLASS_API_GRANT_FILE"] = str(grant_file)
            result = subprocess.run(
                [sys.executable, "scripts/glass-api-client", "--help"],
                cwd=Path(__file__).resolve().parents[1],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Usage: glass", result.stdout)

    def test_api_invocation_reads_from_projected_workspace_and_writes_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaigns = root / "campaigns"
            campaign_root = campaigns / "c1"
            campaign_root.mkdir(parents=True)
            projection = root / ".glass-cwd" / "c1" / "0001-tev"
            (projection / "players" / "tev" / "public").mkdir(parents=True)
            (projection / "players" / "tev" / "public" / "intro.md").write_text(
                "hello from projection\n",
                encoding="utf-8",
            )
            os.chmod(projection / "players" / "tev" / "public" / "intro.md", 0)
            config = root / "agents-of-glass.toml"
            config.write_text(
                f"""
[postgres]
host = "192.168.66.3"
port = 5432
database = "agents_of_glass"
user = "agents_of_glass_app"

[falkordb]
host = "192.168.66.3"
port = 16379
graph = "agents_of_glass"

[paths]
content = "{root / "templates"}"
campaigns = "{campaigns}"
""".lstrip(),
                encoding="utf-8",
            )
            initialize_postgres_state(config, "c1")
            token = mint_grant(
                campaigns,
                campaign_id="c1",
                role="player",
                actor="tev",
                glass_role="player:tev",
                turn_id="c1-t0001",
                ttl_seconds=60,
                workspace_root=projection,
                workspace_reader_user="aog-tev",
            )
            claim = validate_grant(
                campaigns,
                token,
                ["sync", "apply", "players/tev/public/intro.md"],
            )
            old_config = os.environ.get("GLASS_CONFIG")
            os.environ["GLASS_CONFIG"] = str(config)
            try:
                with patch("cli.commands.sync.subprocess.run") as run:
                    run.return_value = subprocess.CompletedProcess(
                        args=[],
                        returncode=0,
                        stdout=b"hello from projection\n",
                        stderr=b"",
                    )
                    result = _invoke_glass(
                        ["sync", "apply", "players/tev/public/intro.md"],
                        claim,
                    )
            finally:
                os.chmod(projection / "players" / "tev" / "public" / "intro.md", 0o600)
                if old_config is None:
                    os.environ.pop("GLASS_CONFIG", None)
                else:
                    os.environ["GLASS_CONFIG"] = old_config

            self.assertEqual(result["exit_code"], 0, result["output"])
            self.assertEqual(
                (campaign_root / "players" / "tev" / "public" / "intro.md").read_text(
                    encoding="utf-8"
                ),
                "hello from projection\n",
            )
            self.assertEqual(
                (projection / "players" / "tev" / "public" / "intro.md").read_text(
                    encoding="utf-8"
                ),
                "hello from projection\n",
            )


if __name__ == "__main__":
    unittest.main()
