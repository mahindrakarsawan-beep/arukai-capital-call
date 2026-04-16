# Miller — Figma Pre-Build Review (ARU-17 / POR-147)

**Reviewer:** Miller — Test & Reliability Engineer
**Date:** 2026-04-15
**Figma:** `a6mMsiXmnSdQTQ4qQYS6X2`, Page 3 `9:3` ("Screens @ 1440px")
**Spec audited against:** `.squad/v02-atelier-spec.md`
**Screens walked:** 01 Login (15:2), 02 Operations console (15:21), 03 Package detail · awaiting reviewer (16:2), 04 Package detail · routed for approval (16:139), 05 Package detail · decision recorded (16:292), 06 Attestation modal (17:2), 07 Global audit ledger (17:34)
**Anchor:** POR-146 shipped 5 integration bugs past a curl-only smoke. ARU-02-P20 (browser E2E) is now mandatory. This review exists so the same class of escape cannot happen on v0.2.

---

## 0. Verdict (before detail)

Design is testable but the bill is non-trivial. **I count 11 net-new Playwright-visible features, at least 7 new backend endpoints, a new enum with a non-trivial transition matrix, and a modal with focus-trap semantics that Phase A’s Playwright suite currently does not exercise at all.** If we build Phase A, B, C with the current test baseline (one `smoke.spec.ts` that logs in and uploads), the quality escape probability is functionally identical to POR-146. I am therefore attaching **hard test gates per phase** below.

Two structural risks I want on the record up front:

1. **Contract drift risk (Rule 15).** B1 introduces `POST /packages/{id}/transition`, `POST/GET /packages/{id}/review-notes`, `GET /audit`, and extends the package detail payload with `extracted_fields` and `state`. The frontend in B2 will call each of these. Unless we run a *generated* contract test (schema-derived, not hand-written), we will repeat Bugs 2 and 5 from POR-146 exactly — route string drift is the single highest-frequency bug class in this codebase’s history.
2. **State-machine regression risk.** The 6-state × 9-transition matrix in §2.2 is easy to write and easy to regress. Every future "add a state" or "allow a skip" PR will be a candidate to silently relax the invariant. **Backend invariants must be expressed as pytest parametrizations over the transition matrix, not as happy-path assertions.**

---

## 1. Screen-by-screen review

### Screen 01 — Login (node `15:2`)

**Happy path E2E.**
```
goto /
getByRole heading "Authorized access" visible
getByLabel "Credentialed email" fill(admin@arukai.example)
getByLabel "Passphrase" fill(admin123)
getByRole button "Enter workflow" click
expect url /\/console/
getByRole heading "Operations console" visible
```

**Edge cases that MUST be tested.**
1. Wrong password — alert `Credentials not recognized. Access not granted.` visible (not "Invalid credentials" which is the old copy).
2. Session expired — navigate to `/console` without cookie → re-auth banner `Your workflow session has ended. Re-authenticate to continue.` must render above card (separate Playwright spec, inject expired JWT).
3. Backend unreachable — with `NEXT_PUBLIC_API_URL` pointed at a dead host, submit → user-visible error string. **This is POR-146 Bug 1. Must be a named spec.**
4. Double-click submit — no duplicate `POST /auth/login`. Spy on network: exactly 1 request.
5. Focus-steal / aggressive refocus — with CapsLock banner or browser autofill popup, password field must not lose focus mid-typing (document-scoped `focus()` must not run during user typing).
6. Keyboard nav — Tab order: email → password → submit. Enter on password submits the form (no extra click needed).
7. Reduced-motion — card/tagline must not animate. Ceremony is Phase C only, but A1 must not introduce transitions that break `prefers-reduced-motion`.

**Accessibility.**
- Labels must be `<label for>` bound, not placeholder-only. Placeholders are hints per spec (`name@firm.example`), not labels.
- Card heading `Authorized access` is `<h2>`; page wordmark `Arukai` is `<h1>` — verify semantic hierarchy.
- Contrast: bone card on obsidian is 21:1 (fine); placeholder text `text-fg-muted` on bone must clear 4.5:1. **Action:** automated axe-core scan in CI.
- Button `bg-fgObsidian text-bgBone` — verify focus ring is visible on obsidian surround.

**Phase A regression risk.** Existing `smoke.spec.ts` uses `getByRole('heading', { name: 'Sign in' })` and `getByRole('button', { name: 'Sign in' })`. Those strings are gone. **The existing smoke will break the moment A1 merges.** Bobbie must update the spec in the same commit as the copy change or CI turns red for reasons unrelated to the feature.

