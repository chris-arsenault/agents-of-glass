"""Detached local web UI process manager for the operator CLI."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request

from cli.web_api_daemon import start_daemon as start_web_api_daemon
from cli.web_api_daemon import stop_daemon as stop_web_api_daemon
from cli.web_api_server import DEFAULT_WEB_API_URL


RUNTIME_DIR = Path(os.environ.get("AOG_WEBUI_RUNTIME_DIR", "/tmp/agents-of-glass/webui"))
PID_FILE = RUNTIME_DIR / "server.json"
LOG_FILE = RUNTIME_DIR / "server.log"
DEFAULT_WEBUI_URL = "http://127.0.0.1:26000"


@dataclass(frozen=True)
class WebuiDaemonInfo:
    running: bool
    pid: int | None
    url: str
    api_url: str
    log_path: str
    pid_file: str
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def start_webui(
    *,
    repo_root: Path,
    config_path: str | None,
    url: str = DEFAULT_WEBUI_URL,
    web_api_url: str = DEFAULT_WEB_API_URL,
    host: str = "0.0.0.0",
    api_host: str = "0.0.0.0",
    clean_stale: bool = True,
) -> WebuiDaemonInfo:
    """Start the local UI unless a healthy one is already running."""

    _ensure_runtime_dir()
    if clean_stale:
        cleanup_stale_frontends(repo_root=repo_root, keep_port=_port_from_url(url, 26000))

    start_web_api_daemon(
        url=web_api_url,
        config_path=config_path,
        bind_host=api_host,
    )

    if _health(url):
        pid = _managed_pid()
        return _info(
            running=True,
            pid=pid,
            url=url,
            api_url=web_api_url,
            message="already running",
        )

    script = repo_root / "scripts" / "run-webui-local.sh"
    if not script.exists():
        raise RuntimeError(f"web UI helper not found: {script}")

    env = dict(os.environ)
    env.update(
        {
            "WEB_API_HOST": api_host,
            "WEB_API_PORT": str(_port_from_url(web_api_url, 26002)),
            "WEB_API_HEALTH_URL": web_api_url,
            "API_BASE_URL": _browser_api_base_url(web_api_url),
            "API_CONFIG": config_path or "",
            "FRONTEND_HOST": host,
            "FRONTEND_PORT": str(_port_from_url(url, 26000)),
            "START_WEB_API": "0",
            "PYTHONPATH": _pythonpath_with_src(repo_root, env.get("PYTHONPATH")),
        }
    )

    with LOG_FILE.open("ab") as log:
        proc = subprocess.Popen(  # noqa: S603 - fixed repo-local helper.
            [str(script)],
            cwd=repo_root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    try:
        _wait_for_health(url, proc)
    except Exception:
        _terminate_process_group(proc.pid)
        raise

    info = _info(
        running=True,
        pid=proc.pid,
        url=url,
        api_url=web_api_url,
        message="started",
    )
    _write_pid_file(info)
    return info


def stop_webui(
    *,
    repo_root: Path,
    url: str = DEFAULT_WEBUI_URL,
    web_api_url: str = DEFAULT_WEB_API_URL,
    clean_stale: bool = True,
) -> WebuiDaemonInfo:
    """Stop the managed local UI process and optional repo-local strays."""

    stopped: list[int] = []
    data = _read_pid_file()
    pid = _int_or_none(data.get("pid")) if data else None
    if pid and _pid_exists(pid):
        _terminate_process_group(pid)
        stopped.append(pid)

    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass

    if clean_stale:
        stopped.extend(
            cleanup_stale_frontends(repo_root=repo_root, keep_port=None)
        )

    stop_web_api_daemon(url=web_api_url)

    return _info(
        running=False,
        pid=stopped[-1] if stopped else None,
        url=url,
        api_url=web_api_url,
        message="stopped" if stopped else "not running",
    )


def restart_webui(
    *,
    repo_root: Path,
    config_path: str | None,
    url: str = DEFAULT_WEBUI_URL,
    web_api_url: str = DEFAULT_WEB_API_URL,
    host: str = "0.0.0.0",
    api_host: str = "0.0.0.0",
) -> WebuiDaemonInfo:
    stop_webui(
        repo_root=repo_root,
        url=url,
        web_api_url=web_api_url,
    )
    return start_webui(
        repo_root=repo_root,
        config_path=config_path,
        url=url,
        web_api_url=web_api_url,
        host=host,
        api_host=api_host,
        clean_stale=True,
    )


def status_webui(
    *,
    repo_root: Path,
    url: str = DEFAULT_WEBUI_URL,
    web_api_url: str = DEFAULT_WEB_API_URL,
) -> WebuiDaemonInfo:
    data = _read_pid_file()
    pid = _int_or_none(data.get("pid")) if data else None
    if _health(url):
        return _info(
            running=True,
            pid=pid if pid and _pid_exists(pid) else _frontend_pid(repo_root, url),
            url=url,
            api_url=web_api_url,
            message="healthy",
        )
    return _info(
        running=False,
        pid=pid,
        url=url,
        api_url=web_api_url,
        message="not running",
    )


def cleanup_stale_frontends(*, repo_root: Path, keep_port: int | None) -> list[int]:
    """Terminate repo-local Vite/npm dev processes except the intended port."""

    stopped: list[int] = []
    frontend_dir = (repo_root / "frontend").resolve()
    candidates: set[int] = set()
    for pid in _all_pids():
        cmdline = _proc_cmdline(pid)
        if not cmdline:
            continue
        if not _is_frontend_dev_process(pid, cmdline, frontend_dir):
            continue
        if keep_port is not None and _cmdline_uses_port(cmdline, keep_port):
            continue
        candidates.add(pid)

    # Children first keeps parent process managers from respawning while their
    # direct Vite child is still alive.
    for pid in sorted(candidates, reverse=True):
        if not _pid_exists(pid):
            continue
        _terminate_pid(pid)
        stopped.append(pid)
    return stopped


def _frontend_pid(repo_root: Path, url: str) -> int | None:
    keep_port = _port_from_url(url, 26000)
    frontend_dir = (repo_root / "frontend").resolve()
    for pid in _all_pids():
        cmdline = _proc_cmdline(pid)
        if (
            cmdline
            and _is_frontend_dev_process(pid, cmdline, frontend_dir)
            and _cmdline_uses_port(cmdline, keep_port)
        ):
            return pid
    return None


def _is_frontend_dev_process(pid: int, cmdline: list[str], frontend_dir: Path) -> bool:
    joined = " ".join(cmdline)
    if "vite" not in joined and "pnpm dev" not in joined and "npm run dev" not in joined:
        return False
    cwd = _proc_cwd(pid)
    if cwd == frontend_dir:
        return True
    return str(frontend_dir) in cmdline or str(frontend_dir) in joined


def _cmdline_uses_port(cmdline: list[str], port: int) -> bool:
    expected = str(port)
    for index, part in enumerate(cmdline):
        if part == "--port" and index + 1 < len(cmdline) and cmdline[index + 1] == expected:
            return True
        if part == f"--port={expected}":
            return True
    return False


def _health(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            return 200 <= response.status < 500
    except (OSError, urllib.error.URLError):
        return False


def _wait_for_health(url: str, proc: subprocess.Popen) -> None:
    deadline = time.time() + 15
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"web UI process exited early with {proc.returncode}; see {LOG_FILE}"
            )
        if _health(url):
            return
        time.sleep(0.1)
    raise RuntimeError(f"web UI did not become healthy at {url}; see {LOG_FILE}")


def _terminate_process_group(pid: int) -> None:
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.time() + 5
    while time.time() < deadline:
        if not _pid_exists(pid):
            return
        time.sleep(0.05)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return


def _terminate_pid(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.time() + 3
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


def _proc_cmdline(pid: int) -> list[str]:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return []
    return [part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part]


def _proc_cwd(pid: int) -> Path | None:
    try:
        return Path(f"/proc/{pid}/cwd").resolve()
    except OSError:
        return None


def _all_pids() -> list[int]:
    proc = Path("/proc")
    if not proc.exists():
        return []
    out: list[int] = []
    for child in proc.iterdir():
        if child.name.isdigit():
            out.append(int(child.name))
    return out


def _read_pid_file() -> dict[str, Any] | None:
    try:
        payload = json.loads(PID_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_pid_file(info: WebuiDaemonInfo) -> None:
    tmp = PID_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(info.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(PID_FILE)
    os.chmod(PID_FILE, 0o600)


def _managed_pid() -> int | None:
    data = _read_pid_file()
    pid = _int_or_none(data.get("pid")) if data else None
    return pid if pid and _pid_exists(pid) else None


def _ensure_runtime_dir() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(RUNTIME_DIR, 0o755)


def _info(
    *,
    running: bool,
    pid: int | None,
    url: str,
    api_url: str,
    message: str,
) -> WebuiDaemonInfo:
    return WebuiDaemonInfo(
        running=running,
        pid=pid,
        url=url,
        api_url=api_url,
        log_path=str(LOG_FILE),
        pid_file=str(PID_FILE),
        message=message,
    )


def _port_from_url(url: str, default: int) -> int:
    try:
        from urllib.parse import urlparse

        return int(urlparse(url).port or default)
    except (TypeError, ValueError):
        return default


def _pythonpath_with_src(repo_root: Path, existing: str | None) -> str:
    src = str(repo_root / "src")
    if not existing:
        return src
    parts = existing.split(os.pathsep)
    if src in parts:
        return existing
    return os.pathsep.join([src, existing])


def _browser_api_base_url(web_api_url: str) -> str:
    explicit = os.environ.get("AOG_WEB_API_PUBLIC_URL")
    if explicit is not None:
        return explicit
    try:
        from urllib.parse import urlparse

        host = urlparse(web_api_url).hostname or ""
    except (TypeError, ValueError):
        return web_api_url
    if host in {"127.0.0.1", "localhost", "0.0.0.0", "::1"}:
        return ""
    return web_api_url


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
