#!/usr/bin/env bash
#
# Build, push, deploy, smoke-test, and roll back the Resume Analysis API on
# Google Cloud Run.
#
# Usage:
#   cp deploy/cloudrun/.env.example deploy/cloudrun/.env
#   $EDITOR deploy/cloudrun/.env
#   ./deploy/cloudrun/bootstrap.sh     # once
#   ./deploy/cloudrun/deploy.sh
#
# The script uses the current gcloud account. In GitHub Actions, the workflow
# authenticates with Workload Identity Federation and then runs this script.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ -f "$ROOT/deploy/cloudrun/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/deploy/cloudrun/.env"
  set +a
fi

die() {
  echo "error: $*" >&2
  exit 1
}

info() {
  echo "[cloudrun] $*" >&2
}

warn() {
  echo "[cloudrun] warning: $*" >&2
}

command -v gcloud >/dev/null 2>&1 || die "gcloud is not installed."
command -v docker >/dev/null 2>&1 || die "docker is not installed."
command -v curl >/dev/null 2>&1 || die "curl is not installed."

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -1 || true)"
if [[ -z "${CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE:-}" && -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" && -z "$ACTIVE_ACCOUNT" ]]; then
  die "No active gcloud account. Run: gcloud auth login"
fi

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  die "PROJECT_ID is not set. Set it in deploy/cloudrun/.env or run: gcloud config set project YOUR_PROJECT_ID"
fi

REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-resume-analysis-api}"
REPO_NAME="${REPO_NAME:-resume-analysis}"
RUNTIME_SERVICE_ACCOUNT="${RUNTIME_SERVICE_ACCOUNT:-resume-api-runtime@$PROJECT_ID.iam.gserviceaccount.com}"
SECRET_NAME="${SECRET_NAME:-opencode-api-key}"
CORS_ORIGINS="${CORS_ORIGINS:-https://resume-analysis-ruddy.vercel.app}"
CORS_ORIGIN_REGEX="${CORS_ORIGIN_REGEX:-https://resume-analysis-[a-z0-9-]+\.vercel\.app}"
LLM_ENABLED="${LLM_ENABLED:-false}"
RATE_LIMIT_PER_HOUR="${RATE_LIMIT_PER_HOUR:-10}"
RATE_LIMIT_PER_DAY="${RATE_LIMIT_PER_DAY:-50}"
LLM_MAX_REQUESTS_PER_DAY="${LLM_MAX_REQUESTS_PER_DAY:-50}"
LLM_MONTHLY_ALLOWANCE_USD="${LLM_MONTHLY_ALLOWANCE_USD:-50}"

case "$LLM_ENABLED" in
  true|false) ;;
  *) die "LLM_ENABLED must be true or false, got: $LLM_ENABLED" ;;
esac

gcloud config set project "$PROJECT_ID" >/dev/null

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
DEFAULT_HOST="$SERVICE_NAME-$PROJECT_NUMBER.$REGION.run.app"
LEGACY_HOST="$SERVICE_NAME-$PROJECT_NUMBER.a.run.app"
EXISTING_URL="$(gcloud run services describe "$SERVICE_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format='value(status.url)' 2>/dev/null || true)"
EXISTING_HOST=""
if [[ -n "$EXISTING_URL" ]]; then
  EXISTING_HOST="${EXISTING_URL#https://}"
  EXISTING_HOST="${EXISTING_HOST%%/*}"
fi
TRUSTED_HOSTS="${TRUSTED_HOSTS:-$DEFAULT_HOST,$LEGACY_HOST,localhost,127.0.0.1,[::1]}"
if [[ -n "$EXISTING_HOST" && ",$TRUSTED_HOSTS," != *",$EXISTING_HOST,"* ]]; then
  TRUSTED_HOSTS="$EXISTING_HOST,$TRUSTED_HOSTS"
fi

PREV_REVISION="$(gcloud run services describe "$SERVICE_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format='value(status.latestReadyRevisionName)' 2>/dev/null || true)"

HAS_SECRET="false"
if gcloud secrets versions list "$SECRET_NAME" \
  --project="$PROJECT_ID" \
  --limit=1 \
  --format='value(name)' 2>/dev/null | grep -q .; then
  HAS_SECRET="true"
fi

