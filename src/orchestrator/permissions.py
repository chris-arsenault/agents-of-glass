"""Unix security model for the orchestrator.

Each player agent runs as a dedicated Unix user (`aog-tev`, `aog-sumi`,
`aog-renno`, `aog-kit`); the DM runs as the current operator user. Filesystem
access is gated by group-based chmod on campaign workspaces and per-turn
ephemeral CWDs.

The chown/chmod operations that require root are delegated to a small
helper script (`aog-permset`) installed by `scripts/provision-agents.sh`
and invoked via sudo. If provisioning hasn't been run, this module falls
back gracefully: no permission setup happens, agents all run as the
operator, and the orchestrator behaves as it did before.
"""

from __future__ import annotations

from pathlib import Path
import getpass
import grp
import logging
import os
import pwd
import shutil
import subprocess


log = logging.getLogger(__name__)


# Map from agent id -> Unix user. DM is intentionally absent (DM runs as
# the operator, whoever that is).
PLAYER_USERS: dict[str, str] = {
    "tev": "aog-tev",
    "sumi": "aog-sumi",
    "renno": "aog-renno",
    "kit": "aog-kit",
}

SHARED_GROUP = "aog-agents"
HELPER_PATH = Path("/usr/local/bin/aog-permset")


def has_provisioned_users() -> bool:
    """True when the player Unix users, the shared group, and the permset
    helper are all present. False if any are missing — in which case the
    orchestrator falls back to running everything as the operator user.
    """
    try:
        grp.getgrnam(SHARED_GROUP)
    except KeyError:
        return False
    for user in PLAYER_USERS.values():
        try:
            pwd.getpwnam(user)
        except KeyError:
            return False
    if not HELPER_PATH.exists():
        return False
    return True


def player_user_for(agent_id: str) -> str | None:
    """Return the Unix user this agent should run as, or None to run as the
    operator. The DM always returns None.
    """
    if agent_id == "dm":
        return None
    if not has_provisioned_users():
        return None
    return PLAYER_USERS.get(agent_id)


def apply_campaign_permissions(campaign_dir: Path) -> bool:
    """Set ownership + modes on a freshly-created campaign workspace.

    Returns True if permissions were applied, False if provisioning isn't
    set up (and the orchestrator should fall back to current-user mode).
    """
    if not has_provisioned_users():
        log.info(
            "permissions: provisioning not detected; skipping. "
            "Run scripts/provision-agents.sh as root to enable Unix isolation."
        )
        return False
    _run_helper(["campaign", str(campaign_dir.resolve())])
    return True


def apply_player_turn_dir_permissions(player_id: str, turn_dir: Path) -> bool:
    """Prepare a per-turn artifact dir (under sessions/<id>/turns/) so the
    player Unix user can read TURN_START.md and write TURN.md.
    """
    if not has_provisioned_users():
        return False
    _run_helper(["turn-dir-player", player_id, str(turn_dir.resolve())])
    return True


def apply_dm_turn_dir_permissions(turn_dir: Path) -> bool:
    """Prepare a per-turn artifact dir for the DM (operator)."""
    if not has_provisioned_users():
        return False
    _run_helper(["turn-dir-dm", str(turn_dir.resolve())])
    return True


def _run_helper(args: list[str]) -> None:
    """Invoke /usr/local/bin/aog-permset via sudo with the given args."""
    if shutil.which("sudo") is None:
        raise RuntimeError("sudo is required for the Unix security model but is not on PATH")
    cmd = ["sudo", "-n", str(HELPER_PATH), *args]
    log.debug("permissions: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"aog-permset {' '.join(args)} failed (exit {exc.returncode}): "
            f"{exc.stderr.strip() or exc.stdout.strip() or 'no output'}"
        ) from exc


def operator_user() -> str:
    """The current operator user (the one running aog)."""
    try:
        return pwd.getpwuid(os.geteuid()).pw_name
    except KeyError:
        return getpass.getuser()
