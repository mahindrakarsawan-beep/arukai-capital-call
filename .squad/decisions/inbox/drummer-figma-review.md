# Drummer Figma Review — Backend Requirements (Phase B)
**Author:** Drummer (Sonnet)
**Date:** 2026-04-15
**Ticket scope:** ARU-17-B1
**Inputs:** v02-atelier-spec.md (§2 state machine, §3–§7 screens), full backend audit of v0.1 code
**Figma node:** Page 3 (9:3) — metadata retrieved; `get_design_context` tool was unavailable. All analysis below is driven from the authoritative spec + current codebase. Where Figma visual detail would add precision I note the gap explicitly.

---

## 0. Executive summary

v0.1 backend has 6 tables, 2 package states (`pending_classification` / `pending_review` / `approved` / `rejected` — actually 4 values), a single per-document classification confidence float, no reviewer-note concept, and an audit endpoint that is per-package only. v0.2 needs a 6-state machine, a new `reviewer_notes` table, per-field confidence on the classification, a global audit endpoint with filters, a `POST /packages/{id}/transition` gate, a third role (`approver`), and role enforcement on all mutating endpoints. This is substantial migration work — I'm claiming the data layer, state machine, and new endpoints; Naomi takes CSV export and audit pagination.

---

## 1. Screen-by-screen API contract derivation

### 1.1 Operations console (`GET /packages`)

**What the screen shows:** Five named sections — Exceptions, Pending approval, Needs review, Active packages, Recent decisions — each with a count badge, a list of package rows, and an empty state. Every row carries: package reference title, classification label, state pill, next-owner chip, relative timestamp.

**Current endpoint:** `GET /documents` — returns a flat list, no section grouping, no state filter, no pagination.

**v0.2 contract:**

```
GET /packages
  Query params:
    state: submitted | intake_complete | under_review | routed_for_approval |
           decision_recorded | exception_surfaced   (repeatable, OR logic)
    next_owner: system | reviewer | approver | operator   (maps to chip groupings)
    page: int (default 1)
    page_size: int (default 50, max 200)
    sort: last_moved_at:desc (default)

Response 200:
  {
    "total": int,
    "page": int,
    "page_size": int,
    "items": [
      {
        "id": str,
        "title": str,
        "state": package_state_enum,
        "classification_label": str,          // "Capital call notice" etc.
        "classification_confidence": float,   // document-level, for pill display
        "next_owner": str,                    // computed chip text
        "reviewer_id": str | null,            // for "With {reviewer}" chip
        "reviewer_name": str | null,
        "approver_name": str | null,          // populated on decision_recorded
        "decided_at": datetime | null,
        "last_moved_at": datetime,            // updated_at proxy
        "exception_reason": str | null        // "low_confidence" | "missing_field" | "extraction_failure"
      }
    ]
  }
```

**Design note:** The frontend needs the five sections without making five round trips. The recommended approach is a single endpoint with `state` multi-value filter and let the frontend segment by state. Avoid a `/console` aggregation endpoint — it binds the backend to a single layout and makes testing harder. Five parallel requests with `state=X` are acceptable but wasteful given SSE is not in scope for Phase B.

**Role-based visibility filter (server-side):**
- `operator` role: only packages where `uploaded_by == current_user.id`
- `reviewer` role: all packages in any state (read access), plus packages claimed by `current_user.id`
- `approver` role: all packages

**Index plan:**
```sql
CREATE INDEX ix_packages_state ON packages(state);
CREATE INDEX ix_packages_uploaded_by ON packages(uploaded_by);
CREATE INDEX ix_packages_last_moved_at ON packages(last_moved_at DESC);
-- Composite for the console query:
CREATE INDEX ix_packages_state_last_moved ON packages(state, last_moved_at DESC);
```

---

### 1.2 Package detail (`GET /packages/{id}`)

**What the screen shows:** Four blocks — Source document, Extracted facts (with per-field confidence), Review notes, Audit trail. Header shows state pill + next-owner chip + approver/date if terminal.

**Current endpoint:** `GET /documents/{pkg_id}` — returns package + document + classification with a single `confidence` float. No reviewer notes. No per-field breakdown.

