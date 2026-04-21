# Miller Verdict — POR-156 Full-Test Gate

**Verdict: BOUNCE-BACK**

**Date:** 2026-04-20
**Sprint:** Sprint 19a
**Deploy under test:** `main` @ `ac1a00b` → revision 00019 on `arukai-capital-call-backend-staging` / `arukai-capital-call-frontend-staging` (europe-west4, `arukai-testbed`)
**Total wall-clock:** ~8 minutes (gate halted at Gate 2)

---

## Executive summary

Gate **2 FAILED** with a server-side HTTP 500 on `POST /auth/login` for every seed user. Root cause is a missing Alembic migration: the `sessions` table in the staging database lacks the `refresh_token_hash` and `refresh_expires_at` columns that the `Session` ORM model (and `backend/app/routers/auth.py` line 65-82) now require. These columns were added to the code in Sprint 8-10 (commit `42ccee6` — JWT hardening / refresh / revoke-all) but were never encoded as an Alembic migration; the only migration on disk is `0001_v02_state_machine.py`, which predates them.

Because login is the first authenticated surface, **Gates 2, 4, and row 5 of Gate 5 cannot pass**. This is a hard bounce-back per the dispatch brief:
> "qa_e2e_verifier exits non-zero with a real error (not 'seed user missing')"

HTTP 500 is a server error, not a missing-user error (which would be 401). `seed user missing` would produce the same 401 we already see for unknown email addresses — which staging does return correctly.

**This is not a deploy regression in the Sprint 18 sense** — the migration gap has been latent since Sprint 10. But it surfaces now on this staging environment (fresh DB or DB that never had the refresh-token migration applied) and must be fixed before POR-156 can close.

---

## Gate-by-gate results

### Gate 1 — Version sanity — PASS

```
GET /health
→ 200 {"status":"ok","service":"capital-call","version":"0.2.1"}

GET /openapi.json
→ 200, path count = 26  (matches baseline exactly)
```
26 documented paths, including the full Sprint-18 surface (`/packages/*`, `/approvals/*`, `/audit/*`, `/auth/oidc/*`, `/health/detailed`, `/metrics`). **No API regression.**

### Gate 2 — qa_e2e_verifier smoke — FAIL (bounce-back)

**Dispatch discrepancy note:** The brief says `BACKEND_URL=... python3 qa_e2e_verifier.py`. That script (`scripts/qa_e2e_verifier.py`, line 380-385) actually requires `--frontend-url` and `--backend-url` CLI flags, and is Playwright-based. I used the sibling script `scripts/qa_verifier.py --smoke` — that's the curl-based numbered-smoke verifier that matches POR-143's intent. Not a code fix; just a flag-level adjustment. No code was modified.

Command run:
```
python3 scripts/qa_verifier.py --smoke \
  --backend-url https://arukai-capital-call-backend-staging-1035777337524.europe-west4.run.app \
  --frontend-url https://arukai-capital-call-frontend-staging-1035777337524.europe-west4.run.app
```

Final verdict line: **`4/8 checks passed — VERDICT: FAIL`**

Passing: Backend health, Frontend loads, No localhost:8000 in HTML, Arukai branding present.
Failing: Login as admin (HTTP 500), Login as reviewer (HTTP 500), Login as approver (HTTP 500), Skipping auth'd checks (no admin token).

### Root-cause evidence (from Cloud Run logs)

```
sqlalchemy.exc.ProgrammingError: (sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError)
  <class 'asyncpg.exceptions.UndefinedColumnError'>: column sessions.refresh_token_hash does not exist

[SQL: SELECT sessions.id, sessions.user_id, sessions.token_hash, sessions.refresh_token_hash,
             sessions.expires_at, sessions.refresh_expires_at, sessions.revoked_at
       FROM sessions WHERE sessions.token_hash = $1::VARCHAR]
```

Stack trace terminates at:
`/app/app/routers/auth.py:65` → `existing_result = await db.execute(...)` inside `login()`.

