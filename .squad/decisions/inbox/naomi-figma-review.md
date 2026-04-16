# Naomi — Figma + Backend Second-Opinion Review
**Date:** 2026-04-15
**Author:** Naomi (backup BE, fresh eyes)
**Spec ref:** v02-atelier-spec.md (POR-147 / ARU-17)
**Backend reviewed:** `/backend/app/` — models.py, routers/packages.py, routers/approvals.py, auth.py, classify.py, db.py
**Figma page:** 9:3 (metadata retrieved; design_context tool not available — review based on spec + code)

---

## Executive summary

The v0.1 backend is clean but was designed for a two-state world (`pending_review` → `approved`/`rejected`). V0.2 introduces a six-state machine, a new role tier, reviewer notes, per-field confidence, and audit-ledger requirements. The gap is large. I count **8 structural risks** that Drummer may not surface because they are invisible from the happy-path flow. I am claiming ownership of the two highest-risk pieces (state machine + reviewer notes) and flagging 9 concrete data-integrity questions.

---

## 1. State machine analysis

### 1.1 Current shape

The `Package.status` column is a four-value SQLAlchemy `Enum` (`pending_classification`, `pending_review`, `approved`, `rejected`). Transitions are implicit: the upload endpoint hard-codes `→ pending_review`; the approval endpoint hard-codes `→ body.decision`. There is **no transition guard anywhere**.

### 1.2 Risks on the six-state model

**R1 — No transition guard = no idempotency.**
The approval endpoint does:
```python
pkg.status = body.decision
```
With v0.2 states, a second `POST /approvals/{id}` on an already-`decision_recorded` package will silently overwrite the terminal state and insert a second `Approval` row — but `Approval.package_id` has `unique=True`, so it will actually raise an `IntegrityError` unhandled at the ORM layer, surfacing as a 500 rather than a 409. The client gets an ambiguous crash instead of a governed response.

**Fix required:** A transition table in the service layer that validates `(current_state, requested_transition)` and raises HTTP 409 with the spec-mandated body `{"detail":"Transition {from}→{to} not permitted"}` before any DB write.

**R2 — Double-submit race condition on `POST /packages/{id}/transition`.**
If two reviewers simultaneously send the `under_review → routed_for_approval` transition, both will read the same `current_state = under_review`, both will pass the guard, and both will commit. The second commit silently re-writes the state with no error. The spec's audit trail will show two `routed_for_approval` events from different actors — a governance inconsistency.

**Fix required:** Optimistic locking. Add a `version: int` column to `Package`. The transition service issues `UPDATE packages SET state=:new, version=version+1 WHERE id=:id AND version=:expected_version`. If 0 rows updated, return 409 `{"detail":"Concurrent modification — reload and retry"}`. Do not rely on SQLAlchemy session-level locking alone with async sessions.

**R3 — `exception_surfaced` can be entered from `intake_complete` by a reviewer, but the spec says the operator resolves it.**
The spec transition matrix (§2.2) allows `exception_surfaced → intake_complete` only by an operator. The current role model has only `admin` and `reviewer`. There is no `operator` role. If Drummer maps `operator → admin` for Phase A, the guard logic must explicitly document this mapping and it must be audited. If an approver inadvertently resolves an exception (because they are admin-equivalent), the audit trail will incorrectly attribute the resolution.

**R4 — `under_review → intake_complete` is only allowed "if no notes recorded".**
This condition requires a database check at transition time, not just a role check. The transition guard must `SELECT COUNT(*) FROM reviewer_notes WHERE package_id=:id` before permitting this rollback. If Drummer forgets this, a reviewer can silently abandon a reviewed package, stripping it of its notes, which is an audit integrity violation.

---

## 2. Reviewer notes model

### 2.1 What the spec requires (§6.3)

- Notes are **entirely separate** from approval/attestation notes (the spec calls this "the single most important backend separation in Phase B").
- Each note: `author_id`, `timestamp`, `body`, `linked_field` (nullable).
- Notes are **never deleted** by anyone — they are part of the governance record.
- The attestation modal recaps reviewer notes inline (§7.1, item 4).