**Hard-to-test item.** The Phase C ceremony (hairline draw 360ms, card fade 240ms) needs a Playwright toHaveScreenshot or an explicit `data-ceremony-phase="drawing"` hook. **Ask:** Bobbie to emit a `data-ceremony-step` attribute at each phase so we can assert without relying on timing.

---

### Screen 02 — Operations console (node `15:21`)

**Happy path E2E.**
```
login as approver
expect heading "Operations console"
expect subtext matches /\d+ active packages across your desk/
expect section order: Exceptions, Pending approval, Needs review, Active packages, Recent decisions
each section has header (title · count), rows OR empty state copy
click first row in "Pending approval"
expect url /\/packages\/[a-f0-9-]+/
```

**Edge cases that MUST be tested.**
1. **Empty every section simultaneously** (fresh tenant) — all 5 empty-state strings render exactly (§1.3). Spec Rule 14 combinatorics: filter × empty state. Here we have no filter but we *do* have 5 sections × 2 states (empty, populated) = 10 combinations. Minimum: each section with zero items and with ≥1 item.
2. **Role visibility.** §5.5: Operators see Exceptions/Active/Recent *own*, NOT Needs review or Pending approval. Reviewers see all but Pending approval is read-only. Approvers see all actionable. **Three separate Playwright specs** — one per role. Failure mode: reviewer sees brass count → security escape.
3. **Brass discipline.** Pending approval count badge is brass ONLY when count > 0. When count = 0: neutral, not brass. Screenshot diff or CSS class assertion.
4. **`routed_for_approval` pill** — only pill in the app rendering brass. Scan DOM: `[data-state="routed_for_approval"]` has brass class; no other element does.
5. **Clicking any row anywhere in the row opens detail.** Keyboard: Tab to row, Enter opens. Focus-visible ring on row.
6. **Stale banner** — if `/packages` list fetch fails, `Workflow state could not be refreshed. The information shown may be stale.` must render. Simulate via 500 on backend.
7. **Slow network** — with 3s throttling, skeletons must render per section, not a single global spinner.
8. **Relative timestamp rounding** — "3h ago" vs "4h ago" at the minute boundary. Use Playwright clock-freeze.

**Accessibility.**
- Section headers as `<h2>`; rows as focusable elements with accessible names built from `title · state · next owner · timestamp`.
- Count badges must have `aria-label="2 exceptions"` not just "2".
- Brass is a hue close to warning amber — **contrast test on brass text vs bone surface is required; brass at small sizes is the riskiest color on the palette.**

**Phase A regression risk.** v0.1 dashboard was a flat table at `/documents`. v0.2 route is `/console`. Existing test asserts `/\/documents/`. **Action:** redirect `/documents` → `/console` during Phase A to avoid breaking bookmarks AND keep existing auth test URL-assertion green via a redirect match.

**Hard-to-test items.**
- Section order is visually stacked but DOM order must match. Assert with `page.locator('[data-section]').all()` returning exactly the five keys in order.
- Row-click target is the whole row. Easy to regress to an anchor-on-title-only. **E2E:** click a known-empty area of the row (e.g. the state pill column), not just the title.

---

### Screen 03 — Package detail · awaiting reviewer (node `16:2`)

**Happy path E2E.**
```
navigate to /packages/{id} where state=intake_complete
expect header: title, "Package submitted {date} by {actor}", state pill "INTAKE COMPLETE · AWAITING REVIEWER", next-owner chip "Awaiting reviewer"
expect four blocks: Source document, Extracted facts, Review notes, Audit trail
expect bottom action bar: "Release claim" (ghost), "Route for approval" (primary — secondary-strong)
```