### Exact file + line references (DO NOT MODIFY — Drummer's fix territory)

- **Model declaration** (`backend/app/models.py:328`)
  - `refresh_token_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)`
  - Line ~330: `refresh_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)`
- **Call sites** (`backend/app/routers/auth.py:65-82`) — reads/writes `Session.refresh_token_hash` and `Session.refresh_expires_at`
- **Migration gap:** `backend/alembic/versions/0001_v02_state_machine.py` has no reference to `refresh_token_hash` or `refresh_expires_at`. No 0002+ migration exists.
- **Commit that introduced the uncovered columns:** `42ccee6` ("Sprints 8-10: Backup script, metrics/monitoring, JWT hardening (15-min tokens + refresh + revoke-all)")

### Fix-shape Holden should dispatch (Drummer territory, not mine)

1. New Alembic migration `0002_add_refresh_token_columns.py`:
   - `ALTER TABLE sessions ADD COLUMN refresh_token_hash VARCHAR(64) NULL`
   - `CREATE INDEX ix_sessions_refresh_token_hash ON sessions(refresh_token_hash)`
   - `ALTER TABLE sessions ADD COLUMN refresh_expires_at TIMESTAMP WITH TIME ZONE NULL`
2. Deploy pipeline must run `alembic upgrade head` against the staging Cloud SQL instance before the gate is re-run.
3. Failing test first (TDD): integration test that executes `SELECT ... FROM sessions` via the async engine should fail on a pre-migration DB and pass post-migration.

### Gate 3 — Backend pytest (local conftest DB) — PASS (with one note)

```
cd backend && source venv/bin/activate
SKIP_WINDMILL_TESTS=1 python3 -m pytest tests/ -q --ignore=tests/test_windmill_integration.py
→ 198 passed, 2 warnings in 14.32s
```

Collection: 200 tests (198 run + 2 ignored Windmill integration tests). No failures, no errors, no regressions.

**Count note (not a bounce-back trigger):** Dispatch baseline quoted "215 passed, 2 skipped" (217 collected). We collected 200. I did not find a 15-test delta cause; possibilities include a branch/merge where additional tests never landed on `main`, or the baseline was measured with a different ignore set. Since no test failed, this is informational only.

### Gate 4 — Playwright E2E — INCONCLUSIVE (environment), but predicted FAIL

`npm run e2e:staging` launched Playwright 1.59.1 / chromium headless-shell, but every spec failed at browser launch with:
```
error while loading shared libraries: libnspr4.so: cannot open shared object file: No such file or directory
```
System deps missing in WSL. Attempted `sudo npx playwright install-deps chromium`; the sudo prompt could not complete non-interactively in the agent shell.

**However:** even with deps installed, spec 1 (`admin login → operations console loads`) and specs 2-6 (which all depend on a successful login) would fail at the login step because of the Gate-2 HTTP 500. Gate 4 cannot produce meaningful signal until Gate 2 is green.

Result reported as: `6 failed / 0 passed` (environmental, with the login 500 behind it).

### Gate 5 — Manual smoke checklist — 6/7 PASS

| # | Request | Expected | Got | Verdict |
|---|---------|----------|-----|---------|
| 1 | `GET /health` | 200, status=ok | 200, `{"status":"ok","service":"capital-call","version":"0.2.1"}` | PASS |
| 2 | `GET /openapi.json` | 200, paths ≥ 26 | 200, paths=26 | PASS |
| 3 | `GET /docs` | 200, "Arukai Capital Call API" | 200, `<title>Arukai Capital Call API - Swagger UI</title>` | PASS |
| 4 | `POST /auth/login` invalid creds | 401 | 401, `{"detail":"Invalid credentials"}` | PASS |
| 5 | `POST /auth/login` valid seed | 200 + JWT | **500, "Internal Server Error"** | **FAIL** |
| 6 | `GET /packages` (no JWT) | 401 (unauth) | 401 | PASS (auth gate correct) |
| 7 | `GET /` (frontend) | 200, renders login | 200, HTML contains `<form`, `<input` | PASS |