if [[ "$LLM_ENABLED" == "true" && "$HAS_SECRET" != "true" ]]; then
  die "LLM_ENABLED=true but $SECRET_NAME has no version. Add one with: gcloud secrets versions add $SECRET_NAME --data-file=/path/to/key"
fi

TAG="${TAG:-$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
IMAGE="${IMAGE:-$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$SERVICE_NAME:$TAG}"

if [[ "${SKIP_BUILD:-false}" != "true" ]]; then
  BUILD_ARGS=(--build-arg PRELOAD_MODEL=1 -t "$IMAGE")
  MACHINE="$(uname -m)"
  if [[ "$MACHINE" == "arm64" || "$MACHINE" == "aarch64" ]]; then
    BUILD_ARGS=(--platform linux/amd64 "${BUILD_ARGS[@]}")
  fi
  info "Building $IMAGE"
  docker build "${BUILD_ARGS[@]}" "$ROOT/backend"
else
  info "Skipping image build (SKIP_BUILD=true)"
fi

if [[ "${SKIP_PUSH:-false}" != "true" ]]; then
  info "Pushing image to Artifact Registry"
  gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet >/dev/null
  docker push "$IMAGE"
else
  info "Skipping image push (SKIP_PUSH=true)"
fi

ENV_FILE="$(mktemp)"
trap 'rm -f "$ENV_FILE"' EXIT

export ENVIRONMENT=production
export LOG_LEVEL=INFO
export EMBEDDER_BACKEND=fastembed
export EMBEDDER_CACHE_DIR=/models/fastembed
export HF_HOME=/models
export HF_HUB_OFFLINE=1
export TRUST_PROXY_HEADERS=true
export TRUSTED_HOSTS
export CORS_ORIGINS
export CORS_ORIGIN_REGEX
export MAX_UPLOAD_MB=10
export MAX_PAGES=10
export MAX_JD_CHARS=10000
export RATE_LIMIT_PER_HOUR
export RATE_LIMIT_PER_DAY
export REQUIRE_CONSENT=true
export LLM_ENABLED
export LLM_PROVIDER=opencode_go
export OPENCODE_BASE_URL=https://opencode.ai/inference/go/openai/v1
export OPENCODE_MODEL=beam-free
export OPENCODE_FALLBACK_MODEL=glm-5.3-flash
export OPENCODE_USER_AGENT=resume-analysis/2.0
export OPENCODE_ALLOW_PAID_FALLBACK=false
export LLM_TIMEOUT_SECONDS=30
export LLM_MAX_RETRIES=1
export LLM_MAX_REQUESTS_PER_DAY
export LLM_MONTHLY_ALLOWANCE_USD

python3 - "$ENV_FILE" <<'PY'
import json
import os
import sys

keys = [
    "ENVIRONMENT",
    "LOG_LEVEL",
    "EMBEDDER_BACKEND",
    "EMBEDDER_CACHE_DIR",
    "HF_HOME",
    "HF_HUB_OFFLINE",
    "TRUST_PROXY_HEADERS",
    "TRUSTED_HOSTS",
    "CORS_ORIGINS",
    "CORS_ORIGIN_REGEX",
    "MAX_UPLOAD_MB",
    "MAX_PAGES",
    "MAX_JD_CHARS",
    "RATE_LIMIT_PER_HOUR",
    "RATE_LIMIT_PER_DAY",
    "REQUIRE_CONSENT",
    "LLM_ENABLED",
    "LLM_PROVIDER",
    "OPENCODE_BASE_URL",
    "OPENCODE_MODEL",
    "OPENCODE_FALLBACK_MODEL",
    "OPENCODE_USER_AGENT",
    "OPENCODE_ALLOW_PAID_FALLBACK",
    "LLM_TIMEOUT_SECONDS",
    "LLM_MAX_RETRIES",
    "LLM_MAX_REQUESTS_PER_DAY",
    "LLM_MONTHLY_ALLOWANCE_USD",
]

with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump({key: os.environ[key] for key in keys}, handle, indent=2)
PY