**Edge cases.**
1. PDF iframe auth — **POR-146 Bug category.** If the frontend `<iframe src="/packages/{id}/pdf">` doesn't forward the JWT, the iframe will render backend's 401 HTML. Phase A spec 6.1 says "acceptable fallback: `<iframe src={pdfUrl}>` at 600px". **This will break in the browser if auth is cookie-based and backend is on a different origin.** Must be tested with a Playwright spec that asserts the iframe body is a PDF (or that the Source panel falls back to "View source document" link without a visible 401 strip).
2. **All 4 confidence bands render** — high, confident, needs-review, low-confidence. Seed backend with a package that has exactly one field in each band, assert each visual treatment (hairline, needs-review pill, dashed box + flag pill, missing "—" + pill).
3. **Empty review notes** — italic empty state `No review notes recorded. Reviewers will annotate here before routing for approval.` visible when zero notes.
4. **Audit trail with single submission event** — never rendered empty (spec guarantees). If backend returns empty array, that is a backend bug and the UI must show the placeholder copy.
5. **Reviewer role routing** — "Record review note" button is present only for reviewer. Operator viewing the same page does NOT see the input.
6. **Release claim guarded** — spec §2.2 says `under_review → intake_complete` is allowed only if no notes recorded. Test: after first note, "Release claim" button must be disabled or absent.
7. **Route for approval requires ≥1 note** — secondary at zero notes, secondary-strong after first note. Assert both states.
8. **Slow network on the four-block grid** — four skeletons, not one. Each block loads independently.
9. **Focus order** — tabbing should be: nav → header actions → each block in reading order → bottom action bar.
10. **Long field values** — truncation or wrap? Design currently shows compact values. Test with a 200-char fund name; it must wrap, not push the confidence marker off-screen.

**Accessibility.**
- PDF iframe needs `title` attribute per WCAG — e.g. `title="Source PDF preview for {package title}"`.
- Confidence pills must have screen-reader text per §4.1 ("extracted with high confidence", "needs reviewer attention", "low confidence, flagged for manual verification"). These are in the spec — **audit that they render in DOM, not just visually.**
- "View source document" link opens in new tab — `rel="noopener"` required.

**Phase A regression risk.** v0.1 detail page URL is `/documents/{id}`. v0.2 is `/packages/{id}`. Redirect required. Existing `approve` button flow — spec A2 renames to `Attest approval`. All existing tests that target `getByRole('button', { name: 'Approve' })` will break.

**Hard-to-test items.**
- **PDF iframe is the single biggest testability risk on this page.** In a Cloud Run / cross-origin world, `<iframe src>` with JWT auth requires either a server-proxy route `/pdf-proxy/{id}` or a short-lived signed URL. Phase A spec says iframe, Phase C says pdf.js. **The auth question is not answered in the spec.** Raised as Quality Question Q1.
- 2×2 grid at ≥lg viewport vs stacked on narrow — responsive test in two viewport sizes.

---

### Screen 04 — Package detail · routed for approval (node `16:139`)

**Happy path E2E.**
```
same as Screen 03 but state=routed_for_approval
expect state pill BRASS "ROUTED FOR APPROVAL · AWAITING APPROVER"
expect next-owner "Awaiting approver attestation"
expect bottom action bar: "Return to reviewer" (ghost), "Record rejection" (neutral dark), "Attest approval" (brass primary)
expect multiple review notes rendered
```

**Edge cases.**
1. **Double-click Attest approval** — modal must open exactly once. After the first open, the second click is absorbed by the modal scrim or the button is debounced. Spy on calls to the modal-open reducer: exactly 1.
2. **Focus-steal during typing in attestation note** — once modal is open, tabbing must stay trapped; no background element can steal focus if backend issues a state refetch.
3. **Return to reviewer** — transitions `routed_for_approval → under_review`. Backend spec §2.2 allows. Test: after this click, pill flips from brass to neutral; action bar re-routes to reviewer controls.
4. **Record rejection** — opens modal in reject variant (see Screen 06).
5. **Approver role guard** — Reviewer viewing this page sees the bar but actions are disabled or hidden. Reviewer double-clicking "Attest approval" via direct DOM manipulation must 403 from backend. **Backend authorization test, not just UI.**
6. **Brass appears only here and on the modal confirm** — scan DOM: one brass pill + one brass button = two brass elements total. Any third is a §9.3 violation.
7. **Stale state** — if the package was already decided in another tab, clicking Attest must surface the 409 gracefully ("This package has already been decided") without a raw JSON dump.

**Accessibility.**
- Three-button action bar needs correct focus order; destructive/binding actions should not be default-focused.
- Brass primary button contrast on bone surface — verified against WCAG AA at 4.5:1.

**Phase A regression risk.** A2 ships the attestation modal. Existing E2E does not cover approval at all today, so new. But A2 also renames the API client functions — any component still importing `approveDocument` from `lib/api.ts` must be updated.

---

### Screen 05 — Package detail · decision recorded (node `16:292`)