### 2.2 What v0.1 has

Nothing. There is no `ReviewNote` table, no endpoint, no foreign key. The spec's `ReviewNote` table (B1 scope) must be created from scratch.

### 2.3 Risks I am raising

**R5 — No edit history on reviewer notes.**
The spec does not explicitly require edit history, but it implies immutability: the attestation modal recaps notes "on record" as if they were ledger entries. If the API exposes a `PATCH /packages/{id}/review-notes/{note_id}` without versioning, a reviewer could silently alter a note after the approver has read it and before the attestation completes. The attestation modal would then show the edited text, not what the approver actually reviewed.

**Recommendation:** Make `reviewer_notes` append-only. No `UPDATE` or `DELETE` endpoint. If a correction is needed, append a new note with a `supersedes_note_id` foreign key (nullable). This is the same pattern as the audit table.

**R6 — Who can write a review note is not enforced by the spec's API contract.**
The spec says only reviewers annotate. But the current auth model has no `reviewer` role — it has `admin` and `reviewer`, where `admin` maps to both Operator and Approver in v0.2. Without an explicit role check on `POST /packages/{id}/review-notes`, an approver can write reviewer notes, which muddies the attestation chain.

**Fix:** The note creation endpoint must require `role in ('reviewer')`. If operator/approver annotation is needed, it must use a separate endpoint with a distinct note type.

---

## 3. Confidence scoring

### 3.1 Current shape

`Classification.confidence` is a single `Float` — document-level, not field-level. `key_indicators` is a `JSON` blob with no schema. There is no per-field confidence anywhere in the model.

### 3.2 What v0.2 requires (§4, §6.2)

Per-field confidence: `{field_name: {value, confidence}}` shape in `extracted_fields` on the `Classification` row. Backfill existing rows with `backfilled: true` flag.

### 3.3 Risks

**R7 — Re-classification / re-extraction has no history.**
The spec requires that after a reviewer resolves an `exception_surfaced` package (operator corrects fields), the package transitions back to `intake_complete`. But `Classification` has `unique=True` on `document_id` — there can only be one classification per document. If the system re-runs extraction after an exception is resolved, it must `UPDATE` the existing row, **destroying the original extraction result**. The audit trail will show "exception resolved" but there will be no record of what the original extracted values were.

**Fix required:** Change `Classification` to a one-to-many relationship with `Document` (remove `unique=True` constraint, add `is_current: bool` flag or use `created_at` ordering). Each extraction run produces a new row; the old row is retained. The `extracted_fields` diff between runs should be captured in the audit event.

**R8 — `extracted_fields` backfill is lossy.**
The spec says "backfill existing rows with document-level confidence applied uniformly (with `backfilled: true` flag)". But if the existing `key_indicators` JSON does not contain per-field values (it contains phrases like `["Capital call", "drawdown notice"]`), the backfill will produce `{field_name: {value: null, confidence: 0.5}}` for every field. The frontend will render all v0.1 packages as "Confident" band (0.70–0.89 mapped to the backfilled 0.5 threshold? No — 0.5 is exactly the "Needs review" lower bound). This could cause v0.1 packages to incorrectly appear in the `exception_surfaced` filter.

**Fix:** The migration must be explicit about backfill logic: use `document_level_confidence` for all per-field confidence entries, not a uniform 0.5, and mark them `backfilled: true`. Also confirm that `exception_surfaced` routing on intake uses the **per-field** confidence, not the document-level confidence, after B1.

---

## 4. Audit trail integrity

### 4.1 Current shape

`AuditEvent` is SQLAlchemy ORM with no DB-level immutability. The application currently writes audit events in the upload handler and approval handler. There is no global audit endpoint — only per-package `/audit/{pkg_id}`.

### 4.2 Risks

