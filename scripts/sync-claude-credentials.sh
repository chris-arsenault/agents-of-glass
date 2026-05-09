#!/usr/bin/env bash
# sync-claude-credentials.sh
#
# Copy the operator's ~/.claude/.credentials.json (and minimal config dir)
# to each aog-<player> user's home, set ownership and mode correctly so
# the player Unix user can authenticate to claude.
#
# Run as root:
#   sudo bash scripts/sync-claude-credentials.sh
#
# Idempotent: re-running just refreshes the copy if the source has changed.
# The DM doesn't need this — the DM runs as the operator.

set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
    echo "error: must be run as root (use sudo)." >&2
    exit 1
fi

OPERATOR="${SUDO_USER:-${1:-}}"
if [[ -z "$OPERATOR" ]]; then
    echo "error: cannot determine operator user. Run via sudo, or pass username as arg 1." >&2
    exit 1
fi

OPERATOR_HOME=$(getent passwd "$OPERATOR" | cut -d: -f6)
if [[ -z "$OPERATOR_HOME" || ! -d "$OPERATOR_HOME" ]]; then
    echo "error: cannot resolve home dir for $OPERATOR" >&2
    exit 1
fi

SOURCE="$OPERATOR_HOME/.claude/.credentials.json"
if [[ ! -f "$SOURCE" ]]; then
    echo "error: source not found at $SOURCE" >&2
    echo "       Log in as $OPERATOR and run \`claude\` once to create credentials." >&2
    exit 1
fi

PLAYER_USERS=(aog-tev aog-sumi aog-renno aog-kit)

for user in "${PLAYER_USERS[@]}"; do
    if ! id "$user" > /dev/null 2>&1; then
        echo "skip: user $user does not exist (run scripts/provision-agents.sh first)"
        continue
    fi

    home_dir=$(getent passwd "$user" | cut -d: -f6)
    if [[ -z "$home_dir" ]]; then
        echo "skip: no home dir for $user" >&2
        continue
    fi

    install -d -o "$user" -g "$user" -m 0700 "$home_dir/.claude"
    install -o "$user" -g "$user" -m 0600 "$SOURCE" "$home_dir/.claude/.credentials.json"
    echo "synced -> $home_dir/.claude/.credentials.json (owner $user, mode 0600)"
done

echo
echo "Done. Player users now share the operator's claude credentials."
echo "Re-run this script after re-authenticating claude as $OPERATOR."
