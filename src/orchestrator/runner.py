"""Foreground orchestration loop for `aog campaign run`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import os
import grp
import pwd
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import uuid

from cli.api_grants import DEFAULT_API_URL, mint_grant
from cli.api_server import ensure_background_server

from .config import AogConfig, config_env_value, provider_for_actor
from .context import ContextBuilder, ContextPackage
from .glass_bridge import GlassBridgeError
from . import permissions
from .projection import (
    copy_turn_artifacts_to_canonical,
    unsynced_workspace_changes,
    writable_probe_dirs,
)
from .state import (
    AGENTS_BY_ID,
    Agent,
    SessionState,
    advance_scene_play_player_cursor,
    next_agent_for,
    utc_now,
)
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
    turn_end: dict[str, Any] | None = None
    turn_prose_path: Path | None = None
    turn_closeout_path: Path | None = None
    duration_seconds: float | None = None
    queued_speaker_entry: dict[str, Any] | None = None
    action_order_entry: dict[str, Any] | None = None


_GLASS_COMMAND_LINE_RE = re.compile(
    r"^\s*>?\s*glass\s+"
    r"(roll|character|clock|summary|entity|search|tarot|lore|note|arc|"
    r"scene|table|mode|turn|thread|msg|turns|sync)\b"
)
_SCENE_PLAY_MODES = {"scene-play", "action"}
_PROVIDER_EXECUTABLES = {
    "claude": "claude",
    "codex": "codex",
}
_RECOVERABLE_TURN_FAILURE_REASONS = {"invalid_turn_end"}
_MAX_CONSECUTIVE_RECOVERY_REDIRECTS = 8


def _active_turn_kind_for(
    *,
    state: SessionState,
    agent: Agent,
    turn_meta: dict[str, Any],
    queued_entry: dict[str, Any] | None,
    action_entry: dict[str, Any] | None,
) -> str:
    active = state.active_mode
    if queued_entry and queued_entry.get("housekeeping"):
        return "housekeeping"
    if queued_entry and queued_entry.get("rapid_prompt"):
        return "rapid-response"
    if (
        agent.role == "dm"
        and active.mode in _SCENE_PLAY_MODES
        and state.scene_closing_turns is not None
        and state.scene_closing_turns <= 0
    ):
        return "scene-transition"
    if agent.role == "player" and (action_entry or active.mode in _SCENE_PLAY_MODES):
        return "active-play"
    if agent.role == "dm" and (action_entry or active.mode in _SCENE_PLAY_MODES):
        return "active-play-dm"
    if turn_meta.get("action_order"):
        return "active-play"
    return active.mode


def _turn_type_required_for(
    *,
    state: SessionState,
    agent: Agent,
    turn_meta: dict[str, Any],
    queued_entry: dict[str, Any] | None,
    action_entry: dict[str, Any] | None,
) -> bool:
    if agent.role != "player":
        return False
    if queued_entry and (queued_entry.get("housekeeping") or queued_entry.get("rapid_prompt")):
        return False
    if turn_meta.get("housekeeping") or turn_meta.get("rapid_prompt"):
        return False
    return bool(action_entry) or state.active_mode.mode in _SCENE_PLAY_MODES


def _ensure_actor_claude_session(
    state: SessionState,
    agent: Agent,
    *,
    cwd: Path,
) -> dict[str, Any]:
    """Ensure durable per-actor Claude Code session metadata exists."""

    now = utc_now()
    cwd_text = str(cwd)
    existing_raw = state.claude_sessions.get(agent.id)
    existing = dict(existing_raw) if isinstance(existing_raw, dict) else {}
    session_id = str(existing.get("session_id") or "")
    existing_cwd = str(existing.get("cwd") or "")
    needs_new_session = not _valid_uuid(session_id) or (
        bool(existing_cwd) and existing_cwd != cwd_text
    )

    if needs_new_session:
        record: dict[str, Any] = {
            "actor": agent.id,
            "role": agent.role,
            "session_id": str(uuid.uuid4()),
            "cwd": cwd_text,
            "created_at": now,
            "updated_at": now,
        }
        if session_id:
            record["previous_session_id"] = session_id
        if existing_cwd:
            record["previous_cwd"] = existing_cwd
    else:
        record = existing
        record.setdefault("actor", agent.id)
        record.setdefault("role", agent.role)
        record.setdefault("created_at", now)
        record["session_id"] = session_id
        record["cwd"] = cwd_text
        record["updated_at"] = now

    state.claude_sessions[agent.id] = record
    return record


def _record_actor_claude_invocation(
    state: SessionState,
    agent: Agent,
    *,
    turn_id: str,
    session_id_enabled: bool,
    session_cli_mode: str | None = None,
    session_materialized: bool = False,
    returncode: int | None = None,
    timed_out: bool | None = None,
) -> dict[str, Any]:
    record = dict(state.claude_sessions.get(agent.id) or {})
    now = utc_now()
    record["last_turn_id"] = turn_id
    record["last_invoked_at"] = now
    record["last_session_id_flag_enabled"] = session_id_enabled
    if session_cli_mode is not None:
        record["last_claude_session_cli_mode"] = session_cli_mode
    if session_materialized:
        record.setdefault("session_materialized_at", now)
    if returncode is not None:
        record["last_returncode"] = returncode
    if timed_out is not None:
        record["last_timed_out"] = timed_out
    state.claude_sessions[agent.id] = record
    return record


def _claude_session_cli_args(
    claude_session: dict[str, Any],
    *,
    use_session_id: bool,
) -> tuple[list[str], str]:
    if not use_session_id:
        return [], "disabled"
    session_id = str(claude_session.get("session_id") or "")
    if _claude_session_should_resume(claude_session):
        return ["--resume", session_id], "resume"
    return ["--session-id", session_id], "new"


def _claude_session_should_resume(claude_session: dict[str, Any]) -> bool:
    if claude_session.get("session_materialized_at"):
        return True
    if claude_session.get("last_claude_session_cli_mode") == "resume":
        return True

    # Backward compatibility for records written before we distinguished
    # Claude Code's new-session flag from the resume flag. If the CLI was
    # actually invoked with the session flag, assume the local Claude session
    # exists and resume it on the next turn.
    invoked_with_session_id = claude_session.get("last_session_id_flag_enabled") is True
    process_returned = (
        claude_session.get("last_returncode") is not None
        or claude_session.get("last_timed_out") is not None
    )
    return invoked_with_session_id and process_returned


def _claude_session_materialized_after_run(
    *,
    session_cli_mode: str,
    returncode: int,
    timed_out: bool,
    stderr_text: str,
) -> bool:
    if session_cli_mode == "disabled":
        return False
    lower_stderr = stderr_text.lower()
    if "session" in lower_stderr and (
        "not found" in lower_stderr
        or "does not exist" in lower_stderr
        or "no conversation" in lower_stderr
    ):
        return False
    if "session id" in lower_stderr and "already in use" in lower_stderr:
        return True
    return timed_out or returncode == 0


def _valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except (TypeError, ValueError, AttributeError):
        return False
    return True


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
        a dict with at least an `agent` key plus optional metadata such as
        `rapid_prompt` or `housekeeping`. Falls back to action-scene initiative
        order, then round-robin if no queue/order applies.
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
        return self._peek_next_speaker_entry_from_postgres(campaign)

    def _peek_next_speaker_entry_from_postgres(
        self, campaign: str
    ) -> dict[str, Any] | None:
        from cli import db as _glass_db
        from cli.config import load_config as _load_glass_config

        previous = os.environ.get("GLASS_CONFIG")
        os.environ["GLASS_CONFIG"] = config_env_value(self.config)
        try:
            toml_data = _load_glass_config()
            if not _glass_db.postgres_configured(toml_data):
                raise RuntimeError(
                    "Postgres runtime is required; configure [postgres] in "
                    "agents-of-glass.toml or libpq environment variables"
                )
            pg_config = _glass_db.load_pg_config(toml_data)
            with _glass_db.connect(pg_config) as conn:
                return _glass_db.runtime_next_speaker_peek(conn, campaign)
        finally:
            if previous is None:
                os.environ.pop("GLASS_CONFIG", None)
            else:
                os.environ["GLASS_CONFIG"] = previous

    def _peek_action_order_entry(self, state: SessionState) -> dict[str, Any] | None:
        """Return the next initiative-order turn for the active scene, if any."""
        action_order = self._load_action_order_from_postgres(state)
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

    def _load_action_order_from_postgres(
        self, state: SessionState
    ) -> dict[str, Any] | None:
        from cli import db as _glass_db
        from cli.config import load_config as _load_glass_config

        previous = os.environ.get("GLASS_CONFIG")
        os.environ["GLASS_CONFIG"] = config_env_value(self.config)
        try:
            toml_data = _load_glass_config()
            if not _glass_db.postgres_configured(toml_data):
                raise RuntimeError(
                    "Postgres runtime is required; configure [postgres] in "
                    "agents-of-glass.toml or libpq environment variables"
                )
            pg_config = _glass_db.load_pg_config(toml_data)
            with _glass_db.connect(pg_config) as conn:
                return _glass_db.action_order_get(
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

    def _consume_next_speaker_entry(
        self, campaign: str, expected_entry: dict[str, Any]
    ) -> None:
        self._consume_next_speaker_entry_in_postgres(campaign, expected_entry)

    def _consume_next_speaker_entry_in_postgres(
        self, campaign: str, expected_entry: dict[str, Any]
    ) -> bool:
        from cli import db as _glass_db
        from cli.config import load_config as _load_glass_config

        previous = os.environ.get("GLASS_CONFIG")
        os.environ["GLASS_CONFIG"] = config_env_value(self.config)
        try:
            toml_data = _load_glass_config()
            if not _glass_db.postgres_configured(toml_data):
                raise RuntimeError(
                    "Postgres runtime is required; configure [postgres] in "
                    "agents-of-glass.toml or libpq environment variables"
                )
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

    def _advance_action_order(
        self, campaign: str, expected_entry: dict[str, Any]
    ) -> None:
        self._advance_action_order_in_postgres(campaign, expected_entry)

    def _advance_action_order_in_postgres(
        self, campaign: str, expected_entry: dict[str, Any]
    ) -> bool:
        from cli import db as _glass_db
        from cli.config import load_config as _load_glass_config

        previous = os.environ.get("GLASS_CONFIG")
        os.environ["GLASS_CONFIG"] = config_env_value(self.config)
        try:
            toml_data = _load_glass_config()
            if not _glass_db.postgres_configured(toml_data):
                raise RuntimeError(
                    "Postgres runtime is required; configure [postgres] in "
                    "agents-of-glass.toml or libpq environment variables"
                )
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

    def _begin_turn_via_glass(
        self,
        *,
        state: SessionState,
        agent: Agent,
        package: ContextPackage,
        turn_kind: str,
        turn_type_required: bool,
        allow_player_scene_close: bool,
    ) -> None:
        args = [
            "turn",
            "begin",
            "--turn-id",
            package.turn_id,
            "--actor",
            agent.id,
            "--role",
            agent.role,
            "--mode",
            state.active_mode.mode,
            "--scene",
            state.active_mode.scene_id,
            "--kind",
            turn_kind,
        ]
        if agent.character_id:
            args.extend(["--character", agent.character_id])
        if turn_type_required:
            args.append("--turn-type-required")
        else:
            args.append("--no-turn-type-required")
        if allow_player_scene_close:
            args.append("--allow-player-scene-close")
        else:
            args.append("--disallow-player-scene-close")
        try:
            self.store.glass.invoke(
                args,
                campaign=state.campaign,
            )
        except GlassBridgeError as exc:
            raise TurnFailure(
                "glass turn begin failed.",
                {
                    "reason": "glass_turn_begin_failed",
                    "turn_id": package.turn_id,
                    "speaker": agent.id,
                    "turn_dir": str(package.turn_dir),
                    "glass_output": exc.result.output,
                },
            ) from exc

    def _collect_turn_end_from_postgres(
        self,
        campaign: str,
        *,
        expected_turn_id: str,
    ) -> dict[str, Any]:
        from cli import db as _glass_db
        from cli.config import load_config as _load_glass_config

        previous = os.environ.get("GLASS_CONFIG")
        os.environ["GLASS_CONFIG"] = config_env_value(self.config)
        try:
            toml_data = _load_glass_config()
            if not _glass_db.postgres_configured(toml_data):
                raise ValueError("Postgres runtime is required for active turn closeout")
            pg_config = _glass_db.load_pg_config(toml_data)
            with _glass_db.connect(pg_config) as conn:
                runtime_turn = _glass_db.runtime_active_turn_get(conn, campaign)
        finally:
            if previous is None:
                os.environ.pop("GLASS_CONFIG", None)
            else:
                os.environ["GLASS_CONFIG"] = previous
        return _collect_turn_end(runtime_turn, expected_turn_id=expected_turn_id)

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
                f"Campaign {state.campaign} is failed; use `aog campaign run`.",
                state.failure or {"reason": "failed"},
            )
        if state.status in {"failed", "interrupted", "running", "paused"} and resume_failed:
            state.mark_ready()
            self.store.save(state)

        turns_run = 0
        consecutive_redirects = 0
        try:
            while self._should_continue(state, turns_run, max_turns):
                turn_started_at = time.monotonic()
                self._ensure_turn_allowed(state)
                state.mark_running()
                self.store.save(state)
                try:
                    result = self.run_one_turn(state, dry_run=dry_run)
                    self.commit_turn(state, result)
                except TurnFailure as exc:
                    if _is_recoverable_turn_failure(exc.failure):
                        try:
                            self._redirect_recoverable_turn_failure(state, exc.failure)
                        except Exception as redirect_exc:
                            failure = {
                                "reason": "recoverable_turn_redirect_failed",
                                "turn_id": str(exc.failure.get("turn_id") or ""),
                                "speaker": str(exc.failure.get("speaker") or ""),
                                "error": repr(redirect_exc),
                            }
                            state.mark_failed(failure)
                            self.store.save(state)
                            self.store.append_audit(
                                state.campaign, {"event": "turn.failed", **failure}
                            )
                            raise TurnFailure(
                                "failed to redirect recoverable turn repair.", failure
                            ) from redirect_exc
                        consecutive_redirects += 1
                        if (
                            consecutive_redirects
                            >= _MAX_CONSECUTIVE_RECOVERY_REDIRECTS
                        ):
                            failure = {
                                "reason": "recoverable_turn_redirect_limit",
                                "turn_id": str(exc.failure.get("turn_id") or ""),
                                "speaker": str(exc.failure.get("speaker") or ""),
                                "error": (
                                    "too many consecutive recoverable turn redirects; "
                                    "the agents are not correcting the turn contract"
                                ),
                            }
                            state.mark_failed(failure)
                            self.store.save(state)
                            self.store.append_audit(
                                state.campaign, {"event": "turn.failed", **failure}
                            )
                            raise TurnFailure(
                                "recoverable turn redirects exceeded limit.", failure
                            ) from exc
                        if self._should_continue(state, turns_run, max_turns):
                            self._sleep_for_turn_minimum(
                                turn_started_at,
                                dry_run=dry_run,
                            )
                        continue
                    state.mark_failed(exc.failure)
                    self.store.save(state)
                    self.store.append_audit(
                        state.campaign, {"event": "turn.failed", **exc.failure}
                    )
                    raise
                consecutive_redirects = 0
                turns_run += 1
                if self._should_continue(state, turns_run, max_turns):
                    self._sleep_for_turn_minimum(turn_started_at, dry_run=dry_run)
            if state.status == "running":
                state.mark_ready()
                self.store.save(state)
            return turns_run
        except KeyboardInterrupt:
            state.status = "interrupted"
            state.updated_at = utc_now()
            self.store.save(state)
            raise

    def _sleep_for_turn_minimum(self, turn_started_at: float, *, dry_run: bool) -> None:
        if dry_run:
            return
        minimum = int(self.config.orchestrator.turn_minimum_seconds)
        if minimum <= 0:
            return
        elapsed = time.monotonic() - turn_started_at
        remaining = minimum - elapsed
        if remaining <= 0:
            return
        print(
            (
                "--- turn pacing: waiting "
                f"{_format_duration(remaining)} to enforce "
                f"{_format_duration(float(minimum))} minimum ---"
            ),
            flush=True,
        )
        time.sleep(remaining)

    def run_one_turn(self, state: SessionState, *, dry_run: bool) -> TurnResult:
        agent, turn_meta, queued_entry, action_entry = self._resolve_next_agent(state)
        package = self.context_builder.build(state, agent, turn_meta=turn_meta)
        if dry_run:
            prose = (
                f"_Dry run: prepared turn `{package.turn_id}` for {agent.display_name}. "
                f"TURN_START at `{package.turn_start_path}`._"
            )
            package.turn_prose_path.write_text(prose.rstrip() + "\n", encoding="utf-8")
            return TurnResult(
                turn_id=package.turn_id,
                agent=agent,
                turn_dir=package.turn_dir,
                spawn_cwd=package.spawn_cwd,
                prose=prose,
                dry_run=True,
                turn_prose_path=package.turn_prose_path,
                duration_seconds=0.0,
                queued_speaker_entry=queued_entry,
                action_order_entry=action_entry,
            )

        return self._invoke_agent(
            state,
            agent,
            package,
            turn_meta=turn_meta,
            queued_entry=queued_entry,
            action_entry=action_entry,
        )

    def commit_turn(self, state: SessionState, result: TurnResult) -> None:
        active = state.active_mode
        command_lines = _tool_transcript_lines(result.prose)
        if command_lines:
            self._append_turn_warning(
                state,
                result,
                {
                    "reason": "turn_prose_contains_glass_command_lines",
                    "message": (
                        "turn prose included Glass command-looking lines; "
                        "commands are audited separately, but prose is still committed"
                    ),
                    "lines": command_lines,
                },
            )
        if not result.dry_run:
            try:
                unsynced_changes = unsynced_workspace_changes(
                    result.spawn_cwd,
                    result.agent,
                )
            except Exception as exc:
                self._append_turn_warning(
                    state,
                    result,
                    {
                        "reason": "workspace_sync_check_failed",
                        "message": "could not inspect projected workspace for unsynced edits",
                        "error": repr(exc),
                    },
                )
            else:
                if unsynced_changes:
                    self._append_turn_warning(
                        state,
                        result,
                        {
                            "reason": "workspace_has_unsynced_markdown",
                            "message": (
                                "projected workspace has markdown edits that were not "
                                "committed with glass sync apply"
                            ),
                            "changes": unsynced_changes,
                            "count": len(unsynced_changes),
                        },
                    )

        if result.turn_prose_path is None:
            raise TurnFailure(
                "Turn result did not include a prose file.",
                {
                    "reason": "missing_turn_prose_path",
                    "turn_id": result.turn_id,
                    "speaker": result.agent.id,
                    "turn_dir": str(result.turn_dir),
                },
            )

        # The agent's TURN.md is what we commit. glass turn append owns the
        # transcript header; we just hand it the markdown file.
        append_args = [
            "turn",
            "append",
            str(result.turn_prose_path),
        ]
        try:
            self.store.glass.invoke(
                append_args,
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
                "duration_seconds": (
                    round(result.duration_seconds, 3)
                    if result.duration_seconds is not None
                    else None
                ),
                "turn_summary": (
                    result.turn_end.get("summary")
                    if isinstance(result.turn_end, dict)
                    else None
                ),
                "next_speaker": (
                    result.turn_end.get("next")
                    if isinstance(result.turn_end, dict)
                    else None
                ),
            },
        )
        self._tick_closing_countdown(state.campaign)
        if result.queued_speaker_entry is not None:
            self._consume_next_speaker_entry(
                state.campaign, result.queued_speaker_entry
            )
        elif result.action_order_entry is not None:
            self._advance_action_order(state.campaign, result.action_order_entry)
        if active.mode in _SCENE_PLAY_MODES and result.agent.role == "player":
            advance_scene_play_player_cursor(state, result.agent.id)
        synced = self.store.sync_from_glass(state)
        state.__dict__.update(synced.__dict__)
        self._validate_scene_prep_dm_handoff(state, result, active)
        self._validate_active_play_scene_contract_handoff(state, result, active)
        self._redirect_active_play_contract_gap_to_dm(state, result, active)
        self._validate_scene_boundary_dm_handoff(state, result, active)

    def _append_turn_warning(
        self,
        state: SessionState,
        result: TurnResult,
        warning: dict[str, Any],
    ) -> None:
        payload = {
            "event": "turn.warning",
            "turn_id": result.turn_id,
            "turn_number": state.turn_number + 1,
            "speaker": result.agent.id,
            "role": result.agent.role,
            "turn_dir": str(result.turn_dir),
            "severity": "warning",
            **warning,
        }
        self.store.append_audit(state.campaign, payload)
        reason = str(payload.get("reason") or "turn_warning")
        message = str(payload.get("message") or reason)
        print(f"Warning: {result.turn_id}: {message}", flush=True)

    def _actor_display_name(self, actor_id: str) -> str:
        agent = AGENTS_BY_ID.get(actor_id)
        if agent is not None:
            return agent.display_name
        return actor_id or "agent"

    def _redirect_recoverable_turn_failure(
        self, state: SessionState, failure: dict[str, Any]
    ) -> None:
        turn_id = str(failure.get("turn_id") or "").strip()
        speaker = str(failure.get("speaker") or "").strip()
        error = str(failure.get("error") or "").strip()
        runtime_turn = self._load_active_turn_runtime(state.campaign)
        problems = _turn_end_problem_list(runtime_turn, fallback_error=error)
        recipient = self._recovery_recipient_for_problems(problems, speaker=speaker)
        scene_id = None
        if isinstance(runtime_turn, dict):
            raw_scene_id = str(runtime_turn.get("scene_id") or "").strip()
            scene_id = raw_scene_id or None
        body = self._recovery_message_body(
            turn_id=turn_id,
            speaker=speaker,
            recipient=recipient,
            scene_id=scene_id,
            problems=problems,
        )
        self._prepend_next_speaker_entry(state.campaign, {"agent": recipient})
        self._send_system_instruction(
            state.campaign,
            recipient=recipient,
            body=body,
        )
        try:
            synced = self.store.sync_from_glass(state)
        except Exception:
            synced = None
        if synced is not None:
            state.__dict__.update(synced.__dict__)
        state.mark_ready()
        self.store.save(state)
        payload: dict[str, Any] = {
            "event": "turn.redirected",
            "reason": str(failure.get("reason") or "invalid_turn_end"),
            "turn_id": turn_id,
            "speaker": speaker,
            "recipient": recipient,
            "problems": problems,
            "message": body,
        }
        for key in ("turn_dir", "debug_path", "duration_seconds", "exit_code"):
            if failure.get(key) is not None:
                payload[key] = failure.get(key)
        self.store.append_audit(state.campaign, payload)

    def _redirect_scene_contract_repair_to_dm(
        self,
        state: SessionState,
        result: TurnResult,
        *,
        previous_mode: str,
        active_mode: str,
        active_scene: str,
        failures: list[str],
    ) -> None:
        body = self._scene_contract_dm_message(
            turn_id=result.turn_id,
            speaker=result.agent.id,
            previous_mode=previous_mode,
            active_mode=active_mode,
            scene_id=active_scene,
            failures=failures,
        )
        self._prepend_next_speaker_entry(state.campaign, {"agent": "dm"})
        self._send_system_instruction(
            state.campaign,
            recipient="dm",
            body=body,
        )
        self.store.append_audit(
            state.campaign,
            {
                "event": "turn.redirected",
                "reason": "scene_contract_missing",
                "turn_id": result.turn_id,
                "speaker": result.agent.id,
                "recipient": "dm",
                "previous_mode": previous_mode,
                "active_mode": active_mode,
                "active_scene": active_scene,
                "problems": failures,
                "message": body,
            },
        )

    def _redirect_scene_boundary_repair_to_dm(
        self,
        state: SessionState,
        result: TurnResult,
        previous_active: Any,
        *,
        active_arc: str,
    ) -> None:
        body = self._scene_boundary_repair_message(
            turn_id=result.turn_id,
            speaker=result.agent.id,
            previous_mode=previous_active.mode,
            previous_scene=previous_active.scene_id,
            active_arc=active_arc,
        )
        queued_entry = self._peek_next_speaker_entry(state.campaign)
        if not (isinstance(queued_entry, dict) and queued_entry.get("agent") == "dm"):
            self._prepend_next_speaker_entry(
                state.campaign,
                {"agent": "dm", "scene_boundary_repair": body},
            )
        self._send_system_instruction(
            state.campaign,
            recipient="dm",
            body=body,
        )
        self.store.append_audit(
            state.campaign,
            {
                "event": "turn.redirected",
                "reason": "scene_boundary_no_next_scene",
                "turn_id": result.turn_id,
                "speaker": result.agent.id,
                "recipient": "dm",
                "previous_mode": previous_active.mode,
                "previous_scene": previous_active.scene_id,
                "active_arc": active_arc,
                "message": body,
            },
        )

    def _redirect_dm_handoff_repair(
        self,
        state: SessionState,
        result: TurnResult,
        *,
        reason: str,
        active_mode: str,
        active_scene: str,
        instruction: str,
    ) -> None:
        body = "\n".join(
            [
                f"System recovery notice: Mara's turn `{result.turn_id}` did not hand control to a playable mode.",
                instruction,
                "",
                "On your next turn, make the missing handoff explicit and close with `glass done`.",
            ]
        ).strip()
        queued_entry = self._peek_next_speaker_entry(state.campaign)
        if not (isinstance(queued_entry, dict) and queued_entry.get("agent") == "dm"):
            self._prepend_next_speaker_entry(
                state.campaign,
                {"agent": "dm", "handoff_repair": body},
            )
        self._send_system_instruction(
            state.campaign,
            recipient="dm",
            body=body,
        )
        self.store.append_audit(
            state.campaign,
            {
                "event": "turn.redirected",
                "reason": reason,
                "turn_id": result.turn_id,
                "speaker": result.agent.id,
                "recipient": "dm",
                "active_mode": active_mode,
                "active_scene": active_scene,
                "message": body,
            },
        )

    def _redirect_active_play_contract_gap_to_dm(
        self,
        state: SessionState,
        result: TurnResult,
        previous_active: Any,
    ) -> None:
        """Route empty active-play contract gaps to the DM instead of players."""
        if result.dry_run:
            return
        if not state.has_active_mode or state.active_mode.mode not in _SCENE_PLAY_MODES:
            return
        if result.agent.id == "dm" and previous_active.mode == "scene-prep":
            return
        snapshot = self._scene_contract_snapshot_for_scene(
            campaign=state.campaign,
            scene_id=state.active_mode.scene_id,
        )
        active_clock_count = int(snapshot.get("active_clock_count", 0) or 0)
        active_beat_count = int(snapshot.get("active_beat_count", 0) or 0)
        if active_clock_count > 0 and active_beat_count > 0:
            return

        completed_beats = int(snapshot.get("completed_beats", 0) or 0)
        body = self._scene_contract_closure_gap_message(
            turn_id=result.turn_id,
            speaker=result.agent.id,
            scene_id=state.active_mode.scene_id,
            active_clock_count=active_clock_count,
            active_beat_count=active_beat_count,
            completed_beats=completed_beats,
            scene_note=str(snapshot.get("scene_note") or "").strip() or None,
        )
        queued_entry = self._peek_next_speaker_entry(state.campaign)
        if not (isinstance(queued_entry, dict) and queued_entry.get("agent") == "dm"):
            self._prepend_next_speaker_entry(
                state.campaign,
                {"agent": "dm", "scene_contract_nudge": body},
            )
        self._send_system_instruction(
            state.campaign,
            recipient="dm",
            body=body,
        )
        self.store.append_audit(
            state.campaign,
            {
                "event": "turn.redirected",
                "reason": "scene_contract_closure_gap",
                "turn_id": result.turn_id,
                "speaker": result.agent.id,
                "recipient": "dm",
                "active_mode": state.active_mode.mode,
                "active_scene": state.active_mode.scene_id,
                "active_clock_count": active_clock_count,
                "active_beat_count": active_beat_count,
                "completed_beats": completed_beats,
                "scene_note": snapshot.get("scene_note"),
                "message": body,
            },
        )

    def _recovery_recipient_for_problems(
        self, problems: list[str], *, speaker: str
    ) -> str:
        if any(_problem_requires_dm_recovery(problem) for problem in problems):
            return "dm"
        if speaker in AGENTS_BY_ID:
            return speaker
        return "dm"

    def _recovery_message_body(
        self,
        *,
        turn_id: str,
        speaker: str,
        recipient: str,
        scene_id: str | None,
        problems: list[str],
    ) -> str:
        if recipient == "dm" and any(
            _problem_requires_dm_recovery(problem) for problem in problems
        ):
            return self._scene_contract_dm_message(
                turn_id=turn_id,
                speaker=speaker,
                previous_mode=None,
                active_mode=None,
                scene_id=scene_id,
                failures=problems,
            )
        speaker_name = self._actor_display_name(speaker)
        fixes = _turn_end_fix_suggestions(problems)
        lines = [
            f"System recovery notice: your turn `{turn_id}` did not close cleanly.",
            f"Review the reported problems, correct them, then rerun `glass done`.",
            "",
            "Problems:",
        ]
        lines.extend(f"- {problem}" for problem in problems)
        if fixes:
            lines.extend(["", "Required fixes:"])
            lines.extend(f"- {fix}" for fix in fixes)
        lines.extend(
            [
                "",
                f"This notice is for {speaker_name}. Once the closeout is valid, continue normal play.",
            ]
        )
        return "\n".join(lines).strip()

    def _scene_contract_dm_message(
        self,
        *,
        turn_id: str,
        speaker: str,
        previous_mode: str | None,
        active_mode: str | None,
        scene_id: str | None,
        failures: list[str],
    ) -> str:
        speaker_name = self._actor_display_name(speaker)
        scene_label = scene_id or "the active scene"
        lines = [
            f"System recovery notice: {speaker_name}'s turn `{turn_id}` cannot hand active play forward yet.",
            f"Scene `{scene_label}` is missing a valid beat/clock contract or still needs DM repair.",
        ]
        if previous_mode and active_mode:
            lines.append(
                f"The handoff moved from `{previous_mode}` into `{active_mode}` without a complete scene contract."
            )
        lines.extend(["", "Current problems:"])
        lines.extend(f"- {failure}" for failure in failures)
        lines.extend(
            [
                "",
                "On your next turn, do one of the following before handing back to players:",
                "- If active play should continue, declare a scene clock or repair the existing one, keep 2-3 active beats live across distinct problem lanes, then run `glass check` and `glass done`.",
                "- If the scene is already done, close or transition the scene instead of continuing active play.",
            ]
        )
        return "\n".join(lines).strip()

    def _scene_contract_closure_gap_message(
        self,
        *,
        turn_id: str,
        speaker: str,
        scene_id: str,
        active_clock_count: int,
        active_beat_count: int,
        completed_beats: int,
        scene_note: str | None,
    ) -> str:
        speaker_name = self._actor_display_name(speaker)
        missing: list[str] = []
        if active_clock_count <= 0:
            missing.append("no active scene clock")
        if active_beat_count <= 0:
            missing.append("no active beat")
        missing_text = " and ".join(missing) if missing else "an incomplete contract"
        lines = [
            f"System pacing notice: {speaker_name}'s turn `{turn_id}` left scene `{scene_id}` with {missing_text}.",
            f"The scene has {completed_beats} completed beat(s). Do not hand this gap to another player by default.",
        ]
        if scene_note:
            lines.append(f"`glass check` says: {scene_note}")
        if completed_beats > 8:
            lines.append(
                "Strong closure nudge: this is enough resolved material. Prefer closing or transitioning unless a genuinely new scene question still belongs in this scene."
            )
        else:
            lines.append(
                "This is usually a scene-board repair gap, not a scene ending. A closed beat by itself is not a reason for the DM to take a full turn after every player."
            )
        lines.extend(
            [
                "",
                "On your next turn, run `glass check`, then choose deliberately:",
                "- If the scene has truly landed, close or transition it with the scene-transition workflow and `glass scene end`.",
                "- If play continues, restore 2-3 active beats across different problem lanes, keep the existing scene question alive, and hand back to the player cursor.",
            ]
        )
        return "\n".join(lines).strip()

    def _scene_boundary_repair_message(
        self,
        *,
        turn_id: str,
        speaker: str,
        previous_mode: str,
        previous_scene: str,
        active_arc: str,
    ) -> str:
        speaker_name = self._actor_display_name(speaker)
        return "\n".join(
            [
                f"System recovery notice: {speaker_name}'s turn `{turn_id}` closed `{previous_scene}` and left active arc `{active_arc}` with no active scene mode.",
                "Do not hand this boundary to players yet.",
                "",
                "On your next turn, choose one course correction:",
                "- If the campaign should continue in this arc, start `scene-prep` with `glass mode start scene-prep <scene-id>` and stage the next scene from there.",
                "- If the next scene is already fully staged, start its actual play mode with `glass mode start <scene-play|action> <scene-id>`, create a scene clock and beat, run `glass check`, then close the turn.",
                "- If the arc is actually complete, close the active arc instead of leaving it open.",
                "",
                f"Previous mode was `{previous_mode}`; previous scene was `{previous_scene}`.",
            ]
        ).strip()

    def _load_active_turn_runtime(self, campaign: str) -> dict[str, Any] | None:
        return self._load_active_turn_runtime_from_postgres(campaign)

    def _load_active_turn_runtime_from_postgres(
        self, campaign: str
    ) -> dict[str, Any] | None:
        from cli import db as _glass_db
        from cli.config import load_config as _load_glass_config

        previous = os.environ.get("GLASS_CONFIG")
        os.environ["GLASS_CONFIG"] = config_env_value(self.config)
        try:
            toml_data = _load_glass_config()
            if not _glass_db.postgres_configured(toml_data):
                raise RuntimeError(
                    "Postgres runtime is required; configure [postgres] in "
                    "agents-of-glass.toml or libpq environment variables"
                )
            pg_config = _glass_db.load_pg_config(toml_data)
            with _glass_db.connect(pg_config) as conn:
                return _glass_db.runtime_active_turn_get(conn, campaign)
        finally:
            if previous is None:
                os.environ.pop("GLASS_CONFIG", None)
            else:
                os.environ["GLASS_CONFIG"] = previous

    def _prepend_next_speaker_entry(
        self, campaign: str, entry: dict[str, Any]
    ) -> None:
        if not self._prepend_next_speaker_entry_in_postgres(campaign, entry):
            raise RuntimeError(
                f"could not prepend next-speaker entry for campaign {campaign}"
            )

    def _prepend_next_speaker_entry_in_postgres(
        self, campaign: str, entry: dict[str, Any]
    ) -> bool:
        from cli import db as _glass_db
        from cli.config import load_config as _load_glass_config

        previous = os.environ.get("GLASS_CONFIG")
        os.environ["GLASS_CONFIG"] = config_env_value(self.config)
        try:
            toml_data = _load_glass_config()
            if not _glass_db.postgres_configured(toml_data):
                raise RuntimeError(
                    "Postgres runtime is required; configure [postgres] in "
                    "agents-of-glass.toml or libpq environment variables"
                )
            pg_config = _glass_db.load_pg_config(toml_data)
            with _glass_db.connect(pg_config) as conn:
                return _glass_db.runtime_next_speaker_prepend(
                    conn,
                    campaign_id=campaign,
                    entry=entry,
                )
        finally:
            if previous is None:
                os.environ.pop("GLASS_CONFIG", None)
            else:
                os.environ["GLASS_CONFIG"] = previous

    def _send_system_instruction(
        self, campaign: str, *, recipient: str, body: str
    ) -> None:
        if not self._send_system_instruction_in_postgres(
            campaign,
            recipient=recipient,
            body=body,
        ):
            raise RuntimeError(
                f"could not send recovery instruction to {recipient} for {campaign}"
            )

    def _send_system_instruction_in_postgres(
        self,
        campaign: str,
        *,
        recipient: str,
        body: str,
    ) -> bool:
        from cli import db as _glass_db
        from cli.config import load_config as _load_glass_config

        previous = os.environ.get("GLASS_CONFIG")
        os.environ["GLASS_CONFIG"] = config_env_value(self.config)
        try:
            toml_data = _load_glass_config()
            if not _glass_db.postgres_configured(toml_data):
                raise RuntimeError(
                    "Postgres runtime is required; configure [postgres] in "
                    "agents-of-glass.toml or libpq environment variables"
                )
            pg_config = _glass_db.load_pg_config(toml_data)
            with _glass_db.connect(pg_config) as conn:
                _glass_db.message_send(
                    conn,
                    campaign_id=campaign,
                    session_id=campaign,
                    sender="system",
                    recipient=recipient,
                    type_="instruction",
                    body=body,
                )
            return True
        finally:
            if previous is None:
                os.environ.pop("GLASS_CONFIG", None)
            else:
                os.environ["GLASS_CONFIG"] = previous

    def _validate_scene_prep_dm_handoff(
        self,
        state: SessionState,
        result: TurnResult,
        previous_active: Any,
    ) -> None:
        """Fail fast if scene prep did not hand into an actual play mode."""
        if result.dry_run or result.agent.id != "dm":
            return
        if previous_active.mode != "scene-prep":
            return
        if state.has_active_mode and state.active_mode.mode != "scene-prep":
            return
        if self._peek_next_speaker_entry(state.campaign):
            return
        if self._peek_action_order_entry(state):
            return
        active_mode = state.active_mode.mode if state.has_active_mode else "none"
        active_scene = state.active_mode.scene_id if state.has_active_mode else "none"
        self._redirect_dm_handoff_repair(
            state,
            result,
            reason="scene_prep_no_handoff",
            active_mode=active_mode,
            active_scene=active_scene,
            instruction=(
                "Scene-prep must hand into actual play. Create or repair the "
                "scene/table files, end `scene-prep` if it is still active, "
                "then start `scene-play` or `action`."
            ),
        )

    def _validate_scene_boundary_dm_handoff(
        self,
        state: SessionState,
        result: TurnResult,
        previous_active: Any,
    ) -> None:
        """Fail fast when an open-act scene ends without staging what follows."""
        if result.dry_run or result.agent.id != "dm":
            return
        if previous_active.mode not in _SCENE_PLAY_MODES:
            return
        if state.has_active_mode:
            return
        active_arc = self._campaign_open_active_arc(state.campaign)
        if not active_arc:
            return
        self._redirect_scene_boundary_repair_to_dm(
            state,
            result,
            previous_active,
            active_arc=active_arc,
        )

    def _validate_active_play_scene_contract_handoff(
        self,
        state: SessionState,
        result: TurnResult,
        previous_active: Any,
    ) -> None:
        """Fail fast if a DM handoff enters active play without clocks/beats."""
        if result.dry_run or result.agent.id != "dm":
            return
        if previous_active.mode != "scene-prep":
            return
        if not state.has_active_mode or state.active_mode.mode not in _SCENE_PLAY_MODES:
            return
        failures = self._scene_contract_failures_for_scene(
            campaign=state.campaign,
            scene_id=state.active_mode.scene_id,
        )
        if not failures:
            return
        try:
            self._redirect_scene_contract_repair_to_dm(
                state,
                result,
                previous_mode=previous_active.mode,
                active_mode=state.active_mode.mode,
                active_scene=state.active_mode.scene_id,
                failures=failures,
            )
        except Exception as exc:
            raise TurnFailure(
                "failed to queue DM repair for missing scene contract.",
                {
                    "reason": "scene_contract_redirect_failed",
                    "turn_id": result.turn_id,
                    "speaker": result.agent.id,
                    "turn_dir": str(result.turn_dir),
                    "active_mode": state.active_mode.mode,
                    "active_scene": state.active_mode.scene_id,
                    "error": repr(exc),
                },
            ) from exc

    def _scene_contract_failures_for_scene(
        self,
        *,
        campaign: str,
        scene_id: str,
    ) -> list[str]:
        from cli.scene_beats import scene_contract_failures

        return scene_contract_failures(
            self._scene_contract_snapshot_for_scene(
                campaign=campaign,
                scene_id=scene_id,
            )
        )

    def _scene_contract_snapshot_for_scene(
        self,
        *,
        campaign: str,
        scene_id: str,
    ) -> dict[str, Any]:
        from cli import db as _glass_db
        from cli.config import load_config as _load_glass_config
        from cli.scene_beats import scene_contract_snapshot

        previous = os.environ.get("GLASS_CONFIG")
        os.environ["GLASS_CONFIG"] = config_env_value(self.config)
        try:
            toml_data = _load_glass_config()
            if not _glass_db.postgres_configured(toml_data):
                raise RuntimeError(
                    "Postgres runtime is required; configure [postgres] in "
                    "agents-of-glass.toml or libpq environment variables"
                )
            pg_config = _glass_db.load_pg_config(toml_data)
            with _glass_db.connect(pg_config) as conn:
                snapshot = scene_contract_snapshot(
                    conn,
                    campaign_id=campaign,
                    scene_id=scene_id,
                    role_kind="dm",
                    reference_turn_number=None,
                )
            return snapshot
        finally:
            if previous is None:
                os.environ.pop("GLASS_CONFIG", None)
            else:
                os.environ["GLASS_CONFIG"] = previous

    def _campaign_open_active_arc(self, campaign: str) -> str | None:
        try:
            glass_state = self.store._load_glass_state(campaign)
        except Exception:
            return None
        active_arc = str(glass_state.get("active_arc") or "")
        closed = {str(arc_id) for arc_id in glass_state.get("closed_arcs", [])}
        if active_arc and active_arc not in closed:
            return active_arc
        return None

    def _tick_closing_countdown(self, campaign: str) -> None:
        """Decrement state["scene_closing_turns"] by 1 if set, after a turn.

        The closing countdown is set by `glass scene closing-down --turns N`
        as N+1 (so the DM's setting turn is the first decrement). When the
        value reaches 0 the next TURN_START renders a "Final round" section;
        below 0 indicates an overrun that the methodology flags as a hard
        backstop ("end the scene now even if it feels unfinished").
        """
        self._tick_closing_countdown_in_postgres(campaign)

    def _tick_closing_countdown_in_postgres(self, campaign: str) -> bool:
        from cli import db as _glass_db
        from cli.config import load_config as _load_glass_config

        previous = os.environ.get("GLASS_CONFIG")
        os.environ["GLASS_CONFIG"] = config_env_value(self.config)
        try:
            toml_data = _load_glass_config()
            if not _glass_db.postgres_configured(toml_data):
                raise RuntimeError(
                    "Postgres runtime is required; configure [postgres] in "
                    "agents-of-glass.toml or libpq environment variables"
                )
            pg_config = _glass_db.load_pg_config(toml_data)
            with _glass_db.connect(pg_config) as conn:
                return _glass_db.runtime_scene_closing_tick(conn, campaign)
        finally:
            if previous is None:
                os.environ.pop("GLASS_CONFIG", None)
            else:
                os.environ["GLASS_CONFIG"] = previous

    def _invoke_agent(
        self,
        state: SessionState,
        agent: Agent,
        package: ContextPackage,
        *,
        turn_meta: dict[str, Any],
        queued_entry: dict[str, Any] | None,
        action_entry: dict[str, Any] | None,
    ) -> TurnResult:
        # The prompt is intentionally short — the heavy lifting is in
        # TURN_START.md, which the agent reads as its first action.
        turn_start_ref = _agent_path(package.agent_turn_start_path, package.spawn_cwd)
        turn_prose_ref = _agent_path(package.agent_turn_prose_path, package.spawn_cwd)
        prompt = (
            f"Read {turn_start_ref} and follow its instructions. "
            f"Write your final public prose to {turn_prose_ref}, run "
            "`glass done`, and exit."
        )
        turn_kind = _active_turn_kind_for(
            state=state,
            agent=agent,
            turn_meta=turn_meta,
            queued_entry=queued_entry,
            action_entry=action_entry,
        )
        turn_type_required = _turn_type_required_for(
            state=state,
            agent=agent,
            turn_meta=turn_meta,
            queued_entry=queued_entry,
            action_entry=action_entry,
        )
        self._begin_turn_via_glass(
            state=state,
            agent=agent,
            package=package,
            turn_kind=turn_kind,
            turn_type_required=turn_type_required,
            allow_player_scene_close=False,
        )

        # Agents run in an actor-owned projection. `glass` uses the local API
        # so file reads can come from the projection while mutations land in
        # the canonical campaign tree.
        target_user = permissions.player_user_for(agent.id)
        _assert_actor_workspace_ready(package, target_user=target_user)
        provider = provider_for_actor(
            self.config,
            actor_id=agent.id,
            role=agent.role,
        )
        provider_executable = _resolve_provider_executable(provider)
        claude_session: dict[str, Any] = {}
        claude_session_args: list[str] = []
        claude_session_cli_mode = "disabled"
        if provider == "claude":
            claude_session = _ensure_actor_claude_session(
                state,
                agent,
                cwd=package.spawn_cwd,
            )
            claude_session_args, claude_session_cli_mode = _claude_session_cli_args(
                claude_session,
                use_session_id=self.config.claude.use_session_id,
            )
            _record_actor_claude_invocation(
                state,
                agent,
                turn_id=package.turn_id,
                session_id_enabled=self.config.claude.use_session_id,
                session_cli_mode=claude_session_cli_mode,
            )
            self.store.save(state)
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
            workspace_reader_user=target_user,
            turn_prose_path=package.agent_turn_prose_path,
            turn_closeout_path=package.agent_turn_closeout_path,
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

        actor_command: list[str] = []
        claude_debug_path = package.agent_turn_dir / "claude-debug.log"
        preserved_env = _provider_preserved_env(provider)
        if provider == "claude":
            claude_debug_ref = _agent_path(claude_debug_path, package.spawn_cwd)
            actor_command.append(provider_executable)
            if self.config.claude.model:
                actor_command.extend(["--model", self.config.claude.model])
            actor_command.extend(claude_session_args)
            actor_command.extend([
                "-p",
                prompt,
                "--dangerously-skip-permissions",
                "--debug-file",
                claude_debug_ref,
            ])
        else:
            actor_command.extend(
                [
                    provider_executable,
                    "exec",
                    "--dangerously-bypass-approvals-and-sandbox",
                    prompt,
                ]
            )
        command = actor_command
        if target_user is not None:
            runtime_path = _player_path(extra_dirs=[str(Path(provider_executable).parent)])
            command = [
                "sudo",
                "-n",
                f"--preserve-env={','.join(preserved_env)}",
                "-u",
                target_user,
                "--",
                "env",
                f"PATH={runtime_path}",
                "bash",
                "-lc",
                'umask 0007; exec "$@"',
                "bash",
                *actor_command,
            ]

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
                "AOG_TURN_PROSE": str(package.agent_turn_prose_path),
                "AOG_TURN_CLOSEOUT": str(package.agent_turn_closeout_path),
                "AOG_AGENT_PROVIDER": provider,
            }
        )
        if package.player_surface:
            env["AOG_PLAYER_SURFACE"] = package.player_surface
        if target_user is not None:
            env["PATH"] = runtime_path
            if glass_api_grant_file is not None:
                env["GLASS_API_GRANT_FILE"] = str(glass_api_grant_file)

        prefix = f"[{agent.id}] "
        stderr_prefix = _stderr_prefix_for_provider(provider, prefix)
        stream_stdout, stream_stderr = _live_stream_policy_for_provider(provider)
        print(
            f"\n--- {agent.display_name} (mode: {state.active_mode.mode}, "
            f"provider {provider}, "
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
            provider=provider,
            claude_debug_path=claude_debug_path,
            claude_session=claude_session,
            claude_session_enabled=(
                provider == "claude" and self.config.claude.use_session_id
            ),
            claude_session_cli_mode=claude_session_cli_mode,
        )
        _write_json(debug_path, debug_payload)

        turn_started = time.monotonic()
        try:
            stdout_text, stderr_text, returncode, timed_out = _stream_subprocess(
                command,
                cwd=package.spawn_cwd,
                env=env,
                timeout=self.config.claude.turn_timeout_seconds,
                stdout_prefix=prefix,
                stderr_prefix=stderr_prefix,
                stream_stdout=stream_stdout,
                stream_stderr=stream_stderr,
                stdout_capture_path=package.turn_dir / "agent-stdout.txt",
                stderr_capture_path=package.turn_dir / "agent-stderr.txt",
            )
        except FileNotFoundError as exc:
            duration_seconds = time.monotonic() - turn_started
            debug_payload["phase"] = "spawn_failed"
            debug_payload["exception"] = repr(exc)
            debug_payload["resolved_executable"] = shutil.which(command[0])
            debug_payload["duration_seconds"] = round(duration_seconds, 3)
            debug_payload["paths_after"] = _turn_path_debug(package)
            _write_json(debug_path, debug_payload)
            _print_turn_duration(
                agent,
                package,
                duration_seconds,
                status="spawn failed",
            )
            raise TurnFailure(
                f"{provider.title()} CLI was not found on PATH.",
                {
                    "reason": f"{provider}_not_found",
                    "turn_id": package.turn_id,
                    "speaker": agent.id,
                    "turn_dir": str(package.turn_dir),
                    "debug_path": str(debug_path),
                    "duration_seconds": round(duration_seconds, 3),
                },
            ) from exc
        duration_seconds = time.monotonic() - turn_started
        status = "timed out" if timed_out else f"exit {returncode}"
        _print_turn_duration(agent, package, duration_seconds, status=status)
        if provider == "claude":
            _record_actor_claude_invocation(
                state,
                agent,
                turn_id=package.turn_id,
                session_id_enabled=self.config.claude.use_session_id,
                session_cli_mode=claude_session_cli_mode,
                session_materialized=_claude_session_materialized_after_run(
                    session_cli_mode=claude_session_cli_mode,
                    returncode=returncode,
                    timed_out=timed_out,
                    stderr_text=stderr_text,
                ),
                returncode=returncode,
                timed_out=timed_out,
            )

        _normalize_actor_projection(package, target_user=target_user)
        copy_turn_artifacts_to_canonical(
            projection=package.projection,
            canonical_turn_dir=package.turn_dir,
            reader_user=target_user,
        )
        _write_process_capture(package.turn_dir, stdout_text, stderr_text)
        debug_payload.update(
            {
                "phase": "after_subprocess",
                "returncode": returncode,
                "timed_out": timed_out,
                "duration_seconds": round(duration_seconds, 3),
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
                    "duration_seconds": round(duration_seconds, 3),
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
                    "duration_seconds": round(duration_seconds, 3),
                    "stdout_bytes": debug_payload["stdout_bytes"],
                    "stderr_bytes": debug_payload["stderr_bytes"],
                    "stderr_preview": debug_payload["stderr_preview"],
                },
            )

        prose = _collect_prose(package.turn_prose_path, stdout_text)
        if not prose:
            output_debug = _turn_path_debug(package)
            raise TurnFailure(
                f"Turn {package.turn_id} produced no prose.",
                {
                    "reason": "empty_turn",
                    "turn_id": package.turn_id,
                    "speaker": agent.id,
                    "turn_dir": str(package.turn_dir),
                    "debug_path": str(debug_path),
                    "exit_code": returncode,
                    "duration_seconds": round(duration_seconds, 3),
                    "stdout_bytes": debug_payload["stdout_bytes"],
                    "stderr_bytes": debug_payload["stderr_bytes"],
                    "stdout_preview": debug_payload["stdout_preview"],
                    "stderr_preview": debug_payload["stderr_preview"],
                    "turn_prose_path": str(package.turn_prose_path),
                    "turn_paths": output_debug,
                },
            )
        try:
            turn_end = self._collect_turn_end_from_postgres(
                state.campaign,
                expected_turn_id=package.turn_id,
            )
        except ValueError as exc:
            output_debug = _turn_path_debug(package)
            raise TurnFailure(
                f"Turn {package.turn_id} did not complete `glass done`.",
                {
                    "reason": "invalid_turn_end",
                    "turn_id": package.turn_id,
                    "speaker": agent.id,
                    "turn_dir": str(package.turn_dir),
                    "debug_path": str(debug_path),
                    "exit_code": returncode,
                    "duration_seconds": round(duration_seconds, 3),
                    "error": str(exc),
                    "turn_closeout_path": str(package.turn_closeout_path),
                    "turn_paths": output_debug,
                },
            ) from exc
        return TurnResult(
            turn_id=package.turn_id,
            agent=agent,
            turn_dir=package.turn_dir,
            spawn_cwd=package.spawn_cwd,
            prose=prose,
            dry_run=False,
            turn_end=turn_end,
            turn_prose_path=package.turn_prose_path,
            turn_closeout_path=package.turn_closeout_path,
            duration_seconds=duration_seconds,
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
    stream_stdout: bool = True,
    stream_stderr: bool = True,
    stdout_capture_path: Path | None = None,
    stderr_capture_path: Path | None = None,
) -> tuple[str, str, int, bool]:
    """Run a subprocess, streaming stdout/stderr to the operator's terminal
    line-by-line (with a prefix per agent), while also capturing the full
    text for audit. If capture paths are provided, tee output to those files
    as lines arrive so the local API can expose in-progress process output.
    Enforces a wall-clock timeout.

    Returns (stdout_text, stderr_text, returncode, timed_out).
    """
    for capture_path in (stdout_capture_path, stderr_capture_path):
        if capture_path is not None:
            capture_path.parent.mkdir(parents=True, exist_ok=True)
            capture_path.write_text("", encoding="utf-8")

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

    def pump(stream, sink, prefix, target_io, capture_path, should_stream):
        capture_handle = None
        try:
            if capture_path is not None:
                capture_handle = capture_path.open("a", encoding="utf-8")
            for line in iter(stream.readline, ""):
                sink.append(line)
                if capture_handle is not None:
                    capture_handle.write(line)
                    capture_handle.flush()
                if should_stream:
                    target_io.write(prefix + line)
                    target_io.flush()
        finally:
            if capture_handle is not None:
                capture_handle.close()
            stream.close()

    out_thread = threading.Thread(
        target=pump,
        args=(
            proc.stdout,
            stdout_chunks,
            stdout_prefix,
            sys.stdout,
            stdout_capture_path,
            stream_stdout,
        ),
        daemon=True,
    )
    err_thread = threading.Thread(
        target=pump,
        args=(
            proc.stderr,
            stderr_chunks,
            stderr_prefix,
            sys.stderr,
            stderr_capture_path,
            stream_stderr,
        ),
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
    provider: str,
    claude_debug_path: Path,
    claude_session: dict[str, Any],
    claude_session_enabled: bool,
    claude_session_cli_mode: str,
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
            "provider": provider,
            "cwd": str(package.spawn_cwd),
            "timeout_seconds": timeout_seconds,
            "command": command,
            "resolved_executable": shutil.which(command[0]),
            "resolved_provider": shutil.which(
                _PROVIDER_EXECUTABLES.get(provider, provider),
                path=env.get("PATH"),
            ),
            "resolved_claude": shutil.which("claude", path=env.get("PATH")),
            "operator_uid": os.getuid(),
            "operator_euid": os.geteuid(),
            "target_home": _home_for_user(target_user) if target_user else None,
            "claude_debug_path": str(claude_debug_path),
        },
        "claude_session": {
            "enabled": claude_session_enabled,
            "actor": claude_session.get("actor"),
            "session_id": claude_session.get("session_id"),
            "cwd": claude_session.get("cwd"),
            "created_at": claude_session.get("created_at"),
            "updated_at": claude_session.get("updated_at"),
            "previous_session_id": claude_session.get("previous_session_id"),
            "previous_cwd": claude_session.get("previous_cwd"),
            "session_materialized_at": claude_session.get("session_materialized_at"),
            "cli_mode": claude_session_cli_mode,
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
            "AOG_TURN_PROSE",
            "AOG_TURN_CLOSEOUT",
            "AOG_AGENT_PROVIDER",
            "AOG_PLAYER_SURFACE",
            "CODEX_HOME",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_API_BASE",
            "OPENAI_ORG_ID",
            "OPENAI_PROJECT_ID",
            "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME",
            "XDG_STATE_HOME",
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


def _print_turn_duration(
    agent: Agent,
    package: ContextPackage,
    duration_seconds: float,
    *,
    status: str,
) -> None:
    print(
        f"--- {agent.display_name} completed turn {package.turn_number} "
        f"in {_format_duration(duration_seconds)} ({status}) ---",
        flush=True,
    )


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remaining = seconds - (minutes * 60)
    return f"{minutes}m {remaining:04.1f}s"


def _assert_actor_workspace_ready(
    package: ContextPackage,
    *,
    target_user: str | None,
) -> None:
    """Prove the actor can create/edit/delete files in writable surfaces."""

    if target_user is not None:
        _assert_actor_owns_path(package.spawn_cwd, target_user=target_user)
        _assert_actor_owns_path(package.agent_turn_dir, target_user=target_user)

    probe_dirs = [package.agent_turn_dir]
    probe_dirs.extend(writable_probe_dirs(package.spawn_cwd, package.agent))
    seen: set[Path] = set()
    unique_probe_dirs: list[Path] = []
    for probe_dir in probe_dirs:
        resolved = probe_dir.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_probe_dirs.append(probe_dir)

    probe_refs = [
        _agent_path(probe_dir, package.spawn_cwd)
        for probe_dir in unique_probe_dirs
    ]
    probe_name = ".aog-write-probe"
    probe_files = [probe_dir / probe_name for probe_dir in unique_probe_dirs]
    script = "\n".join(
        ["set -eu"]
        + [
            "\n".join(
                [
                    f"probe_dir={shlex.quote(probe_ref)}",
                    f"probe_file=\"$probe_dir/{probe_name}\"",
                    'probe_tmp="$probe_file.tmp"',
                    'rm -f "$probe_file" "$probe_tmp"',
                    'printf "%s\\n" first > "$probe_file"',
                    'printf "%s\\n" second > "$probe_tmp"',
                    'mv "$probe_tmp" "$probe_file"',
                    'test "$(cat "$probe_file")" = "second"',
                    'chmod 700 "$probe_file"',
                ]
            )
            for probe_ref in probe_refs
        ]
    )
    command = ["bash", "-lc", script]
    if target_user is not None:
        command = ["sudo", "-n", "-u", target_user, "--", *command]

    result = subprocess.run(
        command,
        cwd=package.spawn_cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TurnFailure(
            "actor workspace write probe failed before spawn.",
            {
                "reason": "actor_workspace_write_probe_failed",
                "turn_id": package.turn_id,
                "target_user": target_user,
                "spawn_cwd": str(package.spawn_cwd),
                "turn_dir": str(package.agent_turn_dir),
                "probe_dirs": [str(path) for path in unique_probe_dirs],
                "command": command,
                "exit_code": result.returncode,
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-2000:],
                "paths": _turn_path_debug(package),
            },
        )

    _normalize_actor_projection(package, target_user=target_user)
    unreadable: list[dict[str, str]] = []
    for probe_file in probe_files:
        try:
            if probe_file.read_text(encoding="utf-8").strip() != "second":
                unreadable.append({"path": str(probe_file), "error": "unexpected content"})
        except OSError as exc:
            unreadable.append({"path": str(probe_file), "error": repr(exc)})
    for probe_file in probe_files:
        try:
            probe_file.unlink()
        except OSError:
            pass
    if unreadable:
        raise TurnFailure(
            "operator could not read actor-created workspace probe files.",
            {
                "reason": "actor_workspace_operator_read_probe_failed",
                "turn_id": package.turn_id,
                "target_user": target_user,
                "spawn_cwd": str(package.spawn_cwd),
                "probe_files": unreadable,
                "paths": _turn_path_debug(package),
            },
        )


def _normalize_actor_projection(
    package: ContextPackage,
    *,
    target_user: str | None,
) -> None:
    permissions.apply_projection_permissions(
        package.spawn_cwd,
        actor_user=target_user,
    )


def _assert_actor_owns_path(path: Path, *, target_user: str) -> None:
    try:
        expected_uid = pwd.getpwnam(target_user).pw_uid
    except KeyError as exc:
        raise TurnFailure(
            "target Unix user is missing.",
            {
                "reason": "target_user_missing",
                "target_user": target_user,
                "path": str(path),
            },
        ) from exc
    try:
        st = path.stat()
    except OSError as exc:
        raise TurnFailure(
            "actor-owned projection path is not statable by the operator.",
            {
                "reason": "actor_projection_stat_failed",
                "target_user": target_user,
                "path": str(path),
                "error": repr(exc),
            },
        ) from exc
    if st.st_uid != expected_uid:
        raise TurnFailure(
            "projection path is not owned by the spawned actor.",
            {
                "reason": "actor_projection_owner_mismatch",
                "target_user": target_user,
                "path": str(path),
                "expected_uid": expected_uid,
                "actual_uid": st.st_uid,
                "actual_user": _name_for_uid(st.st_uid),
                "mode": oct(st.st_mode & 0o7777),
            },
        )


def _turn_path_debug(package: ContextPackage) -> dict[str, Any]:
    return {
        "spawn_cwd": _path_debug(package.spawn_cwd),
        "campaign_root": _path_debug(package.campaign_root),
        "projection_turn_dir": _path_debug(package.agent_turn_dir),
        "projection_turn_start_path": _path_debug(package.agent_turn_start_path),
        "projection_turn_prose_path": _path_debug(package.agent_turn_prose_path),
        "projection_turn_closeout_path": _path_debug(package.agent_turn_closeout_path),
        "projection_claude_debug_path": _path_debug(
            package.agent_turn_dir / "claude-debug.log"
        ),
        "turn_dir": _path_debug(package.turn_dir),
        "turn_start_path": _path_debug(package.turn_start_path),
        "turn_prose_path": _path_debug(package.turn_prose_path),
        "turn_closeout_path": _path_debug(package.turn_closeout_path),
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


def _resolve_provider_executable(provider: str) -> str:
    binary = _PROVIDER_EXECUTABLES.get(provider, provider)
    search_paths = [
        os.environ.get("PATH", ""),
        str(Path.home() / ".local" / "bin"),
        _player_path(),
    ]
    for search_path in search_paths:
        resolved = shutil.which(binary, path=search_path)
        if resolved:
            return resolved
    raise FileNotFoundError(binary)


def _provider_preserved_env(provider: str) -> list[str]:
    keys = [
        "GLASS_ROLE",
        "GLASS_CAMPAIGN_ID",
        "GLASS_CONFIG",
        "GLASS_TURN_ID",
        "GLASS_API_URL",
        "GLASS_API_GRANT",
        "GLASS_API_GRANT_FILE",
        "AOG_TURN_START",
        "AOG_TURN_PROSE",
        "AOG_TURN_CLOSEOUT",
        "AOG_AGENT_PROVIDER",
        "AOG_PLAYER_SURFACE",
    ]
    if provider == "codex":
        keys.extend(
            [
                "CODEX_HOME",
                "OPENAI_API_KEY",
                "OPENAI_BASE_URL",
                "OPENAI_API_BASE",
                "OPENAI_ORG_ID",
                "OPENAI_PROJECT_ID",
                "XDG_CONFIG_HOME",
                "XDG_CACHE_HOME",
                "XDG_STATE_HOME",
            ]
        )
    return [key for key in keys if key in os.environ or key.startswith(("GLASS_", "AOG_"))]


def _stderr_prefix_for_provider(provider: str, prefix: str) -> str:
    if provider == "codex":
        return prefix + "(log) "
    return prefix + "(err) "


def _live_stream_policy_for_provider(provider: str) -> tuple[bool, bool]:
    if provider == "codex":
        return False, False
    return True, True


def _player_path(extra_dirs: list[str] | None = None) -> str:
    parts = list(extra_dirs or [])
    parts.extend(
        [
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
            "/usr/local/sbin",
            "/usr/sbin",
            "/sbin",
        ]
    )
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        if not part or part in seen:
            continue
        seen.add(part)
        unique.append(part)
    return ":".join(unique)


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


def _is_recoverable_turn_failure(failure: dict[str, Any] | None) -> bool:
    if not isinstance(failure, dict):
        return False
    return str(failure.get("reason") or "") in _RECOVERABLE_TURN_FAILURE_REASONS


def _problem_requires_dm_recovery(problem: str) -> bool:
    return any(
        marker in problem
        for marker in (
            "0 scene clocks",
            "0 active beats",
            "3-beat cap",
            "No active scene is staged for beat tracking",
            "No active mode is staged while active arc",
        )
    )


def _turn_end_problem_list(
    runtime_turn: dict[str, Any] | None,
    *,
    fallback_error: str,
) -> list[str]:
    if isinstance(runtime_turn, dict):
        closeout = runtime_turn.get("closeout")
        if isinstance(closeout, dict):
            problems = [
                str(item).strip()
                for item in closeout.get("problems", [])
                if str(item).strip()
            ]
            if problems:
                return problems
    detail = fallback_error.strip()
    if detail.startswith("turn closeout is invalid:"):
        detail = detail.split(":", 1)[1].strip()
    if not detail:
        return ["turn closeout is still invalid"]
    return [item.strip() for item in detail.split(";") if item.strip()] or [detail]


def _turn_end_fix_suggestions(problems: list[str]) -> list[str]:
    fixes: list[str] = []
    seen: set[str] = set()
    for problem in problems:
        if "--turn-type" in problem:
            fix = "Rerun `glass done` with `--turn-type act|answer|support|pass`."
        elif "run `glass turn audit` before `glass turn end`" in problem:
            fix = "Run `glass done` after addressing any hard requirements it prints."
        elif "You MUST still run glass beat check" in problem:
            fix = "Run `glass check`, then rerun `glass done`."
        elif "0 scene clocks" in problem:
            fix = "Have the DM declare a scene clock with `glass scene clock declare ...`."
        elif "0 active beats" in problem:
            fix = "Have the DM start a beat with `glass beat start <beat-id> --clock <clock-id> --label ... --question ...`."
        elif "3-beat cap" in problem:
            fix = "Close or convert an active beat before continuing active play."
        elif "Resolve or convert it before another non-pass turn" in problem:
            fix = "Resolve the beat with `glass beat close`, convert it with `glass beat convert`, or pass instead of taking another non-pass turn."
        elif "requires exactly `--state \"no state change\"`" in problem:
            fix = "Rerun with `--state \"no state change\"` and no other `--state` values."
        elif "`pass` requires `--rolls none`" in problem:
            fix = "Rerun with `--rolls none`."
        elif "`--scene-status" in problem or "must keep `--scene-status active`" in problem:
            fix = "Rerun with a valid `--scene-status`, usually `active`."
        elif "`--next" in problem:
            fix = "Rerun with `--next default|dm|tev|sumi|renno|kit`."
        else:
            fix = "Rerun `glass done` after correcting the reported field."
        if fix not in seen:
            fixes.append(fix)
            seen.add(fix)
    return fixes


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


def _collect_prose(turn_prose_path: Path, stdout: str | None) -> str:
    """Read the agent's committed public turn prose file."""
    if turn_prose_path.exists():
        text = turn_prose_path.read_text(encoding="utf-8").strip()
        if text:
            return text
    return ""


def _collect_turn_end(
    runtime_turn: dict[str, Any] | None,
    *,
    expected_turn_id: str,
) -> dict[str, Any]:
    if not isinstance(runtime_turn, dict):
        raise ValueError(
            "missing active turn closeout in Postgres; run `glass done` after writing public prose"
        )
    turn_id = str(runtime_turn.get("turn_id") or "").strip()
    if turn_id != expected_turn_id:
        raise ValueError(
            f"active turn closeout belongs to {turn_id or 'no turn'}; expected {expected_turn_id}"
        )
    raw = runtime_turn.get("closeout")
    if not isinstance(raw, dict):
        raise ValueError("active turn closeout is missing from Postgres")
    if raw.get("valid") is not True:
        problems = [str(item).strip() for item in raw.get("problems", []) if str(item).strip()]
        detail = "; ".join(problems) if problems else "closeout is still invalid"
        raise ValueError(f"turn closeout is invalid: {detail}")
    summary = str(raw.get("summary") or "").strip()
    if not summary:
        raise ValueError("turn closeout metadata is missing a non-empty summary")
    state_changes = raw.get("state")
    if not isinstance(state_changes, list) or not any(str(item).strip() for item in state_changes):
        raise ValueError("turn closeout metadata is missing --state closeout")
    rolls = str(raw.get("rolls") or "").strip()
    if not rolls:
        raise ValueError("turn closeout metadata is missing --rolls closeout")
    next_speaker = str(raw.get("next") or "default")
    if next_speaker not in {"default", "dm", "tev", "sumi", "renno", "kit"}:
        raise ValueError(f"invalid turn closeout next speaker: {next_speaker}")
    return raw


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
