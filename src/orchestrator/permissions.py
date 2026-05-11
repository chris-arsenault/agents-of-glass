"""Unix security model for the orchestrator.

The canonical campaign tree is operator-owned. Agents do not get direct
filesystem authority over `campaigns/`; they mutate durable state through
Glass. Each spawned actor runs as a dedicated Unix user inside an actor-owned
per-turn projection under `.glass-cwd/`.

The chown/chmod operations that require root are delegated to a small helper
script (`aog-permset`) installed by `scripts/provision-agents.sh` and invoked
via sudo. If provisioning hasn't been run, agents fall back to the operator
user and the projection remains current-user owned.
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

    The projection model no longer depends on the operator process having
    refreshed supplementary groups. Projections are grouped to the operator's
    primary group, and actor access is enforced by owner identity.
    """
    return []


def apply_campaign_permissions(campaign_dir: Path) -> bool:
    """Legacy hook retained for callers.

    Campaign workspaces are intentionally left operator-owned. The agent-facing
    permission boundary is the per-turn projection plus the Glass API.
    """
    log.debug("permissions: leaving campaign workspace operator-owned: %s", campaign_dir)
    return False


def apply_projection_permissions(
    projection_root: Path,
    *,
    actor_user: str | None = None,
) -> bool:
    """Make a per-turn projection actor-owned.

    `projection.py` decides which files are visible and which surfaces are
    writable. This helper enforces the Unix ownership model: the spawned actor
    owns the projected workspace, while `.glass-cwd` parents stay
    operator-owned traversal gates.
    """
    if not has_provisioned_users() or actor_user is None:
        _chmod_projection_parents(projection_root)
        return False
    try:
        _run_helper(["projection", str(projection_root.resolve()), actor_user])
        return True
    except RuntimeError:
        log.exception("permissions: projection helper failed; falling back to chmod")
        _chmod_projection_parents(projection_root)
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


def _chmod_projection_parents(projection_root: Path) -> None:
    for path in (projection_root.parent.parent, projection_root.parent):
        if not path.exists():
            continue
        try:
            os.chmod(path, 0o710)
        except OSError:
            log.debug("permissions: could not chmod projection parent %s", path)
