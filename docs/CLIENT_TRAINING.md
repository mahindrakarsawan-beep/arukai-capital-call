# Client Training Guide — Arukai Capital Call (D2)

**Version:** 1.0.0
**Date:** 2026-04-12
**Handoff item:** H4
**Audience:** First-time operators (admin and reviewer roles)

---

## 1. Getting Started — How to Log In

1. Open your browser and navigate to the frontend URL:
   `https://arukai-capital-call-frontend-staging-1035777337524.europe-west4.run.app`

2. You will see the login screen. Enter your email address and password.

3. Click **Sign In**.

4. On successful login, you will be taken to the main dashboard showing your document queue.

5. Your session lasts **8 hours**. After 8 hours, you will be redirected to the login screen. Any unsaved work will be lost, so complete uploads and reviews before your session expires.

**If you cannot log in:** Verify you are using the correct email address. Contact your admin to confirm your account is active and your role is assigned correctly.

---

## 2. How to Upload a Capital Call Document

> Only users with the **Admin** role can upload documents. Reviewers can view and annotate documents that have been uploaded by an admin.

1. From the main dashboard, click **Upload Document** (or the equivalent button in the navigation).

2. In the upload dialog:
   - Click **Choose File** and select the PDF to upload (capital call notice, subscription agreement, or side letter).
   - Supported formats: PDF only in v0.1.
   - Maximum file size: check the interface for the current limit.

3. Click **Upload**. The document will be submitted to the classification pipeline.

4. You will see a status indicator: **Processing...** while the AI classifies the document. This typically takes 5–30 seconds depending on document length and complexity.

5. Once processing is complete, the document will appear in the queue with its classification results. You will see:
   - Document type
   - Confidence score
   - Extracted fields

6. The upload event is automatically recorded in the audit trail.

---

## 3. Understanding Classification Output

After upload, the system displays three pieces of information for each document.

### 3.1 Document Type (`doc_type`)

The AI-assigned category for the document:

| doc_type | Meaning |
|----------|---------|
| `capital_call` | A capital call notice from a fund manager requesting capital from LPs |
| `subscription_agreement` | A subscription agreement for fund participation |
| `side_letter` | A side letter modifying the terms of a subscription |

> Note: In v0.1, `capital_call` is the primary tested classification. `subscription_agreement` and `side_letter` are supported at the API level but have received less testing coverage. See `KNOWN_ISSUES.md`.

### 3.2 Confidence Score

A number between 0.0 and 1.0 indicating how confident the AI is in the classification:

| Range | Interpretation |
|-------|---------------|
| 0.85 – 1.0 | High confidence — classification is likely correct |
| 0.60 – 0.84 | Moderate confidence — review the extracted fields carefully |
| Below 0.60 | Low confidence — treat classification as a suggestion; verify manually |

### 3.3 Extracted Fields

The system extracts structured data from the document. Typical fields for a capital call:

| Field | Description |
|-------|-------------|
| Fund name | Name of the investment fund |
| Call amount | Capital amount being called |
| Due date | Date by which capital must be transferred |
| Counterparty | Fund manager or GP name |
| LP reference | Investor identifier (if present in the document) |

Extracted fields are displayed alongside the document view. Reviewers should verify these fields against the source PDF.

---

## 4. How Admin Approves or Rejects

> Only users with the **Admin** role can approve or reject packages.

1. From the document queue, click on a document that has been reviewed and is ready for a decision.

2. Review the classification output and any comments left by reviewers.

3. Scroll to the **Decision** panel at the bottom of the document view.

4. Choose:
   - **Approve** — the package is accepted. The system records the approval with your user ID and timestamp.
   - **Reject** — the package is declined. You will be prompted to enter a rejection reason. This reason is stored in the audit trail.

5. Click **Submit Decision**.

6. The document status changes to `approved` or `rejected`. The state change is written to the audit trail immediately.

**Separation of duties note:** An admin cannot approve a package that they uploaded themselves in the same session. This is enforced by the system.

---

## 5. How to Read the Audit Trail

The audit trail records every significant action in the system. Admins can access it to review what happened, when, and by whom.

### Accessing the audit trail

- **Via the UI:** Navigate to **Audit Log** in the main navigation (admin-only section).
- **Via the API:** Send a GET request to `/audit` with a valid admin JWT token.

```bash
curl -H "Authorization: Bearer <your_admin_token>" \
  https://arukai-capital-call-backend-staging-1035777337524.europe-west4.run.app/audit
```

### Reading audit entries

Each entry contains:

| Field | Description |
|-------|-------------|
| `event_id` | Unique identifier for this audit record |
| `timestamp` | ISO 8601 datetime (UTC) when the action occurred |
| `user_id` | ID of the user who performed the action |
| `user_email` | Email of the user (for human readability) |
| `action` | Type of action (see table below) |
| `resource_type` | What was acted on (e.g., `document`, `session`) |
| `resource_id` | ID of the specific resource |
| `details` | Additional context (e.g., rejection reason, old/new role) |

### Common action types

| action | Meaning |
|--------|---------|
| `user.login` | User logged in successfully |
| `user.logout` | User logged out |
| `document.upload` | Document uploaded |
| `document.classify` | Classification completed |
| `document.approve` | Package approved |
| `document.reject` | Package rejected (includes reason) |
| `user.role_changed` | A user's role was modified |

---

## 6. Finding a Document After Upload

All uploaded documents are accessible from the main document queue on the dashboard.

1. From the dashboard, you will see a list of all documents with their status (`processing`, `pending_review`, `approved`, `rejected`).
2. Use the search or filter controls to find a specific document by fund name, date, or status.
3. Click any document row to open the full document view with classification results, extracted fields, comments, and audit history for that document.

Documents are stored persistently. Uploaded documents are not automatically deleted within the retention window (7 years per policy — see `RETENTION_POLICY.md` for current status).

---

## 7. What to Do If Classification Is Wrong

> **Known gap:** There is currently no reclassification mechanism in v0.1. A user cannot override an AI-assigned classification or trigger reprocessing through the UI or API.

If the AI has misclassified a document:

1. **Do not approve the package** based on the incorrect classification.
2. **Add a comment** to the document noting the discrepancy (e.g., "This is a subscription agreement, not a capital call").
3. **Reject the document** with a rejection reason explaining the classification error.
4. **Contact Arukai** (Tier 3 request) to reprocess the document manually or to investigate a pattern of misclassification.

This gap is tracked in `KNOWN_ISSUES.md` (item: reclassification mechanism not built). A correction workflow is planned for a future release.

---

## 8. Role Summary

| Role | Can do |
|------|--------|
| Admin | Upload, approve, reject, view audit trail, manage users (via seed script) |
| Reviewer | View documents, add comments, flag exceptions. Cannot approve/reject. |

---

*Training guide maintained by Arukai squad. For questions or to report a training issue, file a support request.*