Note on row 6: dispatch said "with valid JWT → 200"; I have no valid JWT (row 5 blocked that), so I verified the unauthenticated shape instead — 401 confirms the auth middleware is wired.

### Gate 6 — Evidence pack — see below

---

## Bounce-back action items for Holden

1. **Do not close POR-156.** Staging is not production-certifiable in its current state.
2. **Open a migration fix ticket** for Drummer. Scope: the 0002 Alembic migration described above + a failing test that exercises a session insert before and after the upgrade.
3. **After migration lands and is applied to staging DB**, re-run this gate from Gate 2. Gates 1 and 3 already PASSED and don't need re-running unless something else changes. Gate 4 additionally needs `sudo playwright install-deps chromium` on the WSL host (one-time), or move the E2E run to a container that already has the Chromium OS deps.
4. **Optional defence-in-depth** (separate work): add a `/health/detailed` check that verifies `sessions.refresh_token_hash` exists, so the next latent-schema-drift bug fails loud at deploy time instead of at first login.

---

## Linear comment body (for Holden to relay to POR-156)

```
GATE BOUNCE-BACK — POR-156

Staging deploy post-Sprint-18 (commit ac1a00b, revision 00019) fails the full-test gate at Gate 2.

Version: 0.2.1 (/health returns 200, status=ok)
openapi paths: 26 (matches baseline, no API regression)
qa_verifier.py --smoke final line: "4/8 checks passed — VERDICT: FAIL"
pytest (local conftest DB, SKIP_WINDMILL_TESTS=1, --ignore=tests/test_windmill_integration.py):
  198 passed, 0 failed, 0 skipped, 200 collected (baseline was 215 passed/2 skipped — gap noted but no failures)
Playwright: inconclusive — WSL host is missing libnspr4.so for chromium headless-shell. All 6 specs failed at browser launch. Even with deps installed, all would fail behind the Gate-2 login 500.

Manual smoke grid (7 rows):
  GET /health                         → 200 (status=ok) ✓
  GET /openapi.json                   → 200 (paths=26)  ✓
  GET /docs                           → 200 (title contains "Arukai Capital Call API") ✓
  POST /auth/login invalid creds      → 401 ✓
  POST /auth/login valid seed creds   → 500 (Internal Server Error) ✗  ← BOUNCE
  GET /packages/ (no JWT)             → 401 ✓ (couldn't test with-JWT path; row 5 blocks it)
  GET / (frontend)                    → 200 (<form>, <input> present) ✓

Root cause (from Cloud Run logs):
  asyncpg UndefinedColumnError: column sessions.refresh_token_hash does not exist
  Origin: backend/app/routers/auth.py:65 (select(Session).where(Session.token_hash == ...))
  The Session ORM model (backend/app/models.py:328) declares refresh_token_hash and refresh_expires_at,
  but the only Alembic migration (backend/alembic/versions/0001_v02_state_machine.py) never adds those
  columns. The code added them in commit 42ccee6 (Sprints 8-10 JWT hardening) but no migration was
  authored — staging DB was never upgraded.

Fix shape (Drummer — separate dispatch, TDD):
  1. Alembic 0002_add_refresh_token_columns.py with:
     ALTER TABLE sessions ADD COLUMN refresh_token_hash VARCHAR(64) NULL;
     CREATE INDEX ix_sessions_refresh_token_hash ON sessions(refresh_token_hash);
     ALTER TABLE sessions ADD COLUMN refresh_expires_at TIMESTAMP WITH TIME ZONE NULL;
  2. Failing test committed first (integration test hitting session insert on a pre-migration DB).
  3. Deploy pipeline runs `alembic upgrade head` against Cloud SQL before gate re-runs.

Gate wall-clock: ~8 minutes (halted at Gate 2; pytest + manual smoke + log-dive completed for full diagnostic).

No code was modified by Miller.
```

---

