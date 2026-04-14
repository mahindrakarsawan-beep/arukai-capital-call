#!/usr/bin/env bash
# setup_gcp.sh — Idempotent GCP infrastructure setup for arukai-capital-call Cloud Run deployment.
#
# Adapted from portfolio-analyzer/scripts/setup_gcp_infra.sh (P-5.1 reuse).
#
# Provisions:
#   - Required GCP APIs
#   - Artifact Registry repository
#   - Service account with required IAM roles
#
# Does NOT create Secret Manager secret values — it prints the required secret names and
# instructions so the operator can add values safely without this script ever touching secrets.
#
# Usage:
#   ./scripts/setup_gcp.sh             # Run for real
#   ./scripts/setup_gcp.sh --dry-run   # Print commands, do not execute
#
# Prerequisites: gcloud CLI authenticated with an account that has Owner or Editor role
# on the target project.

set -euo pipefail

# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------
PROJECT="arukai-testbed"
REGION="europe-west4"
AR_REPO="arukai-capital-call"
AR_FORMAT="DOCKER"
SA_NAME="capital-call-deployer"
SA_DISPLAY_NAME="Arukai Capital Call Deployer"
SA_EMAIL="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"

REQUIRED_APIS=(
  "run.googleapis.com"
  "artifactregistry.googleapis.com"
  "secretmanager.googleapis.com"
)

SA_ROLES=(
  "roles/run.admin"
  "roles/artifactregistry.writer"
  "roles/secretmanager.secretAccessor"
  "roles/iam.serviceAccountUser"
)

# Secrets that MUST exist in Secret Manager before first deploy.
# Values are NOT set by this script — the operator must add them manually.
REQUIRED_SECRETS=(
  "DATABASE_URL"
  "JWT_SECRET"
  "ANTHROPIC_API_KEY"
)

OPTIONAL_SECRETS=(
  "LINEAR_API_KEY"
)

# ---------------------------------------------------------------------------
# Dry-run support
# ---------------------------------------------------------------------------
DRY_RUN=false
for arg in "$@"; do
  if [ "$arg" = "--dry-run" ]; then
    DRY_RUN=true
  fi
done

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
# Preflight: confirm target project
# ---------------------------------------------------------------------------
step "Target project: ${PROJECT} | Region: ${REGION}"
if [ "$DRY_RUN" = "true" ]; then
  echo "[dry-run mode -- no GCP resources will be created]"
else
  echo "Running against GCP project: ${PROJECT}"
  if ! command -v gcloud &>/dev/null; then
    echo "ERROR: gcloud CLI not found. Install the Google Cloud SDK first." >&2
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# 1. Enable required APIs
# ---------------------------------------------------------------------------
step "Enabling required GCP APIs"
for api in "${REQUIRED_APIS[@]}"; do
  echo "  Enabling ${api} ..."
  run gcloud services enable "${api}" \
    --project="${PROJECT}"
done
echo "APIs enabled (or already enabled)."

# ---------------------------------------------------------------------------
# 2. Create Artifact Registry repository (idempotent)
# ---------------------------------------------------------------------------
step "Artifact Registry repository: ${AR_REPO}"

if [ "$DRY_RUN" = "true" ]; then
  echo "[dry-run] Would check and create AR repository '${AR_REPO}' in ${REGION}."
else
  if gcloud artifacts repositories describe "${AR_REPO}" \
       --location="${REGION}" \
       --project="${PROJECT}" &>/dev/null 2>&1; then
    echo "  Repository '${AR_REPO}' already exists -- skipping creation."
  else
    echo "  Creating Artifact Registry repository '${AR_REPO}' ..."
    gcloud artifacts repositories create "${AR_REPO}" \
      --repository-format="${AR_FORMAT}" \
      --location="${REGION}" \
      --description="Docker images for arukai-capital-call backend and frontend" \
      --project="${PROJECT}"
    echo "  Repository created."
  fi
