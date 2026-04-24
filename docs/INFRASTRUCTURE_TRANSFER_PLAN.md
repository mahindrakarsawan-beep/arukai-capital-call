# Infrastructure Transfer Plan — Arukai → Client tenancy

**Status:** paper exercise (POR-158 #6). Full rehearsal deferred until a signed pilot client is identified.

**Purpose:** give a family-office COO reading this during due-diligence a concrete, dated answer to _"when we sign, how does the vendor-owned infra actually move into our GCP org, and on what timeline?"_. Every step is a command or a clickable action, not a promise.

## Source state (as of 2026-04-21)

Everything lives under a single vendor-owned project:

| Resource | Identifier | Notes |
|---|---|---|
| GCP project | `arukai-testbed` | Billing: vendor Stripe |
| Cloud Run — backend | `arukai-capital-call-backend-staging` | `europe-west4` |
| Cloud Run — frontend | `arukai-capital-call-frontend-staging` | `europe-west4` |
| Cloud SQL / Postgres | in-Cloud Run env var for now (staging) | prod will be Cloud SQL |
| Artifact Registry | `europe-west4-docker.pkg.dev/arukai-testbed/capital-call` | ~6 images |
| Secret Manager | `CC_WINDMILL_TOKEN`, `CC_JWT_SECRET`, `CC_DATABASE_URL`, `CC_MISTRAL_API_KEY` | |
| GCE VM | `arukai-staging-infra` (europe-west4-a, e2-medium) | Windmill + Authentik |
| DNS | none (raw Cloud Run URLs + VM IP) | Cloudflare-fronted domain pending |

## Target state (after transfer)

Same topology, client-owned:

```
Client GCP org
  └─ project: client-arukai-prod (or similar)
     ├─ Cloud Run services (same images, client-controlled env vars)
     ├─ Cloud SQL instance (client-managed backups)
     ├─ Artifact Registry (client-owned)
     ├─ Secret Manager (client-rotated secrets)
     ├─ GCE VM or GKE (client choice)
     └─ DNS + Cloudflare (client domain)
```

## Transfer sequence — 10 steps, ~4 hours of downtime

**Pre-flight (T-7 days):** client creates the target project, enables APIs (run, sql, secretmanager, artifactregistry, compute, cloudkms, cloudscheduler, monitoring), grants vendor SA `roles/viewer` for observation.

### 1. Freeze writes on source (T+0)

```bash
# Scale Cloud Run backend to 0 — rejects new traffic, pending requests drain
gcloud run services update arukai-capital-call-backend-staging \
  --project=arukai-testbed --region=europe-west4 --max-instances=0
```

Frontend stays up but displays a "pilot maintenance window" banner (static fallback). Out-of-scope for this plan; assume front-door switch lands separately.

### 2. Snapshot Postgres (T+5m)

```bash
# Staging still uses in-Cloud-Run dev DB; prod will be Cloud SQL.
# Cloud SQL export:
gcloud sql export sql arukai-prod-db gs://arukai-transfer-bucket/cc-$(date +%Y%m%d-%H%M).sql \
  --database=capital_call --project=arukai-testbed
```

Evidence: export file listed, size > 0, sha256 recorded in handoff doc.

### 3. Snapshot the GCE VM disk (T+10m)

```bash
gcloud compute disks snapshot arukai-staging-infra \
  --snapshot-names=arukai-staging-infra-transfer-$(date +%Y%m%d-%H%M) \
  --zone=europe-west4-a --project=arukai-testbed
```

Snapshot captures Windmill state + Authentik DB. Windmill token tables ship with it; client rotates all tokens post-cutover.

### 4. Sync Artifact Registry images (T+20m)

```bash
for img in cc-backend cc-frontend cc-migrator; do
  gcloud artifacts docker tags list \
    europe-west4-docker.pkg.dev/arukai-testbed/capital-call/$img \
    --format='value(tag)' --project=arukai-testbed | while read -r tag; do
      # copy to client project
      gcloud artifacts docker images copy \
        europe-west4-docker.pkg.dev/arukai-testbed/capital-call/$img:$tag \
        europe-west4-docker.pkg.dev/client-arukai-prod/capital-call/$img:$tag \
        --project=client-arukai-prod
    done
done
```

### 5. Import Postgres on the client side (T+40m)

Client runs:

```bash
gcloud sql instances create arukai-prod-db \
  --database-version=POSTGRES_16 --region=europe-west4 \
  --tier=db-custom-2-4096 --project=client-arukai-prod
gcloud sql databases create capital_call --instance=arukai-prod-db --project=client-arukai-prod
gcloud sql import sql arukai-prod-db gs://arukai-transfer-bucket/cc-<timestamp>.sql \
  --database=capital_call --project=client-arukai-prod
```

Vendor observes via granted `roles/viewer`; does not perform the import.

### 6. Rotate every secret onto the client's key (T+1h)

```bash
# Generate fresh values — these never touch the vendor project
for name in CC_JWT_SECRET CC_DATABASE_URL CC_WINDMILL_TOKEN CC_MISTRAL_API_KEY; do
  echo -n "$(openssl rand -base64 48)" | \
    gcloud secrets create $name --data-file=- --project=client-arukai-prod
done
```

The client manually enters real values (DB URL, Windmill token from the re-minted token on the transferred VM, Mistral API key on the client's Mistral account).

### 7. Restore the GCE VM under client ownership (T+1h15m)

Snapshot from step 3 is **not** portable across GCP orgs without the `--source-snapshot-project` flag; we instead:

```bash
# On the client side — copy the disk via snapshot-to-snapshot transfer
gcloud compute snapshots create arukai-staging-infra-incoming \
  --source-snapshot=projects/arukai-testbed/global/snapshots/arukai-staging-infra-transfer-<timestamp> \
  --project=client-arukai-prod
gcloud compute disks create arukai-prod-infra \
  --source-snapshot=arukai-staging-infra-incoming \
  --zone=europe-west4-a --project=client-arukai-prod
gcloud compute instances create arukai-prod-infra \
  --disk=name=arukai-prod-infra,boot=yes \
  --machine-type=e2-medium --zone=europe-west4-a --project=client-arukai-prod
```

Post-boot: client logs into Windmill UI, rotates every token, re-mints `CC_WINDMILL_TOKEN` into client Secret Manager (step 6 placeholder gets replaced here).

### 8. Deploy Cloud Run on the client project (T+2h)

```bash
gcloud run deploy arukai-capital-call-backend \
  --image=europe-west4-docker.pkg.dev/client-arukai-prod/capital-call/cc-backend:<sha> \
  --region=europe-west4 --project=client-arukai-prod \
  --set-secrets=JWT_SECRET=CC_JWT_SECRET:latest,DATABASE_URL=CC_DATABASE_URL:latest,\
WINDMILL_TOKEN=CC_WINDMILL_TOKEN:latest,MISTRAL_API_KEY=CC_MISTRAL_API_KEY:latest \
  --set-env-vars=WINDMILL_BASE_URL=http://<client-vm-ip>:8100,\
WINDMILL_WORKSPACE=capital-call
# Same for frontend
```

### 9. DNS + TLS (T+3h)

Client points their DNS at the Cloud Run URLs; Cloudflare Tunnel or Cloud Load Balancer fronts the VM. Raw HTTP on the VM is never exposed to the public internet in the target state.

### 10. Smoke + IAM cleanup (T+4h)

```bash
# Smoke: health, login, package upload E2E on the client-owned stack
curl -f https://api.<client-domain>/health
# Remove vendor SA's roles/viewer on the client project
gcloud projects remove-iam-policy-binding client-arukai-prod \
  --member=user:vendor-ops@arukai.example --role=roles/viewer
# Optional — vendor project shutdown after 30-day quarantine
gcloud projects delete arukai-testbed  # DELAYED — keep for rollback
```

## Rollback

Until step 10 completes, the vendor project is untouched and still scaled to 0 — rollback is `gcloud run services update --max-instances=100` on the vendor side and DNS flip. After the 30-day quarantine, rollback requires a new transfer from the client project back; paper-only in this plan.

## What this plan does NOT cover

- **Data in flight to Mistral during transfer** — classification jobs mid-queue. Mitigation: drain the Windmill queue (zero in-flight flows) before step 1. Operator check: Windmill UI → Jobs → "Running" count == 0.
- **User sessions** — every session invalidates at cutover (new `JWT_SECRET`). Users re-login against Authentik on the client VM.
- **Backups of the vendor project post-transfer** — vendor retains the 30-day Cloud SQL backup file for insurance; deleted on day 31.
- **Monitoring continuity** — Cloud Monitoring alerts on the vendor project go silent post-cutover; client sets up their own alert policies in step 7–8 (template in `docs/runbook-gce-staging.md` applies).
- **Compliance artifacts** — SOC 2 / ISO 27001 attestations are the vendor's responsibility to provide as PDFs; not a transfer step.

## Success criteria

1. Client-owned stack passes the same smoke + E2E we run on staging (`frontend/e2e/` suite against the new URLs).
2. `GET /audit/verify` on the new backend returns `{ok: true}` — hash chain survived the Postgres export/import.
3. No vendor credential (Arukai service account, Mistral API key on vendor account) appears in any grep of the client project's Secret Manager or env vars.
4. DNS resolves to Cloud Load Balancer / Cloudflare-proxied endpoints with valid TLS certs.
5. Vendor `roles/viewer` removed; no vendor IAM binding remains on the client project.

Until a pilot client is identified, items 1–5 are paper-only. The first rehearsal is scheduled for the first signed pilot's onboarding — this doc gets copied to `docs/runbook-transfer-<client-name>.md` and walked through with their ops team a week before cutover.
