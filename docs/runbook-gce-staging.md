# GCE staging infra runbook — Windmill + Authentik VM

**VM:** `arukai-staging-infra` · `europe-west4-a` · `e2-medium`
**Public IP:** `34.12.153.46` (ephemeral — if VM is stopped/started the IP may change; see "IP rotation" below)
**GCP project:** `arukai-testbed`
**Created by:** POR-162 (Sprint 19b, 2026-04-21)

## Services (all in /opt/arukai)

| Service | Port | Image | Purpose |
|---|---|---|---|
| `arukai-windmill-server-1` | `8100` | `ghcr.io/windmill-labs/windmill:1.390.0` | REST API + UI |
| `arukai-windmill-worker-1` | — | same | Executes flow scripts |
| `arukai-windmill-db-1` | — | `postgres:16-alpine` | Windmill state |
| `arukai-authentik-server-1` | `9000` | `ghcr.io/goauthentik/server:2024.12` | OIDC/IdP UI + API |
| `arukai-authentik-worker-1` | — | same | Background tasks |
| `arukai-authentik-db-1` | — | `postgres:16-alpine` | Authentik state |
| `arukai-authentik-redis-1` | — | `redis:alpine` | Authentik cache/queue |

## Public URLs

- Windmill: `http://34.12.153.46:8100`
  - Bootstrap login: `admin@windmill.dev` / `changeme` — **change immediately**
- Authentik: `http://34.12.153.46:9000/if/flow/initial-setup/`
  - Bootstrap admin: `admin@arukai.example`
  - Bootstrap password: **in `/opt/arukai/staging.env` on the VM** (line `AUTHENTIK_BOOTSTRAP_PASSWORD`). Fetch with:
    ```
    gcloud compute ssh arukai-staging-infra --zone=europe-west4-a --project=arukai-testbed \
      --command='sudo grep AUTHENTIK_BOOTSTRAP_PASSWORD /opt/arukai/staging.env'
    ```

## Ops

### Check health

```bash
gcloud compute ssh arukai-staging-infra --zone=europe-west4-a --project=arukai-testbed \
  --command='cd /opt/arukai && sudo docker compose -f compose.gce.yaml --env-file staging.env ps'
```

### Tail logs

```bash
gcloud compute ssh arukai-staging-infra --zone=europe-west4-a --project=arukai-testbed \
  --command='cd /opt/arukai && sudo docker compose -f compose.gce.yaml --env-file staging.env logs -f --tail=100 windmill-server'
```

### Restart a service

```bash
gcloud compute ssh arukai-staging-infra --zone=europe-west4-a --project=arukai-testbed \
  --command='cd /opt/arukai && sudo docker compose -f compose.gce.yaml --env-file staging.env restart windmill-server'
```

### Full wipe + reinstall (secrets NOT preserved — new Authentik SECRET_KEY kills all sessions)

```bash
gcloud compute ssh arukai-staging-infra --zone=europe-west4-a --project=arukai-testbed \
  --command='cd /opt/arukai && sudo docker compose -f compose.gce.yaml --env-file staging.env down -v && sudo rm /opt/arukai/staging.env && sudo /tmp/bootstrap.sh'
```

### Upgrade images

Edit `/opt/arukai/compose.gce.yaml` on the VM (bump the `image:` tag), then:

```bash
cd /opt/arukai && sudo docker compose -f compose.gce.yaml --env-file staging.env pull && sudo docker compose -f compose.gce.yaml --env-file staging.env up -d
```

### Snapshot (before risky changes)

```bash
gcloud compute disks snapshot arukai-staging-infra \
  --snapshot-names=arukai-staging-infra-$(date +%Y%m%d-%H%M) \
  --zone=europe-west4-a --project=arukai-testbed
```

### Restore from snapshot

```bash
# 1. Stop the VM
gcloud compute instances stop arukai-staging-infra --zone=europe-west4-a --project=arukai-testbed

# 2. Detach disk
gcloud compute instances detach-disk arukai-staging-infra \
  --disk=arukai-staging-infra --zone=europe-west4-a --project=arukai-testbed

# 3. Delete the disk (after confirming snapshot exists!)
gcloud compute disks delete arukai-staging-infra --zone=europe-west4-a --project=arukai-testbed

# 4. Create new disk from snapshot
gcloud compute disks create arukai-staging-infra \
  --source-snapshot=<snapshot-name> \
  --zone=europe-west4-a --project=arukai-testbed

# 5. Attach + boot
gcloud compute instances attach-disk arukai-staging-infra --disk=arukai-staging-infra --zone=europe-west4-a --project=arukai-testbed
gcloud compute instances start arukai-staging-infra --zone=europe-west4-a --project=arukai-testbed
```

## Cloud Run backend wiring

Backend env vars (on `arukai-capital-call-backend-staging`):

```
WINDMILL_BASE_URL=http://34.12.153.46:8100     (env var)
WINDMILL_WORKSPACE=capital-call                 (env var)
WINDMILL_TOKEN=<secret ref CC_WINDMILL_TOKEN>   (Secret Manager)
```

**Rotating the Windmill token:** log into Windmill UI → Settings → Tokens → create a new one → store in Secret Manager:

```bash
echo -n "<new-token>" | gcloud secrets versions add CC_WINDMILL_TOKEN --data-file=- --project=arukai-testbed
gcloud run services update arukai-capital-call-backend-staging \
  --project=arukai-testbed --region=europe-west4 \
  --update-secrets=WINDMILL_TOKEN=CC_WINDMILL_TOKEN:latest
```

Then revoke the old token in the Windmill UI.

## IP rotation (VM restart)

The VM uses an **ephemeral** external IP. If stopped + restarted, the IP may change. To handle:

1. After restart: `gcloud compute instances describe arukai-staging-infra --zone=europe-west4-a --project=arukai-testbed --format='value(networkInterfaces[0].accessConfigs[0].natIP)'`
2. Update the backend: `gcloud run services update arukai-capital-call-backend-staging --project=arukai-testbed --region=europe-west4 --update-env-vars="WINDMILL_BASE_URL=http://<new-ip>:8100"`

To avoid this permanently, reserve a static IP (~$3/mo extra):

```bash
gcloud compute addresses create arukai-staging-infra --region=europe-west4 --project=arukai-testbed
# then assign to the VM via --address=arukai-staging-infra on next instances create, or swap via start/stop
```

## Teardown (when the VM is no longer needed)

```bash
# Nuclear — delete VM + disk + firewall rule + Secret Manager entry
gcloud compute instances delete arukai-staging-infra --zone=europe-west4-a --project=arukai-testbed --quiet
gcloud compute firewall-rules delete arukai-staging-infra --project=arukai-testbed --quiet
gcloud secrets delete CC_WINDMILL_TOKEN --project=arukai-testbed --quiet
# Also unset the backend env vars:
gcloud run services update arukai-capital-call-backend-staging \
  --project=arukai-testbed --region=europe-west4 \
  --remove-env-vars=WINDMILL_BASE_URL,WINDMILL_WORKSPACE \
  --remove-secrets=WINDMILL_TOKEN
```

Monthly cost estimate (as of 2026-04): e2-medium + 30GB pd-balanced + egress ≈ **$25-30/mo**.

## Known follow-ups

- **SSL / custom domain** — Cloudflare Tunnel, separate ticket
- **Authentik OIDC wiring** — plug backend auth into Authentik, separate ticket
- **VM static IP** — reserve if we demo externally
- **Automated backups** — VM disk snapshot schedule, POR-158 scope
- **Monitoring** — Cloud Monitoring uptime check on `:8100/api/version`, POR-158 scope