## Re-gate result: GATE PASS (with two non-blocking latent E2E findings)

## Re-gate after Holden fixes (2026-04-21)

**Deploy under test (unchanged):** `main` @ `ac1a00b` → revision 00019 on `arukai-capital-call-backend-staging` / `arukai-capital-call-frontend-staging` (europe-west4, `arukai-testbed`)
**Fixes applied since last verdict:**
1. `backend/alembic/versions/0002_add_sessions_refresh_columns.py` (Naomi, 54 lines) — applied to staging DB via `alembic upgrade head`. Confirms `sessions.refresh_token_hash` + `sessions.refresh_expires_at` now present.
2. `/home/sawan/dispatches/reset_staging_creds.py` (Holden) — reset 3 seed users to `admin@arukai.example / admin123`, `reviewer@.../reviewer123`, `approver@.../approver123`.

**Total wall-clock for this re-gate:** ~7 minutes (Gate 2: ~10 s, Playwright dep install: ~3 min, Gate 4: ~24 s, Gate 5 row 5–7: ~5 s, analysis + write-up: remainder).

**No Miller code modifications during this re-gate.** `qa_verifier.py` already consumed the correct creds and env vars — no inline patch needed. Playwright spec already hardcoded the correct seeds.

### Gate 2 revisited — qa_verifier.py --smoke — PASS

Command:
```
cd scripts && BACKEND_URL=https://arukai-capital-call-backend-staging-1035777337524.europe-west4.run.app \
              FRONTEND_URL=https://arukai-capital-call-frontend-staging-1035777337524.europe-west4.run.app \
              python3 qa_verifier.py --smoke
```

Final line: **`13/13 checks passed — VERDICT: PASS`**

All three role logins now return HTTP 200 + correct role. Downstream auth'd checks (packages classification shape, v0.2 states, admin-sees-all, `/audit` RBAC, `/approvals` 410 gone) all green. Frontend smoke green (no localhost, Arukai branding present).

The Alembic 0002 migration closed the asyncpg `UndefinedColumnError` cleanly. No Cloud Run error logs during this run.

### Gate 4 revisited — Playwright E2E against staging — MIXED (3 pass, 2 fail, 1 conditional skip)

Playwright deps installed one-time via `sudo -u root npx playwright install-deps chromium` + `npx playwright install chromium` (Chromium 1217, chrome-headless-shell 1217). `libnspr4`, `libnss3`, fonts, xvfb all now present on the WSL host.

Command: `cd frontend && npm run e2e:staging`

Results:
| # | Spec | Result |
|---|------|--------|
| 1 | admin login → operations console loads with 5 sections | **PASS** (2.3 s) |
| 2 | Begin intake → submit PDF → verify no error and redirect | **PASS** (2.5 s) |
| 3 | Document detail: 4-block layout renders | **FAIL** (6.4 s) — test-selector drift |
| 4 | Attest approval → modal opens | skipped (conditional `test.skip` — no routed_for_approval package in staging) |
| 5 | Reviewer cannot access audit ledger (role gate) | **PASS** (1.5 s) |
| 6 | Approver can access audit ledger | **FAIL** (7.2 s) — copy drift |

Summary line: `3 passed, 2 failed, 1 skipped`.

### Gate 4 failure diagnosis — both are pre-existing latent E2E drift, NOT Sprint-18 regressions

**Failure 3 — test-selector bug (NOT a product bug):**
- Spec file: `frontend/e2e/smoke.spec.ts:113` — `const firstRow = page.locator('a[href^="/documents/"]').first();`
- That selector matches both `/documents/upload` (the "Begin intake" link in the console hero) AND `/documents/{id}` rows. On staging the "Begin intake" link is the first such anchor, so Playwright routed to the intake form instead of a document detail.
- Error-context page snapshot (`test-results/smoke-3-.../error-context.md`) confirms: the final URL rendered the **"Begin governed intake"** form, not a document detail. Product surface at `/documents/{id}` is correct — verified by commit inspection at `frontend/src/app/documents/[id]/page.tsx:175` which does render the `Source document` heading.
- Fix shape (implementer territory, one-line): tighten the selector to `a[href^="/documents/"]:not([href="/documents/upload"])` or `a[href*="/documents/"]:not(:has-text("Begin intake"))`.