**Happy path E2E.**
```
navigate to a closed package
expect state pill POSITIVE "APPROVED · MARCUS PELL · 2026-04-17" (or NEGATIVE for rejected)
expect next-owner "Decision recorded — Marcus Pell attested on 2026-04-17"
expect bottom banner italic "Package closed. Decision recorded by Marcus Pell on 2026-04-17."
expect NO action buttons
expect review notes input is absent or disabled
expect audit trail includes final row "under_review → decision_recorded" (or equivalent)
```

**Edge cases.**
1. **No actions period.** Any action button present is a bug. DOM assert: `getByRole('button', { name: /Attest|Route|Record|Release/ })` must return zero.
2. **Rejected variant** — negative pill tone (not brass, not amber). Verify color role.
3. **Attempt to POST a transition from a terminal state** — backend must 409. Frontend must not even offer the button, but if someone hand-crafts a request, 409 with `{"detail":"Transition decision_recorded→... not permitted"}`.
4. **Review note input** — spec §6.3 says reviewer sees input on under_review / intake_complete. On decision_recorded: absent.

**Accessibility.**
- Positive pill color + icon (dot leading) — color alone is not enough. Screen-reader reads "Approved by Marcus Pell on 2026-04-17".

**Phase A regression risk.** Today's `approved` / `rejected` state maps here. §2.3 migration mapping must be verified with a pytest fixture.

---

### Screen 06 — Attestation modal (node `17:2`)

**Happy path E2E.**
```
from Screen 04, click "Attest approval"
expect modal heading "Attestation"
expect subheading "You are about to record a binding decision on this package."
expect warning strip if any needs-review fields ("1 field was flagged during review. Proceed only if resolved.")
expect package summary panel with title, classification, amount, due date, fund
expect "Reviewer notes on record" panel with N notes
expect attestation language italic block
expect optional textarea "Attestation note (optional)"
expect buttons "Return to package" (ghost) + "Attest and record decision" (brass primary)
initial focus on "Return to package"
focus trap: Tab from last element cycles back to "Return to package"
Escape key closes modal, no mutation
Backdrop click closes modal, no mutation
click "Attest and record decision"
expect POST to /packages/{id}/transition with {to: "decision_recorded", decision: "approved", note: ""}
expect modal fades over 240ms (data-animation-state changes)
expect toast "Decision recorded. Package closed."
expect package detail re-renders in closed state
```

**Edge cases.**
1. **Initial focus NOT on destructive button.** Spec §7.3: focus on "Return to package". Assert via `page.evaluate(() => document.activeElement.textContent)`.
2. **Focus trap.** Tab through all focusable, last Tab cycles to first; Shift+Tab on first goes to last. Focus never escapes to background.
3. **Escape key** — closes modal without mutation. Assert no network POST fired.
4. **Backdrop click** — same.
5. **Double-click confirm** — single POST. Button must disable during request.
6. **Network failure on confirm** — modal stays open, error strip at top, button re-enabled. Must NOT close optimistically.
7. **Rejection variant** — attestation note is REQUIRED. Confirm button disabled until note has content. Brass is NOT used; button is neutral dark.
8. **"N fields flagged" warning strip** — exact count pluralization ("1 field was flagged" vs "2 fields were flagged"). Zero fields: strip not rendered.
9. **Empty reviewer notes** — italic warning `No review notes were recorded before this attestation.` Attestation still allowed (spec §7.1.4). Regression test: does *not* block submit.
10. **Reduced motion** — 240ms fade becomes instant. `prefers-reduced-motion: reduce` path.
11. **Modal opens on slow backend** — if the "fetch package fresh" happens on modal open, handle the spinner state; if data is already in memory, open instantly.
12. **Keyboard-only submission** — user can Tab to confirm and Enter to submit. No mouse required.

**Accessibility.**
- `role="dialog"`, `aria-modal="true"`, `aria-labelledby` pointing at heading, `aria-describedby` at subheading.
- Body scroll locked while modal open. Test: scroll attempt does not move background.

**Phase A regression risk.** A2 introduces this modal. No prior modal component in the codebase (verified via `ls frontend/src/components/`). The modal primitive itself is new infra — unit tests required for open/close/trap/escape BEFORE it lands in a screen.

**Hard-to-test item.** **Modal focus trap** is notoriously flaky. Options: (a) Radix UI `Dialog`, which we should adopt; (b) hand-rolled with manual `focus()` management, which will have edge cases. **Recommendation:** Radix. Easier to unit-test because focus trap is a library-verified invariant.

---

### Screen 07 — Global audit ledger (node `17:34`)