DEPLOY_ARGS=(
  run deploy "$SERVICE_NAME"
  --image "$IMAGE"
  --region "$REGION"
  --project "$PROJECT_ID"
  --platform managed
  --memory 1Gi
  --cpu 1
  --port 8080
  --min-instances 0
  --max-instances 1
  --concurrency 4
  --timeout 90
  --cpu-boost
  --deploy-health-check
  --startup-probe "httpGet.path=/api/health/ready,httpGet.port=8080,initialDelaySeconds=5,periodSeconds=5,failureThreshold=24,timeoutSeconds=3"
  --liveness-probe "httpGet.path=/api/health,httpGet.port=8080,initialDelaySeconds=0,periodSeconds=30,failureThreshold=3,timeoutSeconds=5"
  --allow-unauthenticated
  --service-account "$RUNTIME_SERVICE_ACCOUNT"
  --env-vars-file "$ENV_FILE"
  --labels "app=resume-analysis,managed-by=cloudrun-deploy"
  --quiet
)

if [[ "$HAS_SECRET" == "true" ]]; then
  DEPLOY_ARGS+=(--set-secrets "OPENCODE_API_KEY=$SECRET_NAME:latest")
fi

info "Deploying $SERVICE_NAME to Cloud Run in $REGION"
gcloud "${DEPLOY_ARGS[@]}"

NEW_REVISION="$(gcloud run services describe "$SERVICE_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format='value(status.latestReadyRevisionName)')"
SERVICE_URL="$(gcloud run services describe "$SERVICE_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format='value(status.url)')"

rollback() {
  if [[ -n "$PREV_REVISION" && "$PREV_REVISION" != "$NEW_REVISION" ]]; then
    warn "Smoke test failed; shifting 100% of traffic back to $PREV_REVISION"
    gcloud run services update-traffic "$SERVICE_NAME" \
      --region="$REGION" \
      --project="$PROJECT_ID" \
      --to-revisions="$PREV_REVISION=100" \
      --quiet || warn "Rollback failed. Inspect the service manually."
  else
    warn "No previous revision is available to roll back to."
  fi
}

info "Waiting for $SERVICE_URL/api/health/ready"
READY="false"
READY_JSON=""
for _ in $(seq 1 60); do
  if READY_JSON="$(curl -fsS "$SERVICE_URL/api/health/ready" 2>/dev/null)"; then
    if grep -q '"ready":true' <<<"$READY_JSON"; then
      READY="true"
      break
    fi
  fi
  sleep 2
done

if [[ "$READY" != "true" ]]; then
  warn "Readiness check failed: $READY_JSON"
  gcloud run services logs read "$SERVICE_NAME" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --limit=50 2>/dev/null || true
  rollback
  exit 1
fi

PRIMARY_CORS="${CORS_ORIGINS%%,*}"
info "Checking CORS for $PRIMARY_CORS"
CORS_HEADERS="$(curl -fsS -D - -o /dev/null -X OPTIONS "$SERVICE_URL/api/analyze" \
  -H "Origin: $PRIMARY_CORS" \
  -H "Access-Control-Request-Method: POST" 2>/dev/null || true)"
if ! grep -qi '^access-control-allow-origin:' <<<"$CORS_HEADERS"; then
  warn "CORS preflight did not return Access-Control-Allow-Origin"
  rollback
  exit 1
fi

info "Running sample PDF + job brief analysis"
if ! ANALYZE_RESPONSE="$(curl -fsS "$SERVICE_URL/api/analyze" \
  -F "file=@$ROOT/frontend/public/samples/sample-resume.pdf" \
  -F "target_role=Software Engineer" \
  -F "job_description=<$ROOT/frontend/public/samples/sample-jd.txt" \
  -F "consent=false" 2>/dev/null)"; then
  warn "Sample analysis request failed"
  rollback
  exit 1
fi

if ! SMOKE_OUTPUT="$(python3 -c 'import json, sys; data=json.load(sys.stdin); assert data.get("score") is not None, "missing score"; print("smoke score:", data["score"], "(" + str(len(data.get("evidence", []))) + " citations)")' <<<"$ANALYZE_RESPONSE" 2>&1)"; then
  warn "Sample analysis response failed validation: $SMOKE_OUTPUT"
  rollback
  exit 1
fi
info "$SMOKE_OUTPUT"

cat <<EOF

Deployed successfully.

Service:  $SERVICE_NAME
Revision: $NEW_REVISION
URL:      $SERVICE_URL

Set the Vercel production environment variable and redeploy the frontend:

  cd frontend
  vercel env add VITE_API_URL production   # $SERVICE_URL
  vercel --prod

EOF
