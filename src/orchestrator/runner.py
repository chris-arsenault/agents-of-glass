"""Foreground orchestration loop for `aog campaign bootstrap` / `aog campaign run`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import os
import grp
import pwd
import re
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
from .projection import copy_turn_artifacts_to_canonical
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
    action_order_entry: dict[str, Any] | None = None


_GLASS_COMMAND_LINE_RE = re.compile(
    r"^\s*>?\s*glass\s+"
    r"(roll|character|clock|summary|entity|search|tarot|lore|note|arc|"
    r"scene|table|mode|turn|thread|msg|turns)\b"
)


class Orchestrator:
    def __init__(self, config: AogConfig, store: SessionStore):
        self.config = config
        self.store = store
        self.context_builder = ContextBuilder(config, store)

    def prepare_turn(self, state: SessionState) -> ContextPackage:
        agent, turn_meta, _queued_entry, _action_entry = self._resolve_next_agent(state)
        return self.context_builder.build(state, agent, turn_meta=turn_meta)

    def _resolve_next_agent(
        self, state: SessionState
    ) -> tuple[
        Agent,
        dict[str, Any],
        dict[str, Any] | None,
        dict[str, Any] | None,
    ]:
        """Pick the next agent + any per-turn metadata.

        Peeks at the head of `state["next_speakers"]` if non-empty. Each entry is
        a dict with at least an `agent` key plus optional `rapid_prompt` for
        rapid-response turns. Falls back to action-scene initiative order,
        then round-robin if no queue/order applies.
        """
        entry = self._peek_next_speaker_entry(state.campaign)
        if entry:
            agent_id = entry.get("agent")
            if agent_id in AGENTS_BY_ID:
                meta = {k: v for k, v in entry.items() if k != "agent"}
                return AGENTS_BY_ID[agent_id], meta, entry, None
            return next_agent_for(state), {}, entry, None
        action_entry = self._peek_action_order_entry(state)
        if action_entry:
            return (
                AGENTS_BY_ID[action_entry["agent"]],
                {"action_order": action_entry},
                None,
                action_entry,
            )
        return next_agent_for(state), {}, None, None

    def _peek_next_speaker_entry(self, campaign: str) -> dict[str, Any] | None:
        checked_postgres, entry = self._peek_next_speaker_entry_from_postgres(campaign)
        if checked_postgres:
            return entry
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

    def _peek_next_speaker_entry_from_postgres(
        self, campaign: str
    ) -> tuple[bool, dict[str, Any] | None]:
        try:
            from cli import db as _glass_db
            from cli.config import load_config as _load_glass_config

            previous = os.environ.get("GLASS_CONFIG")
            os.environ["GLASS_CONFIG"] = config_env_value(self.config)
            try:
                toml_data = _load_glass_config()
                if not _glass_db.postgres_configured(toml_data):
                    return False, None
                pg_config = _glass_db.load_pg_config(toml_data)
                with _glass_db.connect(pg_config) as conn:
                    return True, _glass_db.runtime_next_speaker_peek(conn, campaign)
            finally:
                if previous is None:
                    os.environ.pop("GLASS_CONFIG", None)
                else:
                    os.environ["GLASS_CONFIG"] = previous
        except Exception:
            return False, None

    def _peek_action_order_entry(self, state: SessionState) -> dict[str, Any] | None:
        """Return the next initiative-order turn for the active scene, if any."""
        checked_postgres, action_order = self._load_action_order_from_postgres(state)
        if not checked_postgres:
            action_order = self._load_action_order(state.campaign)
        if not isinstance(action_order, dict):
            return None
        active = state.active_mode
        if (
            action_order.get("mode") != active.mode
            or action_order.get("scene_id") != active.scene_id
        ):
            return None
        order = action_order.get("order")
        if not isinstance(order, list) or not order:
            return None
        cursor = int(action_order.get("cursor", 0)) % len(order)
        agent_id = str(order[cursor])
        if agent_id not in AGENTS_BY_ID:
            return None
        return {
            "agent": agent_id,
            "mode": active.mode,
            "scene_id": active.scene_id,
            "label": action_order.get("label", "initiative"),
            "round": int(action_order.get("round", 1)),
            "cursor": cursor,
            "order": [str(agent) for agent in order],
        }

    def _load_action_order(self, campaign: str) -> dict[str, Any] | None:
        path = self.store.glass_state_path(campaign)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        action_order = raw.get("action_order")
        return action_order if isinstance(action_order, dict) else None

    def _load_action_order_from_postgres(
        self, state: SessionState
    ) -> tuple[bool, dict[str, Any] | None]:
        try:
            from cli import db as _glass_db
            from cli.config import load_config as _load_glass_config

            previous = os.environ.get("GLASS_CONFIG")
            os.environ["GLASS_CONFIG"] = config_env_value(self.config)
            try:
                toml_data = _load_glass_config()
                if not _glass_db.postgres_configured(toml_data):
                    return False, None
                pg_config = _glass_db.load_pg_config(toml_data)
                with _glass_db.connect(pg_config) as conn:
                    return True, _glass_db.action_order_get(
                        conn,
                        campaign_id=state.campaign,
                        mode=state.active_mode.mode,
                        scene_id=state.active_mode.scene_id,
                    )
            finally:
                if previous is None:
                    os.environ.pop("GLASS_CONFIG", None)
                else:
                    os.environ["GLASS_CONFIG"] = previous
        except Exception:
            return False, None

    def _consume_next_speaker_entry(
        self, campaign: str, expected_entry: dict[str, Any]
    ) -> None:
        if self._consume_next_speaker_entry_in_postgres(campaign, expected_entry):
            return
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

    def _consume_next_speaker_entry_in_postgres(
        self, campaign: str, expected_entry: dict[str, Any]
    ) -> bool:
        try:
            from cli import db as _glass_db
            from cli.config import load_config as _load_glass_config

            previous = os.environ.get("GLASS_CONFIG")
            os.environ["GLASS_CONFIG"] = config_env_value(self.config)
            try:
                toml_data = _load_glass_config()
                if not _glass_db.postgres_configured(toml_data):
                    return False
                pg_config = _glass_db.load_pg_config(toml_data)
                with _glass_db.connect(pg_config) as conn:
                    return _glass_db.runtime_next_speaker_consume(
                        conn,
                        campaign_id=campaign,
                        expected_entry=expected_entry,
                    )
            finally:
                if previous is None:
                    os.environ.pop("GLASS_CONFIG", None)
                else:
                    os.environ["GLASS_CONFIG"] = previous
        except Exception:
            return False

    def _advance_action_order(
        self, campaign: str, expected_entry: dict[str, Any]
    ) -> None:
        if self._advance_action_order_in_postgres(campaign, expected_entry):
            return
        path = self.store.glass_state_path(campaign)
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        action_order = raw.get("action_order")
        if not isinstance(action_order, dict):
            return
        if (
            action_order.get("mode") != expected_entry.get("mode")
            or action_order.get("scene_id") != expected_entry.get("scene_id")
        ):
            return
        order = action_order.get("order")
        if not isinstance(order, list) or not order:
            return
        cursor = int(action_order.get("cursor", 0)) % len(order)
        if str(order[cursor]) != expected_entry.get("agent"):
            return
        cursor += 1
        if cursor >= len(order):
            cursor = 0
            action_order["round"] = int(action_order.get("round", 1)) + 1
        action_order["cursor"] = cursor
        raw["action_order"] = action_order
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        tmp.replace(path)

    def _advance_action_order_in_postgres(
        self, campaign: str, expected_entry: dict[str, Any]
    ) -> bool:
        try:
            from cli import db as _glass_db
            from cli.config import load_config as _load_glass_config

            previous = os.environ.get("GLASS_CONFIG")
            os.environ["GLASS_CONFIG"] = config_env_value(self.config)
            try:
                toml_data = _load_glass_config()
                if not _glass_db.postgres_configured(toml_data):
                    return False
                pg_config = _glass_db.load_pg_config(toml_data)
                with _glass_db.connect(pg_config) as conn:
                    advanced = _glass_db.action_order_advance(
                        conn,
                        campaign_id=campaign,
                        mode=str(expected_entry.get("mode")),
                        scene_id=str(expected_entry.get("scene_id")),
                        expected_agent=str(expected_entry.get("agent")),
                    )
                return advanced is not None
            finally:
                if previous is None:
                    os.environ.pop("GLASS_CONFIG", None)
                else:
                    os.environ["GLASS_CONFIG"] = previous
        except Exception:
            return False

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
        agent, turn_meta, queued_entry, action_entry = self._resolve_next_agent(state)
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
                action_order_entry=action_entry,
            )

        return self._invoke_agent(
            state,
            agent,
            package,
            queued_entry=queued_entry,
            action_entry=action_entry,
        )

    def commit_turn(self, state: SessionState, result: TurnResult) -> None:
        active = state.active_mode
        command_lines = _tool_transcript_lines(result.prose)
        if command_lines:
            raise TurnFailure(
                "turn output included glass command transcript lines instead of executing them.",
                {
                    "reason": "turn_output_contains_tool_transcript",
                    "turn_id": result.turn_id,
                    "speaker": result.agent.id,
                    "turn_dir": str(result.turn_dir),
                    "lines": command_lines,
                    "hint": (
                        "Run required `glass` commands during the turn. Do not "
                        "write command transcripts into the public prose file."
                    ),
                },
            )

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
        elif result.action_order_entry is not None:
            self._advance_action_order(state.campaign, result.action_order_entry)
        synced = self.store.sync_from_glass(state)
        state.__dict__.update(synced.__dict__)
        self._validate_prelude_dm_handoff(state, result, active)

    def _validate_prelude_dm_handoff(
        self,
        state: SessionState,
        result: TurnResult,
        previous_active: Any,
    ) -> None:
        """Fail fast if the prelude coordinator did not enter table play.

        `prelude` is a DM-only coordinator mode. Its job is to scaffold the
        normal/action scenes and then hand control to `scene-play`, `action`,
        initiative, or an explicit next-speaker queue. If the DM remains in
        bare `prelude` with no queue, the scheduler will select the DM again
        forever and the players never get a turn.
        """
        if result.dry_run or result.agent.id != "dm":
            return
        if previous_active.mode != "prelude":
            return
        if not state.has_active_mode or state.active_mode.mode != "prelude":
            return
        if self._peek_next_speaker_entry(state.campaign):
            return
        if self._peek_action_order_entry(state):
            return
        raise TurnFailure(
            "prelude DM turn did not start a scene mode or queue player turns.",
            {
                "reason": "prelude_dm_no_handoff",
                "turn_id": result.turn_id,
                "speaker": result.agent.id,
                "turn_dir": str(result.turn_dir),
                "active_mode": state.active_mode.mode,
                "active_scene": state.active_mode.scene_id,
                "hint": (
                    "In prelude mode, the DM must execute `glass mode start "
                    "scene-play <scene>` or `glass mode start action <scene>`, "
                    "queue players with `glass turn rapid-round`/handoff, or "
                    "end the prelude mode before finishing the turn."
                ),
            },
        )

    def _tick_closing_countdown(self, campaign: str) -> None:
        """Decrement state["scene_closing_turns"] by 1 if set, after a turn.

        The closing countdown is set by `glass scene closing-down --turns N`
        as N+1 (so the DM's setting turn is the first decrement). When the
        value reaches 0 the next TURN_START renders a "Final round" section;
        below 0 indicates an overrun that the methodology flags as a hard
        backstop ("end the scene now even if it feels unfinished").
        """
        if self._tick_closing_countdown_in_postgres(campaign):
            return
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

    def _tick_closing_countdown_in_postgres(self, campaign: str) -> bool:
        try:
            from cli import db as _glass_db
            from cli.config import load_config as _load_glass_config

            previous = os.environ.get("GLASS_CONFIG")
            os.environ["GLASS_CONFIG"] = config_env_value(self.config)
            try:
                toml_data = _load_glass_config()
                if not _glass_db.postgres_configured(toml_data):
                    return False
                pg_config = _glass_db.load_pg_config(toml_data)
                with _glass_db.connect(pg_config) as conn:
                    return _glass_db.runtime_scene_closing_tick(conn, campaign)
            finally:
                if previous is None:
                    os.environ.pop("GLASS_CONFIG", None)
                else:
                    os.environ["GLASS_CONFIG"] = previous
        except Exception:
            return False

    def _invoke_agent(
        self,
        state: SessionState,
        agent: Agent,
        package: ContextPackage,
        *,
        queued_entry: dict[str, Any] | None,
        action_entry: dict[str, Any] | None,
    ) -> TurnResult:
        # The prompt is intentionally short — the heavy lifting is in
        # TURN_START.md, which the agent reads as its first action.
        turn_start_ref = _agent_path(package.agent_turn_start_path, package.spawn_cwd)
        turn_output_ref = _agent_path(package.agent_turn_output_path, package.spawn_cwd)
        prompt = (
            f"Read {turn_start_ref} and follow its instructions. "
            f"Write your final public prose to {turn_output_ref} and exit."
        )

        # Agents run in a read-only projection. `glass` uses the local API so
        # file reads can come from the projection while mutations land in the
        # canonical campaign tree.
        target_user = permissions.player_user_for(agent.id)
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
            workspace_root=package.spawn_cwd,
        )
        glass_api_grant_file: Path | None = None
        if target_user is not None:
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
        claude_debug_path = package.agent_turn_dir / "claude-debug.log"
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
                "GLASS_API_URL": glass_api_url,
                "GLASS_API_GRANT": glass_api_grant,
                "AOG_TURN_START": str(package.agent_turn_start_path),
                "AOG_TURN_OUTPUT": str(package.agent_turn_output_path),
            }
        )
        if target_user is not None:
            env["PATH"] = _player_path()
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

        copy_turn_artifacts_to_canonical(
            projection=package.projection,
            canonical_turn_dir=package.turn_dir,
        )
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

        prose = _collect_prose(package.agent_turn_output_path, stdout_text)
        if not prose:
            output_debug = _path_debug(package.agent_turn_output_path)
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
                    "turn_output_path": str(package.agent_turn_output_path),
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
            action_order_entry=action_entry,
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
        "campaign_root": _path_debug(package.campaign_root),
        "projection_turn_dir": _path_debug(package.agent_turn_dir),
        "projection_turn_start_path": _path_debug(package.agent_turn_start_path),
        "projection_turn_output_path": _path_debug(package.agent_turn_output_path),
        "projection_claude_debug_path": _path_debug(
            package.agent_turn_dir / "claude-debug.log"
        ),
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
    """Read the agent's committed public turn prose file."""
    if turn_output_path.exists():
        text = turn_output_path.read_text(encoding="utf-8").strip()
        if text:
            return text
    return ""


def _tool_transcript_lines(prose: str) -> list[str]:
    """Return public prose lines that look like unexecuted glass commands."""
    matches: list[str] = []
    for line in prose.splitlines():
        stripped = line.strip()
        if _GLASS_COMMAND_LINE_RE.match(stripped):
            matches.append(stripped)
    return matches


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