**Happy path E2E.**
```
click "Audit ledger" in nav
expect heading "Audit ledger"
expect subtext "A first-class record of every package event across the workflow..."
expect filter bar: Actor, Action, Between (date range), Export CSV
expect table with columns: TIMESTAMP, ACTOR, PACKAGE, ACTION, BEFORE → AFTER
fill Actor=Lena Voss
expect table filters client-side OR re-fetches with query params
click Export CSV
expect download triggers
```

**Edge cases.**
1. **Combinatorics — the Rule 14 hotspot.** Filter × empty state. Three filters, each independently settable.
   - No filter, has events → render table.
   - No filter, zero events → empty state `No events match the current filter.` ← even though "no filter" ≠ "filter"; spec uses this copy generically.
   - Actor filter with match → filtered table.
   - Actor filter with zero matches → same empty state.
   - Action filter, date filter, all three combined → 8 combinations minimum. **Parametrize in Playwright.**
2. **Date range bounds** — inclusive or exclusive? Spec does not say. Raised as Quality Question Q4.
3. **Before → After truncation** — if transition string is long (e.g. `routed_for_approval → decision_recorded`), does the column overflow? Test with the longest possible pair.
4. **Export CSV** — does the server-side export respect the filter? Playwright: set filter, click Export, read the downloaded file, assert row count matches table.
5. **Sort order** — newest first by default. Assert.
6. **Pagination or infinite scroll** — spec does not mention. Audit ledger grows unboundedly. **Raised as Quality Question Q5.**
7. **Permission gate** — every role sees the audit ledger? Or only approvers? Spec does not say. **Raised as Q6.**
8. **Click an event** — does it navigate to the package detail? Spec §6.4 says audit trail has "Open in audit ledger →" but not the reverse. Raised as Q7.

**Accessibility.**
- Table needs `<caption>` or `aria-label="Audit ledger events"`.
- Filter inputs have labels (visible in screenshot: FILTER BY ACTOR, FILTER BY ACTION, BETWEEN).
- Date range picker must be keyboard-accessible.

**Hard-to-test item.** Date range picker — if Bobbie rolls their own, every edge case is ours. **Recommend:** use a vetted component (react-day-picker, Radix).

---

## 2. New components — unit + E2E test plan

### 2.1 `SourceViewer` (PDF preview, §6.1)

**Unit tests.**
- Renders `<iframe>` fallback with correct `src` and `title`.
- Handles 401/403 — shows "Source document unavailable. Re-authenticate." strip.
- Handles missing `pdfUrl` — shows "No source document attached." placeholder.
- `View source document` link has `target="_blank" rel="noopener"`.

**E2E.**
- Iframe body is `application/pdf` (Playwright: `page.frameLocator('iframe').locator('body')` + content-type check via response listener).
- Clicking "View source document" opens new tab with the PDF URL.
- PDF proxy (if we add one — see Q1) forwards auth.

**Hard-to-test risks:** cross-origin iframe auth (see POR-146 Bug 3 pattern). **Gate:** must have a Playwright spec `source-viewer-auth.spec.ts` before B2 merges.

### 2.2 Filter bar (audit ledger, §7 of this review)

**Unit tests.**
- Each filter change fires an `onFilterChange` with the canonical shape `{actor, action, dateStart, dateEnd}`.
- Clear-filter returns to identity state.
- Date range validation: end ≥ start; bad input → inline error.

**E2E.**
- 8-combination matrix (see Screen 07 edge 1).
- Debounce: rapid typing does not hammer backend. Spy network: max 1 request per 300ms.

### 2.3 Kebab menu (not explicitly in spec, but likely on rows)

**Not visible in the 7 screens I walked.** Spec does not reference a kebab. **Raised as Q8** — do rows have overflow menus (copy link, mark reviewed, etc.)? If no, delete this section. If yes, it needs its own test plan (keyboard open, escape close, outside-click close, focus-restore-on-close).

### 2.4 Audit entry expand (per §6.4 — "expandable before/after JSON diff")

**Unit tests.**
- Collapsed by default.
- Click expands; click again collapses.
- Keyboard: Enter/Space toggles.
- `aria-expanded` flips.
- JSON diff renders with before/after columns.

**E2E.**
- Expand first entry, assert diff visible.
- Collapse, assert diff hidden.
- Tab into entry, Enter expands, Tab into diff content, Shift-Tab returns to entry.

### 2.5 `StatePill` + `NextOwnerChip` (pair, §1.4 + §3)

