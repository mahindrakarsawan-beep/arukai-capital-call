#!/usr/bin/env bash
# deploy.sh — Local (non-CI) deploy script for arukai-capital-call Cloud Run.
#
# Adapted from portfolio-analyzer/scripts/deploy_cloud_run.sh (P-5.2 reuse).
#
# Builds backend and frontend Docker images, pushes to Artifact Registry,
# deploys both services to Cloud Run, and runs a health-check smoke test.
#
# Usage:
#   ./scripts/deploy.sh --env staging
#   ./scripts/deploy.sh --env production
#   ./scripts/deploy.sh --env staging --dry-run
#
# Prerequisites:
#   - gcloud CLI authenticated as capital-call-deployer (or equivalent)
#   - Docker daemon running and authenticated to Artifact Registry
#     (run 'gcloud auth configure-docker europe-west4-docker.pkg.dev' once)
#   - GCP Secret Manager secrets populated (see scripts/setup_gcp.sh)

set -euo pipefail

# ---------------------------------------------------------------------------
# Fixed project variables
# ---------------------------------------------------------------------------
PROJECT="arukai-testbed"
REGION="europe-west4"
AR_REGISTRY="${REGION}-docker.pkg.dev/${PROJECT}/arukai-capital-call"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
ENV_NAME=""
DRY_RUN=false

