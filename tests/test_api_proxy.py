import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cli.api_grants import mint_grant, validate_grant
from cli.api_server import ensure_background_server
from cli.errors import GlassError


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class GlassApiProxyTests(unittest.TestCase):
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

            with self.assertRaises(GlassError):
                validate_grant(campaigns, token, ["db", "init"])

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


if __name__ == "__main__":
    unittest.main()
