"""Foreground orchestration loop for `aog campaign bootstrap` / `aog session run`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import os
import subprocess
import sys
import threading

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


class Orchestrator:
    def __init__(self, config: AogConfig, store: SessionStore):
        self.config = config
        self.store = store
        self.context_builder = ContextBuilder(config, store)

    def prepare_turn(self, state: SessionState) -> ContextPackage:
        agent = self._resolve_next_agent(state)
        return self.context_builder.build(state, agent)

    def _resolve_next_agent(self, state: SessionState) -> Agent:
        """Pick the next agent, consuming a `next_speaker` override if set.

        Override is one-shot: read it, clear it, then return the override
        agent. Falls back to the round-robin order from `next_agent_for` if
        no override is pending or the override id is invalid.
        """
        override = self._consume_handoff_override(state.session_id)
        if override and override in AGENTS_BY_ID:
            return AGENTS_BY_ID[override]
        return next_agent_for(state)

    def _consume_handoff_override(self, session_id: str) -> str | None:
        path = self.store.glass_state_path(session_id)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        override = raw.get("next_speaker")
        if not override:
            return None
        raw["next_speaker"] = None
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)
        return override

    def run_loop(
        self,
        state: SessionState,
        *,
        max_turns: int | None,
        dry_run: bool,
        keep_cwd: bool = True,  # legacy flag name; per-turn dirs always preserved now
        resume_failed: bool = False,
    ) -> int:
        if state.status == "failed" and not resume_failed:
            raise TurnFailure(
                f"Session {state.session_id} is failed; use `aog session resume`.",
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
            self.store.append_audit(state.session_id, {"event": "turn.failed", **exc.failure})
            raise

    def run_one_turn(self, state: SessionState, *, dry_run: bool) -> TurnResult:
        agent = self._resolve_next_agent(state)
        package = self.context_builder.build(state, agent)
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
            )

        return self._invoke_agent(state, agent, package)

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
                session_id=state.session_id,
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
            state.session_id,
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
        synced = self.store.sync_from_glass(state)
        state.__dict__.update(synced.__dict__)

    def _invoke_agent(
        self, state: SessionState, agent: Agent, package: ContextPackage
    ) -> TurnResult:
        # The prompt is intentionally short — the heavy lifting is in
        # TURN_START.md, which the agent reads as its first action.
        prompt = (
            f"Read {package.turn_start_path} and follow its instructions. "
            f"Write your final public prose to {package.turn_output_path} and exit."
        )

        # If the agent has a dedicated Unix user (provisioning is set up),
        # sudo into that user. The DM runs as the operator (None).
        target_user = permissions.player_user_for(agent.id)

        command: list[str] = []
        if target_user is not None:
            command.extend([
                "sudo",
                "-n",
                "-u", target_user,
                "--preserve-env=ANTHROPIC_API_KEY,ANTHROPIC_BASE_URL,CLAUDE_API_KEY,GLASS_ROLE,GLASS_SESSION_ID,GLASS_CAMPAIGN_ID,GLASS_CONFIG,GLASS_TURN_ID,AOG_SESSION_DIR,AOG_TURN_START,AOG_TURN_OUTPUT,AOG_PG_PASSWORD,PGPASSWORD,PGHOST,PGPORT,PGDATABASE,PGUSER,AOG_FALKOR_PASSWORD,REDIS_PASSWORD,AOG_FALKOR_HOST,AOG_FALKOR_PORT,AOG_FALKOR_GRAPH,PATH",
                "--",
            ])

        command.append("claude")
        if self.config.claude.model:
            command.extend(["--model", self.config.claude.model])
        command.extend(["-p", prompt, "--dangerously-skip-permissions"])

        env = os.environ.copy()
        env.update(
            {
                "GLASS_ROLE": agent.glass_role,
                "GLASS_SESSION_ID": state.session_id,
                "GLASS_CAMPAIGN_ID": state.campaign,
                "GLASS_CONFIG": config_env_value(self.config),
                "GLASS_TURN_ID": package.turn_id,
                "AOG_SESSION_DIR": str(self.store.session_dir(state.session_id)),
                "AOG_TURN_START": str(package.turn_start_path),
                "AOG_TURN_OUTPUT": str(package.turn_output_path),
            }
        )

        prefix = f"[{agent.id}] "
        print(
            f"\n--- {agent.display_name} (mode: {state.active_mode.mode}, "
            f"turn {package.turn_number}, timeout {self.config.claude.turn_timeout_seconds}s) ---",
            flush=True,
        )

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
            raise TurnFailure(
                "Claude CLI was not found on PATH.",
                {
                    "reason": "claude_not_found",
                    "turn_id": package.turn_id,
                    "speaker": agent.id,
                    "turn_dir": str(package.turn_dir),
                },
            ) from exc

        _write_process_capture(package.turn_dir, stdout_text, stderr_text)

        if timed_out:
            raise TurnFailure(
                f"Turn {package.turn_id} timed out.",
                {
                    "reason": "timeout",
                    "turn_id": package.turn_id,
                    "speaker": agent.id,
                    "turn_dir": str(package.turn_dir),
                    "timeout_seconds": self.config.claude.turn_timeout_seconds,
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
                },
            )

        prose = _collect_prose(package.turn_output_path, stdout_text)
        if not prose:
            raise TurnFailure(
                f"Turn {package.turn_id} produced no prose.",
                {
                    "reason": "empty_turn",
                    "turn_id": package.turn_id,
                    "speaker": agent.id,
                    "turn_dir": str(package.turn_dir),
                },
            )
        return TurnResult(
            turn_id=package.turn_id,
            agent=agent,
            turn_dir=package.turn_dir,
            spawn_cwd=package.spawn_cwd,
            prose=prose,
            dry_run=False,
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
