# Handoff Checklist — Arukai Capital Call (D2)

**Version:** 1.0.0
**Date:** 2026-04-12
**Milestone:** M5 — Governance Package
**Author:** Arukai squad (Alex, backup frontend)

---

## Delivery Summary

**Delivered: 6/15 | Partial: 5/15 | Missing: 3/15 | Not applicable: 1/15**

Handoff is complete when all H1-H15 are delivered + operator admin confirms + 72-hour acceptance window passes.

---

## Checklist

| # | Deliverable | Status | Notes |
|---|-------------|--------|-------|
| H1 | Operational runbook | DELIVERED | `docs/OPERATIONAL_RUNBOOK.md` — system overview, auth, Tier 1/2/3 ops, rollback, log access, secret rotation |
| H2 | Monitoring dashboard | MISSING | Cloud Monitoring not configured. KI-001. Manual /health check and log access documented in `MONITORING_GUIDE.md`. |
| H3 | Alert configuration | MISSING | No alert policies configured. KI-002. Alert intent and setup instructions documented in `MONITORING_GUIDE.md` Section 3. |
| H4 | Training documentation | DELIVERED | `docs/CLIENT_TRAINING.md` — login, upload, classification output, approve/reject, audit trail, reclassification gap documented |
| H5 | Support tier card | DELIVERED | `docs/SUPPORT_TIERS.md` — Tier 1/2/3 operations, SLAs, 90-day window, incident severity, contacts (placeholders) |
| H6 | Access credentials | PARTIAL | `docs/ACCESS_CREDENTIALS.md` — dev/UAT seed creds documented. Production rotation checklist included. Prod creds not yet set. |
| H7 | Deployment scorecard | DELIVERED (by M6) | `scorecard-deployment-2.md` per evidence model schema. Produced at M4/M6 milestone. |
| H8 | UAT report | NOT DELIVERED | No external operator participated. Phase 2A internal rehearsal only. Cannot be delivered until Phase 2B with real client. KI-006. |
| H9 | Production smoke report | PARTIAL | M4 smoke results exist for staging environment. No production deployment yet — this is a staging-only build at M5. |
| H10 | Known issues register | DELIVERED | `docs/KNOWN_ISSUES.md` — 9 issues catalogued with severity, status, and resolution phase |
| H11 | Architecture decision log | PARTIAL | Key decisions in `.squad/v01-scope.md` and Linear tickets. Formal ADL document not yet produced. |
| H12 | Source code access | DELIVERED | GitHub repo `arukai-capital-call` — access to be granted at handoff. Arukai retains owner access. |
| H13 | RBAC administration guide | PARTIAL | `docs/RBAC_ADMIN.md` — role model, seed script procedure, direct DB user management. No admin UI yet (KI-009). Only 2 of 4 planned roles implemented (KI-004). |
| H14 | Document retention policy | PARTIAL | `docs/RETENTION_POLICY.md` — 7-year policy documented, schedule defined. Automated enforcement NOT implemented (KI-005). Manual export and legal hold procedures documented. |
| H15 | Audit trail guide | DELIVERED | `docs/AUDIT_TRAIL_GUIDE.md` — what is logged, /audit endpoint, export procedure, regulatory response guidance, retention gap documented |

---

## Documents Produced at M5

| File | Handoff item | Status |
|------|-------------|--------|
| `docs/OPERATIONAL_RUNBOOK.md` | H1 | Delivered |
| `docs/MONITORING_GUIDE.md` | H2/H3 | Partial (gap documented) |
| `docs/CLIENT_TRAINING.md` | H4 | Delivered |
| `docs/SUPPORT_TIERS.md` | H5 | Delivered |
| `docs/ACCESS_CREDENTIALS.md` | H6 | Partial |
| `docs/AUDIT_TRAIL_GUIDE.md` | H15 | Delivered |
| `docs/KNOWN_ISSUES.md` | H10 | Delivered |
| `docs/RBAC_ADMIN.md` | H13 | Partial |
| `docs/RETENTION_POLICY.md` | H14 | Partial |
| `docs/HANDOFF_CHECKLIST.md` | — | This document |

---

## Open Items for Phase 2B

The following must be completed before this system is considered fully handed off to an external operator:

1. **H2** — Configure GCP Cloud Monitoring dashboard (uptime, latency, error rate panels)
2. **H3** — Configure alert policies (/health, latency >3s, error rate >5%, crash loop)
3. **H8** — Conduct external UAT with real operator and produce UAT report
4. **H13** — Build admin UI for user management; implement approver and viewer roles
5. **H14** — Implement automated retention enforcement (DB deletion blocks, lifecycle rules, legal hold)
6. **KI-007** — Build reclassification mechanism (doc_type override and field correction)
7. **KI-003** — Provision dedicated Neon database for production
8. **H6** — Complete production credential rotation before external handoff
9. **H9** — Produce production smoke report when production deployment occurs

---

## Client Sign-off

72-hour acceptance window begins on delivery of this package. No response = implied acceptance.

Sign-off required from: designated operator admin.

Admin must confirm:
- [ ] All user accounts provisioned and roles assigned
- [ ] Training materials reviewed
- [ ] Known issues register reviewed and acknowledged
- [ ] Retention policy gaps acknowledged

---

*Handoff checklist produced by Arukai squad at M5 milestone. POR-144.*