**v0.2 contract:**

```
GET /packages/{id}
Response 200:
  {
    "id": str,
    "title": str,
    "state": package_state_enum,
    "legacy_status": str | null,          // kept for one sprint per spec §2.3
    "uploaded_by": str,
    "uploader_name": str,
    "created_at": datetime,
    "last_moved_at": datetime,
    "exception_reason": str | null,
    "reviewer_id": str | null,
    "reviewer_name": str | null,
    "approver_name": str | null,
    "decided_at": datetime | null,
    "decision": "approved" | "rejected" | null,
    "next_owner": str,                    // computed server-side
    "document": {
      "id": str,
      "filename": str,
      "mime_type": str,
      "size_bytes": int,
      "pdf_url": str,                     // GET /packages/{id}/pdf
      "created_at": datetime
    },
    "classification": {
      "id": str,
      "document_type": str,
      "document_label": str,              // "Capital call notice"
      "confidence": float,                // document-level
      "model_version": str | null,
      "fallback": bool,
      "classification_error": str | null,
      "classified_at": datetime,
      "extracted_fields": {               // NEW — per §4 / spec §4.1
        "fund_name":               {"value": str | null, "confidence": float, "backfilled": bool},
        "call_number":             {"value": str | null, "confidence": float, "backfilled": bool},
        "call_amount":             {"value": str | null, "confidence": float, "backfilled": bool},
        "due_date":                {"value": str | null, "confidence": float, "backfilled": bool},
        "wire_instructions_ref":   {"value": str | null, "confidence": float, "backfilled": bool},
        "investor_of_record":      {"value": str | null, "confidence": float, "backfilled": bool},
        "side_letter_ref":         {"value": str | null, "confidence": float, "backfilled": bool}
      }
    },
    "review_notes": [                     // NEW — spec §6.3
      {
        "id": str,
        "author_id": str,
        "author_name": str,
        "body": str,
        "linked_field": str | null,
        "created_at": datetime
      }
    ],
    "audit_trail": [                      // per-package subset of global audit
      {
        "id": str,
        "actor_name": str | null,
        "action": str,
        "before_state": any,
        "after_state": any,
        "created_at": datetime
      }
    ]
  }
```

**Important:** `review_notes` and `approval.note` are separate. The `Approval.note` column is the attestation note (optional on approval, required on rejection). Review notes belong to `reviewer_notes` table. Never conflate them.

---

### 1.3 Attestation modal — record decision

**What the screen triggers:** Approver clicks [Attest approval] or [Record rejection]. Modal shows reviewer notes recap + attestation text. On confirm, POSTs decision atomically.

**Current endpoint:** `POST /approvals/{pkg_id}` — sets `pkg.status = "approved"|"rejected"` directly, no state machine gate.

**v0.2 contract:**

```
POST /packages/{id}/attest
  Role required: approver
  Precondition: package.state == routed_for_approval
  Body:
    {
      "decision": "approved" | "rejected",
      "note": str | null                  // null only if decision == "approved"
    }
  Validation:
    - If decision == "rejected" AND note is null or blank → 422 {"detail": "Attestation note required on rejection"}
    - If state != routed_for_approval → 409 {"detail": "Transition routed_for_approval→decision_recorded not permitted from state {current_state}"}
  On success (atomic, single transaction):
    1. Create Approval row (decision, note, decided_by, decided_at)
    2. Set package.state = decision_recorded
    3. Set package.last_moved_at = now()
    4. Write AuditEvent(action="attest_approval"|"record_rejection",
                        before_state={state:"routed_for_approval"},
                        after_state={state:"decision_recorded", decision:..., note:...})
  Response 200:
    {
      "id": str,
      "package_id": str,
      "decision": str,
      "note": str | null,
      "decided_at": datetime,
      "decided_by": str,
      "decided_by_name": str
    }
```

**Why not keep `POST /approvals/{pkg_id}`?** Keep the old endpoint functional for Phase A (the frontend uses it via `attestApproval`/`recordRejection` shim per spec §10 Phase A2). In B1 the old endpoint gets a deprecation header but stays alive. The new `/attest` endpoint is the canonical path and validates the state machine.

