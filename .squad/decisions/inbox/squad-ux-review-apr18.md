# Squad UX Review — Operations Console Quality Escape

**Date:** 2026-04-18
**Trigger:** Client walkthrough feedback — "the flow makes no sense, all three logins show the same page, active packages shows nothing useful"
**Called by:** Holden
**Severity:** Quality escape — shipped UI that looks correct in screenshots but breaks under real data

---

## Confirmed live state (Playwright + API)

1. Login page: good (obsidian, Arukai language)
2. Post-login: ALL roles (admin, reviewer, approver) land on identical `/documents` console
3. Console sections mostly empty or misleading:
   - Exceptions: 0 (correct — all test packages passed confidence threshold)
   - Pending approval: 0 (correct — none routed yet)
   - Needs review: 2 packages (show "Unclassified" + "awaiting system intake" — wrong labels)
   - Active packages: 4 (show "Unclassified" badges, bare filenames, no classification data)
   - Recent decisions: 0 (WRONG — one package IS approved but the filter misses it)
4. Package rows display: bare "Unclassified" badge, "awaiting system intake" status, filename as title — because the list endpoint returns `PackageOut` with NO document/classification data
5. No role-specific affordances anywhere

---

## Squad Roundtable

### 1. Holden (UX / Information Architecture)

The console is supposed to feel like walking up to a desk where your work is already sorted for you. Right now it feels like looking at a blank filing cabinet with the wrong labels on the drawers. The information architecture is broken at two levels: the sections don't correctly partition the data (Recent decisions misses the approved package entirely), and the rows within sections don't carry enough information to be actionable — you see a filename and "Unclassified" when you should see "Capital Call Notice — 94% confidence — Fund III — awaiting your review." The role differentiation failure is the most damaging part: an approver logging in should immediately see "1 package pending your attestation" as a brass-highlighted call to action, not the same generic console a reviewer sees.

### 2. Drummer (Backend)

The root cause is a schema mismatch between the list and detail endpoints. `GET /packages` returns `PackageOut` which has `title`, `state`, `version` — but zero document-level data. No `doc_type`, no `confidence`, no `filename`. The frontend calls `listDocuments()` which hits the legacy `/documents` endpoint, which returns `DocumentSummary` shape — but the backend's list endpoint returns `PackageOut` shape. The frontend type expects `doc_type`, `confidence`, `filename` on the list response but the API never sends them. I need to either: (a) add a `PackageListOut` schema that includes a summary classification (doc_type + confidence from the first document's current classification), or (b) add an `include=classification_summary` query param. Option (a) is simpler and correct — the list endpoint should eagerly load first-document classification. I also need to surface the approval decision on the list response so Recent Decisions can render properly. The admin role-scoping is also inverted: line 304-306 in `packages.py` restricts admin to `uploaded_by == current_user.id`, which means admin sees FEWER packages than reviewer — that's backwards.

### 3. Bobbie (Frontend — section bucketing)

The bucketing logic in `documents/page.tsx` lines 165-185 has two bugs. First, the `resolvePackageState()` call receives `d.status` and `d.confidence` — but `d.status` is the legacy v0.1 status (e.g., `"pending_review"`) while the backend now sends v0.2 `state` (e.g., `"intake_complete"`). The state facade in `state.ts` only handles v0.1 status strings (`pending_classification`, `pending_review`, `approved`, `rejected`), so v0.2 states like `intake_complete` or `decision_recorded` fall through to the `default` case and resolve as `"submitted"` — which doesn't match ANY section filter except the catch-all `activePackages`. That's why everything piles into Active and nothing appears in Recent Decisions. Second, the `!isDecided` guard on line 170 pushes non-decided packages into `activePackages` unconditionally, AND then the elif chain can also push them into `needsReview` — causing double-counting. The fix is: update `resolvePackageState` to handle v0.2 state strings natively, OR map the API response correctly before bucketing.

### 4. Alex (Frontend — PackageRow data)

`PackageRow` is designed correctly — it accepts `docType`, `confidence`, `title` and renders `ClassificationBadge` and `StatusPill` with real data. The problem is upstream: `toRowPkg()` on line 28-38 maps `doc.doc_type` and `doc.confidence` from the list response, but these fields are always `null` because the list endpoint doesn't return them. So `ClassificationBadge` gets `null` and renders "Unclassified", `StatusPill` gets no confidence and shows the fallback label. The `title` field maps to `doc.filename` which is a bare filename like `test-capital-call.pdf` — not useful when 3 packages have similar names. I need to: (a) use `pkg.title` from the API response instead of filename, and (b) once Drummer adds classification summary to the list response, wire `doc_type` and `confidence` through.

### 5. Naomi (Backend — data integrity)

