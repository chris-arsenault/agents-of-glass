"""Per-campaign runtime state store for the orchestrator.

There is no `session` concept. Each campaign has exactly one runtime state
at `campaigns/<id>/`. This module owns:

  campaigns/<id>/aog-state.json   — no-Postgres orchestrator fallback cache
  campaigns/<id>/state.json       — no-Postgres glass runtime fallback
  campaigns/<id>/transcript.md    — derived public transcript export
  campaigns/<id>/audit.jsonl      — append-only audit log
  campaigns/<id>/scene-framing.md — current scene framing
  campaigns/<id>/table/           — current public short-term table state
  campaigns/<id>/<agent>/turns/<NNNN>/ — per-turn artifacts

The class is named `SessionStore` only to limit churn in the orchestrator
module; it operates on campaigns now.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from .config import AogConfig
from .config import config_env_value
from .glass_bridge import GlassBridge, GlassBridgeError
from .state import ModeFrame, SessionState, utc_now


class SessionStore:
    def __init__(self, config: AogConfig):
        self.config = config
        self.glass = GlassBridge(config)

    # --- paths (campaign-rooted) ---

    def campaign_dir(self, campaign: str) -> Path:
        return self.config.campaigns_dir / campaign

    def state_path(self, campaign: str) -> Path:
        return self.campaign_dir(campaign) / "aog-state.json"

    def glass_state_path(self, campaign: str) -> Path:
        return self.campaign_dir(campaign) / "state.json"

    def transcript_path(self, campaign: str) -> Path:
        return self.campaign_dir(campaign) / "transcript.md"

    def audit_path(self, campaign: str) -> Path:
        return self.campaign_dir(campaign) / "audit.jsonl"

    def scene_framing_path(self, campaign: str) -> Path:
        return self.campaign_dir(campaign) / "scene-framing.md"

    # --- lifecycle ---

    def create_session(self, campaign: str, initial_mode: str, initial_scene: str) -> SessionState:
        """Initialize / resume the campaign's runtime state.

        Idempotent: if the requested mode is already at the top of the
        mode stack (e.g. on resume from a failed phase), do nothing
        beyond loading. Otherwise push the new mode.
        """
        if not self.campaign_dir(campaign).exists():
            raise FileNotFoundError(
                f"Campaign workspace does not exist at {self.campaign_dir(campaign)}; "
                "run `aog campaign bootstrap <id>` first."
            )
        try:
            self.glass.invoke(["session", "new", "--campaign", campaign])
        except GlassBridgeError as exc:
            raise RuntimeError(f"glass init for {campaign!r} failed: {exc}") from exc

        # Check if the requested bootstrap mode is already on the stack
        # (resume case). It may be below a child scene mode, e.g. the prelude
        # coordinator beneath scene-play/action.
        existing = self._state_from_glass(campaign)
        already_active = (
            any(
                frame.mode == initial_mode and frame.scene_id == initial_scene
                for frame in existing.mode_stack
            )
        )
        if not already_active:
            try:
                self.glass.invoke(
                    ["mode", "start", initial_mode, initial_scene],
                    role="dm",
                    campaign=campaign,
                )
            except GlassBridgeError as exc:
                raise RuntimeError(
                    f"glass mode start for {campaign!r} failed: {exc}"
                ) from exc

        state = self._state_from_glass(campaign)
        state.run_metadata.setdefault("initial_mode", initial_mode)
        state.run_metadata.setdefault("initial_scene", initial_scene)
        self.save(state)
        self.append_audit(
            campaign,
            {
                "event": "campaign.resume" if already_active else "campaign.start",
                "campaign": campaign,
                "mode": initial_mode,
                "scene_id": initial_scene,
            },
        )
        return state

    def load(self, campaign: str | None = None) -> SessionState:
        resolved = campaign or self.latest_campaign()
        if not resolved:
            raise FileNotFoundError("No campaigns exist yet")
        path = self.state_path(resolved)
        if path.exists():
            state = SessionState.from_dict(json.loads(path.read_text(encoding="utf-8")))
            return self.sync_from_glass(state)
        if self._glass_runtime_exists(resolved):
            state = self._state_from_glass(resolved)
            self.save(state)
            return state
        raise FileNotFoundError(f"No state found for campaign {resolved!r}")

    def save(self, state: SessionState) -> None:
        state.updated_at = utc_now()
        if self._postgres_runtime_configured():
            self._save_aog_state_to_postgres(state)
            path = self.state_path(state.campaign)
            if path.exists():
                path.unlink()
            return
        path = self.state_path(state.campaign)
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n")

    def list_campaigns(self) -> list[SessionState]:
        if not self.config.campaigns_dir.exists():
            return []
        states: list[SessionState] = []
        for d in sorted(self.config.campaigns_dir.iterdir()):
            if not d.is_dir():
                continue
            campaign = d.name
            if not (
                self.state_path(campaign).exists()
                or self.glass_state_path(campaign).exists()
                or self._glass_runtime_exists(campaign)
            ):
                continue
            try:
                states.append(self.load(campaign))
            except (json.JSONDecodeError, KeyError, ValueError, FileNotFoundError):
                continue
        return sorted(states, key=lambda item: item.created_at)

    def latest_campaign(self) -> str | None:
        states = self.list_campaigns()
        if not states:
            return None
        return max(states, key=lambda item: item.created_at).campaign

    def append_transcript(self, campaign: str, markdown: str) -> None:
        with self.transcript_path(campaign).open("a", encoding="utf-8") as handle:
            handle.write(markdown)

    def recent_turns_markdown(self, campaign: str, *, limit: int) -> str:
        records = self._recent_turn_records(campaign, limit=limit)
        if records:
            return _render_turn_records(records)
        path = self.transcript_path(campaign)
        if path.exists():
            return _last_turns(path.read_text(encoding="utf-8"), limit)
        return "No transcript exists yet.\n"

    def _recent_turn_records(self, campaign: str, *, limit: int) -> list[dict[str, Any]]:
        try:
            from cli import db as _glass_db
            from cli.config import load_config as _load_glass_config

            previous = os.environ.get("GLASS_CONFIG")
            os.environ["GLASS_CONFIG"] = config_env_value(self.config)
            try:
                toml_data = _load_glass_config()
                if not _glass_db.postgres_configured(toml_data):
                    return []
                pg_config = _glass_db.load_pg_config(toml_data)
                with _glass_db.connect(pg_config) as conn:
                    return _glass_db.turn_list(
                        conn,
                        campaign_id=campaign,
                        limit=limit,
                        latest=True,
                    )
            finally:
                if previous is None:
                    os.environ.pop("GLASS_CONFIG", None)
                else:
                    os.environ["GLASS_CONFIG"] = previous
        except Exception:
            return []

    def append_audit(self, campaign: str, event: dict[str, Any]) -> None:
        payload = {"ts": utc_now(), **event}
        path = self.audit_path(campaign)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def clear_state(self, campaign: str) -> None:
        """Delete runtime state/cache (Postgres runtime rows plus fallback files).

        Does NOT delete the campaign workspace itself or any DM/player-
        authored content. Operator escape hatch.
        """
        self._clear_runtime_db(campaign)
        for filename in (
            "state.json", "aog-state.json", "transcript.md",
            "audit.jsonl", "scene-framing.md",
        ):
            target = self.campaign_dir(campaign) / filename
            if target.exists():
                target.unlink()
        # Per-agent turns/ subdirs.
        campaign_root = self.campaign_dir(campaign)
        for agent_root in [campaign_root / "dm"] + list((campaign_root / "players").glob("*")):
            turns_dir = agent_root / "turns"
            if turns_dir.exists():
                shutil.rmtree(turns_dir)

    def _clear_runtime_db(self, campaign: str) -> None:
        try:
            from cli import db as _glass_db
            from cli.config import load_config as _load_glass_config

            previous = os.environ.get("GLASS_CONFIG")
            os.environ["GLASS_CONFIG"] = config_env_value(self.config)
            try:
                toml_data = _load_glass_config()
                if not _glass_db.postgres_configured(toml_data):
                    return
                pg_config = _glass_db.load_pg_config(toml_data)
                with _glass_db.connect(pg_config) as conn:
                    _glass_db.runtime_state_delete(conn, campaign)
            finally:
                if previous is None:
                    os.environ.pop("GLASS_CONFIG", None)
                else:
                    os.environ["GLASS_CONFIG"] = previous
        except Exception:
            return

    def clear_scene(self, campaign: str, scene_id: str | None = None) -> str:
        state = self.load(campaign)
        target_scene = scene_id or state.active_mode.scene_id
        if target_scene == state.active_mode.scene_id:
            _atomic_write(
                self.scene_framing_path(state.campaign),
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
        glass_state = self._load_glass_state(state.campaign)
        synced = self._state_from_glass_state(glass_state, existing=state)
        self.save(synced)
        return synced

    def _postgres_runtime_configured(self) -> bool:
        try:
            from cli import db as _glass_db
            from cli.config import load_config as _load_glass_config

            previous = os.environ.get("GLASS_CONFIG")
            os.environ["GLASS_CONFIG"] = config_env_value(self.config)
            try:
                return _glass_db.postgres_configured(_load_glass_config())
            finally:
                if previous is None:
                    os.environ.pop("GLASS_CONFIG", None)
                else:
                    os.environ["GLASS_CONFIG"] = previous
        except Exception:
            return False

    def _glass_runtime_exists(self, campaign: str) -> bool:
        if self.glass_state_path(campaign).exists():
            return True
        try:
            from cli.config import get_paths as _get_glass_paths
            from cli.config import load_config as _load_glass_config
            from cli.state import state_exists as _runtime_state_exists

            previous = os.environ.get("GLASS_CONFIG")
            os.environ["GLASS_CONFIG"] = config_env_value(self.config)
            try:
                _load_glass_config()
                return _runtime_state_exists(_get_glass_paths(), campaign)
            finally:
                if previous is None:
                    os.environ.pop("GLASS_CONFIG", None)
                else:
                    os.environ["GLASS_CONFIG"] = previous
        except Exception:
            return False

    def _save_aog_state_to_postgres(self, state: SessionState) -> None:
        from cli.config import get_paths as _get_glass_paths
        from cli.config import load_config as _load_glass_config
        from cli.state import default_state as _default_glass_state
        from cli.state import load_state as _load_runtime_state
        from cli.state import save_state as _save_runtime_state

        previous = os.environ.get("GLASS_CONFIG")
        os.environ["GLASS_CONFIG"] = config_env_value(self.config)
        try:
            _load_glass_config()
            paths = _get_glass_paths()
            try:
                glass_state = _load_runtime_state(paths, state.campaign)
            except Exception:
                glass_state = _default_glass_state(state.campaign)
            glass_state["aog_status"] = state.status
            glass_state["aog_failure"] = state.failure
            glass_state["aog_run_metadata"] = state.run_metadata
            glass_state["aog_last_speaker"] = state.last_speaker
            glass_state["aog_turn_number"] = state.turn_number
            _save_runtime_state(paths, glass_state)
        finally:
            if previous is None:
                os.environ.pop("GLASS_CONFIG", None)
            else:
                os.environ["GLASS_CONFIG"] = previous

    def _state_from_glass(self, campaign: str) -> SessionState:
        glass_state = self._load_glass_state(campaign)
        return self._state_from_glass_state(glass_state, existing=None)

    def _load_glass_state(self, campaign: str) -> dict[str, Any]:
        try:
            from cli.config import get_paths as _get_glass_paths
            from cli.config import load_config as _load_glass_config
            from cli.state import load_state as _load_runtime_state

            previous = os.environ.get("GLASS_CONFIG")
            os.environ["GLASS_CONFIG"] = config_env_value(self.config)
            try:
                _load_glass_config()
                return _load_runtime_state(_get_glass_paths(), campaign)
            finally:
                if previous is None:
                    os.environ.pop("GLASS_CONFIG", None)
                else:
                    os.environ["GLASS_CONFIG"] = previous
        except Exception:
            if self._postgres_runtime_configured():
                raise
            path = self.glass_state_path(campaign)
            if not path.exists():
                raise FileNotFoundError(f"No glass state found for campaign {campaign!r}")
            return json.loads(path.read_text(encoding="utf-8"))

    def _state_from_glass_state(
        self,
        glass_state: dict[str, Any],
        *,
        existing: SessionState | None,
    ) -> SessionState:
        # v4 (flat): top-level fields. v3 (nested): glass_state["session"] dict.
        legacy_session = glass_state.get("session")
        if isinstance(legacy_session, dict):
            campaign = str(legacy_session.get("campaign") or legacy_session.get("id", ""))
            status_raw = str(legacy_session.get("status", "active"))
            created_at = str(legacy_session.get("created_at") or utc_now())
            updated_at = str(legacy_session.get("updated_at") or utc_now())
            turn_counter = int(legacy_session.get("turn_counter", 0))
        else:
            campaign = str(glass_state.get("campaign", existing.campaign if existing else ""))
            status_raw = str(glass_state.get("status", "active"))
            created_at = str(
                glass_state.get("created_at")
                or (existing.created_at if existing else utc_now())
            )
            updated_at = str(glass_state.get("updated_at") or utc_now())
            turn_counter = int(glass_state.get("turn_counter", 0))

        turns = list(glass_state.get("turns", []))
        glass_stack_raw = glass_state.get("mode_stack")
        glass_stack_explicit = glass_stack_raw is not None
        glass_stack = list(glass_stack_raw) if glass_stack_explicit else []

        aog_status = glass_state.get("aog_status")
        if existing and existing.status in {"failed", "interrupted", "paused", "running"}:
            status = existing.status
        elif isinstance(aog_status, str) and status_raw != "wrapped":
            status = aog_status
        else:
            status = _aog_status_from_glass(status_raw)

        frames: list[ModeFrame] = []
        for frame in glass_stack:
            mode = str(frame["mode"])
            scene_id = str(frame["scene_id"])
            initial_budget = self.config.caps.budget_for(mode)
            turns_taken = _turns_taken_for_frame(turns, mode, scene_id)
            remaining = (
                None if initial_budget is None else max(initial_budget - turns_taken, 0)
            )
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
            frames = existing.mode_stack
        if not frames and not glass_stack_explicit:
            frames = [
                ModeFrame(
                    mode="none",
                    scene_id="none",
                    started_at=created_at,
                    turn_budget_remaining=None,
                    turns_taken=0,
                )
            ]

        last_speaker = (
            turns[-1].get("speaker")
            if turns
            else glass_state.get("aog_last_speaker")
        )
        run_metadata = dict(glass_state.get("aog_run_metadata") or {})
        if existing:
            run_metadata.update(existing.run_metadata)
        run_metadata["glass_state"] = "postgres runtime state"

        closing_raw = glass_state.get("scene_closing_turns")
        scene_closing_turns = int(closing_raw) if closing_raw is not None else None

        return SessionState(
            campaign=campaign,
            created_at=created_at,
            updated_at=updated_at,
            status=status,
            turn_number=turn_counter,
            mode_stack=frames,
            last_speaker=last_speaker,
            failure=existing.failure if existing else glass_state.get("aog_failure"),
            run_metadata=run_metadata,
            scene_closing_turns=scene_closing_turns,
        )


def _atomic_write(path: Path, body: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(path)


def _turns_taken_for_frame(turns: list[dict[str, Any]], mode: str, scene_id: str) -> int:
    return sum(
        1 for turn in turns
        if turn.get("mode") == mode and turn.get("scene_id") == scene_id
    )


def _render_turn_records(records: list[dict[str, Any]]) -> str:
    return "\n".join(
        str(record.get("markdown") or _turn_record_to_markdown(record)).rstrip()
        for record in records
    ).rstrip() + "\n"


def _turn_record_to_markdown(record: dict[str, Any]) -> str:
    header = (
        f"## Turn {record['turn_id']} - {record['speaker']} ({record['role']}) - "
        f"{record['mode']}, {record['scene_id']}"
    )
    parts = [header, "", str(record.get("prose") or "").strip()]
    event_lines = [f"> {summary}" for summary in record.get("event_summaries", [])]
    if event_lines:
        parts.extend(["", *event_lines])
    return "\n".join(parts).rstrip() + "\n"


def _last_turns(markdown: str, max_turns: int) -> str:
    chunks = []
    current: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("## Turn ") and current:
            chunks.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append("\n".join(current).strip())
    turn_chunks = [chunk for chunk in chunks if chunk.startswith("## Turn ")]
    if not turn_chunks:
        return markdown.strip() + "\n"
    return "\n\n".join(turn_chunks[-max_turns:]).strip() + "\n"


def _aog_status_from_glass(value: str) -> str:
    mapping = {
        "active": "ready",
        "wrapped": "complete",
        "complete": "complete",
        "ready": "ready",
        "running": "running",
        "paused": "paused",
        "failed": "failed",
        "interrupted": "interrupted",
    }
    return mapping.get(value, "ready")


def summarize_states(states: list[SessionState]) -> str:
    """Render a short, human-readable summary of multiple campaign states."""
    if not states:
        return "(no campaigns)"
    lines = []
    for state in states:
        active = state.active_mode if state.mode_stack else None
        mode_str = f"{active.mode}:{active.scene_id}" if active else "(no mode)"
        lines.append(
            f"  {state.campaign:32s}  {state.status:10s}  turn={state.turn_number:>3}  {mode_str}"
        )
    return "\n".join(lines)