**Does the backend validate that reviewer notes exist before approving?** Per spec §7.1: the modal shows a warning if no notes are recorded but attestation is still permitted. The backend should NOT hard-block on missing reviewer notes — only surface them in the response. The attestation endpoint should return `reviewer_notes_count: int` in the 200 so the modal can display the warning. No 422 for missing notes.

---

### 1.4 State transition endpoint

**New endpoint — all non-attest transitions:**

```
POST /packages/{id}/transition
  Role: depends on transition (enforced per §2.2)
  Body:
    {
      "to_state": package_state_enum,
      "note": str | null
    }
  Logic:
    Valid transition matrix (from spec §2.2):
    submitted           → intake_complete        (system only — internal, not user-callable)
    submitted           → exception_surfaced      (system only)
    intake_complete     → under_review            (reviewer: claim)
    intake_complete     → exception_surfaced      (reviewer: flag)
    under_review        → routed_for_approval     (reviewer: route)
    under_review        → intake_complete         (reviewer: release — only if no notes)
    under_review        → exception_surfaced      (reviewer: escalate)
    routed_for_approval → under_review            (approver: return for revision)
    exception_surfaced  → intake_complete         (operator: resolve)
    exception_surfaced  → decision_recorded       → use /attest endpoint instead

  On invalid transition: 409 {"detail": "Transition {from}→{to} not permitted"}
  On wrong role: 403 {"detail": "This action is outside your workflow role."}

  On success:
    - Update package.state, last_moved_at
    - Write AuditEvent with before_state, after_state, actor_user_id
    - If to_state == under_review AND no reviewer_id claimed yet: set package.reviewer_id = current_user.id
    - If to_state == intake_complete (release): clear package.reviewer_id

  Response 200: full PackageDetailOut (so frontend can re-render without a second GET)
```

**System transitions (submitted → intake_complete / exception_surfaced):** These happen inside the upload handler synchronously (same transaction as classify). They are NOT exposed via the `/transition` endpoint. The upload handler evaluates confidence thresholds post-classification and sets state directly.

---

### 1.5 Review notes endpoints

```
POST /packages/{id}/review-notes
  Role: reviewer
  Precondition: package.state in (intake_complete, under_review)
  Body:
    {
      "body": str,          // non-empty required
      "linked_field": str | null   // e.g. "call_amount" — links to extracted field
    }
  On success:
    1. Create ReviewNote row
    2. If package.state == intake_complete: transition to under_review (implicit claim)
    3. Write AuditEvent(action="record_review_note")
  Response 201:
    {
      "id": str,
      "package_id": str,
      "author_id": str,
      "author_name": str,
      "body": str,
      "linked_field": str | null,
      "created_at": datetime
    }

GET /packages/{id}/review-notes
  Role: any authenticated
  Response 200: list of ReviewNoteOut (newest first)
```

---

### 1.6 Global audit ledger (`GET /audit`)

**What the screen shows:** Filterable, paginated log of all audit events across all packages. Filters: actor, action, date range. Export to CSV.

**Current:** Only `GET /audit/{pkg_id}` exists — per-package, no global, no filters.

**v0.2 contract (Drummer owns):**

```
GET /audit
  Role: any authenticated (scoped by role — operator sees own packages only)
  Query params:
    actor_user_id: str             // exact match
    action: str                    // exact or prefix match
    package_id: str                // filter to one package
    date_from: datetime (ISO 8601)
    date_to: datetime (ISO 8601)
    page: int (default 1)
    page_size: int (default 50, max 200)

  Response 200:
    {
      "total": int,
      "page": int,
      "page_size": int,
      "items": [AuditEventOut + actor_name + package_title fields]
    }
```

**CSV export (Naomi owns):**
```
GET /audit/export
  Same query params as GET /audit (no pagination — streams full result set)
  Accept: text/csv  (or ?format=csv query param)
  Response: StreamingResponse, Content-Disposition: attachment; filename="audit-{date}.csv"
  Columns: id, package_id, package_title, actor_name, action, before_state (JSON string), after_state (JSON string), created_at
```

