# Miller — POR-159 / Sprint 19d RED-phase verdict

**Date:** 2026-04-20
**Scope:** POR-152 — author 3 RED-phase E2E specs for D2 Visible AI before Bobbie/Drummer/Naomi start 19d.1–3.
**Branch:** `savnya/por-159-sprint-19d-visible-ai` (created from `origin/main` tip `805e026`).
**Commit:** `09d0f10` — single file `frontend/e2e/visible-ai.spec.ts` (+258 lines, no changes to `smoke.spec.ts`).
**Verdict:** RED-phase PASS. All 3 specs fail for the predicted reasons. Ready to hand off to 19d.1–3.

---

## 1. Charter note (read first)

Standard Miller scope is the test *gate*, not test *authorship* — the SDLC workflow memory says `Holden → Bobbie/Drummer TDD → Miller gate`. Test files are source code and my charter's Write scope is limited to verdict docs under `.squad/decisions/inbox/miller-*.md`.

Holden's replan `holden-d2-visible-ai-replan-2026-04-21.md` §7 explicitly delegates POR-152 (the E2E specs) to Miller for this sprint as a one-off. I've executed under that explicit delegation. Future sprints: default back to Bobbie/Drummer authoring TDD specs, with Miller validating them.

Also: my charter references `/home/sawan/portfolio-analyzer` as the primary working directory. This sprint lives in `/home/sawan/src/arukai-capital-call/`. Same squad, different repo. If Holden wants my charter refreshed to cover the Arukai repo as a first-class target, flag it.

---

## 2. File decision: new isolated file, not an extension of `smoke.spec.ts`

Chose `frontend/e2e/visible-ai.spec.ts` (new) over extending `smoke.spec.ts`:

- Keeps the existing 6 smoke specs a single-purpose ARU-02-P20 file (login / intake / detail layout / attestation / role gates). Those are "is the app alive?" tests.
- Visible-AI specs are a different class: they assert on the *content* of AI output, not on the *shape* of the console. Mixing them muddies intent.
- Red-to-green flip in 19d.4 will show as a clean green on `visible-ai.spec.ts` in isolation — easy to review in Copilot.
- If the AI feature is ever pulled back behind a flag, killing the file is one `git rm`, no surgery on `smoke.spec.ts`.

Justification is in the commit message so Holden doesn't have to dig.

---

## 3. The three specs — RED evidence

Run command (from `frontend/`):

```
FRONTEND_URL=https://arukai-capital-call-frontend-staging-1035777337524.europe-west4.run.app \
BACKEND_URL=https://arukai-capital-call-backend-staging-1035777337524.europe-west4.run.app \
npx playwright test e2e/visible-ai.spec.ts --reporter=list
```

Result: `3 failed`.

### Spec A — Package detail: AI Analysis block shows real data

**Result:** FAIL at `expect(block).toBeVisible()` for `[data-testid="ai-analysis-block"]`.

**Exact error:**
```
Error: expect(locator).toBeVisible() failed
  Locator: locator('[data-testid="ai-analysis-block"]')
  Expected: visible
  Timeout: 5000ms
  Error: element(s) not found
```

**Root cause — deeper than the replan documents:**
`frontend/src/app/documents/[id]/page.tsx:252` renders the block behind `{classification && ( … )}`. Per Holden's live probe (`holden-d2-visible-ai-replan-2026-04-21.md` §2): *`GET /documents/{pkg_id}.classification → null` — POR-151 moved fields top-level and never populated the nested version.* So the block never mounts for existing seed packages on staging.

**Implication for 19d.3:** The replan's 19d.3 scope (threshold 0.5→0.80, "Claude Haiku" fallback, ceremony wiring) does **not** fix the visibility gate. Either:
- (a) backend re-populates `doc.classification` as a compatibility shim, or
- (b) `page.tsx:252` changes its gate to something like `{(classification || doc.extracted_fields) && …}` or just drops the conditional.

This is a **scope-expansion flag to Holden**. Bobbie will hit this the moment the test runs green on A.3–A.5; better to know now. Recommend adding (b) to 19d.3's scope — one-line FE fix.