fi

echo ""
echo "  Docker image paths will be:"
echo "    ${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/backend:<tag>"
echo "    ${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/frontend:<tag>"

# ---------------------------------------------------------------------------
# 3. Create service account (idempotent)
# ---------------------------------------------------------------------------
step "Service account: ${SA_NAME}"

if [ "$DRY_RUN" = "true" ]; then
  echo "[dry-run] Would check and create service account '${SA_NAME}'."
else
  if gcloud iam service-accounts describe "${SA_EMAIL}" \
       --project="${PROJECT}" &>/dev/null 2>&1; then
    echo "  Service account '${SA_NAME}' already exists -- skipping creation."
  else
    echo "  Creating service account '${SA_NAME}' ..."
    gcloud iam service-accounts create "${SA_NAME}" \
      --display-name="${SA_DISPLAY_NAME}" \
      --project="${PROJECT}"
    echo "  Service account created."
  fi
fi

# ---------------------------------------------------------------------------
# 4. Grant IAM roles to service account (idempotent via add-iam-policy-binding)
# ---------------------------------------------------------------------------
step "Granting IAM roles to ${SA_EMAIL}"
for role in "${SA_ROLES[@]}"; do
  echo "  Granting ${role} ..."
  run gcloud projects add-iam-policy-binding "${PROJECT}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${role}" \
    --condition=None \
    --quiet
done
echo "Roles granted (add-iam-policy-binding is idempotent)."

# ---------------------------------------------------------------------------
# 5. Secret Manager -- list required secrets, print creation instructions
# ---------------------------------------------------------------------------
step "Required GCP Secret Manager secrets"
echo ""
echo "  The following secrets MUST be created in Secret Manager before the first deploy."
echo "  This script does NOT set their values -- add them manually using the commands below."
echo ""
echo "  Project: ${PROJECT}"
echo ""

for secret in "${REQUIRED_SECRETS[@]}"; do
  echo "  ---- ${secret} ----"
  echo "  gcloud secrets create ${secret} \\"
  echo "    --replication-policy=automatic \\"
  echo "    --project=${PROJECT}"
  echo ""
  echo "  # Then add the secret value (replace <VALUE> -- never commit real values):"
  echo "  echo -n '<VALUE>' | gcloud secrets versions add ${secret} \\"
  echo "    --data-file=- \\"
  echo "    --project=${PROJECT}"
  echo ""
done

echo "  Optional secrets:"
for secret in "${OPTIONAL_SECRETS[@]}"; do
  echo "    - ${secret}"
done

# ---------------------------------------------------------------------------
# 6. Next steps
# ---------------------------------------------------------------------------
step "Next steps for the operator"
cat <<'NEXTSTEPS'

  1. Add secret VALUES manually (see section above).
     Never store actual secret values in this script or in version control.

  2. Download a service account key for GitHub CI auth:

       gcloud iam service-accounts keys create sa-key.json \
         --iam-account=capital-call-deployer@arukai-testbed.iam.gserviceaccount.com \
         --project=arukai-testbed

     WARNING: sa-key.json is a long-lived credential. Store it securely and delete
     the local copy after uploading to GitHub.

  3. Add the key to GitHub:
       GitHub -> repository Settings -> Environments -> staging -> Secrets
         -> Add secret: GCP_SA_KEY = (paste contents of sa-key.json)
       Repeat for the 'production' environment.

     Then DELETE the local key file:
       rm sa-key.json

  4. (Recommended) Migrate to Workload Identity Federation to eliminate long-lived keys.

  5. Trigger the deploy workflow:
       GitHub Actions -> "Deploy to Cloud Run" -> Run workflow
       Select environment (staging or production) and git_ref.

NEXTSTEPS

echo "=================================================================="
echo "  setup_gcp.sh complete."
if [ "$DRY_RUN" = "true" ]; then
  echo "  (DRY RUN -- no resources were created)"
fi
echo "=================================================================="