**Index plan for audit_events:**
```sql
-- Already has: ix on package_id, ix on action
-- Add:
CREATE INDEX ix_audit_events_actor_user_id ON audit_events(actor_user_id);
CREATE INDEX ix_audit_events_created_at ON audit_events(created_at DESC);
-- Composite for filtered queries:
CREATE INDEX ix_audit_events_actor_created ON audit_events(actor_user_id, created_at DESC);
CREATE INDEX ix_audit_events_action_created ON audit_events(action, created_at DESC);
```

The audit table could grow large (every state transition + every review note = ~8-15 events per package). At 10K packages/year that's ~150K rows/year — manageable without partitioning for several years. Add a `created_at DESC` index now; revisit partitioning at 1M rows.

---

## 2. Phase B data model — new tables and migrations

### 2.1 Alembic migration: `package_state` enum

**Action:** Add `package_state` enum column, migrate data per spec §2.3, keep `legacy_status` for one sprint.

```python
# Migration pseudocode
# Step 1: add new column (nullable initially)
op.add_column('packages', sa.Column('state', sa.Enum(
    'submitted', 'intake_complete', 'under_review',
    'routed_for_approval', 'decision_recorded', 'exception_surfaced',
    name='package_state'
), nullable=True))

# Step 2: rename old column
op.alter_column('packages', 'status', new_column_name='legacy_status')

# Step 3: data migration (one-shot UPDATE)
# pending_classification → submitted
# pending_review + confidence < 0.5 → exception_surfaced
# pending_review + confidence >= 0.5 → intake_complete
# approved → decision_recorded
# rejected → decision_recorded

# Step 4: set NOT NULL constraint on state column

# Step 5: add last_moved_at column
op.add_column('packages', sa.Column('last_moved_at', sa.DateTime(timezone=True), nullable=True))
# Backfill: last_moved_at = updated_at for existing rows
```

**Additional columns on `packages`:**
```
reviewer_id: String(36) FK → users.id (nullable) — the reviewer who has claimed this package
exception_reason: Enum('low_confidence','missing_field','extraction_failure') (nullable)
last_moved_at: DateTime(timezone=True) — updated on every state transition
```

### 2.2 New table: `reviewer_notes`

```python
class ReviewNote(Base):
    __tablename__ = "reviewer_notes"

    id: Mapped[str]            # uuid
    package_id: Mapped[str]    # FK packages.id CASCADE DELETE, indexed
    author_id: Mapped[str]     # FK users.id SET NULL
    body: Mapped[str]          # Text, non-empty
    linked_field: Mapped[str | None]  # e.g. "call_amount" — nullable
    created_at: Mapped[datetime]

    # Indexes:
    # ix_reviewer_notes_package_id (package_id)
    # ix_reviewer_notes_author_id (author_id)
```

**Critical separation note (per spec §6.3):** `ReviewNote.body` is reviewer annotation. `Approval.note` is the attestation note written by the approver at decision time. They are never mixed. The package detail API returns them in separate keys (`review_notes` vs `approval.note`).

### 2.3 Classification schema extension: `extracted_fields`

**Action:** Add `extracted_fields` JSON column to `classifications` table.

```python
# New column
extracted_fields: Mapped[Any] = mapped_column(JSON, nullable=True)
# Shape: {"field_name": {"value": any, "confidence": float, "backfilled": bool}}
```

**Backfill strategy for existing rows:** Set all field confidence values = document-level `confidence`, `backfilled: true`. Values remain as-is from `key_indicators` if parseable, else null. Do NOT re-run Anthropic classification on existing documents — that would incur cost with no user-facing benefit.

**Impact on token cost (see §4.3 below).**

### 2.4 `user_role` enum expansion

Add `approver` to the `user_role` enum:
```python
Enum("admin", "reviewer", "approver", name="user_role")
# "admin" maps to "Operator" in the UI (per spec §1.6)
# "reviewer" stays
# "approver" is new
```

Alembic: ALTER TYPE or recreate enum (SQLite: recreate table). Add seed user: `approver@arukai.example` / `approver123` / role=`approver`.

---

## 3. Endpoint ownership split — Drummer vs Naomi

### Drummer owns