**Downstream assertions in Spec A (A.3, A.5, A.6)** will exercise the remaining Defect 2 (threshold) and Defect 3 (Claude Haiku fallback) once the block renders. A.6 specifically targets the 0.5→0.80 threshold delta — the exception callout must appear for any field in `[0.5, 0.80)`, which is exactly the case for the staging package that ends `· 1 flagged` in its `ai_summary`.

### Spec B — Operations console: each row shows a well-formed AI summary

**Result:** FAIL at format regex.

**Exact error:**
```
Error: Row 0 summary does not match the 19d.1 target format:
  "Capital Call Notice · 2500000 · due 2026-05-15 · 99% confidence · 0 flags"
  Expected pattern: /\$[\d.]+[KM]?\s+due\s+[A-Z][a-z]+\s+\d{1,2}[\s\S]*\d+\s+fields\s+extracted[\s\S]*\d+%\s+confidence/
  Received string:  "Capital Call Notice · 2500000 · due 2026-05-15 · 99% confidence · 0 flags"
```

**Root cause:** `backend/app/routers/packages.py:181 _build_ai_summary` emits the raw integer from `extracted_fields["amount_due"].value` without currency formatting, emits the ISO `due_date` verbatim, and never writes a "N fields extracted" clause. Lines 185–200 are the scope of the fix.

**Fix (19d.1, Drummer):** rewrite `_build_ai_summary` to produce:
```
Capital Call · $120M due May 15 · 8 fields extracted · 99% confidence · 1 flagged
```
(i.e. short doc-type, compact currency, human date, field count, confidence, flag count.)

**Spec tolerance:** the regex deliberately permits arbitrary separators between the three content anchors (`$… due …`, `N fields extracted`, `% confidence`) so 19d.1 can pick ` · ` or `, ` without breaking.

**Note on the probe snapshot:** Holden's replan quotes the summary as `"Capital Call Notice · 120000000 · due 2026-05-15 · 99% confidence · 1 flagged"` (8-digit amount, 1 flagged). The run I captured returned `2500000 · 0 flags`. Staging seed data has shifted but the *format defect* is identical. The target regex is data-independent so this is fine.

### Spec C — Intake ceremony: `/packages/{id}/intake-status` returns real step data

**Result:** FAIL at status assertion.

**Exact error:**
```
Error: GET /packages/e70b0da6-bb82-4d92-b503-2155fb6fd41b/intake-status
  must be 200 (RED today — returns 404; GREEN after 19d.2).
  Expected: 200
  Received: 404
```

**Root cause:** endpoint not yet built. 19d.2 (Naomi) ships it.

**Strategy chosen — Option 2 (API-level):** justified inline in the spec. Rationale: the ceremony overlay is animation-timed (`ceremonyFadeIn 200ms`, opacity transitions, poll cadence), making the full UI flow flaky unless the poller is deterministically stubbed. The endpoint contract is the artifact that *causes* the ceremony to show real data — if the endpoint returns 200 with the contracted shape, the ceremony will render real labels by construction (IntakeCeremony.tsx's `buildReceiveLabel` / `buildClassifyLabel` / `buildExtractLabel` / `buildReadyLabel` are pure functions of `stepData`, and Bobbie's 19d.3 wiring populates `stepData` directly from the endpoint response).

**TODO left in code:** an Option-1 follow-up spec that uploads a PDF, polls for the overlay, and asserts `data-testid="step-label-{1..4}"` each render real data strings. Separate ticket post-19d.

**Auth fix made during the run:** initial draft tried `window.localStorage.getItem('access_token')`. Staging returned `null` because the frontend stores the JWT in an **httpOnly cookie** (`src/lib/auth.ts:10–31`). Corrected the spec to mint its own bearer token via direct `POST /auth/login` against the backend — matches the public `LoginResponse` shape (`access_token`, `token_type`) exported from `src/lib/api.ts:161`. Cleaner anyway: Spec C no longer depends on page cookies at all.

---

## 4. Testid correction versus the dispatch brief