**Unit tests.**
- Renders correct copy for each of the 6 states + 2 decision variants.
- Applies correct color class per state.
- `routed_for_approval` → `bg-brandBrass`; no other state uses brass.
- Next-owner chip matches state via a pure function (reducer). **Snapshot test the whole table.**

**E2E.**
- Every state rendered on the console once — visual regression screenshot.

### 2.6 `ConfidenceField` (§4)

**Unit tests.**
- Numeric 0.0–1.0 input → correct band classification.
- Each band's visual treatment (high: bare, confident: hairline, needs_review: amber pill, low: dashed box + flag pill).
- Missing (null) value → "—" + Missing pill.
- Screen-reader text per band is present in DOM.
- Tooltip shows exact percentage on hover (RTL with userEvent.hover).

**E2E.**
- Seed a package with one field per band, screenshot the whole extracted-facts block.
- Click low-confidence field → exception panel opens.

### 2.7 `AttestationModal` (§7)

**Unit tests.**
- Opens with focus on "Return to package".
- Escape closes, backdrop click closes, no mutation.
- Confirm button disabled when `variant="reject"` AND note empty.
- Pluralization of flagged-fields warning strip.
- Fade animation duration 240ms (`withTiming` only, no spring — memory note).

**E2E.** See Screen 06 above.

### 2.8 State machine invariants — **backend tests (Drummer owns, Miller audits)**

Invariants to enforce with pytest parametrization in `tests/test_state_machine.py`:

1. **Allowed transitions only.** For each `(from, to)` pair in §2.2's matrix, assert 200. For each `(from, to)` NOT in the matrix (there are 36 − 9 = 27 negative cases), assert 409 with body `Transition {from}→{to} not permitted`.
2. **Terminal is terminal.** `decision_recorded → *` for any `*` returns 409.
3. **Every successful transition writes exactly one AuditEvent row.** Assert row count delta = 1.
4. **AuditEvent has `before_state`, `after_state`, `actor_user_id`.** No nullable fields on these three.
5. **`under_review → intake_complete` allowed only if zero review notes.** Parametrize: with notes → 409 `cannot release claim after annotation`.
6. **Role-scoped transitions.** Approver role cannot drive `intake_complete → under_review` (reviewer-only). Reviewer role cannot drive `routed_for_approval → decision_recorded` (approver-only). Matrix with role × transition.
7. **Concurrency — optimistic lock.** Two approvers click Attest simultaneously on the same package → one succeeds, one gets 409. (Requires DB-level version or `WHERE state = expected_state`.)
8. **Migration round-trip.** v0.1 `pending_review` + confidence 0.8 → `intake_complete`. v0.1 `pending_review` + confidence 0.4 → `exception_surfaced`. `approved` → `decision_recorded` with Approval.decision = approved. Fixtures per §2.3 table.

---

## 3. Contract risks (POR-146 replay check)

**This is Rule 15. I am doing it mentally right now.**

Frontend `fetch()` calls that will exist after B2 ships:

| Method | Path | Source (frontend fn) | Backend responsible | Risk |
|---|---|---|---|---|
| POST | `/auth/login` | `lib/api.login` | existing | low (works today) |
| GET | `/auth/me` | `lib/api.getMe` | existing | low |
| GET | `/packages` | **renamed from /documents** | B1 | **HIGH** — Bug 2 replay if Drummer doesn't rename the router prefix. Write a contract test NOW. |
| GET | `/packages/{id}` | `getPackage` | B1 | HIGH — same reason |
| POST | `/packages/upload` or `/packages` (intake) | `submitIntake` | B1 | **HIGH** — Bug 5 replay. Exact path must be agreed in the ticket, not inferred. |
| GET | `/packages/{id}/pdf` | `getSourcePdfUrl` | existing or B1 | medium — iframe auth |
| POST | `/packages/{id}/transition` | `transitionPackage({to, decision?, note?})` | B1 — **NEW** | **HIGH** |
| GET | `/packages/{id}/review-notes` | `listReviewNotes` | B1 — **NEW** | HIGH |
| POST | `/packages/{id}/review-notes` | `recordReviewNote({body, linked_field?})` | B1 — **NEW** | HIGH |
| GET | `/audit?actor=&action=&start=&end=` | `listAuditEvents` | B1 — **NEW** | HIGH — query param names must match exactly |
| GET | `/audit.csv?...` (or `/audit/export`) | `exportAuditCsv` | B1 — **NEW** | **Unspecified in the spec. Q3.** |