**Failure 6 — product/test copy drift (NOT a product bug in the strict sense):**
- Test expects H1 `"Audit ledger"` and body text `"Visible to admins and approvers only"`.
- Product renders H1 `"Governed record"` and body `"Visible to administrators and approvers"` — confirmed at `frontend/src/app/audit/page.tsx:78` and `:146`.
- Introduced by commit `26d70f5` ("Audit ledger: governed record language, editorial typography, premium filter bar") — a deliberate visual-polish copy change. Test spec was never updated to match.
- Error-context page snapshot confirms the page fully rendered the audit ledger UI for the approver (108 events, filter bar, export CSV, table headers). Role gate works; only the H1 string assertion is stale.
- Fix shape (implementer territory, two-line test update): change test expectation to `'Governed record'` and `/Visible to administrators and approvers/i`. OR rename H1 back to `'Audit ledger'` — product owner's call (Holden to decide).

**Why these are NOT a bounce-back for POR-156:**
1. Both failures reproduce on `main` @ `ac1a00b` (same commit the previous gate ran against, both pre-Sprint-18 and pre-Sprint-19a).
2. Neither failure touches the Sprint-18 surface (packages classification, v0.2 states, audit endpoint RBAC, deprecated approvals 410) — all of those are GREEN.
3. Commits that introduced the drift (`26d70f5`, `a0ad768`) predate Sprint 18. The failures were masked in the previous re-gate by the login 500 (every spec died at login before reaching assertion-level code).
4. No deploy-certifiability impact: the product actually works correctly; only the test spec is stale.

**Recommendation to Holden:** file a separate P2 ticket `Update staging E2E smoke spec to match shipped copy + tighten doc-detail selector` for Bobbie (or Alex, since this is frontend test-infra). Do NOT block POR-156 on this. The real deployment-verification surface (qa_verifier.py --smoke + manual gate 5 + pytest + admin/reviewer/approver role gates in E2E 1/2/5) is 100 % green.

### Gate 5 row 5–7 revisited — all 7 rows now PASS

| # | Request | Expected | Got | Verdict |
|---|---------|----------|-----|---------|
| 1 | `GET /health` | 200, status=ok | 200, `{"status":"ok","service":"capital-call","version":"0.2.1"}` | PASS (cached from first gate) |
| 2 | `GET /openapi.json` | 200, paths ≥ 26 | 200, paths=26 | PASS (cached) |
| 3 | `GET /docs` | 200, Arukai title | 200 | PASS (cached) |
| 4 | `POST /auth/login` invalid creds | 401 | 401 | PASS (cached) |
| 5 | `POST /auth/login` valid seed | 200 + JWT | **200 + access_token (227 chars) + role=admin** | **PASS** |
| 6 | `GET /packages` with valid JWT | 200 + package list | **200, 7 packages, first state=decision_recorded, has doc_type/confidence/filename** | **PASS** |
| 7 | `GET /` (frontend) | 200, renders login | 200 | PASS (cached) |

Row 6 response shape: first package includes `id`, `title`, `state` (v0.2 value `decision_recorded`, not a v0.1 state), `legacy_status`, `uploaded_by`, `claimed_by_user_id`, `claimed_at`, `last_moved_at`, `created_at`. Matches Sprint-18 contract.

### Final verdict

**GATE PASS** for POR-156 deploy certification of `main` @ `ac1a00b` → revision 00019 on staging.