**R9 — No database-level append-only enforcement.**
The table has no `CHECK` constraints, no row-level security, and no trigger preventing `UPDATE` or `DELETE`. Any code path with DB access (including a future bug, a migration gone wrong, or a compromised service account) can modify or delete audit rows without leaving a trace. For a "governed capital-call" system, this is a compliance exposure.

**Fix options (in order of preference):**
1. PostgreSQL production: add a `BEFORE UPDATE OR DELETE` trigger on `audit_events` that raises an exception. This is enforced at the DB layer regardless of application code.
2. Cloud Run: enable PostgreSQL RLS so the application user has `INSERT` only on `audit_events`, not `UPDATE`/`DELETE`.
3. Minimum viable: add a `UNIQUE` constraint on `(package_id, actor_user_id, action, created_at)` so identical events cannot be silently duplicated (does not prevent deletion but catches double-writes).

**R10 — `ondelete="SET NULL"` on `audit_events.package_id` allows orphan events without package context.**
If a package is deleted (even accidentally via cascade from a user delete), all its audit events will have `package_id = NULL`. They will not appear in the per-package audit log. They will be invisible in the global ledger if filtered by package. The governance record evaporates.

**Fix:** The spec calls `decision_recorded` a terminal state with no transitions. Packages in terminal state must not be deletable. Add a `CHECK` or application-level guard: `DELETE /packages/{id}` should be entirely absent from the API, or restricted to non-terminal states only. The `ondelete` on `audit_events.package_id` should be `RESTRICT`, not `SET NULL`.

---

## 5. 7-year retention

The spec does not explicitly state 7 years but the "Audit ledger" and "governed capital-call intake" framing implies regulatory retention (typical for fund administration: 7 years under SEC/FINRA rules).

**R11 — audit_events table will grow unboundedly.**
At scale (hundreds of packages per year, ~10 events each), the table is manageable. But if the system ever ingests historical data or runs high-frequency intake batches, the table becomes a bottleneck on unindexed queries. The global audit ledger endpoint (B1 scope) requires `actor`, `action`, and `date range` filters. Without a composite index on `(created_at, action, actor_user_id)`, every filter is a full table scan.

**Partitioning plan:**
- PostgreSQL: partition `audit_events` by `RANGE(created_at)` with monthly or annual partitions.
- Each partition older than 7 years can be detached and archived to cold storage (e.g., GCS) while remaining queryable via foreign data wrapper or BigQuery federated query.
- SQLite (dev): not partitionable — not a concern for dev, but the migration to PostgreSQL must create the partitioned table from day one, not retrofit it.

**Archive strategy:**
- A quarterly job exports partitions older than 6 years to GCS in Parquet format, signed with a HMAC to preserve tamper evidence.
- The exported partition is detached from the live table but its manifest is retained in a `audit_archive_manifest` table: `{partition_name, created_at, row_count, sha256_hash, gcs_uri}`.

---

## 6. Migration: v0.1 → v0.2

### 6.1 The mapping (from spec §2.3)

| v0.1 status | v0.2 state | Condition |
|---|---|---|
| `pending_classification` | `submitted` | — |
| `pending_review` | `intake_complete` | classification.confidence ≥ 0.5 |
| `pending_review` | `exception_surfaced` | classification.confidence < 0.5 |
| `approved` | `decision_recorded` | + Approval.decision = 'approved' |
| `rejected` | `decision_recorded` | + Approval.decision = 'rejected' |

### 6.2 Migration risks

**R12 — The confidence threshold check for `pending_review` requires a JOIN at migration time.**
The migration must `JOIN packages p ON classifications c ON documents d` to read `c.confidence` and decide which `pending_review` packages become `exception_surfaced`. This is a data-dependent migration, not a schema-only migration. If any package has documents without a classification row (e.g., classification failed silently and left the package at `pending_review`), the JOIN will produce NULL and the migration will have no rule to follow.

**Fix:** The Alembic migration must explicitly handle the NULL confidence case: treat missing classification as `confidence = 0.0` → `exception_surfaced`. This must be a documented assumption in the migration script, not a silent default.

