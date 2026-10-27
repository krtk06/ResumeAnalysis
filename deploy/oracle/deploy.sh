#!/usr/bin/env bash
set -euo pipefail

# Run on the Oracle VM after the first manual clone:
#   sudo mkdir -p /opt/resumeanalysis
#   sudo chown "$USER":"$USER" /opt/resumeanalysis
#   git clone https://github.com/krtk06/ResumeAnalysis.git /opt/resumeanalysis
#
# Then deploy from the repo root:
#   ./deploy/oracle/deploy.sh

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [[ ! -f deploy/oracle/.env ]]; then
  echo "Missing deploy/oracle/.env. Copy deploy/oracle/.env.example and fill it in." >&2
  exit 1
fi

git pull --ff-only

docker compose \
  --env-file deploy/oracle/.env \
  -f deploy/oracle/docker-compose.yml \
  up -d --build --remove-orphans

docker image prune -f >/dev/null 2>&1 || true

echo "Waiting for readiness..."
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/api/health/ready >/dev/null 2>&1; then
    echo "API is ready."
    exit 0
  fi
  sleep 2
done

echo "API did not become ready in time. Inspect:" >&2
echo "  docker compose --env-file deploy/oracle/.env -f deploy/oracle/docker-compose.yml logs --tail=100 api" >&2
exit 1
