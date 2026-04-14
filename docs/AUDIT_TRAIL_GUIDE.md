# Audit Trail Guide — Arukai Capital Call (D2)

**Version:** 1.0.0
**Date:** 2026-04-12
**Handoff item:** H15
**Audience:** Operator admin, compliance officers

---

## 1. What Is Logged

The audit trail records every significant action in the system. Entries are immutable once written — they cannot be edited or deleted through the application.

### Logged events

| Event type | Trigger | Fields captured |
|------------|---------|----------------|
| `user.login` | User authenticates successfully | user_id, email, IP address, timestamp |
| `user.login_failed` | Failed login attempt | email attempted, IP address, timestamp |
| `user.logout` | User logs out or session expires | user_id, timestamp |
| `document.upload` | Document uploaded | user_id, document_id, filename, file_size, timestamp |
| `document.classify` | Classification pipeline completes | document_id, doc_type, confidence, extracted_fields, timestamp |
| `document.view` | User opens a document | user_id, document_id, timestamp |
| `document.approve` | Admin approves a package | user_id, document_id, timestamp |
| `document.reject` | Admin rejects a package | user_id, document_id, rejection_reason, timestamp |
| `document.comment` | User adds a comment | user_id, document_id, comment_text, timestamp |
| `user.created` | New user account created | created_by (admin user_id), new_user_id, email, role, timestamp |
| `user.role_changed` | User role modified | changed_by, target_user_id, old_role, new_role, timestamp |
| `user.deactivated` | User account deactivated | changed_by, target_user_id, timestamp |

### What is NOT logged

- Document content (the PDF itself is not stored in the audit table)
- Internal system health checks and infrastructure metrics
- Unauthenticated requests (except failed logins)

---

## 2. How to View the Audit Log

### Via the application UI (admin only)

1. Log in with an admin account.
2. Navigate to **Audit Log** in the main navigation.
3. The audit log is displayed in reverse chronological order (newest first).
4. Use filters to narrow by date range, user, or event type.

### Via the API (admin only)

The `/audit` endpoint returns audit entries as JSON. Requires a valid admin JWT.

**Basic query — all recent entries:**

```bash
curl -s \
  -H "Authorization: Bearer <your_admin_token>" \
  https://arukai-capital-call-backend-staging-1035777337524.europe-west4.run.app/audit
```

**Query with filters (if supported by the API):**

```bash
# Filter by event type
curl -s \
  -H "Authorization: Bearer <your_admin_token>" \
  "https://arukai-capital-call-backend-staging-1035777337524.europe-west4.run.app/audit?event_type=document.approve"

# Filter by user
curl -s \
  -H "Authorization: Bearer <your_admin_token>" \
  "https://arukai-capital-call-backend-staging-1035777337524.europe-west4.run.app/audit?user_id=<user_id>"
```

Check the API documentation or contact Arukai for the full list of supported query parameters.

---

## 3. Retention Policy

| Record type | Minimum retention | Policy basis |
|-------------|------------------|--------------|
| Approval and rejection records | 7 years | Financial regulatory requirement |
| Document upload and classification records | 7 years | Same |
| User management events (role changes, deactivation) | 7 years | Audit integrity |
| Login/logout records | 3 years | Operational |

> **Known gap — H14:** The 7-year retention minimum is a documented policy. Automated enforcement (lifecycle rules, deletion blocking, legal hold mechanism) is NOT YET implemented in v0.1. Retention is currently dependent on the Neon Postgres database remaining intact. See `KNOWN_ISSUES.md` and `RETENTION_POLICY.md`.

---

## 4. Export Procedure

Use the export procedure when you need to produce audit records for a regulatory request, legal inquiry, or internal investigation.

### Option A: Via the API (if export endpoint is available)

```bash
curl -s \
  -H "Authorization: Bearer <your_admin_token>" \
  "https://arukai-capital-call-backend-staging-1035777337524.europe-west4.run.app/audit/export" \
  -o audit_export_$(date +%Y%m%d).json
```

### Option B: Direct SQL query via Neon console

For bulk exports or when the API export is unavailable:

1. Log in to the Neon console at https://console.neon.tech (Arukai-managed; request access for regulatory exports).
2. Open the SQL editor for the `arukai-capital-call` database.
3. Run the appropriate query:

```sql
-- Full audit trail export (all time)
SELECT
  event_id,
  event_type,
  user_id,
  user_email,
  resource_type,
  resource_id,
  details,
  ip_address,
  created_at
FROM audit_events
ORDER BY created_at ASC;
```

```sql
-- Export for a specific date range
SELECT *
FROM audit_events
WHERE created_at BETWEEN '2026-01-01' AND '2026-12-31'
ORDER BY created_at ASC;
```

```sql
-- Export for a specific document
SELECT *
FROM audit_events
WHERE resource_type = 'document'
  AND resource_id = '<document_id>'
ORDER BY created_at ASC;
```

4. Use the Neon console's **Export** function to download the result as CSV.
5. Store the exported file securely. Log the export event in your own compliance records.

---

## 5. Responding to Regulatory Requests

If you receive a regulatory or legal request for audit records:

1. **Do not delete or modify** any records. If there is any risk of accidental deletion, contact Arukai to implement a manual hold on the database.
2. Identify the scope of the request (date range, document IDs, user IDs, event types).
3. Export the relevant records using Option B above or request Arukai assistance (Tier 3).
4. Review the export for completeness before submitting.
5. Log the regulatory request and your export action in your own compliance records.

> **Note:** The automated legal hold feature (which would prevent deletion of flagged records in the system) is not yet implemented. See `KNOWN_ISSUES.md`. For now, treat this as a manual process and contact Arukai before any database maintenance that could affect records.

---

## 6. Audit Trail Integrity

The audit trail is append-only. Application users cannot modify or delete audit entries through the API or UI. Direct database modifications are restricted to Arukai admins.

If you suspect audit trail tampering or a gap:

1. This is a **P0 security incident** — treat it with the highest urgency.
2. Contact Arukai immediately via the emergency contact in `SUPPORT_TIERS.md`.
3. Do not attempt to investigate or remediate independently.
4. Preserve all logs and access records for the investigation period.

---

*Audit trail guide maintained by Arukai squad. Compliance questions should be escalated via the support tier process.*
