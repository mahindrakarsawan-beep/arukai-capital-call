# Access Credentials — Arukai Capital Call (D2)

**Version:** 1.0.0
**Date:** 2026-04-12
**Handoff item:** H6
**Classification:** Internal — Dev/UAT only

---

> **WARNING:** The credentials in this document are seed credentials for development and UAT environments ONLY. They must NOT be used in production. All credentials must be rotated or replaced before any external client or production deployment. Do not share this document externally.

---

## 1. Application Seed Credentials (Dev/UAT Only)

These accounts are seeded by the `scripts/seed_users.py` (or equivalent seed script) and are present in the staging environment.

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@arukai.example | admin123 |
| Reviewer | reviewer@arukai.example | reviewer123 |

### What these accounts can do

- **admin@arukai.example** — full access: upload documents, approve/reject packages, view and export audit trail, manage users (via seed script), access all API endpoints.
- **reviewer@arukai.example** — restricted access: view documents assigned to them, add comments, flag exceptions. Cannot approve, reject, or access admin functions.

### Before production handoff

1. Disable or delete both seed accounts.
2. Create named accounts for each real operator user (see `RBAC_ADMIN.md`).
3. Distribute credentials via a secure channel (not email in plain text).
4. Rotate the JWT secret (see `OPERATIONAL_RUNBOOK.md` Section 7).

---

## 2. GCP Service Account

| Field | Value |
|-------|-------|
| Service account email | arukai-capital-call-deployer@arukai-testbed.iam.gserviceaccount.com |
| Purpose | CI/CD deployment to Cloud Run |
| IAM roles held | Cloud Run Admin, Storage Object Admin (for deployment artifacts) |
| Key management | Arukai retains the service account key. Client operators do not receive this key. |

If you believe this service account has been compromised, contact Arukai immediately (P0 incident).

---

## 3. GCP Project

| Field | Value |
|-------|-------|
| Project ID | arukai-testbed |
| Region | europe-west4 |
| Console URL | https://console.cloud.google.com/home/dashboard?project=arukai-testbed |

Operator admins are granted the following GCP IAM roles:

| Role | Scope |
|------|-------|
| Cloud Run Viewer | View service status and revisions |
| Cloud Run Traffic Admin | Manage traffic splits (enables rollback) |
| Secret Manager Secret Version Manager | Add new secret versions (enables secret rotation) |
| Logging Viewer | Read application logs |

> Arukai retains Owner-level access to the GCP project. Client operators do not hold Owner or Editor roles.

---

## 4. Database

| Field | Value |
|-------|-------|
| Provider | Neon Postgres (serverless) |
| Database name | Confirm at deployment time (may share with other services in current setup — see `KNOWN_ISSUES.md`) |
| Connection string | Stored in GCP Secret Manager as `DATABASE_URL` |
| Direct access | Neon console at https://console.neon.tech — Arukai-managed |

Operators do not receive direct database credentials. Access to the database is via the application API only, except for audit trail exports (see `AUDIT_TRAIL_GUIDE.md`).

---

## 5. Production Credential Checklist

Before handing off to an external client or promoting to production, complete the following:

- [ ] Disable or delete seed accounts (`admin@arukai.example`, `reviewer@arukai.example`)
- [ ] Create named admin account(s) for the operator (minimum 2 admins — see `RBAC_ADMIN.md`)
- [ ] Create named reviewer accounts for each operator user
- [ ] Rotate `JWT_SECRET` in Secret Manager
- [ ] Rotate `DATABASE_URL` if the Neon project is being transferred to the client
- [ ] Confirm IAM roles are scoped correctly for each client operator
- [ ] Confirm Arukai service account key is not accessible to the client
- [ ] Deliver credentials to the client via a secure channel (e.g., 1Password share, encrypted email)
- [ ] Document the delivery in the handoff log

---

*Credentials document maintained by Arukai squad. Access restricted to Arukai internal and operator admin.*