| Endpoint | Reason |
|---|---|
| `POST /packages/{id}/transition` | Core state machine — Drummer's primary domain |
| `POST /packages/{id}/attest` | State machine + atomic approval + audit write |
| `POST /packages/{id}/review-notes` | New table, state side-effect (implicit claim) |
| `GET /packages/{id}/review-notes` | Complement to POST |
| `GET /packages` (v0.2 refresh) | Pagination + state filters + role scoping rewrite |
| `GET /packages/{id}` (v0.2 refresh) | Add extracted_fields, review_notes, audit_trail, next_owner |
| Alembic migrations (all) | Schema owns the migration chain |
| `GET /audit` (global, non-export) | Core audit ledger query + filters + pagination |
| `app/models.py` updates | ReviewNote, package_state, approver role, extracted_fields |
| Transition validator module (`app/state_machine.py`) | Encapsulate the transition matrix as a pure function for Miller to test |

### Naomi owns

| Endpoint | Reason |
|---|---|
| `GET /audit/export` (CSV streaming) | Streaming response, file format concern — separate from query logic |
| `GET /packages/{id}/pdf` enhancement | Phase C: SHA-256 checksum header, content-range support |
| Seed script updates (`scripts/seed.py`) | Naomi updates seed to include `approver` role user and sample packages in all 6 states |
| Any background worker (if async classification needed in Phase C) | Drummer does not own async infra |

**Do NOT split the state machine itself.** Only Drummer touches `POST /packages/{id}/transition` and `POST /packages/{id}/attest`. Naomi must not write code that directly mutates `package.state` — route through the transition validator or raise a question (see §5).

---

## 4. Cross-cutting concerns

### 4.1 Auth / role enforcement

**Current state:** Only two roles: `admin` (approver equivalent) and `reviewer`. `require_role("admin")` gates approval. No `approver` role exists.

**v0.2 changes required:**

```python
# Role → allowed transitions
ROLE_TRANSITION_PERMISSIONS = {
    "reviewer": {
        "intake_complete → under_review",
        "intake_complete → exception_surfaced",
        "under_review → routed_for_approval",
        "under_review → intake_complete",
        "under_review → exception_surfaced",
    },
    "approver": {
        "routed_for_approval → decision_recorded",   # via /attest
        "routed_for_approval → under_review",
        "exception_surfaced → decision_recorded",     # via /attest
    },
    "admin": {  # operator
        "exception_surfaced → intake_complete",
    },
    "system": {  # internal only, not user-callable
        "submitted → intake_complete",
        "submitted → exception_surfaced",
    }
}
```

**Implement as `app/state_machine.py`** — pure module, no DB imports, fully unit-testable by Miller without async setup:

```python
def validate_transition(from_state: str, to_state: str, actor_role: str) -> None:
    """Raise TransitionError or PermissionError. Otherwise returns None."""
```

**`require_role` on existing endpoints:**
- `POST /approvals/{pkg_id}` — currently `require_role("admin")`. In v0.2 this must also accept `approver`. Update to `require_role("admin", "approver")` as a bridge.
- `GET /packages` — currently `get_current_user` (any role). Keep, but add role-scoping filter logic.

### 4.2 Polling / SSE concern

**Is SSE needed?** The console lists packages by state. When classification completes (synchronous in v0.1), the package moves from `submitted` to `intake_complete` or `exception_surfaced` in the same request. No async background worker exists, so the client gets the final state on upload response.

**Phase B verdict:** No SSE needed. The upload endpoint returns state synchronously. The console polls via standard GET. If Phase C introduces async classification (for large PDFs), SSE or WebSocket would be needed — flag for Phase C, not B.

**The one polling risk:** If intake takes >30s for large PDFs, the frontend shows `submitted` and must poll. Mitigation: ensure `GET /packages/{id}` is cheap (indexed lookup) and document the polling interval (suggest 3s, max 5 attempts, then show StaleBanner).

### 4.3 Per-field confidence and Anthropic token cost

**v0.1 classification prompt:** Classify document type + return a single confidence score. Cost per doc: ~1,000–2,000 input tokens (text extract) + ~200 output tokens.

**v0.2 extracted fields requirement:** 7 fields × (value + confidence) per field requires a structured extraction call. Two options:

