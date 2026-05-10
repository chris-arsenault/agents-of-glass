"""Local HTTP API for player-facing glass CLI calls."""

from __future__ import annotations

import contextlib
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Iterator

from click.testing import CliRunner

from .api_grants import DEFAULT_API_URL, validate_grant
from .config import get_paths
from .errors import GlassError


_server: HTTPServer | None = None
_server_thread: threading.Thread | None = None
_server_url: str | None = None
_invoke_lock = threading.Lock()


def ensure_background_server(
    *,
    url: str = DEFAULT_API_URL,
    config_path: str | None = None,
) -> str:
    """Start the local API in this process unless something healthy exists."""

    global _server, _server_thread, _server_url
    if config_path:
        os.environ["GLASS_CONFIG"] = config_path
    if _server_thread is not None and _server_thread.is_alive() and _server_url == url:
        return url

    health = _server_health(url)
    if health is not None:
        server_config = health.get("config_path")
        if config_path and server_config and server_config != config_path:
            raise RuntimeError(
                f"glass API already running at {url} with different config: {server_config}"
            )
        return url

    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8765
    _server = HTTPServer((host, port), _GlassApiHandler)
    _server_thread = threading.Thread(
        target=_server.serve_forever,
        name="glass-api",
        daemon=True,
    )
    _server_thread.start()
    _server_url = url
    _wait_for_health(url)
    return url


def serve_forever(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    config_path: str | None = None,
) -> None:
    if config_path:
        os.environ["GLASS_CONFIG"] = config_path
    server = HTTPServer((host, port), _GlassApiHandler)
    server.serve_forever()


def is_server_available(url: str = DEFAULT_API_URL) -> bool:
    return _server_health(url) is not None


def _server_health(url: str = DEFAULT_API_URL) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/v1/health", timeout=1) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("utf-8"))
            return payload if isinstance(payload, dict) else None
    except OSError:
        return None
    except json.JSONDecodeError:
        return None


def _wait_for_health(url: str) -> None:
    deadline = time.time() + 2
    while time.time() < deadline:
        if is_server_available(url):
            return
        time.sleep(0.05)
    raise RuntimeError(f"glass API did not become healthy at {url}")


class _GlassApiHandler(BaseHTTPRequestHandler):
    server_version = "glass-api/0.1"

    def do_GET(self) -> None:
        if self.path == "/v1/health":
            self._write_json(
                200,
                {
                    "status": "ok",
                    "pid": os.getpid(),
                    "config_path": os.environ.get("GLASS_CONFIG"),
                },
            )
            return
        self._write_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/v1/command":
            self._write_json(404, {"error": "not found"})
            return
        self._handle_command()

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _handle_command(self) -> None:
        try:
            payload = self._read_payload()
            token = str(payload.get("grant") or "")
            args = payload.get("args")
            if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
                raise GlassError("invalid glass API payload: args must be a string list")
            paths = get_paths()
            claim = validate_grant(paths.campaigns, token, args)
            result = _invoke_glass(args, claim)
            self._write_json(200, result)
        except GlassError as exc:
            self._write_json(
                403,
                {
                    "exit_code": 77,
                    "output": f"Error: {exc}\n",
                },
            )
        except Exception as exc:
            self._write_json(
                500,
                {
                    "exit_code": 70,
                    "output": f"glass API internal error: {exc}\n",
                },
            )

    def _read_payload(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise GlassError("invalid Content-Length") from exc
        raw = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            raise GlassError(f"invalid JSON payload: {exc}") from exc
        if not isinstance(payload, dict):
            raise GlassError("invalid glass API payload: expected object")
        return payload

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _invoke_glass(args: list[str], claim: dict[str, Any]) -> dict[str, Any]:
    from .main import main as glass_main

    campaigns_dir = get_paths().campaigns
    campaign_id = str(claim["campaign_id"])
    campaign_root = campaigns_dir / campaign_id
    workspace_root = _claim_workspace_root(claim, fallback=campaign_root)
    env = os.environ.copy()
    env.update(
        {
            "GLASS_API_INTERNAL": "1",
            "GLASS_CAMPAIGN_ID": campaign_id,
            "GLASS_ROLE": str(claim["glass_role"]),
            "GLASS_TURN_ID": str(claim["turn_id"]),
        }
    )
    runner = CliRunner()
    with _invoke_lock, _pushd(workspace_root):
        raw = runner.invoke(glass_main, args, env=env, prog_name="glass")
        if raw.exit_code == 0:
            _refresh_projection(campaign_root, workspace_root, claim)
    return {
        "exit_code": raw.exit_code,
        "output": raw.output,
    }


def _claim_workspace_root(claim: dict[str, Any], *, fallback: Path) -> Path:
    value = claim.get("workspace_root")
    if not isinstance(value, str) or not value:
        return fallback
    path = Path(value).expanduser()
    if not path.exists() or not path.is_dir():
        return fallback
    return path


def _refresh_projection(
    campaign_root: Path,
    workspace_root: Path,
    claim: dict[str, Any],
) -> None:
    if workspace_root.resolve() == campaign_root.resolve():
        return
    turn_number = _turn_number_from_claim(claim)
    if turn_number is None:
        return
    try:
        from orchestrator.config import load_config as _load_aog_config
        from orchestrator.projection import refresh_projection_from_canonical
        from orchestrator.state import Agent

        role = str(claim.get("role") or "")
        actor = str(claim.get("actor") or "")
        agent = Agent(
            id=actor,
            display_name=actor,
            role="dm" if role == "dm" else "player",
        )
        refresh_projection_from_canonical(
            config=_load_aog_config(os.environ.get("GLASS_CONFIG")),
            campaign_root=campaign_root,
            agent=agent,
            turn_number=turn_number,
            projection_root=workspace_root,
        )
    except Exception:
        # Command success should remain authoritative; projection refresh is a
        # same-turn convenience and the next turn rebuilds from canonical state.
        return


def _turn_number_from_claim(claim: dict[str, Any]) -> int | None:
    raw = str(claim.get("turn_id") or "")
    marker = raw.rsplit("t", 1)
    if len(marker) != 2 or not marker[1].isdigit():
        return None
    return int(marker[1])


@contextlib.contextmanager
def _pushd(path: Path) -> Iterator[None]:
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)
