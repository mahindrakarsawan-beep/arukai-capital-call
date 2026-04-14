# Operational Runbook — Arukai Capital Call (D2)

**Version:** 1.0.0
**Date:** 2026-04-12
**Handoff item:** H1
**Audience:** Operator admin (client-facing)

---

## 1. What the System Does

The Arukai Capital Call system automates the ingestion, classification, and approval of cross-border capital call documents. The core workflow is:

1. **Ingest** — an operator uploads a PDF document (capital call notice, subscription agreement, side letter) via the web interface.
2. **Classify** — the backend uses an AI model to determine the document type (`capital_call`, `subscription_agreement`, `side_letter`), extract structured fields (fund name, amount, due date, counterparty), and assign a confidence score.
3. **Review** — a reviewer examines the extracted fields and classification output, flags exceptions, and adds comments.
4. **Approve** — an admin approves or rejects the package. Every state change is written to the immutable audit trail.

The system supports multi-user access with two roles: **admin** and **reviewer**. Role-based access control (RBAC) ensures that only authorized users can approve or administer the system.

---

## 2. Service URLs

| Service | URL |
|---------|-----|
| Frontend (UI) | https://arukai-capital-call-frontend-staging-1035777337524.europe-west4.run.app |
| Backend (API) | https://arukai-capital-call-backend-staging-1035777337524.europe-west4.run.app |
| Backend health | https://arukai-capital-call-backend-staging-1035777337524.europe-west4.run.app/health |

> Note: These are staging URLs. Production URLs will be provided at the time of production deployment.

---

## 3. Authentication

### Login Page

Navigate to the frontend URL. You will be presented with a login form. Enter your email address and password.

On successful login, a JWT token is issued and stored in your browser session. The session is valid for 8 hours. After 8 hours you will be redirected to the login page.

### Default Seed Credentials (Dev/UAT Only)

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@arukai.example | admin123 |
| Reviewer | reviewer@arukai.example | reviewer123 |

> **WARNING:** These credentials are for development and UAT environments only. They must be rotated or replaced before any external client or production deployment. See Section 7 (Secret Rotation).

---

## 4. Tier 1 Operations — Client Does Independently

### 4.1 Health Check

Verify the backend is running:

```bash
curl https://arukai-capital-call-backend-staging-1035777337524.europe-west4.run.app/health
```

Expected response: `{"status": "ok"}` with HTTP 200.

If the response is not 200, proceed to Section 4.3 (Restart) or contact Arukai.

### 4.2 Rollback to Previous Revision

Use this when a recent deployment has caused a regression.

1. Open [GCP Cloud Console](https://console.cloud.google.com) and navigate to **Cloud Run**.
2. Select the GCP project: `arukai-testbed`.
3. Identify the service (`arukai-capital-call-backend` or `arukai-capital-call-frontend`).
4. Click **Revisions** and note the previous stable revision name (e.g., `00005-abc`).
5. Run:

```bash
gcloud run services update-traffic arukai-capital-call-backend \
  --to-revisions=<PREVIOUS_REVISION>=100 \
  --region=europe-west4 \
  --project=arukai-testbed
```

Replace `<PREVIOUS_REVISION>` with the revision name from step 4. Repeat for the frontend service if needed.

6. Verify via health check (Section 4.1).

### 4.3 Restart a Service

Cloud Run services restart automatically when traffic is sent. To force a fresh instance:

```bash
gcloud run services update arukai-capital-call-backend \
  --region=europe-west4 \
  --project=arukai-testbed \
  --update-env-vars RESTART_TRIGGER=$(date +%s)
```

> Note: This temporarily sets an env var to force a new revision. Remove it afterward via Tier 2 guidance if needed.

Alternatively, from the GCP Console: **Cloud Run → service → Edit & Deploy New Revision → Deploy** (no changes needed — a new revision is spun up).

---

## 5. Tier 2 Operations — Client with Arukai Guidance

These operations require Arukai to provide specific instructions. Submit a request via Linear (label: `client-request`) or email. SLA: **4 business hours**.

| Operation | Notes |
|-----------|-------|
| Add or change an environment variable | Arukai confirms the variable name and safe value; client applies via GCP Console |
| Update CORS allowed origins | Required when adding a new frontend domain |
| Scale Cloud Run instances (min/max) | Adjust via Cloud Run service edit; Arukai recommends values |
| Change cron schedule | Arukai updates and redeploys |
| Add a new document type | Requires Tier 2 configuration guidance from Arukai |
| Modify retention policy settings | See `RETENTION_POLICY.md` |

---

## 6. Tier 3 Operations — Arukai Only

These require code changes and must be handled by the Arukai squad. SLA: **1 business day scoping**.

- New features or workflow changes
- Bug fixes in application logic
- Database schema migrations
- RBAC model changes (adding new roles)
- New AI model integration or prompt changes
- Infrastructure changes (new services, VPC, etc.)

---

## 7. Secret Rotation

Secrets are stored in **GCP Secret Manager** under project `arukai-testbed`.

### Rotating the JWT Secret

1. Open GCP Console → **Secret Manager**.
2. Find the secret named `JWT_SECRET` (or equivalent — Arukai will confirm the exact name).
3. Click **Add New Version** and enter a new strong random value (at least 32 characters, alphanumeric + symbols).
4. Set the new version as **Active** and disable the old version.
5. Restart the backend service (Section 4.3) to pick up the new secret.
6. All existing user sessions will be invalidated. Users must log in again.

### Rotating Database Credentials

Contact Arukai (Tier 3) — database credential rotation requires a coordinated deployment to avoid downtime.

---

## 8. Viewing Logs in GCP Console

1. Open [GCP Console](https://console.cloud.google.com) → **Logging → Logs Explorer**.
2. Select project `arukai-testbed`.
3. In the query box, filter by resource:

```
resource.type="cloud_run_revision"
resource.labels.service_name="arukai-capital-call-backend"
```

4. Set the time range (top right) to the period of interest.
5. Use severity filters to narrow to `ERROR` or `WARNING` if investigating an incident.

Alternatively, from Cloud Run: **Cloud Run → service → Logs tab** for a quick view of the last 24 hours.

---

## 9. Rollback Procedure (Full Detail)

This expands on Section 4.2 for production use.

1. **Identify the incident.** Confirm via health check or user reports that the current revision is broken.
2. **Find the stable revision.**
   ```bash
   gcloud run revisions list \
     --service=arukai-capital-call-backend \
     --region=europe-west4 \
     --project=arukai-testbed \
     --format="table(name,creationTimestamp,status.conditions[0].type)"
   ```
3. **Route all traffic to the stable revision.**
   ```bash
   gcloud run services update-traffic arukai-capital-call-backend \
     --to-revisions=<STABLE_REVISION>=100 \
     --region=europe-west4 \
     --project=arukai-testbed
   ```
4. **Verify recovery.** Run the health check and confirm the frontend is functional.
5. **Notify Arukai.** File a Tier 3 request to investigate and fix the root cause in the broken revision.
6. **Do not delete the broken revision** — it may be needed for root cause analysis.

---

## 10. GCP Project Reference

| Item | Value |
|------|-------|
| Project ID | arukai-testbed |
| Region | europe-west4 |
| Backend Cloud Run service | arukai-capital-call-backend |
| Frontend Cloud Run service | arukai-capital-call-frontend |
| Service account (deploy) | arukai-capital-call-deployer@arukai-testbed.iam.gserviceaccount.com |

---

*Runbook maintained by Arukai squad. For changes or corrections, file a Tier 3 request.*