| Option | Token cost | Risk |
|---|---|---|
| A. Single prompt: classify + extract all 7 fields with per-field confidence | ~1,000–2,500 input + ~500–800 output | Prompt complexity; harder to tune confidence calibration |
| B. Two prompts: classify first, then extract fields only if type == capital_call_notice | Same input re-sent twice if not cached; ~2,000–4,000 total | More API calls, but cleaner |
| C. Single prompt with structured output (JSON mode / tool_use) | ~1,500–2,500 input + ~600 output | Best option — one call, structured response |

**Recommendation: Option C** — use Claude tool_use / structured JSON output to return classification + all extracted fields + per-field confidence in a single call. No cost increase beyond ~300–400 extra output tokens per document (~$0.002/doc at Sonnet pricing). Naomi does not need to touch the classify module — Drummer updates `app/classify.py` in B1.

**Raise with Holden:** confirm whether extraction runs on ALL document types or only `capital_call_notice`. Running extraction on a K-1 is wasteful. Spec §6.2 implies extraction is for capital call notices only — add a guard in `classify.py`.

### 4.4 `AuditEvent` — `before_state` and `after_state` schema

Currently `before_state` and `after_state` are freeform JSON. In v0.2, standardize the shape for state transitions:

```json
{
  "before_state": {"state": "under_review", "reviewer_id": "abc"},
  "after_state":  {"state": "routed_for_approval", "reviewer_id": "abc"}
}
```

For review note events:
```json
{
  "after_state": {"review_note_id": "...", "linked_field": "call_amount", "body_excerpt": "first 80 chars"}
}
```

For attestation events:
```json
{
  "before_state": {"state": "routed_for_approval"},
  "after_state":  {"state": "decision_recorded", "decision": "approved", "decided_by": "...", "note_present": true}
}
```

Do NOT store full note body in audit event after_state — notes are in `reviewer_notes` and `approvals` tables. Body excerpt (80 chars) is enough for audit display.

---

## 5. Concrete backend questions for the squad

**Q1 — Role naming (for Holden):** The spec says UI displays `Operator`, `Reviewer`, `Approver` but the DB still uses `admin`, `reviewer` (§1.6). Do we rename the DB enum values to `operator`/`reviewer`/`approver` in this migration, or keep `admin` in the DB and map at the display layer forever? A rename is cleaner but requires more migration risk. Request a decision before B1 starts.

**Q2 — `uploaded_by` vs `operator` scope (for Holden / Bobbie):** Spec §5.5 says "Operators: see Exceptions (own), Active (own)". Does "own" mean `uploaded_by == current_user.id`, or does it mean any package the operator has taken an action on? For Phase B, I'm implementing `uploaded_by` ownership — confirm this is correct.

**Q3 — Reviewer claim model (for Holden):** Spec says `under_review` state carries "reviewer identity." Can multiple reviewers claim the same package simultaneously, or is it single-claim? The spec implies single reviewer per package at any time (`With {reviewer}` chip, singular). I'm implementing single reviewer claim (`packages.reviewer_id`). Confirm, because multi-reviewer requires a join table.

**Q4 — Release-claim condition (for Holden):** Spec §2.2 says a reviewer can transition `under_review → intake_complete` "only if no notes recorded." What if the reviewer recorded notes then deleted intent (no delete endpoint exists)? Are notes ever deletable? Confirming: notes are immutable append-only. A reviewer cannot release a claim once a note is written. Flag for Miller's gate test.

**Q5 — Approver return-for-revision note (for Holden):** `routed_for_approval → under_review` ("return to reviewer with note") — where does that note live? Is it a `ReviewNote` written by the approver, or a new `RevisionNote` type? The spec §2.2 mentions it but §6.3 only covers reviewer annotations. Proposing: store as a `ReviewNote` with `author_id = approver_user_id` and `linked_field = null`. Confirm or specify a separate type.

**Q6 — `exception_surfaced → decision_recorded` (direct rejection path, for Holden):** Spec §2.2 allows `exception_surfaced → decision_recorded` via approver. This means an approver can reject a package that was never reviewed. Should the `/attest` endpoint accept `exception_surfaced` as a valid from-state, or is this path only accessible via a separate "reject from exception" action? Needs confirmation to avoid a silent state machine edge case.

