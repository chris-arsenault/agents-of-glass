"""Foreground orchestration loop for `aog session run`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os
import shutil
import subprocess

from .config import AogConfig, config_env_value
from .context import ContextBuilder, ContextPackage
from .glass_bridge import GlassBridgeError
from .state import Agent, SessionState, next_agent_for, utc_now
from .store import SessionStore


class TurnFailure(RuntimeError):
    def __init__(self, message: str, failure: dict[str, Any]):
        super().__init__(message)
        self.failure = failure


@dataclass(frozen=True)
class TurnResult:
    turn_id: str
    agent: Agent
    cwd: Path
    prose: str
    dry_run: bool


class Orchestrator:
    def __init__(self, config: AogConfig, store: SessionStore):
        self.config = config
        self.store = store
        self.context_builder = ContextBuilder(config, store)

    def prepare_turn(self, state: SessionState) -> ContextPackage:
        agent = next_agent_for(state)
        return self.context_builder.build(state, agent)

    def run_loop(
        self,
        state: SessionState,
        *,
        max_turns: int | None,
        dry_run: bool,
        keep_cwd: bool,
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
                if not keep_cwd and not dry_run:
                    shutil.rmtree(result.cwd, ignore_errors=True)
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
        agent = next_agent_for(state)
        package = self.context_builder.build(state, agent)
        if dry_run:
            prose = (
                f"_Dry run: prepared turn `{package.turn_id}` for {agent.display_name}. "
                f"Context package: `{package.cwd}`._"
            )
            return TurnResult(package.turn_id, agent, package.cwd, prose, dry_run=True)

        return self._invoke_agent(state, agent, package)

    def commit_turn(self, state: SessionState, result: TurnResult) -> None:
        active = state.active_mode
        commit_file = result.cwd / "COMMIT.md"
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
                    "cwd": str(result.cwd),
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
        prompt = "Read TURN_START.md and take your turn. Write final public prose to TURN.md."
        command = ["claude"]
        if self.config.claude.model:
            command.extend(["--model", self.config.claude.model])
        command.extend(["-p", prompt, "--dangerously-skip-permissions"])

        env = os.environ.copy()
        env.update(
            {
                "GLASS_ROLE": agent.glass_role,
                "GLASS_SESSION_ID": state.session_id,
                "GLASS_CONFIG": config_env_value(self.config),
                "GLASS_TURN_ID": package.turn_id,
                "AOG_SESSION_DIR": str(self.store.session_dir(state.session_id)),
            }
        )

        try:
            completed = subprocess.run(
                command,
                cwd=package.cwd,
                env=env,
                timeout=self.config.claude.turn_timeout_seconds,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise TurnFailure(
                "Claude CLI was not found on PATH.",
                {
                    "reason": "claude_not_found",
                    "turn_id": package.turn_id,
                    "speaker": agent.id,
                    "cwd": str(package.cwd),
                },
            ) from exc
        except subprocess.TimeoutExpired as exc:
            _write_process_capture(package.cwd, exc.stdout, exc.stderr)
            raise TurnFailure(
                f"Turn {package.turn_id} timed out.",
                {
                    "reason": "timeout",
                    "turn_id": package.turn_id,
                    "speaker": agent.id,
                    "cwd": str(package.cwd),
                    "timeout_seconds": self.config.claude.turn_timeout_seconds,
                },
            ) from exc

        _write_process_capture(package.cwd, completed.stdout, completed.stderr)
        if completed.returncode != 0:
            raise TurnFailure(
                f"Turn {package.turn_id} exited with {completed.returncode}.",
                {
                    "reason": "nonzero_exit",
                    "turn_id": package.turn_id,
                    "speaker": agent.id,
                    "cwd": str(package.cwd),
                    "exit_code": completed.returncode,
                },
            )

        prose = _collect_prose(package.cwd, completed.stdout)
        if not prose:
            raise TurnFailure(
                f"Turn {package.turn_id} produced no prose.",
                {
                    "reason": "empty_turn",
                    "turn_id": package.turn_id,
                    "speaker": agent.id,
                    "cwd": str(package.cwd),
                },
            )
        return TurnResult(package.turn_id, agent, package.cwd, prose, dry_run=False)

    def _should_continue(
        self, state: SessionState, turns_run: int, max_turns: int | None
    ) -> bool:
        if state.turn_number >= self.config.caps.session_max_turns:
            state.mark_paused("session turn cap reached")
            self.store.save(state)
            return False
        if max_turns is not None and turns_run >= max_turns:
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


def _collect_prose(cwd: Path, stdout: str | None) -> str:
    turn_file = cwd / "TURN.md"
    if turn_file.exists():
        text = turn_file.read_text(encoding="utf-8").strip()
        if text:
            return text
    return (stdout or "").strip()


def _write_process_capture(
    cwd: Path,
    stdout: str | bytes | None,
    stderr: str | bytes | None,
) -> None:
    cwd.mkdir(parents=True, exist_ok=True)
    _write_capture_file(cwd / "agent-stdout.txt", stdout)
    _write_capture_file(cwd / "agent-stderr.txt", stderr)


def _write_capture_file(path: Path, value: str | bytes | None) -> None:
    if value is None:
        text = ""
    elif isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    path.write_text(text, encoding="utf-8")
