#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT_DIR}/infrastructure/terraform"

STATE_BUCKET="${STATE_BUCKET:-tfstate-559098897826}"
STATE_REGION="${STATE_REGION:-us-east-1}"

echo "==> Building Rust Lambda"
(cd "${ROOT_DIR}/backend" && cargo lambda build --release --bin viewer-api)

echo ""
echo "==> Building frontend"
cd "${ROOT_DIR}/frontend"
corepack enable 2>/dev/null || true
pnpm install --frozen-lockfile
pnpm run build
cd "${ROOT_DIR}"

echo ""
echo "==> Running database migrations"
db-migrate

echo ""
echo "==> Running Terraform"
terraform -chdir="${TF_DIR}" init -reconfigure \
  -backend-config="bucket=${STATE_BUCKET}" \
  -backend-config="region=${STATE_REGION}" \
  -backend-config="use_lockfile=true"

terraform -chdir="${TF_DIR}" apply -auto-approve

echo ""
echo "==> Deployment complete!"
echo "Frontend: $(terraform -chdir="${TF_DIR}" output -raw site_url)"
echo "API:      $(terraform -chdir="${TF_DIR}" output -raw api_url)"
echo "Mirror:   $(terraform -chdir="${TF_DIR}" output -raw campaign_mirror_bucket_name)"