- All Sprint-18 surfaces verified: authentication (3/3 roles), packages list with v0.2 state & classification fields, audit RBAC (admin yes / reviewer 403), deprecated approvals 410, frontend no-localhost + Arukai branding.
- Local pytest 198/0/0/0 remains green (cached from first gate).
- Browser E2E covers the three critical happy paths (admin console, intake submit, reviewer-blocked audit) end-to-end in real Chromium.
- Two E2E failures are pre-existing latent test-spec drift on frontend copy / selector, not Sprint-18 regressions. Non-blocking per the "mandatory smoke standard" §2 — the browser walkthrough reached the terminal state successfully on the primary happy path (admin login → documents console → all 5 sections). Zero console errors, zero unexpected 4xx/5xx on the successful specs.
- CORS preflight / Rule 15 contract check: not re-run (scope was specifically Gates 2, 4, 5 row 5 per Holden's re-gate brief; the prior verdict did not flag CORS or contract drift as failures).

### Linear comment body (for Holden to paste into POR-156)

```
GATE PASS — POR-156 re-gate after migration + seed-reset fixes

Deploy certified: main @ ac1a00b → revision 00019 (europe-west4, arukai-testbed).

Fixes since bounce:
  1. Alembic 0002_add_sessions_refresh_columns.py applied to staging DB
     (sessions.refresh_token_hash + refresh_expires_at now present).
  2. Seed users reset to admin123 / reviewer123 / approver123 (staging only).

Re-run gates:
  Gate 2 qa_verifier.py --smoke:   13/13 checks passed — VERDICT: PASS
    All 3 role logins 200 + correct role; packages shape OK; v0.2 states;
    admin-sees-all; /audit RBAC correct; /approvals 410 gone.

  Gate 4 Playwright E2E (npm run e2e:staging, real Chromium on WSL):
    Spec 1 admin login → operations console 5 sections     PASS (2.3 s)
    Spec 2 Begin intake → PDF submit → redirect            PASS (2.5 s)
    Spec 3 Document detail 4-block layout                  FAIL — test selector
           bug: locator 'a[href^="/documents/"]' matches both /documents/upload
           and /documents/{id}; picks /upload first and routes away from detail.
           Product surface /documents/{id} renders "Source document" correctly
           (frontend/src/app/documents/[id]/page.tsx:175). Test needs one-line
           selector fix.
    Spec 4 Attest approval modal                           SKIPPED (conditional;
           no routed_for_approval package in staging)
    Spec 5 Reviewer blocked from audit ledger              PASS (1.5 s)
    Spec 6 Approver audit ledger                           FAIL — copy drift:
           commit 26d70f5 renamed audit-ledger H1 to "Governed record" and body
           to "Visible to administrators and approvers"; test still expects
           "Audit ledger" / "admins and approvers only". Product renders the full
           ledger UI (108 events, filter bar, CSV export). Test expectation is
           stale.

  Gate 5 manual smoke grid (all 7 rows):
    1  GET /health                               200 status=ok           PASS
    2  GET /openapi.json                         200 paths=26            PASS
    3  GET /docs                                 200 Arukai title        PASS
    4  POST /auth/login invalid                  401                     PASS
    5  POST /auth/login admin@arukai.example     200 + 227-char JWT      PASS
    6  GET /packages with valid JWT              200, 7 pkgs, v0.2 state PASS
    7  GET /                                     200 login form          PASS

Neither E2E failure is a Sprint-18 regression; both are pre-existing latent
test-spec drift. Recommend separate P2 ticket (Bobbie/Alex) to update
frontend/e2e/smoke.spec.ts: tighten spec 3 selector + align spec 6 copy
assertions to shipped text (or rename H1 back to "Audit ledger" if that's the
product-owner intent). Do NOT block POR-156 on this.

Total re-gate wall-clock: ~7 min (qa_verifier 10 s, Playwright dep install 3 min,
E2E run 24 s, gate 5 5 s, diagnosis + write-up remainder).

No Miller code modifications during this re-gate. No inline test-harness patches
were needed — qa_verifier.py already honoured BACKEND_URL/FRONTEND_URL env vars
and used the correct seed creds; Playwright spec already hardcoded the seeds.
```

