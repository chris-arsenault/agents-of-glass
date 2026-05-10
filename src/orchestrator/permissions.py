"""Unix security model for the orchestrator.

Each player agent runs as a dedicated Unix user (`aog-tev`, `aog-sumi`,
`aog-renno`, `aog-kit`); the DM runs as the current operator user.
Filesystem access is gated by group-based chmod on the campaign workspace,
applied once at campaign creation. There is NO per-turn permission ritual
— per-turn artifact directories inherit perms from their parent (`turns/`)
via setgid.

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


def missing_operator_groups() -> list[str]:
    """Supplementary Unix groups the current operator process still lacks.

    Provisioning can add the operator to `aog-agents` and each player group,
    but an already-running login shell does not pick those groups up. In that
    state campaign bootstrap appears to work until the DM/operator tries to
    read shared or player-authored files and gets EACCES.
    """
    if not has_provisioned_users():
        return []

    current_gids = set(os.getgroups())
    current_gids.add(os.getegid())
    current_groups: set[str] = set()
    for gid in current_gids:
        try:
            current_groups.add(grp.getgrgid(gid).gr_name)
        except KeyError:
            continue

    required = [SHARED_GROUP, *PLAYER_USERS.values()]
    return [name for name in required if name not in current_groups]


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


def clean_workspace_via_helper(campaign_dir: Path) -> bool:
    """rm -rf the campaign workspace via the root-privileged helper.

    Needed because subdirs under `players/<id>/` are owned by aog-<player>
    with restrictive perms; the orchestrator (running as the operator)
    can't traverse or delete them without root. Returns True if removed
    via the helper, False if provisioning isn't set up — caller should
    fall back to plain shutil.rmtree.
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
