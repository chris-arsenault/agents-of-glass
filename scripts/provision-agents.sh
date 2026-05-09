#!/usr/bin/env bash
# provision-agents.sh — operator-run setup for the Agents of Glass Unix
# security model. Run once on a fresh dev machine:
#
#   sudo bash scripts/provision-agents.sh
#
# Idempotent: safe to re-run.
#
# Creates Unix users for each player agent, sets up a shared group and per-
# player private groups, adds the operator (dev) to all relevant groups so
# the DM (running as dev) can read player content via group membership,
# installs a sudoers rule allowing the operator to spawn player invocations
# without password prompts, and installs the aog-permset helper that the
# orchestrator uses to set ownership on freshly-created campaign workspaces.

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

PLAYER_USERS=(aog-tev aog-sumi aog-renno aog-kit)
SHARED_GROUP="aog-agents"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER_SOURCE="$REPO_ROOT/scripts/aog-permset"
HELPER_INSTALLED="/usr/local/bin/aog-permset"
SUDOERS_FILE="/etc/sudoers.d/agents-of-glass"

if [[ ! -f "$HELPER_SOURCE" ]]; then
    echo "error: $HELPER_SOURCE not found." >&2
    exit 1
fi

# --- shared group ---

if ! getent group "$SHARED_GROUP" > /dev/null; then
    echo "creating group $SHARED_GROUP"
    groupadd --system "$SHARED_GROUP"
fi

# --- player users (each gets their own primary group of the same name) ---

for user in "${PLAYER_USERS[@]}"; do
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
# operator must be in: aog-agents (for shared content) and each player's
# primary group (so DM can read player private journals/drafts/notes).

for grp in "$SHARED_GROUP" "${PLAYER_USERS[@]}"; do
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
#   1. spawn claude as a player user (sudo -u aog-<player>)
#   2. invoke the permset helper to chown/chmod new campaign workspaces

PLAYER_LIST="$(IFS=,; echo "${PLAYER_USERS[*]}")"
TMP_SUDOERS="$(mktemp)"
trap 'rm -f "$TMP_SUDOERS"' EXIT
cat > "$TMP_SUDOERS" <<EOF
# Created by scripts/provision-agents.sh
# Allows the operator to spawn player agents and apply campaign workspace
# permissions without password prompts.

Defaults:$OPERATOR env_keep += "ANTHROPIC_API_KEY ANTHROPIC_BASE_URL CLAUDE_API_KEY GLASS_* AOG_* SULION_*"
$OPERATOR ALL=($PLAYER_LIST) NOPASSWD: SETENV: ALL
$OPERATOR ALL=(root) NOPASSWD: $HELPER_INSTALLED
EOF

# Validate before installing
visudo -c -f "$TMP_SUDOERS" > /dev/null

install -o root -g root -m 0440 "$TMP_SUDOERS" "$SUDOERS_FILE"
echo "installed $SUDOERS_FILE"

# --- summary ---

echo
echo "Provisioning complete."
echo "  shared group: $SHARED_GROUP"
echo "  player users: ${PLAYER_USERS[*]}"
echo "  operator:     $OPERATOR (added to aog-agents and all player groups)"
echo "  helper:       $HELPER_INSTALLED"
echo "  sudoers:      $SUDOERS_FILE"
echo
echo "NOTE: if $OPERATOR is currently logged in, group membership changes"
echo "won't take effect until they log out and back in (or run 'newgrp')."
echo "Verify with: groups $OPERATOR"