**Contract test gate (non-negotiable).** Before B2 ships, there must be a `tests/test_api_contract.py::test_frontend_contract` (already exists per ls) that is **updated to cover every new endpoint above**. The test should:
- import the OpenAPI schema from FastAPI at runtime;
- for every `fetch(...)` call in `frontend/src/lib/api.ts`, assert the path + method exists in the schema;
- fail CI if the frontend references a path not in the backend's OpenAPI.

**I will own writing this test.** It's a generic mechanism, not B1-specific. Proposing we add it in B1's TDD phase so it fails-red until B1 lands.

**Also:** response shape contract. Backend returns `extracted_fields: {name: {value, confidence}}`. Frontend `DocumentDetail` type needs a `PackageDetail` replacement. If the types diverge by one character (`extracted_fields` vs `extractedFields`, `due_date` vs `dueDate`), the UI will render "undefined" or crash. **Mitigation:** generate TypeScript types from the FastAPI OpenAPI schema (e.g. `openapi-typescript`). **This is a tooling ask, raised as Q9.**

---

## 4. Ownership split

| Layer | Owner | What |
|---|---|---|
| Unit tests (React components) | Bobbie | Every new component has Jest/RTL tests committed red before impl |
| Unit tests (Python services) | Drummer | Every new service function, every state transition |
| Contract test (OpenAPI vs api.ts) | **Miller** | `tests/contract/test_frontend_contract.py` — generic, lives in backend repo |
| Playwright E2E — happy paths | **Miller** | 7 specs, one per screen, plus the full flow in Appendix A.8 |
| Playwright E2E — edge cases | **Miller** | Empty states, role gates, double-click, focus, network failures |
| State machine invariants | Drummer writes, **Miller audits** | Parametrized transition matrix, role × transition matrix |
| Accessibility (axe-core CI job) | **Miller** sets up, Bobbie maintains | Runs on every PR, fails on violations |
| Visual regression (Playwright toHaveScreenshot) | **Miller** | Brass discipline, section order, confidence bands |
| Reduced-motion path | Bobbie | `prefers-reduced-motion: reduce` coverage, smoke asserts no animation |
| CORS + env baking (POR-146 regression suite) | **Miller** | Keep the ARU-02-P20 browser-E2E smoke green against staging |
| Copy audit (grep for banned strings) | **Miller** | Per Appendix A.1 — zero matches of `Upload`, `Sign in` button, etc. |

**Miller's deliverables for ARU-17:**

1. `frontend/e2e/login.spec.ts` — Screen 01 full coverage
2. `frontend/e2e/console.spec.ts` — Screen 02, three role specs
3. `frontend/e2e/package-detail.spec.ts` — Screens 03/04/05
4. `frontend/e2e/attestation-modal.spec.ts` — Screen 06
5. `frontend/e2e/audit-ledger.spec.ts` — Screen 07, 8-combo filter matrix
6. `frontend/e2e/full-flow.spec.ts` — login → intake → review → attest → audit (Appendix A.8)
7. `frontend/e2e/regression/por-146.spec.ts` — 5 specs, one per Bug 1–5, anti-regression suite
8. `backend/tests/test_state_machine.py` — transition matrix parametrized
9. `backend/tests/test_api_contract.py` — extended for all new endpoints
10. `backend/tests/test_migration.py` — v0.1 → v0.2 per §2.3
11. CI job: axe-core accessibility on every PR
12. CI job: visual regression snapshots for brass discipline + confidence bands
13. Copy audit script: `scripts/audit-copy.sh` — grep banned strings

---

## 5. Quality questions for Holden (raise before build)

**Q1. PDF iframe auth — how does the browser authenticate the iframe src request?**
Cookie-based with same-origin? Server-side proxy route? Short-lived signed URL? This is the single highest-risk testability gap. POR-146 Bug 3 family. **I need a decision before A1 writes the Source document block.**