The approved package not appearing in Recent Decisions is partly a frontend state-mapping bug (Bobbie's finding), but there's also a data issue. The package state is `decision_recorded` (v0.2 state machine value), but the frontend's `DocumentStatus` type only knows `approved` | `rejected` (v0.1 values). The `legacy_status` field on `PackageOut` does map back to `"approved"` — but the frontend reads `state`, not `legacy_status`. The `listDocuments()` call in `api.ts` hits `/documents` (legacy endpoint) which returns `PackageOut` shape, but the frontend type `DocumentSummary` expects `{ id, filename, doc_type, uploaded_at, status, confidence }` — a completely different shape. The response is being silently coerced: fields that don't exist in the API response become `undefined`/`null` in JS. There's no runtime validation catching this type mismatch. The admin role filter (line 304: `uploaded_by == current_user.id`) also means the admin user only sees packages they personally uploaded, which is correct for "operator" role but wrong for "admin" — this needs the role check fixed.

### 6. Miller (Test — why didn't E2E catch this?)

The E2E tests check that sections render and that the page loads without errors — but they don't assert on actual data content. The tests mock the API responses with well-formed `DocumentSummary` objects that include `doc_type` and `confidence`, so the components render perfectly in test. The real API returns a different shape entirely. The fundamental gap: no contract test validates that the actual API response matches the `DocumentSummary` TypeScript type. The E2E tests also don't test role-differentiated views — they log in as one user and verify structure, not behavior. I need to add: (a) a contract/schema test that fetches from the real API and validates against the TS type, (b) role-matrix E2E tests (login as reviewer, verify "Claim to review" appears; login as approver, verify "Pending your attestation" section is highlighted), (c) a "real data" E2E that uploads a package, waits for classification, then verifies the console shows actual classification data.

---

## Concrete Fix Plan — 5 Tickets

### Ticket 1: Backend — Add `PackageListOut` with classification summary
**Owner:** Drummer
**Scope:** Create `PackageListOut` schema that extends `PackageOut` with `doc_type: str | None`, `confidence: float | None`, `lead_filename: str | None`, `decision: str | None` (from first document's current classification + final approval). Update `list_packages()` to eagerly load first document + classification via `selectinload`. Fix admin role filter (line 304-306: admin should see ALL packages, not just own uploads — operator sees own uploads).
**Estimated hours:** 3h
**Files:** `backend/app/routers/packages.py`, `backend/app/schemas.py`

### Ticket 2: Frontend — Fix state facade for v0.2 states
**Owner:** Bobbie
**Scope:** Update `resolvePackageState()` in `state.ts` to handle v0.2 state strings (`intake_complete`, `under_review`, `routed_for_approval`, `decision_recorded`, `exception_surfaced`, `submitted`) as first-class cases instead of relying on v0.1 legacy status mapping. Update `DocumentSummary` type in `api.ts` to match actual `PackageListOut` response shape. Fix `listDocuments()` to call `/packages` endpoint (not legacy `/documents`). Fix section bucketing in `documents/page.tsx`: remove double-counting (the `!isDecided` catch-all into activePackages should be an explicit else, not a pre-filter).
**Estimated hours:** 4h
**Files:** `frontend/src/lib/state.ts`, `frontend/src/lib/api.ts`, `frontend/src/app/documents/page.tsx`

### Ticket 3: Frontend — Role-differentiated console views
**Owner:** Bobbie + Alex
**Scope:** Pass `user.role` into section rendering. Reviewer view: "Needs review" section shows "Claim to review" CTAs, other sections are read-only. Approver view: "Pending approval" section header uses brass highlight and shows "N awaiting your attestation" callout. Admin view: shows all sections + "Audit ledger" link in TopNav (already gated by `canViewAuditLedger()`). Hide "Begin intake" CTA for approver role (approvers don't upload).
**Estimated hours:** 3h
**Files:** `frontend/src/app/documents/page.tsx`, `frontend/src/components/PackageRow.tsx`, `frontend/src/components/TopNav.tsx`

### Ticket 4: Frontend — PackageRow data wiring
**Owner:** Alex
**Scope:** Update `toRowPkg()` to use `pkg.title` (not filename) as display title. Once Ticket 1 lands, wire `doc_type` and `confidence` from `PackageListOut` into `PackageRow`. Add fund name or submission date as subtitle. Show actual classification badge (not "Unclassified") when data is present.
**Estimated hours:** 2h
**Files:** `frontend/src/app/documents/page.tsx`, `frontend/src/components/PackageRow.tsx`

### Ticket 5: Test — Contract tests + role-matrix E2E
**Owner:** Miller
**Scope:** (a) Add API contract test: fetch from `/packages` and validate response matches `PackageListOut` schema — catches shape mismatches between backend and frontend types. (b) Add role-matrix E2E: login as each of admin/reviewer/approver, verify role-specific affordances appear (claim CTAs for reviewer, attestation callout for approver, audit link for admin). (c) Add "real data" E2E: upload PDF, verify console shows classification data (not "Unclassified"). (d) Add empty-state vs populated-state combinatoric tests per Copilot rule 14.
**Estimated hours:** 4h
**Files:** `frontend/src/lib/__tests__/api-contract.test.ts` (new), `e2e/role-matrix.spec.ts` (new), `e2e/real-data-console.spec.ts` (new)

---

## Total estimate: 16h across 4 squad members

## Root cause of the quality escape

The squad built and tested against mock data that matched the frontend types, but the real API returns a different shape. The state facade was written for v0.1 backend states but the backend shipped v0.2 states. No contract test caught the mismatch. No E2E test used real API responses. The result: a console that renders perfectly in Jest but shows garbage with real data.

This is the second time we've shipped a UI that works in tests but fails under real conditions. The fix for next time: Miller adds a "smoke with real API" gate before any UI ticket is marked Done.
