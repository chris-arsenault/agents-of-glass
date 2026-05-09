"""Filesystem-backed session store used by the first orchestrator build."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import json
import re
import shutil

from .config import AogConfig
from .glass_bridge import GlassBridge, GlassBridgeError
from .state import ModeFrame, SessionState, utc_now


class SessionStore:
    def __init__(self, config: AogConfig):
        self.config = config
        self.glass = GlassBridge(config)

    def ensure_layout(self) -> None:
        self.config.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.config.ephemeral_cwd_dir.mkdir(parents=True, exist_ok=True)

    def session_dir(self, session_id: str) -> Path:
        return self.config.sessions_dir / session_id

    def state_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "aog-state.json"

    def glass_state_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "state.json"

    def transcript_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "transcript.md"

    def audit_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "audit.jsonl"

    def scene_framing_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "scene-framing.md"

    def create_session(self, campaign: str, initial_mode: str, initial_scene: str) -> SessionState:
        self.ensure_layout()
        session_id = self._unique_session_id(campaign)
        try:
            self.glass.invoke(
                ["session", "new", "--campaign", campaign, "--session-id", session_id]
            )
            self.glass.invoke(
                ["mode", "start", initial_mode, initial_scene],
                role="dm",
                session_id=session_id,
            )
        except GlassBridgeError as exc:
            raise RuntimeError(f"glass session bootstrap failed: {exc}") from exc

        state = self._state_from_glass(session_id)
        state.run_metadata["initial_mode"] = initial_mode
        state.run_metadata["initial_scene"] = initial_scene
        self.save(state)
        self.append_audit(
            state.session_id,
            {
                "event": "session.new",
                "campaign": campaign,
                "mode": initial_mode,
                "scene_id": initial_scene,
            },
        )
        return state

    def load(self, session_id: str | None = None) -> SessionState:
        resolved = session_id or self.latest_session_id()
        if not resolved:
            raise FileNotFoundError("No sessions exist yet")
        path = self.state_path(resolved)
        if path.exists():
            state = SessionState.from_dict(json.loads(path.read_text(encoding="utf-8")))
            return self.sync_from_glass(state)
        if self.glass_state_path(resolved).exists():
            state = self._state_from_glass(resolved)
            self.save(state)
            return state
        raise FileNotFoundError(f"No state found for session {resolved!r}")

    def save(self, state: SessionState) -> None:
        state.updated_at = utc_now()
        path = self.state_path(state.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n")

    def list_sessions(self) -> list[SessionState]:
        if not self.config.sessions_dir.exists():
            return []
        states: list[SessionState] = []
        state_paths = {
            path.parent.name: path for path in self.config.sessions_dir.glob("*/state.json")
        }
        state_paths.update(
            {
                path.parent.name: path
                for path in self.config.sessions_dir.glob("*/aog-state.json")
            }
        )
        for session_id in sorted(state_paths):
            try:
                states.append(self.load(session_id))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return sorted(states, key=lambda item: item.created_at)

    def latest_session_id(self) -> str | None:
        states = self.list_sessions()
        if not states:
            return None
        return max(states, key=lambda item: item.created_at).session_id

    def append_transcript(self, session_id: str, markdown: str) -> None:
        with self.transcript_path(session_id).open("a", encoding="utf-8") as handle:
            handle.write(markdown)

    def append_audit(self, session_id: str, event: dict[str, Any]) -> None:
        payload = {"ts": utc_now(), **event}
        with self.audit_path(session_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def clear_session(self, session_id: str) -> None:
        shutil.rmtree(self.session_dir(session_id))
        cwd_dir = self.config.ephemeral_cwd_dir / session_id
        if cwd_dir.exists():
            shutil.rmtree(cwd_dir)

    def clear_campaign(self, campaign: str) -> list[str]:
        removed: list[str] = []
        for state in self.list_sessions():
            if state.campaign == campaign:
                self.clear_session(state.session_id)
                removed.append(state.session_id)
        return removed

    def clear_scene(self, session_id: str, scene_id: str | None = None) -> str:
        state = self.load(session_id)
        target_scene = scene_id or state.active_mode.scene_id
        cwd_dir = self.config.ephemeral_cwd_dir / state.session_id
        if cwd_dir.exists():
            shutil.rmtree(cwd_dir)
        if target_scene == state.active_mode.scene_id:
            _atomic_write(
                self.scene_framing_path(state.session_id),
                (
                    "---\n"
                    "status: cleared\n"
                    "---\n\n"
                    f"# Scene Framing - {target_scene}\n\n"
                    "Scene state was cleared by the operator. The DM should reframe it.\n"
                ),
            )
            state.mark_ready()
            self.save(state)
        return target_scene

    def sync_from_glass(self, state: SessionState) -> SessionState:
        glass_state = self._load_glass_state(state.session_id)
        synced = self._state_from_glass_state(glass_state, existing=state)
        self.save(synced)
        return synced

    def _state_from_glass(self, session_id: str) -> SessionState:
        glass_state = self._load_glass_state(session_id)
        return self._state_from_glass_state(glass_state, existing=None)

    def _load_glass_state(self, session_id: str) -> dict[str, Any]:
        path = self.glass_state_path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"No glass state found for session {session_id!r}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _state_from_glass_state(
        self,
        glass_state: dict[str, Any],
        *,
        existing: SessionState | None,
    ) -> SessionState:
        session = glass_state.get("session", {})
        session_id = str(session["id"])
        campaign = str(session.get("campaign", session_id))
        turns = list(glass_state.get("turns", []))
        # Distinguish "glass omitted the key" from "glass explicitly returned []".
        # An explicit empty list is the legitimate post-`mode end` state; we
        # must not mask it by falling back to the existing stack.
        glass_stack_raw = glass_state.get("mode_stack")
        glass_stack_explicit = glass_stack_raw is not None
        glass_stack = list(glass_stack_raw) if glass_stack_explicit else []
        created_at = str(
            session.get("created_at") or (existing.created_at if existing else utc_now())
        )
        updated_at = str(session.get("updated_at") or utc_now())
        if existing and existing.status in {"failed", "interrupted", "paused", "running"}:
            status = existing.status
        else:
            status = _aog_status_from_glass(str(session.get("status", "active")))

        frames = []
        for frame in glass_stack:
            mode = str(frame["mode"])
            scene_id = str(frame["scene_id"])
            initial_budget = self.config.caps.budget_for(mode)
            turns_taken = _turns_taken_for_frame(turns, mode, scene_id)
            remaining = None
            if initial_budget is not None:
                remaining = max(initial_budget - turns_taken, 0)
            frames.append(
                ModeFrame(
                    mode=mode,
                    scene_id=scene_id,
                    started_at=str(frame.get("started_at") or created_at),
                    turn_budget_remaining=remaining,
                    turns_taken=turns_taken,
                )
            )

        if not frames and not glass_stack_explicit and existing and existing.mode_stack:
            # glass didn't report a mode_stack at all; reuse the prior view.
            frames = existing.mode_stack
        if not frames and not glass_stack_explicit:
            # No glass info and nothing to inherit — synthesize a placeholder.
            frames = [
                ModeFrame(
                    mode="none",
                    scene_id="none",
                    started_at=created_at,
                    turn_budget_remaining=None,
                    turns_taken=0,
                )
            ]

        last_speaker = turns[-1].get("speaker") if turns else None
        run_metadata = dict(existing.run_metadata) if existing else {}
        run_metadata["glass_state"] = "sessions/<id>/state.json"

        closing_raw = glass_state.get("scene_closing_turns")
        scene_closing_turns = int(closing_raw) if closing_raw is not None else None

        return SessionState(
            session_id=session_id,
            campaign=campaign,
            created_at=created_at,
            updated_at=updated_at,
            status=status,
            turn_number=int(session.get("turn_counter", len(turns))),
            mode_stack=frames,
            last_speaker=last_speaker,
            failure=existing.failure if existing else None,
            run_metadata=run_metadata,
            scene_closing_turns=scene_closing_turns,
        )

    def _unique_session_id(self, campaign: str) -> str:
        slug = _slugify(campaign)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        candidate = f"{slug}-{stamp}"
        suffix = 2
        while self.session_dir(candidate).exists():
            candidate = f"{slug}-{stamp}-{suffix}"
            suffix += 1
        return candidate

    @staticmethod
    def _write_if_missing(path: Path, text: str) -> None:
        if not path.exists():
            path.write_text(text, encoding="utf-8")


def summarize_states(states: Iterable[SessionState]) -> str:
    rows = ["SESSION ID                         STATUS     TURN  MODE           CAMPAIGN"]
    for state in states:
        active = state.active_mode
        rows.append(
            f"{state.session_id:<34} {state.status:<10} "
            f"{state.turn_number:<5} {active.mode:<14} {state.campaign}"
        )
    return "\n".join(rows)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "campaign"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _aog_status_from_glass(status: str) -> str:
    if status == "wrapped":
        return "complete"
    return "ready"


def _turns_taken_for_frame(turns: list[dict[str, Any]], mode: str, scene_id: str) -> int:
    return sum(
        1
        for turn in turns
        if turn.get("mode") == mode and turn.get("scene_id") == scene_id
    )
