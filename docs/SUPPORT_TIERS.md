# Support Tier Card — Arukai Capital Call (D2)

**Version:** 1.0.0
**Date:** 2026-04-12
**Handoff item:** H5

---

## Tier 1 — Self-Service (Operator does it independently)

No Arukai involvement required. No SLA — operator acts at their own pace.

| Operation | How |
|-----------|-----|
| Health check | `curl /health` — see `OPERATIONAL_RUNBOOK.md` Section 4.1 |
| Rollback to previous revision | `gcloud run services update-traffic` — see Runbook Section 4.2 |
| Restart a service | GCP Console or gcloud — see Runbook Section 4.3 |
| Rotate JWT secret | GCP Secret Manager — see Runbook Section 7 |
| View logs | GCP Console Logs Explorer — see `MONITORING_GUIDE.md` Section 2 |
| View audit trail | `GET /audit` endpoint or UI — see `AUDIT_TRAIL_GUIDE.md` |
| Add a user (seed script) | See `RBAC_ADMIN.md` — admin only |
| Deactivate a user | See `RBAC_ADMIN.md` — direct DB update (no UI yet) |
| View document queue and statuses | Frontend dashboard — see `CLIENT_TRAINING.md` |
| Export audit trail | Neon console SQL query — see `AUDIT_TRAIL_GUIDE.md` |

---

## Tier 2 — Guided (Operator acts with Arukai instructions)

Arukai provides written instructions; operator executes. **SLA: 4 business hours** to provide instructions after request is received.

| Operation | Notes |
|-----------|-------|
| Add or modify an environment variable | Arukai confirms safe values; operator applies in GCP Console |
| Update CORS allowed origins | Required when adding a new domain |
| Scale Cloud Run min/max instances | Arukai recommends values; operator sets via GCP Console |
| Configure a new document type | API-level configuration with Arukai guidance |
| Change a user's role | Direct DB update procedure — see `RBAC_ADMIN.md` |
| Modify retention policy settings | Documented in `RETENTION_POLICY.md` |
| Change cron schedule (if applicable) | Arukai provides updated config; operator redeploys |

**How to request Tier 2 support:**
- Linear: create an issue with label `client-request`
- Email: [insert Arukai support email here]
- Required fields: description, justification, urgency (P0–P3), affected environment, which RBAC roles are impacted, data impact (does this affect retained documents?)

---

## Tier 3 — Arukai-Built (Code work required)

Arukai squad does the work. **SLA: 1 business day scoping** (estimate and timeline provided within 1 business day of request).

| Operation |
|-----------|
| New features or workflow changes |
| Bug fixes in application logic |
| Database schema migrations |
| RBAC model changes (adding new roles) |
| New AI model integration or prompt changes |
| Classification accuracy improvements |
| Reclassification / override mechanism (known gap) |
| Cloud Monitoring dashboard configuration (H2 gap) |
| Alert policy setup (H3 gap) |
| Retention automation (H14 gap) |
| Admin UI for user management (H13 gap) |
| Infrastructure changes (new services, storage buckets, etc.) |

**How to request Tier 3:**
- Same channel as Tier 2 (Linear `client-request` or email)
- Arukai will confirm scope and timeline within 1 business day

---

## Incident Severity and SLAs

| Severity | Definition | Response | Resolution |
|----------|------------|----------|------------|
| P0 Critical | Production down, data corruption, RBAC bypass, unauthorized document access | 30 minutes | 4 hrs mitigate / 24 hrs root cause |
| P1 High | Major feature broken, approval workflow blocked, audit trail gap | 4 business hours | 2 business days |
| P2 Medium | Minor feature broken, classification accuracy degradation | 1 business day | Next release |
| P3 Low | Enhancement, cosmetic issue | 2 business days | Backlog |

P0/P1 incidents during the 90-day monitoring window are covered at no additional cost.

---

## 90-Day Monitoring Window

Arukai actively monitors uptime and key metrics from the date of handoff.

- Window start: date of handoff package delivery + client confirmation
- Window end: 90 calendar days later
- Coverage: P0 and P1 incidents resolved at no additional cost
- After 90 days: support transitions to a retainer or per-incident model (to be agreed separately)

---

## Contacts

| Role | Contact |
|------|---------|
| Primary Arukai contact | [insert name and email] |
| Incident escalation | [insert incident channel or on-call contact] |
| Linear project | [insert Linear project link] |
| Emergency (P0 only) | [insert phone or Slack handle] |

> Placeholder contacts above must be filled in at handoff time.

---

*Support tier card maintained by Arukai squad. Version updates require Arukai sign-off.*