**R13 — The `legacy_status` column adds complexity to the ORM layer for one sprint.**
The spec says "keep old column temporarily as `legacy_status` for one sprint, then drop." During that sprint, both `Package.status` (old enum) and `Package.state` (new enum) will exist. Any code that reads `pkg.status` will get the v0.1 value; any code reading `pkg.state` gets v0.2. If a v0.1 test fixture or seed script writes `status="pending_review"` after the migration, the `state` column will be stale. SQLAlchemy `onupdate` does not propagate across columns.

**Fix:** Add a DB trigger or application-layer enforcement: when `legacy_status` is written, raise an exception directing callers to use `state`. Alternatively, make `legacy_status` a generated column (read-only, derived from `state` via a reverse mapping) so there is only one source of truth.

**R14 — No migration test fixture in the current test suite.**
The existing tests in `test_documents.py` and `test_approvals.py` create packages with `status="pending_review"` and `status="approved"`. After B1, these fixtures will be incompatible with the new enum. If Drummer migrates the enum without updating the test fixtures, all existing tests will fail at the fixture stage — a Miller gate failure that could cost a half-day of debugging.

**Fix (I will own this):** Before B1 merges, I will update conftest and fixture factories to produce packages with the new `package_state` enum values, keeping a `LegacyPackageFactory` that creates rows with `legacy_status` set for testing the migration path.

---

## 7. Proposed split with Drummer

### Naomi owns:

1. **State machine service layer** — `app/services/state_machine.py`: transition table, guard function, optimistic locking via `version` column, 409 responses. Corresponding Alembic migration adding `package_state` enum + `version` column.

2. **`ReviewNote` table + endpoints** — `app/models.py` additions, `POST /packages/{id}/review-notes`, `GET /packages/{id}/review-notes`. Append-only enforcement (no update/delete endpoints). Role guard (`reviewer` only). `supersedes_note_id` nullable FK for corrections.

3. **v0.1 → v0.2 migration script** — Alembic migration with the JOIN-based confidence threshold routing, NULL safety, `legacy_status` column, and documented assumptions.

4. **Test fixture refactor** — update conftest + existing test fixtures for new enum values; add migration-path fixture.

5. **Audit append-only DB trigger** — PostgreSQL trigger preventing UPDATE/DELETE on `audit_events`; SQLite dev guard in application layer.

### Drummer owns:

1. **`POST /packages/{id}/transition` endpoint** — calls Naomi's state machine service, writes the `AuditEvent`.

2. **`extracted_fields` JSON column on `Classification`** — schema extension, per-field confidence shape, backfill migration.

3. **`GET /audit` global ledger endpoint** — with `actor`, `action`, `date_range` filter params; composite index on `(created_at, action, actor_user_id)`.

4. **`approver` role addition** — add `approver` to `user_role` enum; update `require_role` guards on approval endpoints.

5. **Classification one-to-many refactor** — remove `unique=True` on `document_id`, add `is_current` flag, so re-extraction preserves history.

---

## 8. Open questions (9 concrete, requiring answers before B1 starts)

**Q1.** The spec says `under_review → intake_complete` is allowed "only if no notes recorded." Does "no notes" mean zero `ReviewNote` rows, or does it mean no notes in the current review session? If a reviewer adds a note and then deletes it (in a future version), can they still release the claim? We need a definition before we write the guard.

**Q2.** The `Approval` table has `unique=True` on `package_id`. The spec allows `routed_for_approval → under_review` (approver returns to reviewer) and then the package can be routed again and re-approved. A second approval attempt will hit the unique constraint. Does `Approval` need to become one-to-many (with `is_final: bool`), or do we `DELETE` the non-final approval rows (losing history)?