**Q7 — Per-field extraction scope (for Holden):** Should the extraction prompt run on ALL document types or only `capital_call_notice`? Running 7-field extraction on a K-1 or subscription agreement wastes tokens and the fields won't populate. My assumption: extraction only runs when `document_type == capital_call_notice`. Other types get `extracted_fields: {}`. Confirm.

**Q8 — CSV export auth (for Naomi):** The `GET /audit/export` endpoint Naomi owns — what role is permitted? Operator, reviewer, approver all? Or approver/admin only? Given this is a governance document, recommend approver + admin only. Naomi should gate it, but needs Holden's sign-off on the role list.

**Q9 — Pagination cursor vs offset (for Bobbie):** The console list and global audit both use offset-based pagination. If packages are being updated while the operator pages through, they can see duplicates or skip rows. Does the UI team need stable cursor-based pagination (keyset by `last_moved_at, id`)? Offset is simpler to build and fine for Phase B volume. Flag for Phase C if needed.

**Q10 — `last_moved_at` backfill (for Drummer self):** The migration adds `last_moved_at` column and backfills from `updated_at`. However `updated_at` in v0.1 is updated by SQLAlchemy on any field change, not just state changes. This means `last_moved_at` for old rows will be slightly off. For v0.1 data this is acceptable — noting it so Miller doesn't write a test asserting exact timestamps for migrated rows.

---

## 6. Migration checklist (B1 scope)

- [ ] Alembic: add `package_state` enum + `state` column
- [ ] Alembic: rename `status` → `legacy_status` (keep one sprint)
- [ ] Alembic: data migration for 5-path mapping (§2.3)
- [ ] Alembic: add `reviewer_id` FK on `packages`
- [ ] Alembic: add `exception_reason` enum column on `packages`
- [ ] Alembic: add `last_moved_at` column + backfill
- [ ] Alembic: add `approver` to `user_role` enum
- [ ] Alembic: add `extracted_fields` JSON column on `classifications`
- [ ] Alembic: create `reviewer_notes` table
- [ ] Alembic: add indexes (state, last_moved_at, reviewer_id, audit actor/created composite)
- [ ] `app/models.py`: add `ReviewNote` model, update `Package`, update `user_role` enum
- [ ] `app/state_machine.py`: new pure module — transition matrix + role permission map
- [ ] `app/classify.py`: structured output call, per-field confidence, guard for non-capital-call types
- [ ] `app/routers/packages.py`: rewrite list + detail endpoints (new schema, role scoping)
- [ ] `app/routers/packages.py`: add `POST /packages/{id}/review-notes`, `GET /packages/{id}/review-notes`
- [ ] `app/routers/packages.py`: add `POST /packages/{id}/transition`
- [ ] `app/routers/approvals.py`: add `POST /packages/{id}/attest` (new canonical endpoint)
- [ ] `app/routers/audit.py`: new file — `GET /audit` global ledger
- [ ] `scripts/seed.py`: add approver seed user, sample packages in all 6 states
- [ ] `main.py`: include new audit router; bump version to 0.2.0
- [ ] Tests (failing first per TDD gate): state transition matrix, reviewer note isolation, per-field confidence round-trip, role enforcement on /attest, global audit filter

---

## 7. What I am NOT picking up (explicit non-goals for B1)

- CSV export streaming (`GET /audit/export`) → Naomi
- SHA-256 checksum on source document → Phase C
- Background / async classification worker → Phase C (if needed)
- Login ceremony animation → Bobbie (frontend only)
- pdf.js viewer → Phase C
- Exception detail view + "Mark exception resolved" UI flow → Phase C (the backend endpoint via `/transition` covers the state change; Phase C wires the UI)
- Any push notification or SSE infrastructure → not in spec for Phase B

---

*Review complete. Awaiting Q1 (role naming), Q3 (reviewer claim model), Q5 (return-for-revision note), and Q6 (exception direct rejection path) before B1 implementation starts. All other open questions are flagged but non-blocking — Drummer will implement the stated assumption and note it in the PR.*
