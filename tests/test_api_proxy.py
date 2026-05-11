import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cli.api_grants import mint_grant, validate_grant
from cli.api_server import (
    _file_content_payload,
    _file_entry_matches_section,
    _file_section_counts,
    _file_tree_payload,
    _invoke_glass,
    _parse_created_id_cursor,
    ensure_background_server,
)
from cli.errors import GlassError


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class GlassApiProxyTests(unittest.TestCase):
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
                f'[paths]\ncontent = "{root / "templates"}"\ncampaigns = "{campaigns}"\n',
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
            (campaign_root / "state.json").write_text(
                json.dumps(
                    {
                        "schema_version": 5,
                        "campaign": "c1",
                        "status": "active",
                        "turn_counter": 0,
                        "mode_stack": [],
                        "pending_events": [],
                        "note_intake": [],
                        "entities": {},
                        "threads": {},
                        "turns": [],
                        "next_speakers": [],
                        "action_order": None,
                        "scene_trackers": {},
                        "scene_closing_turns": None,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            projection = root / ".glass-cwd" / "c1" / "0001-tev"
            (projection / "scratch").mkdir(parents=True)
            (projection / "scratch" / "intro.md").write_text("hello from projection\n")
            config = root / "agents-of-glass.toml"
            config.write_text(
                f'[paths]\ncontent = "{root / "templates"}"\ncampaigns = "{campaigns}"\n',
                encoding="utf-8",
            )
            token = mint_grant(
                campaigns,
                campaign_id="c1",
                role="player",
                actor="tev",
                glass_role="player:tev",
                turn_id="c1-t0001",
                ttl_seconds=60,
                workspace_root=projection,
            )
            claim = validate_grant(
                campaigns,
                token,
                ["note", "write", "public/intro.md", "--from", "scratch/intro.md"],
            )
            old_config = os.environ.get("GLASS_CONFIG")
            os.environ["GLASS_CONFIG"] = str(config)
            try:
                result = _invoke_glass(
                    ["note", "write", "public/intro.md", "--from", "scratch/intro.md"],
                    claim,
                )
            finally:
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
