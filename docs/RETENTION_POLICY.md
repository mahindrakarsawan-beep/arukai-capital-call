# Document Retention Policy — Arukai Capital Call (D2)

**Version:** 1.0.0
**Date:** 2026-04-12
**Handoff item:** H14 (partial)
**Audience:** Operator admin, compliance officers

---

> **IMPORTANT — H14 Gap:** The retention policy defined in this document reflects the intended compliance requirements. Automated enforcement of this policy is NOT YET IMPLEMENTED in v0.1. No lifecycle rules, deletion blocks, or legal hold mechanisms are active. Adherence to this policy currently depends on manual discipline. See `KNOWN_ISSUES.md` (KI-005).

---

## 1. Policy Statement

All financial records processed by the Arukai Capital Call system must be retained for a minimum of 7 years from the date of the underlying financial event (capital call, subscription, or agreement execution). This baseline is derived from financial regulatory practice across major jurisdictions (EU, UK, US); some jurisdictions may require longer periods. Operators must confirm applicable local requirements.

---

## 2. Retention Schedule

| Document / Record Category | Minimum Retention | Maximum Retention | Notes |
|---------------------------|-------------------|-------------------|-------|
| Capital call notices | 7 years | Indefinite | Core financial instrument record |
| Subscription agreements (signed) | 7 years | Indefinite | Required by financial services regulation |
| Side letters | 7 years | Indefinite | Modifies primary subscription terms |
| Supporting documents (KYC, AML, tax forms) | 7 years | Indefinite | Regulatory; some jurisdictions longer |
| Approval records (who approved, when, evidence) | 7 years | Indefinite | Audit trail integrity |
| Rejection records | 3 years | 7 years | Compliance review trail |
| System audit logs (login, upload, classify, approve, reject) | 3 years | 7 years | Operational; see `AUDIT_TRAIL_GUIDE.md` |
| AI analysis outputs (classification results, extracted fields) | 1 year | 3 years | Operational; not primary records |
| Application logs (HTTP request/response) | 90 days | 1 year | Debugging only |

---

## 3. Enforcement Status

| Control | Intended Implementation | Current Status |
|---------|------------------------|----------------|
| Database deletion block (within retention window) | System prevents deletion of records within retention period | NOT IMPLEMENTED |
| GCP Object Lifecycle rules (document storage) | Automatic storage class transitions; deletion blocked until retention period expires | NOT IMPLEMENTED |
| Legal hold flag | Admin can mark records as legally held, preventing deletion regardless of lifecycle | NOT IMPLEMENTED |
| Automated archival pipeline | Documents move to Nearline storage after 1 year, Coldline after 3 years | NOT IMPLEMENTED |
| Retention policy audit (scheduled review) | Annual review of retention compliance | NOT IMPLEMENTED |

**Current state:** Records are retained as long as the Neon Postgres database and associated storage remain intact. There is no automated mechanism preventing deletion. Operators must not delete records manually and should contact Arukai before any database maintenance.

---

## 4. Manual Export Procedure

Use this procedure to export records for regulatory requests, audits, or backup.

### 4.1 Audit trail export

See `AUDIT_TRAIL_GUIDE.md` Section 4 for the full procedure. Summary:

1. Open Neon console (Arukai-managed; request access).
2. Run SQL query against the `audit_events` table.
3. Export as CSV.
4. Store securely.

### 4.2 Document metadata export

```sql
SELECT
  d.id AS document_id,
  d.filename,
  d.doc_type,
  d.confidence,
  d.status,
  d.uploaded_by,
  d.uploaded_at,
  d.approved_by,
  d.approved_at,
  d.rejected_by,
  d.rejected_at,
  d.rejection_reason
FROM documents d
ORDER BY d.uploaded_at ASC;
```

### 4.3 Full package export (for regulatory requests)

For a specific document package:

```sql
-- Get document details
SELECT * FROM documents WHERE id = '<document_id>';

-- Get all audit events for this document
SELECT * FROM audit_events
WHERE resource_type = 'document' AND resource_id = '<document_id>'
ORDER BY created_at ASC;
```

Export both result sets and combine with the stored PDF file (retrieved from Cloud Storage by Arukai).

---

## 5. Legal Hold

**Current status: NOT IMPLEMENTED.**

Until the automated legal hold feature is built, the following manual procedure applies:

1. If you receive a legal hold instruction or regulatory preservation order:
   - Contact Arukai immediately (Tier 3 request, mark as P0 if under time pressure).
   - Do not delete or modify any records.
   - Arukai will apply a manual hold at the database level by setting a `legal_hold = true` flag (if the column exists) or by documenting the hold in writing.

2. Document the legal hold instruction and Arukai's acknowledgment in your own compliance records.

3. When the legal hold is lifted, contact Arukai to remove it and document the lifting.

---

## 6. Phase 2A Rehearsal Note

During Phase 2A internal rehearsal, a shortened retention period (90 days for all categories) is used to avoid accumulating test data. This does not reflect production requirements. Before any production or external client deployment, retention must be extended to the schedule in Section 2 and automated controls must be implemented (planned for Phase 2B).

---

## 7. Jurisdictional Awareness

The system stores documents with a `jurisdiction` metadata field (where populated). In Phase 2B, per-jurisdiction retention rules can be implemented. Until then, the 7-year baseline applies to all documents regardless of jurisdiction.

Operators are responsible for determining whether local regulatory requirements exceed the 7-year baseline and for ensuring the system is configured accordingly.

---

*Retention policy maintained by Arukai squad. Legal questions should be directed to the operator's legal counsel. Compliance questions should be escalated via the support tier process.*
