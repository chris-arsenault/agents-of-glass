"""Unix permission helpers for operator-owned campaign workspaces.

Agents do not get direct filesystem authority over `campaigns/`; they mutate
durable state through Glass.
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


DM_USER = "aog-mara"
PLAYER_USERS: dict[str, str] = {
    "tev": "aog-tev",
    "sumi": "aog-sumi",
    "renno": "aog-renno",
    "kit": "aog-kit",
}
AGENT_USERS: dict[str, str] = {"dm": DM_USER, **PLAYER_USERS}

SHARED_GROUP = "aog-agents"
HELPER_PATH = Path("/usr/local/bin/aog-permset")


def has_provisioned_users() -> bool:
    """True when the agent Unix users, the shared group, and the permset
    helper are all present. False if any are missing — in which case local
    non-isolated development falls back to the operator user.
    """
    try:
        grp.getgrnam(SHARED_GROUP)
    except KeyError:
        return False
    for user in AGENT_USERS.values():
        try:
            pwd.getpwnam(user)
        except KeyError:
            return False
    if not HELPER_PATH.exists():
        return False
    return True


def player_user_for(agent_id: str) -> str | None:
    """Return the Unix user this agent should run as, or None to run as the
    operator.
    """
    if not has_provisioned_users():
        return None
    return AGENT_USERS.get(agent_id)


def missing_operator_groups() -> list[str]:
    """Legacy compatibility hook.

    Agent turns no longer depend on supplementary Unix groups.
    """
    return []


def apply_campaign_permissions(campaign_dir: Path) -> bool:
    """Legacy hook retained for callers.

    Campaign workspaces are intentionally left operator-owned.
    """
    log.debug("permissions: leaving campaign workspace operator-owned: %s", campaign_dir)
    return False


def clean_workspace_via_helper(campaign_dir: Path) -> bool:
    """rm -rf the campaign workspace via the root-privileged helper.

    This is mostly for compatibility with old workspaces that may still have
    stale agent-owned files. New campaign trees are operator-owned. Returns
    True if removed via the helper, False if provisioning isn't set up —
    caller should fall back to plain shutil.rmtree.
    """
    if not has_provisioned_users():
        return False
    _run_helper(["clean-workspace", str(campaign_dir.resolve())])
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
