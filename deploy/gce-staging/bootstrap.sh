#!/usr/bin/env bash
# Sprint 19b — GCE bootstrap for Windmill + Authentik stack.
#
# Runs on a fresh Debian/Ubuntu GCE VM as the sudo-granted default user.
# Idempotent: re-run is safe. Installs docker + docker compose, writes secrets
# to /opt/arukai/staging.env (mode 0600), starts the stack.
#
# Usage (on the VM, after gcloud ssh):
#   sudo bash /tmp/bootstrap.sh
#
# The compose file must already be at /opt/arukai/compose.gce.yaml.

set -euo pipefail

ARUKAI_DIR="/opt/arukai"
ENV_FILE="${ARUKAI_DIR}/staging.env"
COMPOSE_FILE="${ARUKAI_DIR}/compose.gce.yaml"

log() { echo "[bootstrap] $*" >&2; }

# ── 1. Install docker (docker-ce + compose-plugin) if not present ────────────
if ! command -v docker >/dev/null 2>&1; then
    log "installing docker from Docker's apt repo"
    apt-get update -qq
    apt-get install -y ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
else
    log "docker already installed: $(docker --version)"
fi

# ── 2. Generate + persist secrets if env file doesn't exist ──────────────────
mkdir -p "${ARUKAI_DIR}"
chmod 700 "${ARUKAI_DIR}"

if [ ! -f "${ENV_FILE}" ]; then
    log "writing new ${ENV_FILE} with fresh secrets"
    {
        echo "# Arukai staging infra env — DO NOT COMMIT"
        echo "# Regenerating this file wipes the Authentik SECRET_KEY which breaks existing sessions."
        echo "AUTHENTIK_SECRET_KEY=$(openssl rand -hex 32)"
        echo "AUTHENTIK_BOOTSTRAP_PASSWORD=$(openssl rand -base64 24 | tr -d '=+/' | head -c 24)"
        echo "AUTHENTIK_BOOTSTRAP_EMAIL=admin@arukai.example"
        echo "AUTHENTIK_POSTGRESQL_PASSWORD=$(openssl rand -base64 24 | tr -d '=+/' | head -c 24)"
        echo "WINDMILL_POSTGRESQL_PASSWORD=$(openssl rand -base64 24 | tr -d '=+/' | head -c 24)"
    } > "${ENV_FILE}"
    chmod 600 "${ENV_FILE}"
else
    log "reusing existing ${ENV_FILE} (preserves Authentik sessions)"
fi

# ── 3. Bring up the stack ────────────────────────────────────────────────────
log "docker compose up -d (using ${COMPOSE_FILE})"
cd "${ARUKAI_DIR}"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d

# ── 4. Wait for both HTTP endpoints to come up ───────────────────────────────
log "waiting for Windmill :8100/api/version ..."
for i in $(seq 1 30); do
    if curl -fsS --max-time 3 http://localhost:8100/api/version >/dev/null 2>&1; then
        log "windmill up (${i}s)"
        break
    fi
    sleep 2
done

log "waiting for Authentik :9000 (migrations take ~2-3 min on first boot)..."
for i in $(seq 1 120); do
    if curl -fsS --max-time 3 http://localhost:9000/-/health/live/ >/dev/null 2>&1; then
        log "authentik up (~${i}s)"
        break
    fi
    sleep 3
done

# ── 5. Print the admin credentials for one-time handoff ──────────────────────
log "── handoff ──"
# shellcheck disable=SC1090
source "${ENV_FILE}"
cat <<HANDOFF
Windmill:  http://$(curl -s ifconfig.me || echo '<vm-ip>'):8100
  Bootstrap login: admin@windmill.dev / changeme  (change via UI or scripts/deploy_windmill.py)

Authentik: http://$(curl -s ifconfig.me || echo '<vm-ip>'):9000/if/flow/initial-setup/
  Bootstrap admin: ${AUTHENTIK_BOOTSTRAP_EMAIL}
  Password: ${AUTHENTIK_BOOTSTRAP_PASSWORD}
  (Change the password on first login.)
HANDOFF

log "bootstrap complete"
