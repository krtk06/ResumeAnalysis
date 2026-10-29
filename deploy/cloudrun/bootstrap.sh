#!/usr/bin/env bash
#
# One-time Google Cloud bootstrap for the Resume Analysis API on Cloud Run.
#
# Usage:
#   cp deploy/cloudrun/.env.example deploy/cloudrun/.env
#   $EDITOR deploy/cloudrun/.env
#   ./deploy/cloudrun/bootstrap.sh
#
# Requires a billing-enabled GCP project and an account with permission to
# enable APIs, create service accounts, and grant IAM roles (Owner or Editor).
#
# The script is idempotent: existing APIs, repositories, service accounts,
# secrets, and identity pools are reused.

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

command -v gcloud >/dev/null 2>&1 || die "gcloud is not installed. Install the Google Cloud CLI first."

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -1 || true)"
if [[ -z "$ACTIVE_ACCOUNT" ]]; then
  die "No active gcloud account. Run: gcloud auth login"
fi

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  die "PROJECT_ID is not set. Set it in deploy/cloudrun/.env or run: gcloud config set project YOUR_PROJECT_ID"
fi

REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-resume-analysis-api}"
REPO_NAME="${REPO_NAME:-resume-analysis}"
RUNTIME_SA_NAME="${RUNTIME_SA_NAME:-resume-api-runtime}"
DEPLOYER_SA_NAME="${DEPLOYER_SA_NAME:-cloudrun-deployer}"
SECRET_NAME="${SECRET_NAME:-opencode-api-key}"
GITHUB_REPO="${GITHUB_REPO:-krtk06/ResumeAnalysis}"
GITHUB_BRANCH="${GITHUB_BRANCH:-main}"
WIF_POOL_ID="${WIF_POOL_ID:-github}"
WIF_PROVIDER_ID="${WIF_PROVIDER_ID:-github-actions}"
CORS_ORIGINS="${CORS_ORIGINS:-https://resume-analysis-ruddy.vercel.app}"
CORS_ORIGIN_REGEX="${CORS_ORIGIN_REGEX:-https://resume-analysis-[a-z0-9-]+\.vercel\.app}"
BILLING_ACCOUNT_ID="${BILLING_ACCOUNT_ID:-}"
BUDGET_NAME="${BUDGET_NAME:-$SERVICE_NAME-budget}"
BUDGET_AMOUNT="${BUDGET_AMOUNT:-5USD}"

gcloud config set project "$PROJECT_ID" >/dev/null

BILLING_ENABLED="$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingEnabled)' 2>/dev/null || true)"
if [[ "$BILLING_ENABLED" != "True" && "$BILLING_ENABLED" != "true" ]]; then
  die "Billing is not enabled (or cannot be verified) for $PROJECT_ID. Enable billing in the Google Cloud console first."
fi

info "Enabling required APIs in $PROJECT_ID"
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  cloudbilling.googleapis.com \
  billingbudgets.googleapis.com \
  cloudresourcemanager.googleapis.com \
  serviceusage.googleapis.com \
  --project "$PROJECT_ID" \
  --quiet

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

if ! gcloud artifacts repositories describe "$REPO_NAME" \
  --location="$REGION" \
  --project="$PROJECT_ID" >/dev/null 2>&1; then
  info "Creating Artifact Registry repository $REPO_NAME in $REGION"
  gcloud artifacts repositories create "$REPO_NAME" \
    --repository-format=docker \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --description="Resume analysis API container images" \
    >/dev/null
fi

create_service_account() {
  local name="$1"
  local display_name="$2"
  local email="$name@$PROJECT_ID.iam.gserviceaccount.com"

  if ! gcloud iam service-accounts describe "$email" --project="$PROJECT_ID" >/dev/null 2>&1; then
    info "Creating service account $email"
    gcloud iam service-accounts create "$name" \
      --display-name="$display_name" \
      --project="$PROJECT_ID" \
      >/dev/null
  fi

  printf '%s' "$email"
}

DEPLOYER_SA="$(create_service_account "$DEPLOYER_SA_NAME" "Cloud Run deployer")"
RUNTIME_SA="$(create_service_account "$RUNTIME_SA_NAME" "Cloud Run runtime")"

grant_project_role() {
  local member="$1"
  local role="$2"

  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$member" \
    --role="$role" \
    --condition=None \
    --project="$PROJECT_ID" \
    --quiet \
    >/dev/null
}

info "Granting deployer roles"
grant_project_role "$DEPLOYER_SA" "roles/run.admin"
grant_project_role "$DEPLOYER_SA" "roles/artifactregistry.writer"

info "Granting runtime roles"
grant_project_role "$RUNTIME_SA" "roles/logging.logWriter"
grant_project_role "$RUNTIME_SA" "roles/monitoring.metricWriter"

gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" \
  --member="serviceAccount:$DEPLOYER_SA" \
  --role="roles/iam.serviceAccountUser" \
  --project="$PROJECT_ID" \
  --quiet \
  >/dev/null

SERVICE_AGENT="service-$PROJECT_NUMBER@serverless-robot-prod.iam.gserviceaccount.com"
if gcloud iam service-accounts describe "$SERVICE_AGENT" --project="$PROJECT_ID" >/dev/null 2>&1; then
  grant_project_role "$SERVICE_AGENT" "roles/artifactregistry.reader" || \
    warn "Could not grant Artifact Registry reader to the Cloud Run service agent; the first deploy will confirm access."
else
  warn "Cloud Run service agent $SERVICE_AGENT not found yet; it will be created when the service is deployed."
fi

if ! gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" >/dev/null 2>&1; then
  info "Creating Secret Manager secret $SECRET_NAME"
  gcloud secrets create "$SECRET_NAME" \
    --replication-policy=automatic \
    --project="$PROJECT_ID" \
    >/dev/null
