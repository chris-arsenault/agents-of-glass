"""Foreground orchestration loop for `aog campaign bootstrap` / `aog campaign run`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import os
import grp
import pwd
import shutil
import subprocess
import sys
import threading

from cli.api_grants import DEFAULT_API_URL, mint_grant
from cli.api_server import ensure_background_server

from .config import AogConfig, config_env_value
from .context import ContextBuilder, ContextPackage
from .glass_bridge import GlassBridgeError
from . import permissions
from .state import AGENTS_BY_ID, Agent, SessionState, next_agent_for, utc_now
from .store import SessionStore


class TurnFailure(RuntimeError):
    def __init__(self, message: str, failure: dict[str, Any]):
        super().__init__(message)
        self.failure = failure


@dataclass(frozen=True)
class TurnResult:
    turn_id: str
    agent: Agent
    turn_dir: Path
    spawn_cwd: Path
    prose: str
    dry_run: bool
    queued_speaker_entry: dict[str, Any] | None = None


class Orchestrator:
    def __init__(self, config: AogConfig, store: SessionStore):
        self.config = config
        self.store = store
        self.context_builder = ContextBuilder(config, store)

    def prepare_turn(self, state: SessionState) -> ContextPackage:
        agent, turn_meta, _queued_entry = self._resolve_next_agent(state)
        return self.context_builder.build(state, agent, turn_meta=turn_meta)

    def _resolve_next_agent(
        self, state: SessionState
    ) -> tuple[Agent, dict[str, Any], dict[str, Any] | None]:
        """Pick the next agent + any per-turn metadata.

        Peeks at the head of `state["next_speakers"]` if non-empty. Each entry is
        a dict with at least an `agent` key plus optional `rapid_prompt` for
        rapid-response turns. Falls back to round-robin if the queue is empty
        or the queued agent id is unrecognized.
        """
        entry = self._peek_next_speaker_entry(state.campaign)
        if entry:
            agent_id = entry.get("agent")
            if agent_id in AGENTS_BY_ID:
                meta = {k: v for k, v in entry.items() if k != "agent"}
                return AGENTS_BY_ID[agent_id], meta, entry
            return next_agent_for(state), {}, entry
        return next_agent_for(state), {}, None

    def _peek_next_speaker_entry(self, campaign: str) -> dict[str, Any] | None:
        path = self.store.glass_state_path(campaign)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        queue = raw.get("next_speakers")
        if not isinstance(queue, list) or not queue:
            return None
        entry = queue[0]
        if not isinstance(entry, dict):
            entry = {"agent": entry}
        return entry

    def _consume_next_speaker_entry(
        self, campaign: str, expected_entry: dict[str, Any]
    ) -> None:
        path = self.store.glass_state_path(campaign)
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        queue = raw.get("next_speakers")
        if not isinstance(queue, list) or not queue:
            return
        entry = queue[0]
        normalized = entry if isinstance(entry, dict) else {"agent": entry}
        if normalized != expected_entry:
            return
        raw["next_speakers"] = queue[1:]
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        tmp.replace(path)

    def run_loop(
        self,
        state: SessionState,
        *,
        max_turns: int | None,
        dry_run: bool,
        resume_failed: bool = False,
    ) -> int:
        if state.status == "failed" and not resume_failed:
            raise TurnFailure(
                f"Campaign {state.campaign} is failed; use `aog campaign resume`.",
                state.failure or {"reason": "failed"},
            )
        if state.status in {"failed", "interrupted", "running", "paused"} and resume_failed:
            state.mark_ready()
            self.store.save(state)

        turns_run = 0
        try:
            while self._should_continue(state, turns_run, max_turns):
                self._ensure_turn_allowed(state)
                state.mark_running()
                self.store.save(state)
                result = self.run_one_turn(state, dry_run=dry_run)
                self.commit_turn(state, result)
                turns_run += 1
            if state.status == "running":
                state.mark_ready()
                self.store.save(state)
            return turns_run
        except KeyboardInterrupt:
            state.status = "interrupted"
            state.updated_at = utc_now()
            self.store.save(state)
            raise
        except TurnFailure as exc:
            state.mark_failed(exc.failure)
            self.store.save(state)
            self.store.append_audit(state.campaign, {"event": "turn.failed", **exc.failure})
            raise

    def run_one_turn(self, state: SessionState, *, dry_run: bool) -> TurnResult:
        agent, turn_meta, queued_entry = self._resolve_next_agent(state)
        package = self.context_builder.build(state, agent, turn_meta=turn_meta)
        if dry_run:
            prose = (
                f"_Dry run: prepared turn `{package.turn_id}` for {agent.display_name}. "
                f"TURN_START at `{package.turn_start_path}`._"
            )
            return TurnResult(
                turn_id=package.turn_id,
                agent=agent,
                turn_dir=package.turn_dir,
                spawn_cwd=package.spawn_cwd,
                prose=prose,
                dry_run=True,
                queued_speaker_entry=queued_entry,
            )

        return self._invoke_agent(state, agent, package, queued_entry=queued_entry)

    def commit_turn(self, state: SessionState, result: TurnResult) -> None:
        active = state.active_mode
        # The agent's TURN.md (or the dry-run synthetic prose) is what we
        # commit. glass turn append owns the transcript header; we just hand
        # it the markdown file.
        commit_file = result.turn_dir / "COMMIT.md"
        commit_file.write_text(result.prose.rstrip() + "\n", encoding="utf-8")
        try:
            self.store.glass.invoke(
                [
                    "turn",
                    "append",
                    str(commit_file),
                    "--speaker",
                    result.agent.id,
                    "--role",
                    result.agent.role,
                    "--mode",
                    active.mode,
                    "--scene",
                    active.scene_id,
                ],
                role=result.agent.glass_role,
                campaign=state.campaign,
            )
        except GlassBridgeError as exc:
            raise TurnFailure(
                "glass turn append failed.",
                {
                    "reason": "glass_turn_append_failed",
                    "turn_id": result.turn_id,
                    "speaker": result.agent.id,
                    "turn_dir": str(result.turn_dir),
                    "glass_output": exc.result.output,
                },
            ) from exc

        self.store.append_audit(
            state.campaign,
            {
                "event": "turn.committed",
                "turn_id": result.turn_id,
                "turn_number": state.turn_number + 1,
                "speaker": result.agent.id,
                "role": result.agent.role,
                "mode": active.mode,
                "scene_id": active.scene_id,
                "dry_run": result.dry_run,
            },
        )
        self._tick_closing_countdown(state.campaign)
        if result.queued_speaker_entry is not None:
            self._consume_next_speaker_entry(
                state.campaign, result.queued_speaker_entry
            )
        synced = self.store.sync_from_glass(state)
        state.__dict__.update(synced.__dict__)

    def _tick_closing_countdown(self, campaign: str) -> None:
        """Decrement state["scene_closing_turns"] by 1 if set, after a turn.

        The closing countdown is set by `glass scene closing-down --turns N`
        as N+1 (so the DM's setting turn is the first decrement). When the
        value reaches 0 the next TURN_START renders a "Final round" section;
        below 0 indicates an overrun that the methodology flags as a hard
        backstop ("end the scene now even if it feels unfinished").
        """
        path = self.store.glass_state_path(campaign)
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        val = raw.get("scene_closing_turns")
        if val is None:
            return
        raw["scene_closing_turns"] = int(val) - 1
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        tmp.replace(path)

    def _invoke_agent(
        self,
        state: SessionState,
        agent: Agent,
        package: ContextPackage,
        *,
        queued_entry: dict[str, Any] | None,
    ) -> TurnResult:
        # The prompt is intentionally short — the heavy lifting is in
        # TURN_START.md, which the agent reads as its first action.
        turn_start_ref = _agent_path(package.turn_start_path, package.spawn_cwd)
        turn_output_ref = _agent_path(package.turn_output_path, package.spawn_cwd)
        prompt = (
            f"Read {turn_start_ref} and follow its instructions. "
            f"Write your final public prose to {turn_output_ref} and exit."
        )

        # If the agent has a dedicated Unix user (provisioning is set up),
        # sudo into that user. The DM runs as the operator (None).
        target_user = permissions.player_user_for(agent.id)
        glass_api_url: str | None = None
        glass_api_grant: str | None = None
        glass_api_grant_file: Path | None = None
        if target_user is not None:
            glass_api_url = ensure_background_server(
                url=os.environ.get("GLASS_API_URL", DEFAULT_API_URL),
                config_path=config_env_value(self.config),
            )
            glass_api_grant = mint_grant(
                self.config.campaigns_dir,
                campaign_id=state.campaign,
                role=agent.role,
                actor=agent.id,
                glass_role=agent.glass_role,
                turn_id=package.turn_id,
                ttl_seconds=max(self.config.claude.turn_timeout_seconds + 600, 3600),
            )
            glass_api_grant_file = _write_player_glass_api_file(
                target_user=target_user,
                api_url=glass_api_url,
                grant=glass_api_grant,
                campaign_id=state.campaign,
                turn_id=package.turn_id,
            )

        command: list[str] = []
        preserved_env: list[str] = []
        if target_user is not None:
            command.extend([
                "sudo",
                "-n",
                "-u", target_user,
                "--",
                "env",
                f"PATH={_player_path()}",
            ])

        command.append("claude")
        if self.config.claude.model:
            command.extend(["--model", self.config.claude.model])
        claude_debug_path = package.turn_dir / "claude-debug.log"
        claude_debug_ref = _agent_path(claude_debug_path, package.spawn_cwd)
        command.extend([
            "-p",
            prompt,
            "--dangerously-skip-permissions",
            "--debug-file",
            claude_debug_ref,
        ])

        env = os.environ.copy()
        env.update(
            {
                "GLASS_ROLE": agent.glass_role,
                "GLASS_CAMPAIGN_ID": state.campaign,
                "GLASS_CONFIG": config_env_value(self.config),
                "GLASS_TURN_ID": package.turn_id,
                "AOG_TURN_START": str(package.turn_start_path),
                "AOG_TURN_OUTPUT": str(package.turn_output_path),
            }
        )
        if target_user is not None:
            env["PATH"] = _player_path()
            env["GLASS_API_URL"] = glass_api_url or DEFAULT_API_URL
            if glass_api_grant_file is not None:
                env["GLASS_API_GRANT_FILE"] = str(glass_api_grant_file)

        prefix = f"[{agent.id}] "
        print(
            f"\n--- {agent.display_name} (mode: {state.active_mode.mode}, "
            f"turn {package.turn_number}, timeout {self.config.claude.turn_timeout_seconds}s) ---",
            flush=True,
        )

        debug_path = package.turn_dir / "agent-debug.json"
        debug_payload = _agent_debug_payload(
            state=state,
            agent=agent,
            package=package,
            command=command,
            env=env,
            target_user=target_user,
            preserved_env=preserved_env,
            timeout_seconds=self.config.claude.turn_timeout_seconds,
            phase="before_spawn",
            claude_debug_path=claude_debug_path,
        )
        _write_json(debug_path, debug_payload)

        try:
            stdout_text, stderr_text, returncode, timed_out = _stream_subprocess(
                command,
                cwd=package.spawn_cwd,
                env=env,
                timeout=self.config.claude.turn_timeout_seconds,
                stdout_prefix=prefix,
                stderr_prefix=prefix + "(err) ",
            )
        except FileNotFoundError as exc:
            debug_payload["phase"] = "spawn_failed"
            debug_payload["exception"] = repr(exc)
            debug_payload["resolved_executable"] = shutil.which(command[0])
            debug_payload["paths_after"] = _turn_path_debug(package)
            _write_json(debug_path, debug_payload)
            raise TurnFailure(
                "Claude CLI was not found on PATH.",
                {
                    "reason": "claude_not_found",
                    "turn_id": package.turn_id,
                    "speaker": agent.id,
                    "turn_dir": str(package.turn_dir),
                    "debug_path": str(debug_path),
                },
            ) from exc

        _write_process_capture(package.turn_dir, stdout_text, stderr_text)
        debug_payload.update(
            {
                "phase": "after_subprocess",
                "returncode": returncode,
                "timed_out": timed_out,
                "stdout_bytes": len(stdout_text.encode("utf-8")),
                "stderr_bytes": len(stderr_text.encode("utf-8")),
                "stdout_preview": _preview(stdout_text),
                "stderr_preview": _preview(stderr_text),
                "paths_after": _turn_path_debug(package),
            }
        )
        _write_json(debug_path, debug_payload)

        if timed_out:
            raise TurnFailure(
                f"Turn {package.turn_id} timed out.",
                {
                    "reason": "timeout",
                    "turn_id": package.turn_id,
                    "speaker": agent.id,
                    "turn_dir": str(package.turn_dir),
                    "timeout_seconds": self.config.claude.turn_timeout_seconds,
                    "debug_path": str(debug_path),
                    "stdout_bytes": debug_payload["stdout_bytes"],
                    "stderr_bytes": debug_payload["stderr_bytes"],
                },
            )

        if returncode != 0:
            raise TurnFailure(
                f"Turn {package.turn_id} exited with {returncode}.",
                {
                    "reason": "nonzero_exit",
                    "turn_id": package.turn_id,
                    "speaker": agent.id,
                    "turn_dir": str(package.turn_dir),
                    "exit_code": returncode,
                    "debug_path": str(debug_path),
                    "stdout_bytes": debug_payload["stdout_bytes"],
                    "stderr_bytes": debug_payload["stderr_bytes"],
                    "stderr_preview": debug_payload["stderr_preview"],
                },
            )

        prose = _collect_prose(package.turn_output_path, stdout_text)
        if not prose:
            output_debug = _path_debug(package.turn_output_path)
            raise TurnFailure(
                f"Turn {package.turn_id} produced no prose.",
                {
                    "reason": "empty_turn",
                    "turn_id": package.turn_id,
                    "speaker": agent.id,
                    "turn_dir": str(package.turn_dir),
                    "debug_path": str(debug_path),
                    "exit_code": returncode,
                    "stdout_bytes": debug_payload["stdout_bytes"],
                    "stderr_bytes": debug_payload["stderr_bytes"],
                    "stdout_preview": debug_payload["stdout_preview"],
                    "stderr_preview": debug_payload["stderr_preview"],
                    "turn_output_path": str(package.turn_output_path),
                    "turn_output": output_debug,
                },
            )
        return TurnResult(
            turn_id=package.turn_id,
            agent=agent,
            turn_dir=package.turn_dir,
            spawn_cwd=package.spawn_cwd,
            prose=prose,
            dry_run=False,
            queued_speaker_entry=queued_entry,
        )

    def _should_continue(
        self, state: SessionState, turns_run: int, max_turns: int | None
    ) -> bool:
        if state.turn_number >= self.config.caps.session_max_turns:
            state.mark_paused("session turn cap reached")
            self.store.save(state)
            return False
        if max_turns is not None and turns_run >= max_turns:
            return False
        if not state.has_active_mode:
            # The DM (or the previous turn) ended the active mode and didn't
            # push a new one — the agents are signaling "we're done." Stop.
            state.status = "complete"
            state.updated_at = utc_now()
            self.store.save(state)
            return False
        return True

    def _ensure_turn_allowed(self, state: SessionState) -> None:
        active = state.active_mode
        if active.turn_budget_remaining is not None and active.turn_budget_remaining <= 0:
            state.mark_paused(f"mode budget exhausted for {active.mode}:{active.scene_id}")
            self.store.save(state)
            raise TurnFailure(
                "Active mode budget is exhausted.",
                {
                    "reason": "mode_budget_exhausted",
                    "mode": active.mode,
                    "scene_id": active.scene_id,
                },
            )


def _stream_subprocess(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
    stdout_prefix: str,
    stderr_prefix: str,
) -> tuple[str, str, int, bool]:
    """Run a subprocess, streaming stdout/stderr to the operator's terminal
    line-by-line (with a prefix per agent), while also capturing the full
    text for audit. Enforces a wall-clock timeout.

    Returns (stdout_text, stderr_text, returncode, timed_out).
    """
    proc = subprocess.Popen(  # noqa: S603 — command is built deliberately above
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []

    def pump(stream, sink, prefix, target_io):
        try:
            for line in iter(stream.readline, ""):
                sink.append(line)
                target_io.write(prefix + line)
                target_io.flush()
        finally:
            stream.close()

    out_thread = threading.Thread(
        target=pump,
        args=(proc.stdout, stdout_chunks, stdout_prefix, sys.stdout),
        daemon=True,
    )
    err_thread = threading.Thread(
        target=pump,
        args=(proc.stderr, stderr_chunks, stderr_prefix, sys.stderr),
        daemon=True,
    )
    out_thread.start()
    err_thread.start()

    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass

    # Drain reader threads (they exit when streams close on process death).
    out_thread.join(timeout=5)
    err_thread.join(timeout=5)

    return (
        "".join(stdout_chunks),
        "".join(stderr_chunks),
        proc.returncode if proc.returncode is not None else -1,
        timed_out,
    )


def _agent_debug_payload(
    *,
    state: SessionState,
    agent: Agent,
    package: ContextPackage,
    command: list[str],
    env: dict[str, str],
    target_user: str | None,
    preserved_env: list[str],
    timeout_seconds: int,
    phase: str,
    claude_debug_path: Path,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "turn_id": package.turn_id,
        "turn_number": package.turn_number,
        "campaign": state.campaign,
        "mode": state.active_mode.mode,
        "scene_id": state.active_mode.scene_id,
        "agent": {
            "id": agent.id,
            "role": agent.role,
            "display_name": agent.display_name,
            "glass_role": agent.glass_role,
            "target_user": target_user,
        },
        "process": {
            "cwd": str(package.spawn_cwd),
            "timeout_seconds": timeout_seconds,
            "command": command,
            "resolved_executable": shutil.which(command[0]),
            "resolved_claude": shutil.which("claude", path=env.get("PATH")),
            "operator_uid": os.getuid(),
            "operator_euid": os.geteuid(),
            "target_home": _home_for_user(target_user) if target_user else None,
            "claude_debug_path": str(claude_debug_path),
        },
        "env": _env_debug(env, preserved_env),
        "paths_before": _turn_path_debug(package),
    }


def _env_debug(env: dict[str, str], preserved_env: list[str]) -> dict[str, Any]:
    keys = sorted(
        set(preserved_env)
        | {
            "HOME",
            "PATH",
            "USER",
            "LOGNAME",
            "SHELL",
            "TERM",
            "GLASS_ROLE",
            "GLASS_CAMPAIGN_ID",
            "GLASS_CONFIG",
            "GLASS_TURN_ID",
            "GLASS_API_URL",
            "GLASS_API_GRANT",
            "GLASS_API_GRANT_FILE",
            "AOG_TURN_START",
            "AOG_TURN_OUTPUT",
        }
    )
    return {
        "preserve_env": preserved_env,
        "values": {key: _env_value_debug(key, env.get(key)) for key in keys},
    }


def _env_value_debug(key: str, value: str | None) -> str | None:
    if value is None:
        return None
    secret_markers = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "GRANT")
    if any(marker in key.upper() for marker in secret_markers):
        return "<set>" if value else "<empty>"
    return value


def _turn_path_debug(package: ContextPackage) -> dict[str, Any]:
    return {
        "spawn_cwd": _path_debug(package.spawn_cwd),
        "turn_dir": _path_debug(package.turn_dir),
        "turn_start_path": _path_debug(package.turn_start_path),
        "turn_output_path": _path_debug(package.turn_output_path),
        "agent_stdout_path": _path_debug(package.turn_dir / "agent-stdout.txt"),
        "agent_stderr_path": _path_debug(package.turn_dir / "agent-stderr.txt"),
        "claude_debug_path": _path_debug(package.turn_dir / "claude-debug.log"),
    }


def _path_debug(path: Path) -> dict[str, Any]:
    try:
        st = path.stat()
    except FileNotFoundError:
        return {"path": str(path), "exists": False}
    except OSError as exc:
        return {"path": str(path), "exists": None, "error": repr(exc)}

    return {
        "path": str(path),
        "exists": True,
        "is_dir": path.is_dir(),
        "is_file": path.is_file(),
        "size": st.st_size,
        "mode": oct(st.st_mode & 0o7777),
        "uid": st.st_uid,
        "user": _name_for_uid(st.st_uid),
        "gid": st.st_gid,
        "group": _name_for_gid(st.st_gid),
    }


def _name_for_uid(uid: int) -> str | None:
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return None


def _name_for_gid(gid: int) -> str | None:
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return None


def _home_for_user(user: str) -> str | None:
    try:
        return pwd.getpwnam(user).pw_dir
    except KeyError:
        return None


def _player_path() -> str:
    return "/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"


def _write_player_glass_api_file(
    *,
    target_user: str,
    api_url: str,
    grant: str,
    campaign_id: str,
    turn_id: str,
) -> Path:
    runtime_dir = Path("/tmp/agents-of-glass/glass-api")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(runtime_dir, 0o755)
    target = runtime_dir / f"{target_user}.json"
    tmp = runtime_dir / f".{target_user}.{os.getpid()}.tmp"
    payload = {
        "api_url": api_url,
        "grant": grant,
        "campaign_id": campaign_id,
        "turn_id": turn_id,
    }
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    try:
        user_record = pwd.getpwnam(target_user)
        group_name = _name_for_gid(user_record.pw_gid) or target_user
        subprocess.run(
            [
                "sudo",
                "-n",
                "install",
                "-o",
                target_user,
                "-g",
                group_name,
                "-m",
                "0600",
                str(tmp),
                str(target),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (KeyError, subprocess.CalledProcessError, OSError) as exc:
        raise TurnFailure(
            "failed to install player glass API grant file.",
            {
                "reason": "glass_api_grant_file_failed",
                "turn_id": turn_id,
                "target_user": target_user,
                "grant_file": str(target),
                "error": repr(exc),
            },
        ) from exc
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
    return target


def _preview(text: str, *, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... <truncated {len(text) - limit} chars>"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _agent_path(path: Path, spawn_cwd: Path) -> str:
    try:
        return str(path.relative_to(spawn_cwd))
    except ValueError:
        return str(path)


def _collect_prose(turn_output_path: Path, stdout: str | None) -> str:
    """Read the agent's TURN.md (preferred) or fall back to stdout."""
    if turn_output_path.exists():
        text = turn_output_path.read_text(encoding="utf-8").strip()
        if text:
            return text
    return (stdout or "").strip()


def _write_process_capture(
    turn_dir: Path,
    stdout: str | bytes | None,
    stderr: str | bytes | None,
) -> None:
    turn_dir.mkdir(parents=True, exist_ok=True)
    _write_capture_file(turn_dir / "agent-stdout.txt", stdout)
    _write_capture_file(turn_dir / "agent-stderr.txt", stderr)


def _write_capture_file(path: Path, value: str | bytes | None) -> None:
    if value is None:
        text = ""
    elif isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    path.write_text(text, encoding="utf-8")