**Q3.** Can an approver record a rejection directly from `exception_surfaced`? The spec says yes (§2.2). But `exception_surfaced` packages may not have any reviewer notes. The attestation modal (§7.1) recaps reviewer notes; if there are none, it shows the italic warning. Does the backend need to enforce that the attestation note is required when rejecting from `exception_surfaced` (since there are no reviewer notes to provide context)? Or is that a frontend concern only?

**Q4.** The spec's `exception_surfaced` state is entered by the system on intake (confidence < 0.5) OR by a reviewer escalating from `intake_complete`/`under_review`. Who writes the `AuditEvent` when the system auto-transitions to `exception_surfaced`? The upload endpoint runs classification synchronously — `actor_user_id` would be the uploader, not a system actor. Should we add a `SYSTEM` sentinel user, or use `actor_user_id = NULL` with `action = "system_exception_surfaced"`?

**Q5.** The global audit ledger (`GET /audit`) needs date-range filters. What is the maximum date range the API should accept in a single request? Without a limit, a query like `?from=2019-01-01&to=2026-01-01` on a partitioned table spanning 7 years will be slow and expensive. Should we cap at 90 days per request and require pagination?

**Q6.** `AuditEvent.before_state` and `after_state` are `JSON` with no schema. The current upload handler puts `{package_id, filename, size_bytes}` in `after_state`; the approval handler puts `{status: "approved", note: "..."}`. V0.2 needs `before_state` and `after_state` to contain the full state transition diff for the "expandable before/after JSON diff" in the audit trail UI (§6.4). Do we define a canonical schema for these fields in B1, or leave them free-form and let the frontend render whatever is there?

**Q7.** The `Session` table is the JWT revocation store. Sessions are checked on every authenticated request. As user count and session count grow, this becomes a hot read path. Is there a plan to add a TTL-based cleanup job for expired sessions, or will the sessions table grow indefinitely?

**Q8.** The `Document.content` column stores raw PDF bytes as `LargeBinary`. With multiple packages, this will bloat the database. The 20 MB per-file limit means a 1,000-package intake history could be 20 GB in the `documents` table alone. Is there a plan to move binary content to GCS (or similar object storage) before v0.2 goes to staging, or is this deferred to Phase C?

**Q9.** The spec's `Package.title` is 500 chars (`String(500)`). The `PackageOut` response schema includes `title` but the detail endpoint `PackageDetailOut` inherits it. The global audit ledger needs to display package references. If two packages have identical titles (which is allowed — there is no `unique` constraint), the audit ledger will show ambiguous references. Should we enforce title uniqueness per-uploader, or add a system-generated `package_reference` field (e.g., `ARU-2026-0042`) that is guaranteed unique and human-readable?

---

## Summary of risks by severity

| ID | Risk | Severity | Owner |
|---|---|---|---|
| R2 | Race condition on concurrent state transitions | **Critical** | Naomi |
| R1 | No transition guard → 500 on double-submit | **High** | Naomi |
| R7 | Re-classification destroys extraction history | **High** | Drummer |
| R10 | SET NULL on audit FK hides deleted-package events | **High** | Naomi |
| R5 | Reviewer notes mutable after attestation reads them | **High** | Naomi |
| R9 | No DB-level append-only on audit_events | **High** | Naomi |
| R12 | Migration JOIN with NULL confidence = silent mis-routing | **High** | Naomi |
| R3 | No `operator` role → approver resolves exceptions (audit contamination) | **Medium** | Drummer |
| R4 | `under_review → intake_complete` missing note-count guard | **Medium** | Naomi |
| R6 | No role guard on reviewer note creation | **Medium** | Naomi |
| R8 | Backfill confidence lossy for v0.1 packages | **Medium** | Drummer |
| R11 | No index / partition plan for audit_events at scale | **Medium** | Naomi |
| R13 | Two-column state during migration sprint = stale reads | **Low** | Naomi |
| R14 | Existing test fixtures incompatible with new enum | **Low** | Naomi |

---

*Naomi, 2026-04-15. Ready to take the state machine + reviewer notes pieces immediately once B1 failing tests are committed.*
