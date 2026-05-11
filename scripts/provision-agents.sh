#!/usr/bin/env bash
# provision-agents.sh — operator-run setup for the Agents of Glass Unix
# security model. Run once on a fresh dev machine:
#
#   sudo bash scripts/provision-agents.sh
#
# Idempotent: safe to re-run.
#
# Creates Unix users for each executing agent, sets up a shared group and per-
# actor private groups, adds the operator (dev) to all relevant groups so
# the operator can inspect content via group membership,
# installs a sudoers rule allowing the operator to spawn agent invocations
# without password prompts, installs the aog-permset helper that the
# orchestrator uses for actor-owned projections, and grants the agent users
# read/traverse access to the Glass Frontier lore repository when present.

set -euo pipefail

# --- preflight ---

if [[ "$(id -u)" -ne 0 ]]; then
    echo "error: this script must be run as root (use sudo)." >&2
    exit 1
fi

OPERATOR="${SUDO_USER:-${1:-}}"
if [[ -z "$OPERATOR" ]]; then
    echo "error: cannot determine operator user. Run via sudo, or pass the username as arg 1." >&2
    exit 1
fi
if ! id "$OPERATOR" > /dev/null 2>&1; then
    echo "error: operator user $OPERATOR does not exist." >&2
    exit 1
fi

DM_USER="aog-mara"
PLAYER_USERS=(aog-tev aog-sumi aog-renno aog-kit)
AGENT_USERS=("$DM_USER" "${PLAYER_USERS[@]}")
SHARED_GROUP="aog-agents"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER_SOURCE="$REPO_ROOT/scripts/aog-permset"
HELPER_INSTALLED="/usr/local/bin/aog-permset"
SUDOERS_FILE="/etc/sudoers.d/agents-of-glass"
LORE_ROOT="${AOG_LORE_ROOT:-$REPO_ROOT/../the-glass-frontier-lore}"

if [[ ! -f "$HELPER_SOURCE" ]]; then
    echo "error: $HELPER_SOURCE not found." >&2
    exit 1
fi

# --- shared group ---

if ! getent group "$SHARED_GROUP" > /dev/null; then
    echo "creating group $SHARED_GROUP"
    groupadd --system "$SHARED_GROUP"
fi

# --- agent users (each gets their own primary group of the same name) ---

for user in "${AGENT_USERS[@]}"; do
    if ! id "$user" > /dev/null 2>&1; then
        echo "creating user $user (with primary group $user)"
        useradd --system --create-home --shell /bin/bash "$user"
    fi
    if ! id -nG "$user" | tr ' ' '\n' | grep -qx "$SHARED_GROUP"; then
        echo "adding $user to $SHARED_GROUP"
        usermod -aG "$SHARED_GROUP" "$user"
    fi
done

# --- operator memberships ---
# operator must be in: aog-agents (for shared content) and each agent's
# primary group (so the operator can inspect private journals/drafts/notes).

for grp in "$SHARED_GROUP" "${AGENT_USERS[@]}"; do
    if ! id -nG "$OPERATOR" | tr ' ' '\n' | grep -qx "$grp"; then
        echo "adding $OPERATOR to group $grp"
        usermod -aG "$grp" "$OPERATOR"
    fi
done

# --- install permset helper ---

echo "installing $HELPER_INSTALLED"
install -o root -g root -m 0755 "$HELPER_SOURCE" "$HELPER_INSTALLED"

# --- sudoers ---
# The operator needs two privileges:
#   1. spawn claude as an isolated agent user (sudo -u aog-<agent>)
#   2. invoke the permset helper to chown/chmod per-turn projections

AGENT_LIST="$(IFS=,; echo "${AGENT_USERS[*]}")"
TMP_SUDOERS="$(mktemp)"
trap 'rm -f "$TMP_SUDOERS"' EXIT
cat > "$TMP_SUDOERS" <<EOF
# Created by scripts/provision-agents.sh
# Allows the operator to spawn isolated agents and apply actor projection
# ownership without password prompts.

Defaults:$OPERATOR env_keep += "ANTHROPIC_API_KEY ANTHROPIC_BASE_URL CLAUDE_API_KEY GLASS_* AOG_* SULION_*"
$OPERATOR ALL=($AGENT_LIST) NOPASSWD: SETENV: ALL
$OPERATOR ALL=(root) NOPASSWD: $HELPER_INSTALLED
EOF

# Validate before installing
visudo -c -f "$TMP_SUDOERS" > /dev/null

install -o root -g root -m 0440 "$TMP_SUDOERS" "$SUDOERS_FILE"
echo "installed $SUDOERS_FILE"

# --- world-bible lore access ---

if [[ -d "$LORE_ROOT" ]]; then
    echo "granting $SHARED_GROUP read access to $LORE_ROOT"
    chown -R "$OPERATOR:$SHARED_GROUP" "$LORE_ROOT"
    find "$LORE_ROOT" -type d -exec chmod 0750 {} +
    find "$LORE_ROOT" -type f -exec chmod 0640 {} +
fi

# --- summary ---

echo
echo "Provisioning complete."
echo "  shared group: $SHARED_GROUP"
echo "  dm user:      $DM_USER"
echo "  player users: ${PLAYER_USERS[*]}"
echo "  operator:     $OPERATOR (added to aog-agents and all agent groups)"
echo "  helper:       $HELPER_INSTALLED"
echo "  sudoers:      $SUDOERS_FILE"
if [[ -d "$LORE_ROOT" ]]; then
    echo "  lore access:  $LORE_ROOT (group-readable by $SHARED_GROUP)"
else
    echo "  lore access:  skipped; not found at $LORE_ROOT"
fi
echo
echo "NOTE: bootstrap does not require a refreshed login shell; projections are"
echo "grouped to the operator's primary group. Re-login is only needed if you"
echo "want shell commands to see the supplementary groups directly."
echo "Verify provisioned groups with: groups $OPERATOR"
