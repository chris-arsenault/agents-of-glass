#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/frontend"

API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-26001}"
API_HEALTH_URL="${API_HEALTH_URL:-http://127.0.0.1:${API_PORT}}"
API_BASE_URL="${API_BASE_URL:-${VITE_API_BASE_URL:-}}"
API_CONFIG="${API_CONFIG:-${GLASS_CONFIG:-${ROOT_DIR}/agents-of-glass.local.toml}}"
START_API="${START_API:-1}"
CAMPAIGN_ID="${CAMPAIGN_ID:-${VITE_DEFAULT_CAMPAIGN_ID:-test-7}}"
POLL_INTERVAL_MS="${POLL_INTERVAL_MS:-${VITE_POLL_INTERVAL_MS:-120000}}"
PLAYER_ORDER="${PLAYER_ORDER:-${VITE_PLAYER_ORDER:-tev,sumi,renno,kit}}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-26000}"

if ! command -v pnpm >/dev/null 2>&1; then
  echo "ERROR: pnpm is required to run the web UI." >&2
  exit 1
fi

if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
  pnpm --dir "${FRONTEND_DIR}" install --frozen-lockfile
fi

api_pid=""
frontend_pid=""

cleanup() {
  if [[ -n "${frontend_pid}" ]]; then
    kill "${frontend_pid}" 2>/dev/null || true
  fi
  if [[ -n "${api_pid}" ]]; then
    kill "${api_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

api_health_check() {
  python - "${API_HEALTH_URL}" <<'PY'
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
    raise SystemExit(str(exc))
PY
}

if ! api_health_check >/dev/null 2>&1 && [[ "${START_API}" == "1" ]]; then
  api_command=(
    python -m cli.main api serve
    --host "${API_HOST}"
    --port "${API_PORT}"
  )
  if [[ -f "${API_CONFIG}" ]]; then
    api_command+=(--config "${API_CONFIG}")
  fi
  PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}" "${api_command[@]}" &
  api_pid="$!"
fi

deadline=$((SECONDS + 10))
until api_health_check >/dev/null 2>&1; do
  if [[ -n "${api_pid}" ]] && ! kill -0 "${api_pid}" 2>/dev/null; then
    echo "ERROR: glass API process exited before becoming healthy." >&2
    exit 1
  fi
  if (( SECONDS >= deadline )); then
    echo "ERROR: glass API health check failed at ${API_HEALTH_URL}/v1/health." >&2
    exit 1
  fi
  sleep 0.2
done
api_health_check

echo "web UI: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
echo "glass API: http://${API_HOST}:${API_PORT}"
echo "campaign: ${CAMPAIGN_ID}"
echo "players: ${PLAYER_ORDER}"

vite_env=(
  VITE_DEFAULT_CAMPAIGN_ID="${CAMPAIGN_ID}"
  VITE_POLL_INTERVAL_MS="${POLL_INTERVAL_MS}"
  VITE_PLAYER_ORDER="${PLAYER_ORDER}"
)
if [[ -n "${API_BASE_URL}" ]]; then
  vite_env+=(VITE_API_BASE_URL="${API_BASE_URL}")
else
  echo "frontend API base: browser hostname on port ${API_PORT}"
fi

env \
  "${vite_env[@]}" \
  pnpm --dir "${FRONTEND_DIR}" exec vite \
    --host "${FRONTEND_HOST}" \
    --port "${FRONTEND_PORT}" \
    --strictPort &
frontend_pid="$!"
wait "${frontend_pid}"
