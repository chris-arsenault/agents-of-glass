"""Campaign-level workspace management.

A campaign workspace lives at `campaigns/<id>/` and is populated by copying
the `templates/` tree at campaign-bootstrap time. The campaign's `state.json`
tracks the bootstrap phase (init / campaign_planning / character_creation /
prelude / active) and per-phase history.

This module is the home for the campaign workspace lifecycle. It does NOT
own the per-session/per-scene state machine (that's `store.py`/`state.py`),
nor does it invoke agents directly (that's `runner.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import shutil

from .config import AogConfig
from .config import config_env_value
from . import permissions
from .state import utc_now


PHASE_INIT = "init"
PHASE_PLANNING = "campaign_planning"
PHASE_CHARACTER_CREATION = "character_creation"
PHASE_PRELUDE = "prelude"
PHASE_ACTIVE = "active"

PHASE_ORDER = (
    PHASE_INIT,
    PHASE_PLANNING,
    PHASE_CHARACTER_CREATION,
    PHASE_PRELUDE,
    PHASE_ACTIVE,
)


@dataclass(frozen=True)
class CampaignSpace:
    campaign_id: str
    campaign_dir: Path
    state_path: Path

    @classmethod
    def from_config(cls, config: AogConfig, campaign_id: str) -> "CampaignSpace":
        campaign_dir = config.campaigns_dir / campaign_id
        return cls(
            campaign_id=campaign_id,
            campaign_dir=campaign_dir,
            state_path=campaign_dir / "state.json",
        )

    def exists(self) -> bool:
        return self.campaign_dir.exists()


class CampaignManager:
    """Creates and manages campaign workspaces."""

    def __init__(self, config: AogConfig):
        self.config = config

    # --- workspace lifecycle ---

    def create(self, campaign_id: str) -> CampaignSpace:
        """Create a new campaign workspace by copying templates/ into campaigns/<id>/.

        Initializes state.json at phase `init`. Raises FileExistsError if the
        campaign already exists.
        """
        space = CampaignSpace.from_config(self.config, campaign_id)
        if space.exists():
            raise FileExistsError(
                f"Campaign {campaign_id!r} already exists at {space.campaign_dir}"
            )

        if not self.config.templates_dir.exists():
            raise FileNotFoundError(
                f"Templates directory not found: {self.config.templates_dir}"
            )

        self.config.campaigns_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.config.templates_dir, space.campaign_dir)

        now = utc_now()
        initial_state: dict[str, Any] = {
            "campaign": campaign_id,
            "phase": PHASE_INIT,
            "phase_history": [
                {"phase": PHASE_INIT, "started_at": now}
            ],
            "active_arc": None,
            "active_scene": None,
            "arcs": [],
            "created_at": now,
            "updated_at": now,
        }
        self._write_state(space, initial_state)

        # Apply Unix permissions to the freshly-copied workspace so player
        # agents (running as their own users) can only see what they should.
        # Falls through silently if provisioning hasn't been run; the
        # orchestrator then runs everyone as the current operator user.
        permissions.apply_campaign_permissions(space.campaign_dir)

        return space

    def list_campaigns(self) -> list[str]:
        if not self.config.campaigns_dir.exists():
            return []
        return sorted(
            p.name
            for p in self.config.campaigns_dir.iterdir()
            if p.is_dir() and (p / "state.json").exists()
        )

    def clear(self, campaign_id: str) -> None:
        space = CampaignSpace.from_config(self.config, campaign_id)
        if not space.exists():
            return
        # Subdirs under players/<id>/ are owned by aog-<player> with
        # restrictive perms; the operator can't traverse or rmtree them
        # directly. Delegate to the root-privileged helper when
        # provisioning is set up.
        if not permissions.clean_workspace_via_helper(space.campaign_dir):
            shutil.rmtree(space.campaign_dir)

    # --- state lifecycle ---

    def load_state(self, campaign_id: str) -> dict[str, Any]:
        space = CampaignSpace.from_config(self.config, campaign_id)
        if not space.state_path.exists():
            raise FileNotFoundError(
                f"No campaign state found for {campaign_id!r} at {space.state_path}"
            )
        return json.loads(space.state_path.read_text(encoding="utf-8"))

    def advance_phase(self, campaign_id: str, new_phase: str) -> dict[str, Any]:
        if new_phase not in PHASE_ORDER:
            raise ValueError(f"Unknown phase {new_phase!r}")

        state = self.load_state(campaign_id)
        now = utc_now()

        # close out the current phase
        for entry in reversed(state["phase_history"]):
            if entry["phase"] == state["phase"] and "completed_at" not in entry:
                entry["completed_at"] = now
                break

        state["phase"] = new_phase
        state["phase_history"].append({"phase": new_phase, "started_at": now})
        state["updated_at"] = now

        space = CampaignSpace.from_config(self.config, campaign_id)
        self._write_state(space, state)
        return state

    # --- internals ---

    def _write_state(self, space: CampaignSpace, state: dict[str, Any]) -> None:
        tmp = space.state_path.with_suffix(space.state_path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp.replace(space.state_path)
        self._sync_state_to_postgres(state)

    def _sync_state_to_postgres(self, state: dict[str, Any]) -> None:
        """Keep campaign phase fields in the Postgres runtime row when enabled."""
        import os

        from cli import db as _glass_db
        from cli.config import load_config as _load_glass_config

        previous_config = os.environ.get("GLASS_CONFIG")
        os.environ["GLASS_CONFIG"] = config_env_value(self.config)
        try:
            toml_data = _load_glass_config()
            if not _glass_db.postgres_configured(toml_data):
                return
            pg_config = _glass_db.load_pg_config(toml_data)
            with _glass_db.connect(pg_config) as conn:
                existing = _glass_db.runtime_state_get(conn, state["campaign"]) or {}
                merged = {**existing, **state}
                _glass_db.runtime_state_upsert(conn, merged)
        finally:
            if previous_config is None:
                os.environ.pop("GLASS_CONFIG", None)
            else:
                os.environ["GLASS_CONFIG"] = previous_config