The dispatch brief suggested `data-testid="ai-summary"` or `.ai-summary` and `data-testid="package-row"`. Neither exists. The real testid in `PackageRow.tsx:144, 153` is **`ai-summary-line`**. No `package-row` testid exists — PackageRow renders a Next.js `<Link>` wrapper. Spec B therefore queries `[data-testid="ai-summary-line"]` directly and iterates over all rendered summaries. Documented in the spec header.

---

## 5. RED-to-GREEN map (for 19d.4 phase 2)

| Spec | Assertion that fails | Fixed by |
|---|---|---|
| A (block visibility) | `[data-testid="ai-analysis-block"]` not visible | **19d.3 — scope-expansion needed** (gate in `documents/[id]/page.tsx:252`); or backend populates `doc.classification` |
| A (threshold) | `[data-testid="exception-callout"]` missing for field in `[0.5, 0.80)` | 19d.3 — `AIAnalysisBlock.tsx:203` change `< 0.5` → `< 0.80` |
| A (model) | `/Mistral\|GPT\|Claude/i` — passes today via "Claude Haiku" fallback, stays green after 19d.3 swaps to "Mistral Small" | 19d.3 (covered but not gating) |
| B (format) | target regex missing `$`, "fields extracted", human date | 19d.1 — rewrite `_build_ai_summary` in `backend/app/routers/packages.py:181` |
| C (endpoint) | `GET /packages/{id}/intake-status` → 404 | 19d.2 — Naomi ships endpoint |

---

## 6. Bounce-back criteria met

- [x] Red phase is red: 3/3 specs fail.
- [x] No product-code modifications: only the new test file was added. Verified via `git diff origin/main -- ':(exclude)frontend/e2e/visible-ai.spec.ts'` is empty.
- [x] Env-based URLs: `FRONTEND_URL` / `BACKEND_URL` both env-sourced, with sensible localhost defaults.
- [x] Did not merge, did not open PR.

---

## 7. Scope-expansion ask for Holden

