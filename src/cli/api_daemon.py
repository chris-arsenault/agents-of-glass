"""Detached process manager for the local glass API."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json
import os
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request

from .api_grants import DEFAULT_API_URL
from .config import REPO_ROOT


RUNTIME_DIR = Path(os.environ.get("GLASS_API_RUNTIME_DIR", "/tmp/agents-of-glass/glass-api"))
PID_FILE = RUNTIME_DIR / "server.json"
LOG_FILE = RUNTIME_DIR / "server.log"


@dataclass(frozen=True)
class ApiDaemonInfo:
    running: bool
    pid: int | None
    url: str
    config_path: str | None
    log_path: str
    pid_file: str
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def start_daemon(
    *,
    url: str = DEFAULT_API_URL,
    config_path: str | None = None,
) -> ApiDaemonInfo:
    """Start the API daemon unless a healthy one is already running."""

    _ensure_runtime_dir()
    health = _health(url)
    if health is not None:
        pid = _int_or_none(health.get("pid"))
        return _info(
            running=True,
            pid=pid,
            url=url,
            config_path=_string_or_none(health.get("config_path")) or config_path,
            message="already running",
        )

    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8765
    command = [
        sys.executable,
        "-m",
        "cli.main",
        "api",
        "serve",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if config_path:
        command.extend(["--config", config_path])

    env = _daemon_env()
    if config_path:
        env["GLASS_CONFIG"] = config_path
    env["PYTHONPATH"] = _pythonpath_with_src(env.get("PYTHONPATH"))

    with LOG_FILE.open("ab") as log:
        proc = subprocess.Popen(  # noqa: S603 - fixed command, current interpreter.
            command,
            cwd=REPO_ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    try:
        health = _wait_for_health(url, proc)
    except Exception:
        _terminate_pid(proc.pid)
        raise

    pid = _int_or_none(health.get("pid")) or proc.pid
    info = _info(
        running=True,
        pid=pid,
        url=url,
        config_path=_string_or_none(health.get("config_path")) or config_path,
        message="started",
    )
    _write_pid_file(info)
    return info


def stop_daemon(*, url: str = DEFAULT_API_URL) -> ApiDaemonInfo:
    """Stop the known API daemon, if present."""

    stopped: list[int] = []
    for pid in _candidate_pids(url):
        if pid in stopped:
            continue
        if not _pid_matches_api_server(pid):
            continue
        _terminate_pid(pid)
        stopped.append(pid)

    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass

    return _info(
        running=False,
        pid=stopped[-1] if stopped else None,
        url=url,
        config_path=None,
        message="stopped" if stopped else "not running",
    )


def restart_daemon(
    *,
    url: str = DEFAULT_API_URL,
    config_path: str | None = None,
) -> ApiDaemonInfo:
    stop_daemon(url=url)
    return start_daemon(url=url, config_path=config_path)


def status_daemon(*, url: str = DEFAULT_API_URL) -> ApiDaemonInfo:
    health = _health(url)
    if health is not None:
        return _info(
            running=True,
            pid=_int_or_none(health.get("pid")),
            url=url,
            config_path=_string_or_none(health.get("config_path")),
            message="healthy",
        )

    pid_data = _read_pid_file()
    pid = _int_or_none(pid_data.get("pid")) if pid_data else None
    if pid and _pid_matches_api_server(pid):
        return _info(
            running=True,
            pid=pid,
            url=url,
            config_path=_string_or_none(pid_data.get("config_path")),
            message="process exists but health check failed",
        )
    return _info(
        running=False,
        pid=pid,
        url=url,
        config_path=_string_or_none(pid_data.get("config_path")) if pid_data else None,
        message="not running",
    )


def _candidate_pids(url: str) -> list[int]:
    pids: list[int] = []
    health = _health(url)
    if health is not None:
        pid = _int_or_none(health.get("pid"))
        if pid:
            pids.append(pid)
    data = _read_pid_file()
    if data:
        pid = _int_or_none(data.get("pid"))
        if pid:
            pids.append(pid)
    return pids


def _health(url: str) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/v1/health", timeout=1) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _wait_for_health(url: str, proc: subprocess.Popen) -> dict[str, Any]:
    deadline = time.time() + 5
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"glass API daemon exited early with {proc.returncode}; see {LOG_FILE}"
            )
        health = _health(url)
        if health is not None:
            return health
        time.sleep(0.05)
    raise RuntimeError(f"glass API daemon did not become healthy at {url}; see {LOG_FILE}")


def _terminate_pid(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.time() + 5
    while time.time() < deadline:
        if not _pid_exists(pid):
            return
        time.sleep(0.05)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _pid_matches_api_server(pid: int) -> bool:
    cmdline = _proc_cmdline(pid)
    if not cmdline:
        return False
    joined = " ".join(cmdline)
    return "api" in cmdline and "serve" in cmdline and (
        "cli.main" in joined or "glass" in joined
    )


def _proc_cmdline(pid: int) -> list[str]:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return []
    return [part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part]


def _read_pid_file() -> dict[str, Any] | None:
    try:
        payload = json.loads(PID_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_pid_file(info: ApiDaemonInfo) -> None:
    tmp = PID_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(info.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(PID_FILE)
    os.chmod(PID_FILE, 0o600)


def _ensure_runtime_dir() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(RUNTIME_DIR, 0o755)


def _info(
    *,
    running: bool,
    pid: int | None,
    url: str,
    config_path: str | None,
    message: str,
) -> ApiDaemonInfo:
    return ApiDaemonInfo(
        running=running,
        pid=pid,
        url=url,
        config_path=config_path,
        log_path=str(LOG_FILE),
        pid_file=str(PID_FILE),
        message=message,
    )


def _pythonpath_with_src(existing: str | None) -> str:
    src = str(REPO_ROOT / "src")
    if not existing:
        return src
    parts = existing.split(os.pathsep)
    if src in parts:
        return existing
    return os.pathsep.join([src, existing])


def _daemon_env() -> dict[str, str]:
    """Build the detached daemon environment.

    The API daemon is operator-owned and may outlive the command that started
    it. Load local repo `.env` values first, then let the caller's environment
    override them when secrets are injected by `with-cred`.
    """

    from .local_env import dotenv_values

    env: dict[str, str] = {}
    env.update(dotenv_values(REPO_ROOT / ".env"))
    env.update(os.environ)
    return env


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None