usage() {
  cat <<'EOF'
Usage: scripts/deploy.sh --env <staging|production> [--dry-run]

Options:
  --env staging|production   Target environment (required)
  --dry-run                  Print commands without executing

Examples:
  scripts/deploy.sh --env staging
  scripts/deploy.sh --env production --dry-run
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV_NAME="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [ -z "$ENV_NAME" ]; then
  echo "ERROR: --env is required." >&2
  usage >&2
  exit 1
fi

if [ "$ENV_NAME" != "staging" ] && [ "$ENV_NAME" != "production" ]; then
  echo "ERROR: --env must be 'staging' or 'production', got '${ENV_NAME}'." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Resolve environment-specific values
# ---------------------------------------------------------------------------
if [ "$ENV_NAME" = "production" ]; then
  BACKEND_SERVICE="arukai-capital-call-backend"
  FRONTEND_SERVICE="arukai-capital-call-frontend"
else
  BACKEND_SERVICE="arukai-capital-call-backend-staging"
  FRONTEND_SERVICE="arukai-capital-call-frontend-staging"
fi

TIMESTAMP="$(date +%Y%m%d%H%M%S)"
BACKEND_IMAGE="${AR_REGISTRY}/backend:local-${ENV_NAME}-${TIMESTAMP}"
FRONTEND_IMAGE="${AR_REGISTRY}/frontend:local-${ENV_NAME}-${TIMESTAMP}"

# ---------------------------------------------------------------------------
# Dry-run wrapper
# ---------------------------------------------------------------------------
run() {
  if [ "$DRY_RUN" = "true" ]; then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

# ---------------------------------------------------------------------------
# Helper: step header
# ---------------------------------------------------------------------------
step() {
  echo ""
  echo "=================================================================="
  echo "  $*"
  echo "=================================================================="
}

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
step "Preflight -- environment: ${ENV_NAME}"
echo "  Backend service:  ${BACKEND_SERVICE}"
echo "  Frontend service: ${FRONTEND_SERVICE}"

if ! command -v gcloud &>/dev/null; then
  echo "ERROR: gcloud CLI not found." >&2
  exit 1
fi

if ! command -v docker &>/dev/null; then
  echo "ERROR: Docker CLI not found." >&2
  exit 1
fi

if [ "$DRY_RUN" = "true" ]; then
  echo "[dry-run mode -- no Docker builds or GCP changes will be made]"
else
  echo ""
  echo "Proceeding in 5 seconds -- Ctrl-C to abort."
  sleep 5
fi

# ---------------------------------------------------------------------------
# Step 1: Build Docker images
# ---------------------------------------------------------------------------
step "Step 1 of 5 -- Building Docker images"
# Resolve backend URL BEFORE building frontend so NEXT_PUBLIC_API_URL is baked
# into the client bundle at build time (Next.js requires NEXT_PUBLIC_* at build).
BACKEND_URL_FOR_BUILD="$(gcloud run services describe "${BACKEND_SERVICE}" \
  --region="${REGION}" --project="${PROJECT}" --format="value(status.url)" 2>/dev/null || echo "")"
if [ -z "${BACKEND_URL_FOR_BUILD}" ]; then
  # First deploy — use the project-number URL which is stable across revisions.
  BACKEND_URL_FOR_BUILD="https://${BACKEND_SERVICE}-1035777337524.europe-west4.run.app"
fi

run docker build --tag "${BACKEND_IMAGE}" "${REPO_ROOT}/backend"
run docker build --build-arg "NEXT_PUBLIC_API_URL=${BACKEND_URL_FOR_BUILD}" --tag "${FRONTEND_IMAGE}" "${REPO_ROOT}/frontend"

# ---------------------------------------------------------------------------
# Step 2: Push to Artifact Registry
# ---------------------------------------------------------------------------
step "Step 2 of 5 -- Pushing images to Artifact Registry"
run gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
run docker push "${BACKEND_IMAGE}"
run docker push "${FRONTEND_IMAGE}"

# ---------------------------------------------------------------------------
# Step 3: Deploy backend to Cloud Run
# ---------------------------------------------------------------------------
step "Step 3 of 5 -- Deploying backend: ${BACKEND_SERVICE}"
# Secret-name convention: CC_* (Capital Call) — matches revision 18 binding.
# Unprefixed names in this GCP project belong to portfolio-analyzer; using
# them here would connect this service to the wrong database.
run gcloud run deploy "${BACKEND_SERVICE}" \
  --image="${BACKEND_IMAGE}" \
  --region="${REGION}" \
  --project="${PROJECT}" \
  --platform=managed \
  --set-env-vars="APP_AUTH_ENABLED=true" \
  --set-secrets="DATABASE_URL=CC_DATABASE_URL:latest,JWT_SECRET=CC_JWT_SECRET:latest,ANTHROPIC_API_KEY=CC_ANTHROPIC_API_KEY:latest,MISTRAL_API_KEY=CC_MISTRAL_API_KEY:latest,OPENAI_API_KEY=CC_OPENAI_API_KEY:latest" \
  --allow-unauthenticated

# ---------------------------------------------------------------------------
# Step 4: Deploy frontend to Cloud Run
# ---------------------------------------------------------------------------
step "Step 4 of 5 -- Deploying frontend: ${FRONTEND_SERVICE}"
BACKEND_URL="$(gcloud run services describe "${BACKEND_SERVICE}" \
  --region="${REGION}" --project="${PROJECT}" --format="value(status.url)")"
run gcloud run deploy "${FRONTEND_SERVICE}" \
  --image="${FRONTEND_IMAGE}" \
  --region="${REGION}" \
  --project="${PROJECT}" \
  --platform=managed \
  --set-env-vars="NEXT_PUBLIC_API_URL=${BACKEND_URL}" \
  --allow-unauthenticated

# ---------------------------------------------------------------------------
# Step 5: Health-check smoke test
# ---------------------------------------------------------------------------
step "Step 5 of 5 -- Health-check smoke test"

if [ "$DRY_RUN" = "true" ]; then
  echo "[dry-run] Would fetch backend URL and GET /health"
else
  SERVICE_URL="$(gcloud run services describe "${BACKEND_SERVICE}" \
    --region="${REGION}" --project="${PROJECT}" --format="value(status.url)")"
  echo "  Backend URL: ${SERVICE_URL}"

  HEALTH_RESPONSE="$(curl -sf "${SERVICE_URL}/health")"
  HEALTH_STATUS="$(echo "${HEALTH_RESPONSE}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))")"

  if [ "${HEALTH_STATUS}" != "ok" ]; then
    echo "ERROR: Health check failed." >&2
    echo "  Response: ${HEALTH_RESPONSE}" >&2
    exit 1
  fi

  echo "  Health check passed -- status: ${HEALTH_STATUS}"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
step "Deploy complete"
echo ""
echo "  Environment: ${ENV_NAME}"
echo "  Backend:     ${BACKEND_SERVICE}"
echo "  Frontend:    ${FRONTEND_SERVICE}"
echo "=================================================================="
