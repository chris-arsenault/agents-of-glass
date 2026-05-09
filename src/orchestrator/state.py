"""Session and turn state for the bootstrap orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class Agent:
    id: str
    display_name: str
    role: str
    character_id: str | None = None

    @property
    def glass_role(self) -> str:
        if self.role == "dm":
            return "dm"
        return f"player:{self.id}"


AGENTS: tuple[Agent, ...] = (
    Agent(id="dm", display_name="Mara", role="dm"),
    Agent(id="tev", display_name="Tev", role="player"),
    Agent(id="sumi", display_name="Sumi", role="player"),
    Agent(id="renno", display_name="Renno", role="player"),
    Agent(id="kit", display_name="Kit", role="player"),
)

PLAYER_IDS: tuple[str, ...] = tuple(agent.id for agent in AGENTS if agent.role == "player")
AGENTS_BY_ID: dict[str, Agent] = {agent.id: agent for agent in AGENTS}


@dataclass
class ModeFrame:
    mode: str
    scene_id: str
    started_at: str
    turn_budget_remaining: int | None
    turns_taken: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModeFrame":
        return cls(
            mode=str(data["mode"]),
            scene_id=str(data["scene_id"]),
            started_at=str(data["started_at"]),
            turn_budget_remaining=data.get("turn_budget_remaining"),
            turns_taken=int(data.get("turns_taken", 0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "scene_id": self.scene_id,
            "started_at": self.started_at,
            "turn_budget_remaining": self.turn_budget_remaining,
            "turns_taken": self.turns_taken,
        }


@dataclass
class SessionState:
    session_id: str
    campaign: str
    created_at: str
    updated_at: str
    status: str
    turn_number: int
    mode_stack: list[ModeFrame]
    last_speaker: str | None = None
    failure: dict[str, Any] | None = None
    run_metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(
        cls,
        *,
        session_id: str,
        campaign: str,
        initial_mode: str,
        initial_scene: str,
        initial_budget: int | None,
    ) -> "SessionState":
        now = utc_now()
        return cls(
            session_id=session_id,
            campaign=campaign,
            created_at=now,
            updated_at=now,
            status="ready",
            turn_number=0,
            mode_stack=[
                ModeFrame(
                    mode=initial_mode,
                    scene_id=initial_scene,
                    started_at=now,
                    turn_budget_remaining=initial_budget,
                )
            ],
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionState":
        return cls(
            session_id=str(data["session_id"]),
            campaign=str(data["campaign"]),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            status=str(data.get("status", "ready")),
            turn_number=int(data.get("turn_number", 0)),
            mode_stack=[
                ModeFrame.from_dict(frame) for frame in data.get("mode_stack", [])
            ],
            last_speaker=data.get("last_speaker"),
            failure=data.get("failure"),
            run_metadata=dict(data.get("run_metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "campaign": self.campaign,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "turn_number": self.turn_number,
            "mode_stack": [frame.to_dict() for frame in self.mode_stack],
            "last_speaker": self.last_speaker,
            "failure": self.failure,
            "run_metadata": self.run_metadata,
        }

    @property
    def active_mode(self) -> ModeFrame:
        if not self.mode_stack:
            raise ValueError("Session has no active mode")
        return self.mode_stack[-1]

    @property
    def has_active_mode(self) -> bool:
        """True iff there's a real mode on the stack (not empty, not 'none')."""
        if not self.mode_stack:
            return False
        return self.mode_stack[-1].mode != "none"

    def mark_running(self) -> None:
        self.status = "running"
        self.updated_at = utc_now()

    def mark_ready(self) -> None:
        self.status = "ready"
        self.failure = None
        self.updated_at = utc_now()

    def mark_paused(self, reason: str) -> None:
        self.status = "paused"
        self.failure = {"reason": reason, "ts": utc_now()}
        self.updated_at = utc_now()

    def mark_failed(self, failure: dict[str, Any]) -> None:
        self.status = "failed"
        self.failure = failure
        self.updated_at = utc_now()

    def record_committed_turn(self, speaker: Agent) -> None:
        self.turn_number += 1
        self.last_speaker = speaker.id
        self.failure = None
        self.status = "ready"
        active = self.active_mode
        active.turns_taken += 1
        if active.turn_budget_remaining is not None:
            active.turn_budget_remaining -= 1
        self.updated_at = utc_now()


def speaker_order_for(mode: str) -> tuple[str, ...]:
    normalized = mode.lower()
    if normalized in {"wrap", "campaign-planning"}:
        return ("dm",)
    if normalized in {"travel", "travel/montage", "montage"}:
        return PLAYER_IDS
    if normalized == "character-creation":
        # Round-robin players, then the DM at the end of each round. Players
        # write their character + intro + relationships directly to their own
        # dirs — no per-player propose/ratify. The DM's once-per-round turn is
        # for review, campaign-intro updates, and transitioning between round
        # 1 (build) and round 2 (relationships); ending the mode signals
        # phase complete.
        return PLAYER_IDS + ("dm",)
    return tuple(agent.id for agent in AGENTS)


def next_agent_for(state: SessionState) -> Agent:
    order = speaker_order_for(state.active_mode.mode)
    if not order:
        raise ValueError(f"No speakers configured for mode {state.active_mode.mode!r}")
    if state.last_speaker not in order:
        return AGENTS_BY_ID[order[0]]
    current_index = order.index(state.last_speaker)
    return AGENTS_BY_ID[order[(current_index + 1) % len(order)]]
