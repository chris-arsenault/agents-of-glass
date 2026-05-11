#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/frontend"

API_BASE_URL="${API_BASE_URL:-${VITE_API_BASE_URL:-http://127.0.0.1:8765}}"
CAMPAIGN_ID="${CAMPAIGN_ID:-${VITE_DEFAULT_CAMPAIGN_ID:-test-7}}"
POLL_INTERVAL_MS="${POLL_INTERVAL_MS:-${VITE_POLL_INTERVAL_MS:-120000}}"
PLAYER_ORDER="${PLAYER_ORDER:-${VITE_PLAYER_ORDER:-tev,sumi,renno,kit}}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

if ! command -v pnpm >/dev/null 2>&1; then
  echo "ERROR: pnpm is required to run the web UI." >&2
  exit 1
fi

if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
  pnpm --dir "${FRONTEND_DIR}" install --frozen-lockfile
fi

python - "${API_BASE_URL}" <<'PY'
import json
import sys
import urllib.error
import urllib.request

base_url = sys.argv[1].rstrip("/")
try:
    with urllib.request.urlopen(f"{base_url}/v1/health", timeout=1) as response:
        payload = json.loads(response.read().decode("utf-8"))
    print(f"glass API: {payload.get('status', 'unknown')} at {base_url}")
except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
    print(
        "WARNING: glass API health check failed at "
        f"{base_url}/v1/health: {exc}",
        file=sys.stderr,
    )
    print(
        "The script will still start the frontend; it does not start or modify "
        "the glass API process.",
        file=sys.stderr,
    )
PY

echo "web UI: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
echo "campaign: ${CAMPAIGN_ID}"
echo "players: ${PLAYER_ORDER}"

exec env \
  VITE_API_BASE_URL="${API_BASE_URL}" \
  VITE_DEFAULT_CAMPAIGN_ID="${CAMPAIGN_ID}" \
  VITE_POLL_INTERVAL_MS="${POLL_INTERVAL_MS}" \
  VITE_PLAYER_ORDER="${PLAYER_ORDER}" \
  pnpm --dir "${FRONTEND_DIR}" exec vite \
    --host "${FRONTEND_HOST}" \
    --port "${FRONTEND_PORT}" \
    --strictPort