**Request:** add to 19d.3 a one-line change in `frontend/src/app/documents/[id]/page.tsx:252` so the AIAnalysisBlock no longer depends on `doc.classification` being non-null. Either:
- remove the conditional entirely (block's internals already handle nulls), or
- change the gate to key off `doc.extracted_fields || doc.classification_reasoning`.

Without this, Spec A will remain RED even after 19d.3 completes the threshold + fallback fixes, and Holden's DoD §8 ("ExceptionCallout fires on any field < 0.80 confidence") is physically unreachable — the block never mounts on existing packages.

This is the Defect 0 (block-gated-on-null) hidden behind Defects 1–4 in the replan. Caught in red-phase exactly as the TDD gate is supposed to catch it.

---

## 8. Handoff

Branch `savnya/por-159-sprint-19d-visible-ai` is local only (not yet pushed — waiting on Holden's call on the §7 ask and on 19d.1–3 landing). 19d.1 / 19d.2 / 19d.3 implementers can branch from this branch (or cherry-pick the single test commit `09d0f10`) so the TDD trail stays intact.

Phase 2 (19d.4 part 2) — re-run identical command, expect `3 passed`. I'll file the green verdict as `miller-por159-green.md` at that point.

— Miller

---

# Green-phase result — 2026-04-20

**Branch HEAD:** `137f54f` (19d.1 + 19d.2 + 19d.3 applied + staging deployed).
**Regression:** Backend `SKIP_WINDMILL_TESTS=1 pytest tests/ -q` → **198 passed, 7 skipped** — identical to baseline. Zero regression.
**Verdict:** BOUNCE — not GREEN. 1 real integration defect + 2 spec defects (mine).

## 9. E2E run

Command:
```
FRONTEND_URL=https://arukai-capital-call-frontend-staging-1035777337524.europe-west4.run.app \
  npm run e2e:staging -- e2e/visible-ai.spec.ts --reporter=list
```

Result: **3 failed**, 0 passed.

## 10. Per-spec outcomes

### Spec A — Package detail: AI Analysis block shows real data → FAIL

**Root cause: spec defect I introduced in the RED phase.**

`openFirstPackageDetail` (line 49–58) does `page.locator('a[href^="/documents/"]').first()`. The TopNav component (`src/components/TopNav.tsx:44–56`) renders two `/documents/*` links *before* the PackageRow links:

1. `<Link href="/documents">` — wordmark + Console link
2. `<Link href="/documents/upload">` — "Begin intake"

`.first()` matches one of those and clicks through. The URL regex `/\/documents\/[a-zA-Z0-9_-]+$/` accepts `/documents/upload`, so the assertion passes, and the test body runs against the upload page where `[data-testid="ai-analysis-block"]` of course does not exist.

Playwright page-snapshot in `test-results/visible-ai-A-Package-detai-7729b-…/error-context.md` confirms: browser is on the "Begin governed intake" form, not a package detail.

**This is not a product defect.** The 19d.3 gating fix is correct in source (verified by reading `src/app/documents/[id]/page.tsx:256–284` — the gate now opens on either `classification` OR `doc.classification_reasoning` OR `doc.extracted_fields`). Once the locator actually navigates to a real detail page, A.2–A.6 will exercise the product fixes.

**Fix path (test-code only):**
```ts
// frontend/e2e/visible-ai.spec.ts:50 — was:
const firstRow = page.locator('a[href^="/documents/"]').first();
// fix — match only package-row links (they wrap an ai-summary-line testid):
const firstRow = page.locator('a[href^="/documents/"]')
  .filter({ has: page.locator('[data-testid="ai-summary-line"]') })
  .first();
```
Also tighten the URL regex to require a UUID-shaped slug: `/\/documents\/[0-9a-f]{8}-[0-9a-f]{4}-/`.

Miller can't Write source (charter §"Write tool scope"). Bobbie owns the spec patch.

### Spec B — Operations console: each row shows a well-formed AI summary → FAIL

**Root cause: spec defect. My regex is over-strict on non-capital-call rows.**

Live `GET /packages` (direct curl, admin token) confirms 19d.1 works correctly:

| doc_type | ai_summary |
|---|---|
| `capital_call_notice` | `"Capital Call · $120M due May 15 · 7 fields extracted · 99% confidence · 1 flagged"` ← matches target regex |
| `capital_call_notice` | `"Capital Call · $2M due May 15 · 8 fields extracted · 99% confidence · 0 flags"` ← matches |
| `other` (china_holiday_schedule) | `"Document · 99% confidence · 0 flags"` ← correct for non-extractable doc, does NOT match `$X due … fields extracted` regex |

The console renders sections in order `Exceptions → Pending → Needs review → Active → Recent` (per `src/app/documents/page.tsx:179–214`). The first rendered row in the current staging seed is an `intake_complete` / `other`-type package in Needs-review → summary `"Document · 99% confidence · 0 flags"` → regex rejects it.

My exemption clause only skips literal `"Awaiting classification"`. It should also skip the `"Document · …"` non-capital-call summary, which is a valid, well-formed output.

**Fix path (test-code only):** extend exemption at line 156:
```ts
if (text === 'Awaiting classification') continue;
if (/^Document ·/.test(text)) continue;  // non-capital-call is correctly minimal
```
Again, Bobbie.

### Spec C — Intake ceremony: /packages/{id}/intake-status → FAIL (REAL INTEGRATION DEFECT)

**This one is a genuine product defect.**

19d.2 ships the endpoint — direct curl returns HTTP 200 with a body. But the **JSON case is snake_case**, and the **FE contract is camelCase**. Response body (live staging, package `e70b0da6-bb82-4d92-b503-2155fb6fd41b`):

```json
{
  "current_step": 4,
  "receive":  { "filesize": "1 KB", "mime_type": "application/pdf" },
  "classify": { "doc_type": "Capital Call", "confidence": 0.99, "pending": false },
  "extract":  { "total_fields": 7, "max_fields": 8, "flagged_count": 1 },
  "ready":    { "next_owner": "complete" }
}
```

Frontend contract (`src/components/IntakeCeremony.tsx:31` `IntakeStepData`) requires:
- `receive.mimeType` (not `mime_type`)
- `classify.docType` (not `doc_type`)
- `extract.totalFields` / `maxFields` / `flaggedCount` (not `total_fields` / `max_fields` / `flagged_count`)
- `ready.nextOwner` (not `next_owner`)

Spec C's `typeof body.classify?.docType === 'string'` returns `"undefined"` — exactly what the failure message shows.

**User-visible impact (this is why the charter requires a browser-level smoke):** Bobbie's 19d.3 upload-page poller will hit `/intake-status`, get the 200, and read `undefined` for every label field. The `buildReceiveLabel` / `buildClassifyLabel` / `buildExtractLabel` / `buildReadyLabel` pure functions in `IntakeCeremony.tsx:68–101` all test the camelCase keys and fall through to placeholders (`"Package received"`, `"Classifying materials"`, `"Extracting key fields"`, `"Intake complete"`). Net result: the ceremony renders with the same cosmetic labels POR-159 was supposed to eliminate. **Silent failure — no error, no console log, just fake-AI ceremony still showing.**

**Fix path — Naomi.** Add Pydantic serialization aliases to the four `IntakeStep*` models in `backend/app/routers/packages.py:170–192`:

```python
from pydantic import BaseModel, ConfigDict, Field

def _camel(s: str) -> str:
    head, *tail = s.split("_")
    return head + "".join(w.capitalize() for w in tail)

class IntakeStepBase(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=_camel,
    )

class IntakeStepReceive(IntakeStepBase):
    filesize: Optional[str] = None
    mime_type: Optional[str] = None  # serialized as "mimeType"
# …same for Classify / Extract / Ready
```

This preserves internal Python snake_case and ships camelCase over the wire — the one-line solution.

The root-level `current_step` also needs the alias so the FE gets `currentStep` (confirm this is what `IntakeCeremony.tsx` expects). Quick grep shows the FE consumer pattern reads `stepData.receive`, `stepData.classify`, etc. — not `current_step` directly — so this one is lower priority but still a case-correctness issue.

## 11. Regression delta

- Backend pytest: **198 passed, 7 skipped** — identical to pre-19d baseline. Zero regression.
- FE jest (reported by Holden in handoff, not re-run here): 20 suites / 342 tests pass — baseline preserved.

## 12. Anomalies worth a ticket

1. **FE/BE contract check missing in CI.** The snake_case/camelCase mismatch on `/intake-status` is the exact defect class my charter's §"Mandatory smoke standard" Rule 15 (`scripts/contract_check.py`) is supposed to catch — but that script doesn't exist in this repo. Suggested **POR-160**: add a CI job that diffs FastAPI `openapi.json` response schemas against the TS interfaces used to consume them. Would catch this defect at commit time, not after staging deploy.

2. **`ready.next_owner: "complete"` copy bug.** For `decision_recorded` terminal packages, the endpoint returns `next_owner: "complete"`. `IntakeCeremony.tsx:99` `buildReadyLabel` renders `"Package ready for review · awaiting complete"` — awkward. Either return `null` for terminal states (and let `buildReadyLabel` use its default), or special-case `"complete"` in the label template. Low priority; file follow-up ticket.

3. **Spec defects in `visible-ai.spec.ts`** (A and B) — Bobbie to patch per §10 above. These do not block the 19d.2 case-alias fix.

## 13. Bounce-back summary

Not GREEN. Three actions before re-run:

| Item | Owner | Change |
|---|---|---|
| Spec A locator | Bobbie | `frontend/e2e/visible-ai.spec.ts:50` — scope locator to links that wrap `ai-summary-line`; tighten URL regex to UUID |
| Spec B exemption | Bobbie | `frontend/e2e/visible-ai.spec.ts:156` — add `if (/^Document ·/.test(text)) continue;` |
| Intake-status JSON case | Naomi | `backend/app/routers/packages.py:170–197` — add `ConfigDict(alias_generator=to_camel, populate_by_name=True)` to a shared `IntakeStepBase` |

After all three land on `savnya/por-159-sprint-19d-visible-ai` and staging redeploys, re-run `npm run e2e:staging -- e2e/visible-ai.spec.ts`. Expect 3 passed. Pytest holds at 198 passed.

Not opening PR. Holden dispatches 19d.4a (Bobbie spec fix) and 19d.4b (Naomi alias fix), then re-runs me.

— Miller, 2026-04-20
