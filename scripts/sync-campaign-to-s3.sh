#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat >&2 <<'EOF'
usage: scripts/sync-campaign-to-s3.sh <campaign-root> [campaign-sync args...]

Environment:
  CAMPAIGN_BUCKET                 S3 mirror bucket. Defaults to agents-of-glass-campaign-mirror.
  CAMPAIGN_PREFIX                 S3 key prefix. Defaults to campaigns.
  CAMPAIGN_PUBLISHER_ROLE_ARN     Optional restricted role ARN to assume before publishing.
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

CAMPAIGN_ROOT="$1"
shift

CAMPAIGN_BUCKET="${CAMPAIGN_BUCKET:-agents-of-glass-campaign-mirror}"
CAMPAIGN_PREFIX="${CAMPAIGN_PREFIX:-campaigns}"

if [[ -n "${CAMPAIGN_PUBLISHER_ROLE_ARN:-}" ]]; then
  command -v aws >/dev/null || {
    echo "aws CLI is required when CAMPAIGN_PUBLISHER_ROLE_ARN is set" >&2
    exit 1
  }
  command -v jq >/dev/null || {
    echo "jq is required when CAMPAIGN_PUBLISHER_ROLE_ARN is set" >&2
    exit 1
  }

  CREDS_JSON="$(
    aws sts assume-role \
      --role-arn "${CAMPAIGN_PUBLISHER_ROLE_ARN}" \
      --role-session-name "agents-of-glass-campaign-sync"
  )"
  export AWS_ACCESS_KEY_ID
  export AWS_SECRET_ACCESS_KEY
  export AWS_SESSION_TOKEN
  AWS_ACCESS_KEY_ID="$(jq -r '.Credentials.AccessKeyId' <<<"${CREDS_JSON}")"
  AWS_SECRET_ACCESS_KEY="$(jq -r '.Credentials.SecretAccessKey' <<<"${CREDS_JSON}")"
  AWS_SESSION_TOKEN="$(jq -r '.Credentials.SessionToken' <<<"${CREDS_JSON}")"
fi

cargo run \
  --manifest-path "${ROOT_DIR}/backend/Cargo.toml" \
  --bin campaign-sync \
  -- \
  --campaign-root "${CAMPAIGN_ROOT}" \
  --bucket "${CAMPAIGN_BUCKET}" \
  --prefix "${CAMPAIGN_PREFIX}" \
  "$@"