fi

gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
  --member="serviceAccount:$RUNTIME_SA" \
  --role="roles/secretmanager.secretAccessor" \
  --project="$PROJECT_ID" \
  --quiet \
  >/dev/null

gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
  --member="serviceAccount:$DEPLOYER_SA" \
  --role="roles/secretmanager.secretAccessor" \
  --project="$PROJECT_ID" \
  --quiet \
  >/dev/null

if [[ -n "${OPENCODE_API_KEY_FILE:-}" ]]; then
  [[ -r "$OPENCODE_API_KEY_FILE" ]] || die "OPENCODE_API_KEY_FILE is not readable: $OPENCODE_API_KEY_FILE"
  info "Adding a new version of $SECRET_NAME from OPENCODE_API_KEY_FILE"
  gcloud secrets versions add "$SECRET_NAME" \
    --data-file="$OPENCODE_API_KEY_FILE" \
    --project="$PROJECT_ID" \
    >/dev/null
elif [[ -n "${OPENCODE_API_KEY:-}" ]]; then
  info "Adding a new version of $SECRET_NAME from OPENCODE_API_KEY"
  printf '%s' "$OPENCODE_API_KEY" | gcloud secrets versions add "$SECRET_NAME" \
    --data-file=- \
    --project="$PROJECT_ID" \
    >/dev/null
elif ! gcloud secrets versions list "$SECRET_NAME" \
  --project="$PROJECT_ID" \
  --limit=1 \
  --format='value(name)' 2>/dev/null | grep -q .; then
  warn "Secret $SECRET_NAME has no version yet. Add one with:"
  warn "  gcloud secrets versions add $SECRET_NAME --data-file=/path/to/key"
fi

if ! gcloud iam workload-identity-pools describe "$WIF_POOL_ID" \
  --location=global \
  --project="$PROJECT_ID" >/dev/null 2>&1; then
  info "Creating Workload Identity pool $WIF_POOL_ID"
  gcloud iam workload-identity-pools create "$WIF_POOL_ID" \
    --location=global \
    --display-name="GitHub Actions" \
    --project="$PROJECT_ID" \
    >/dev/null
fi

if ! gcloud iam workload-identity-pools providers describe "$WIF_PROVIDER_ID" \
  --workload-identity-pool="$WIF_POOL_ID" \
  --location=global \
  --project="$PROJECT_ID" >/dev/null 2>&1; then
  info "Creating Workload Identity provider $WIF_PROVIDER_ID"
  gcloud iam workload-identity-pools providers create-oidc "$WIF_PROVIDER_ID" \
    --workload-identity-pool="$WIF_POOL_ID" \
    --location=global \
    --display-name="GitHub Actions" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository == '$GITHUB_REPO' && assertion.ref == 'refs/heads/$GITHUB_BRANCH'" \
    --project="$PROJECT_ID" \
    >/dev/null
else
  warn "Workload Identity provider already exists; leaving its condition unchanged."
fi

WIF_PROVIDER="projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$WIF_POOL_ID/providers/$WIF_PROVIDER_ID"
WIF_PRINCIPAL="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$WIF_POOL_ID/attribute.repository/$GITHUB_REPO"

gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA" \
  --member="$WIF_PRINCIPAL" \
  --role="roles/iam.workloadIdentityUser" \
  --project="$PROJECT_ID" \
  --quiet \
  >/dev/null

if [[ -n "$BILLING_ACCOUNT_ID" ]]; then
  if ! gcloud billing budgets list \
    --billing-account="$BILLING_ACCOUNT_ID" \
    --format='value(displayName)' 2>/dev/null | grep -qx "$BUDGET_NAME"; then
    info "Creating a $BUDGET_AMOUNT budget alert on $BILLING_ACCOUNT_ID"
    gcloud billing budgets create \
      --billing-account="$BILLING_ACCOUNT_ID" \
      --display-name="$BUDGET_NAME" \
      --budget-amount="$BUDGET_AMOUNT" \
      --threshold-rule=percent=0.5 \
      --threshold-rule=percent=0.9 \
      --threshold-rule=percent=1.0 \
      >/dev/null || warn "Budget creation failed; create one manually in the Cloud Billing console."
  fi
else
  warn "BILLING_ACCOUNT_ID is not set; skipping the budget alert. Set one in the Cloud Billing console."
fi

cat <<EOF

Cloud Run bootstrap complete.

Project:                 $PROJECT_ID
Region:                  $REGION
Artifact Registry:       $REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME
Runtime service account: $RUNTIME_SA
Deploy service account:  $DEPLOYER_SA
WIF provider:            $WIF_PROVIDER
Secret:                  $SECRET_NAME

Next steps:
  1. Add the OpenCode key if the secret has no version:
       gcloud secrets versions add $SECRET_NAME --data-file=/path/to/key
  2. Deploy:
       ./deploy/cloudrun/deploy.sh
  3. Set these GitHub Actions repository variables:
       GCP_PROJECT_ID=$PROJECT_ID
       GCP_REGION=$REGION
       GCP_WORKLOAD_IDENTITY_PROVIDER=$WIF_PROVIDER
       GCP_SERVICE_ACCOUNT=$DEPLOYER_SA
       GCP_RUNTIME_SERVICE_ACCOUNT=$RUNTIME_SA
       CORS_ORIGINS=$CORS_ORIGINS
       CORS_ORIGIN_REGEX=$CORS_ORIGIN_REGEX
       LLM_ENABLED=false
  4. After the first deploy, set Vercel production VITE_API_URL to the
     Cloud Run service URL and redeploy the frontend.

EOF
