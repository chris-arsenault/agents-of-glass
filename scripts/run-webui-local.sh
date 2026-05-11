#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/frontend"

WEB_API_HOST="${WEB_API_HOST:-0.0.0.0}"
WEB_API_PORT="${WEB_API_PORT:-26002}"
WEB_API_HEALTH_URL="${WEB_API_HEALTH_URL:-http://127.0.0.1:${WEB_API_PORT}}"
API_BASE_URL="${API_BASE_URL:-${AOG_WEB_API_PUBLIC_URL:-${VITE_API_BASE_URL:-}}}"
API_CONFIG="${API_CONFIG:-${GLASS_CONFIG:-${ROOT_DIR}/agents-of-glass.local.toml}}"
START_WEB_API="${START_WEB_API:-1}"
CAMPAIGN_ID="${CAMPAIGN_ID:-${VITE_DEFAULT_CAMPAIGN_ID:-test-7}}"
POLL_INTERVAL_MS="${POLL_INTERVAL_MS:-${VITE_POLL_INTERVAL_MS:-120000}}"
PLAYER_ORDER="${PLAYER_ORDER:-${VITE_PLAYER_ORDER:-tev,sumi,renno,kit}}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-26000}"
FRONTEND_DEV_SCRIPT="${FRONTEND_DEV_SCRIPT:-dev:vite}"

if ! command -v pnpm >/dev/null 2>&1; then
  echo "ERROR: pnpm is required to run the web UI." >&2
  exit 1
fi

if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
  pnpm --dir "${FRONTEND_DIR}" install --frozen-lockfile
fi

web_api_pid=""
frontend_pid=""

cleanup() {
  trap - EXIT INT TERM
  if [[ -n "${frontend_pid}" ]]; then
    kill "${frontend_pid}" 2>/dev/null || true
    wait "${frontend_pid}" 2>/dev/null || true
  fi
  if [[ -n "${web_api_pid}" ]]; then
    kill "${web_api_pid}" 2>/dev/null || true
    wait "${web_api_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

api_health_check() {
  python - "$1" "$2" <<'PY'
import json
import sys
import urllib.error
import urllib.request

label = sys.argv[1]
base_url = sys.argv[2].rstrip("/")
try:
    with urllib.request.urlopen(f"{base_url}/v1/health", timeout=1) as response:
        payload = json.loads(response.read().decode("utf-8"))
    print(f"{label}: {payload.get('status', 'unknown')} at {base_url}")
except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
    raise SystemExit(str(exc))
PY
}

if ! api_health_check "web API" "${WEB_API_HEALTH_URL}" >/dev/null 2>&1 && [[ "${START_WEB_API}" == "1" ]]; then
  web_api_command=(
    python -m cli.main web-api serve
    --host "${WEB_API_HOST}"
    --port "${WEB_API_PORT}"
  )
  if [[ -f "${API_CONFIG}" ]]; then
    web_api_command+=(--config "${API_CONFIG}")
  fi
  PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}" "${web_api_command[@]}" &
  web_api_pid="$!"
fi

deadline=$((SECONDS + 10))
until api_health_check "web API" "${WEB_API_HEALTH_URL}" >/dev/null 2>&1; do
  if [[ -n "${web_api_pid}" ]] && ! kill -0 "${web_api_pid}" 2>/dev/null; then
    echo "ERROR: web API process exited before becoming healthy." >&2
    exit 1
  fi
  if (( SECONDS >= deadline )); then
    echo "ERROR: web API health check failed at ${WEB_API_HEALTH_URL}/v1/health." >&2
    exit 1
  fi
  sleep 0.2
done
api_health_check "web API" "${WEB_API_HEALTH_URL}"

echo "web UI: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
echo "web API: http://${WEB_API_HOST}:${WEB_API_PORT}"
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
  echo "frontend API base: browser hostname on port ${WEB_API_PORT}"
fi

env \
  "${vite_env[@]}" \
  pnpm --dir "${FRONTEND_DIR}" run "${FRONTEND_DEV_SCRIPT}" \
    --host "${FRONTEND_HOST}" \
    --port "${FRONTEND_PORT}" \
    --strictPort &
frontend_pid="$!"
wait "${frontend_pid}"