**Q2. Global audit ledger — is the export CSV endpoint server-side streamed or client-side blob?**
If client-side, pagination is mandatory (can't export 100k rows through the browser). If server-side, needs a `Content-Disposition` and a streaming response. Spec §7 of this review, not in Atelier spec.

**Q3. Audit filter query param shape.**
Spec says filters by actor, action, date range. Backend endpoint? `/audit?actor=X&action=Y&start=Z&end=W`? Or structured `/audit?filter[actor]=X`? Must be decided in B1 ticket. **Drift risk.**

**Q4. Date range semantics.**
Inclusive both ends? Exclusive end? Same-day range: `2026-04-15 — 2026-04-15` should include everything on that date. Confirm.

**Q5. Audit ledger pagination / infinite scroll / virtualization?**
A year of events on a busy fund could be thousands of rows. Spec shows a simple table. Need a strategy before B2.

**Q6. Audit ledger visibility per role?**
Is it approver-only? All roles? Operators need to see their own submission events at minimum. Spec §5.5 defines role visibility for the console, not the ledger.

**Q7. Audit entry → package link navigation?**
Clicking a row in the ledger opens the package? Spec §6.4 has the reverse link (package → ledger filtered) but not forward.

**Q8. Do rows have a kebab / overflow menu?**
Not in any of the 7 screens. If we add one in C1, it's a whole new test class. If not, delete from my test plan.

**Q9. Type generation from OpenAPI?**
Strong recommendation: adopt `openapi-typescript` (or equivalent) so `PackageDetail`, `ExtractedField`, `AuditEvent` TypeScript types are generated from the backend schema. This eliminates the Bug 2 / Bug 5 field-name-drift class. **Ask:** may I add this to B1 scope?

**Q10. Modal primitive — Radix vs hand-rolled?**
Focus trap + escape + backdrop + aria attributes are non-trivial to get right. Radix UI `Dialog` solves all of this and is library-verified. Hand-rolled is a flaky-test magnet. **Recommend Radix.**

---

## 6. Gates I will enforce (phase-by-phase)

**Before A1 merges:**
- Login, console, 3× package detail, modal, audit ledger screens each have at least 1 Playwright spec — green.
- Copy audit script finds zero matches of `Upload`, `Sign in` (button), `Approve` (button label), `Documents` heading.
- Brass-discipline spec: scan `data-color="brass"` on console page — appears only on the brass-count badge and the `routed_for_approval` pill.
- Existing `smoke.spec.ts` updated to v0.2 copy or replaced.
- POR-146 regression suite (5 specs) green against staging deploy.

**Before A2 merges:**
- Attestation modal: focus trap, escape, backdrop, double-click, reject-requires-note all covered.
- Radix Dialog (or equivalent) adopted — hand-rolled focus trap is a blocker.

**Before B1 merges:**
- Transition matrix test parametrized over §2.2 — every positive allowed, every negative 409.
- Migration test per §2.3 on a seeded v0.1 database.
- Contract test updated for all new endpoints.
- AuditEvent write-on-transition assertion on every allowed transition.

**Before B2 merges:**
- All 4 confidence bands render correctly — visual regression snapshots.
- Review notes panel loads from backend; empty state copy matches §1.3 exactly.
- Audit ledger 8-filter matrix green.
- Per-field confidence screen-reader text present in DOM.

**Before C1 merges:**
- pdf.js replaces iframe — iframe-auth contract test still green (or updated to pdf.js equivalent).
- Ceremony animations respect `prefers-reduced-motion`.
- Exception resolution flow: low-confidence field click → exception panel → mark resolved → state transitions `exception_surfaced → intake_complete`.

**Before Z1 (Holden sign-off):**
- All 13 Miller deliverables committed and green.
- Full flow Playwright spec (login → intake → review → attest → audit) green against live staging, not just local.
- Brass discipline: DOM-wide scan on every page confirms §9.3 exactly — not one instance more, not one less.

---

## 7. Risk summary (weighted)

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Contract drift on 7 new endpoints | **High** | **High** (POR-146 replay) | Generated types + contract test gate |
| State machine regression in future PRs | Medium | High (compliance surface) | Parametrized matrix test, not happy-path |
| PDF iframe auth breaks in staging | High | Medium | Decide auth strategy in A1, not C1 |
| Modal focus trap flaky | High | Medium | Adopt Radix |
| Brass leaks to a 4th location | Medium | Low (visual) | DOM scan in CI |
| Copy regression on future PRs | Medium | Medium | Copy audit script in CI |
| Audit ledger pagination missed | Medium | Medium (prod perf) | Q5 answered pre-B1 |
| Role-based visibility bypass | Low | **High** (security) | Three role specs per page + backend 403 test |
| Reduced-motion not respected | Low | Low (a11y) | axe-core + prefers-reduced-motion spec |
| Migration drops data | Low | **Very high** (audit trail) | Migration test with pre-migration fixture snapshot |

---

*Filed by Miller. If any of Q1–Q10 remain unanswered when Bobbie/Drummer dispatch, I will block the dispatch. POR-146 does not repeat on my watch.*
