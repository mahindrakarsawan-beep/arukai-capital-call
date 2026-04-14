# Known Issues Register — Arukai Capital Call (D2)

**Version:** 1.0.0
**Date:** 2026-04-12
**Handoff item:** H10
**Maintained by:** Arukai squad

---

This register consolidates all known gaps, partial implementations, and deferred features as of the M5 governance handoff. Each item includes its governance impact, severity, and the planned resolution phase.

---

## Issue Register

### KI-001 — No Cloud Monitoring Dashboard

| Field | Value |
|-------|-------|
| Handoff item | H2 |
| Severity | P2 — operational gap |
| Status | MISSING |
| Impact | No automated uptime visibility. Monitoring is manual (curl /health + log inspection). |
| Workaround | Manual health checks per `MONITORING_GUIDE.md` Section 1. |
| Resolution | Phase 2B or follow-on engagement. Configure GCP Cloud Monitoring dashboard with uptime, latency, and error rate panels. |

---

### KI-002 — No Alert Policies Configured

| Field | Value |
|-------|-------|
| Handoff item | H3 |
| Severity | P2 — operational gap |
| Status | MISSING |
| Impact | No automated notification for /health failures, latency spikes, or 5xx error rate increases. |
| Workaround | Manual log monitoring per `MONITORING_GUIDE.md`. Alert intent is documented in Section 3 of that guide. |
| Resolution | Phase 2B. Configure policies in GCP Cloud Monitoring as documented in `MONITORING_GUIDE.md` Section 3. |

---

### KI-003 — No Dedicated Neon Database

| Field | Value |
|-------|-------|
| Handoff item | Infrastructure |
| Severity | P2 — environment isolation gap |
| Status | PARTIAL |
| Impact | The staging deployment may be using a shared Neon Postgres instance (shared with Portfolio Analyzer or another project). Data isolation between projects depends on schema-level separation, not project-level isolation. |
| Workaround | Confirm database isolation at deployment time. Arukai to verify connection strings in Secret Manager. |
| Resolution | Provision a dedicated Neon project for production deployment. |

---

### KI-004 — RBAC Limited to 2 Roles

| Field | Value |
|-------|-------|
| Handoff item | H13 |
| Severity | P2 — feature gap |
| Status | PARTIAL |
| Impact | The governance plan defines 4 roles (admin, approver, reviewer, viewer). v0.1 implements only 2 (admin, reviewer). Approver and Viewer roles are not available. Separation of duties between submission and approval depends on admin discipline, not a distinct approver role. |
| Workaround | Use admin role for approvals. Ensure admins do not approve their own uploads (manual process). |
| Resolution | Phase 2B. Implement approver and viewer roles with full permission matrix. |

---

### KI-005 — No 7-Year Retention Enforcement

| Field | Value |
|-------|-------|
| Handoff item | H14 |
| Severity | P1 — compliance gap |
| Status | PARTIAL |
| Impact | The 7-year minimum retention policy is documented but NOT automated. There are no lifecycle rules, deletion blocks, or legal hold mechanisms in place. Records could theoretically be deleted from the database by a direct admin action. |
| Workaround | Do not delete any records from the audit_events or documents tables manually. See `RETENTION_POLICY.md` for manual export procedures. |
| Resolution | Phase 2B. Implement DB-level deletion constraints, GCP Object Lifecycle rules for stored documents, and automated archival pipeline. |

---

### KI-006 — No External Operator for Handoff

| Field | Value |
|-------|-------|
| Handoff item | H8 |
| Severity | P1 — fundamental Phase 2B gap |
| Status | NOT APPLICABLE (Phase 2A) |
| Impact | This Phase 2A rehearsal has no external operator. UAT was internal only. H8 (UAT report with external operator) cannot be delivered until Phase 2B when a real client operator participates. |
| Workaround | Internal rehearsal UAT documented in M4 smoke results. |
| Resolution | Phase 2B. Engage external operator for formal UAT and produce H8 UAT report. |

---

### KI-007 — No Reclassification Mechanism

| Field | Value |
|-------|-------|
| Handoff item | None (feature gap) |
| Severity | P2 — usability gap |
| Status | NOT BUILT |
| Impact | If the AI classifies a document incorrectly, there is no way for the user to override the classification, correct extracted fields, or trigger reprocessing. The only option is to reject the document and re-upload. |
| Workaround | Reject documents with incorrect classification. Note the error in the rejection reason. Contact Arukai for manual reprocessing (Tier 3). |
| Resolution | Phase 2B. Build a reclassification UI and API endpoint allowing admins to override doc_type and rerun field extraction. |

---

### KI-008 — Single Document Type Fully Tested

| Field | Value |
|-------|-------|
| Handoff item | None (test coverage gap) |
| Severity | P2 — reliability gap |
| Status | PARTIAL |
| Impact | Only `capital_call` documents have been extensively tested through the classification pipeline in v0.1. `subscription_agreement` and `side_letter` are supported at the API level (doc_type enum values exist) but have not been validated with real or representative test documents. Confidence scores and extraction accuracy for these types are unknown. |
| Workaround | Use with capital call documents only until other types are validated. |
| Resolution | Phase 2B. Provide representative test documents for each doc_type. Validate extraction accuracy and update prompt/model as needed. |

---

### KI-009 — No Admin UI for User Management

| Field | Value |
|-------|-------|
| Handoff item | H13 |
| Severity | P2 — operational gap |
| Status | PARTIAL |
| Impact | User accounts can only be created via the seed script. There is no UI for adding users, changing roles, or deactivating accounts. All user management requires direct database access. |
| Workaround | See `RBAC_ADMIN.md` for current user management procedures using direct DB updates. |
| Resolution | Phase 2B. Build an admin user management panel in the frontend. |

---

## Summary

| ID | Issue | Handoff item | Severity | Status |
|----|-------|-------------|----------|--------|
| KI-001 | No Cloud Monitoring dashboard | H2 | P2 | MISSING |
| KI-002 | No alert policies | H3 | P2 | MISSING |
| KI-003 | No dedicated Neon DB | Infrastructure | P2 | PARTIAL |
| KI-004 | RBAC limited to 2 roles | H13 | P2 | PARTIAL |
| KI-005 | No 7-year retention enforcement | H14 | P1 | PARTIAL |
| KI-006 | No external operator for handoff | H8 | P1 | N/A (Phase 2A) |
| KI-007 | No reclassification mechanism | — | P2 | NOT BUILT |
| KI-008 | Single doc type fully tested | — | P2 | PARTIAL |
| KI-009 | No admin UI for user management | H13 | P2 | PARTIAL |

---

*Known issues register maintained by Arukai squad. New issues should be filed in Linear with label `known-issue` and added to this register at the next milestone.*
