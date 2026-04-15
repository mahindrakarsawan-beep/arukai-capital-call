# ARU-16 Incident Report — D2 v0.1 Browser Smoke Quality Escape

**Incident:** POR-146
**Date opened:** 2026-04-15
**Date of report:** 2026-04-12 (backdated to deployment date for audit alignment)
**Severity:** Urgent — quality escape reached the client
**Author:** Miller (Test & Reliability Engineer)
**Status:** Root-caused; process fix in flight

---

## 0. Verdict (no spin)

D2 v0.1 was declared "deployed" on the basis of a backend-only smoke test (ARU-02-P07 adapted, 4 checks). The first real user loaded the app in a browser and hit five integration defects in a row, none of which my M4 smoke had any chance of detecting because my smoke did not open a browser.

This is a quality escape. It is partly a Miller execution issue (I adapted a mobile-era smoke pattern to a web deployment without questioning whether the pattern was still complete) and mostly a commissioning-core gap (ARU-02-P07 has no browser E2E layer and the pattern library never had one because D1 was an Expo Go mobile app where the browser surface did not exist).

The fix requires both: a new pattern (ARU-02-P20), a new KPI rule (Rule 15 — frontend-backend contract test), and a charter change making browser E2E mandatory for web/mobile deployments. All three are in this report.

---

## 1. Timeline

| Time | Event | Source |
|------|-------|--------|
| 2026-04-12 — morning | Holden locks v0.1 scope (1 happy path, 2 roles, sync) | `v01-scope.md` |
| 2026-04-12 — midday | Drummer finishes M2 backend (FastAPI, 8 REST endpoints, JWT) | Drummer handoff |
| 2026-04-12 — afternoon | Bobbie finishes M3 frontend (Next.js 4-page scaffold) | Bobbie handoff |
| 2026-04-12 — afternoon | Drummer runs M4 deploy to Cloud Run staging (both services) | `drummer-gcp-infra-handoff.md` |
| 2026-04-12 — afternoon | **Miller runs M4 smoke test — 4 checks PASS** | `miller-prod-smoke-full.md` (D2 adapted) |
| 2026-04-12 — afternoon | Naomi compiles scorecard (54.8% weighted reuse, smoke PASS) | `scorecard-deployment-2.md` |
| 2026-04-12 — evening | "Deployed" declared; handoff package posted | Scorecard status line |
| 2026-04-15 — morning | Client opens staging frontend → 5 bugs surface on first use | POR-146 filed |

**Elapsed from "deployed" to first client-facing failure: minutes.** That is the entire defect window. My smoke was already stale against reality before the ink was dry.

---

## 2. The Five Bugs — Per-Bug Root Cause

For each bug: (a) why it existed, (b) why unit/integration tests did not catch it, (c) why the M4 smoke did not catch it.

### Bug 1 — Frontend "fetch failed" on login

- **Why it existed.** The Next.js frontend's `api.ts` reads `process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"`. The Cloud Run frontend service was deployed without `NEXT_PUBLIC_API_URL` set, so server-rendered login page fetched `http://localhost:8000` inside a Cloud Run container. No localhost backend; connection refused; surfaced to browser as "fetch failed."
- **Why tests didn't catch it.** Jest / RTL tests run under Node with `NEXT_PUBLIC_API_URL` either mocked or pointing at a test server. Local `npm run dev` uses a developer `.env.local`. No test asserts "in a real Cloud Run environment, the runtime env is populated AND the value matches the deployed backend URL." The defect only exists in the deploy-time config, not in the code under test.
- **Why smoke didn't catch it.** M4 smoke hits `GET /` and sees HTTP 200 (the SSR shell renders before the client-side fetch runs). It never *does* the login. It has no assertion that a POST from the browser to `/auth/login` actually reaches the backend.

### Bug 2 — "Not Found" alert on dashboard (route mismatch)

- **Why it existed.** Backend router was registered at prefix `/packages`. Frontend `api.ts` calls `/documents/list`, `/documents/{id}`, etc. The two sides diverged silently because Drummer renamed the domain from "packages" → "documents" mid-session on the frontend without propagating it to the router prefix.
- **Why tests didn't catch it.** Backend pytest uses TestClient hitting `/packages/*` directly — all green. Frontend tests mock `fetch`. Neither side imports the other's route list. There is zero contract test linking `api.ts` to the FastAPI router tree.
- **Why smoke didn't catch it.** M4 smoke calls `GET /health` and `POST /auth/login` via curl. Neither of those endpoints is domain-prefixed. The router-prefix mismatch is invisible to any smoke check that does not exercise a domain route via the frontend client.

### Bug 3 — CORS error on upload (wildcard + credentials)

- **Why it existed.** Drummer set `allow_origins=["*"]` + `allow_credentials=True` in FastAPI CORS. Browsers reject this combination per the CORS spec (credentials require an explicit origin, not `*`). This is a silent curl vs browser divergence — curl never enforces CORS.
- **Why tests didn't catch it.** Pytest + httpx do not enforce CORS. No test runs in a real browser against the deployed origin.
- **Why smoke didn't catch it.** M4 curl smoke sends `Origin: *` or no origin header; the backend returns 200. The check ran green and was structurally incapable of reproducing the browser's preflight rejection.

### Bug 4 — Client-side fetch to `localhost:8000` (NEXT_PUBLIC build-time vs runtime)

- **Why it existed.** Next.js inlines `NEXT_PUBLIC_*` at **build** time. The frontend Dockerfile did not accept `NEXT_PUBLIC_API_URL` as a `--build-arg`, so even when Cloud Run had the env var set at runtime, the already-compiled JS bundle referenced the fallback `http://localhost:8000`. Setting the runtime env did nothing for the client bundle.
- **Why tests didn't catch it.** No test ever built the production Docker image and inspected the compiled JS for the baked API URL. Local dev works because `npm run dev` reads env vars at process start.
- **Why smoke didn't catch it.** M4 smoke never looked at a browser-fetched network request. The bug lives in the compiled bundle served from the CDN; it is invisible to any server-side check.

### Bug 5 — 405 Method Not Allowed on upload

- **Why it existed.** Backend registered `POST /documents` (router prefix + empty path route). Frontend called `POST /documents/upload`. Same root cause family as Bug 2 — API path drift between builder and frontend.
- **Why tests didn't catch it.** Same as Bug 2. Backend tests hit `/documents` directly. Frontend tests mock responses.
- **Why smoke didn't catch it.** Same as Bug 2. The upload path was never exercised end-to-end.

### Cross-cutting observation

Bugs 1, 3, 4 are **deploy-time configuration defects** that are structurally invisible to any test that runs locally against a mock. Bugs 2, 5 are **contract drift defects** that are structurally invisible to any test suite that does not cross the frontend-backend boundary. Both classes require a browser-plus-real-deployment check. M4 had neither.

---

## 3. Why the D1 pattern library had no browser E2E pattern

Honest answer: **it was never applicable to D1.**

D1 (Portfolio Analyzer) shipped as:
- A **React Native mobile app** consumed via Expo Go → no browser in the loop
- A **FastAPI + GraphQL backend** with a mobile client that has its own bootstrap query and integration harness

The mobile app's RNTL suite and Expo Go reload cycle functioned as the D1 equivalent of browser E2E: the app was exercised on a device against the deployed backend, and integration bugs surfaced during that cycle before smoke was even considered. The curl-based smoke pattern (ARU-02-P07) was designed to cover the *backend-only* surface because the *frontend surface had its own integration layer* (Expo Go hot reload + mobile-app jest suite + physical device run) that already forced every API call through a real network against the real backend.

When D2 was scoped as web (Next.js SSR + REST), the pattern library was carried over without reassessment. P07 was marked "Adapted" (new checks for health/login/frontend 200) but the **underlying assumption** — that a separate frontend integration harness already exists — was silently violated. D2 has no equivalent of Expo Go. The browser IS the integration harness, and nothing in the pattern library put a browser in the loop.

**This is a pattern-library gap, not a D1 defect.** D1's pattern was correct for D1. It was incomplete for any deployment whose primary surface is a browser.

---

## 4. Miller's honest assessment

### What I should have caught (execution gap — on me)

1. **I adapted P07 without questioning the platform assumption.** When Naomi's reuse projection said "P07 adapted, curl smoke + health + login," I implemented it verbatim. I did not ask "does this pattern still cover the integration surface on a web deployment?" A senior validator should have flagged the missing browser layer before declaring smoke PASS.
2. **I did not run the happy path once as a user.** Even without Playwright, a single manual browser walkthrough of login → list → upload → classify → approve on the deployed staging URL would have surfaced bugs 1, 2, 3, 4, and 5 in five minutes. I skipped it because "smoke was green."
3. **I did not grep `api.ts` against the backend router.** A 10-line script comparing frontend API paths to the FastAPI route table would have caught bugs 2 and 5 before any deploy.

### What was a genuine commissioning-core gap (on the library)

1. **No browser E2E pattern existed.** ARU-02-P07 was designed for mobile deployments where the device is the integration harness. Web deployments have no equivalent — the browser IS the harness, and the library had no pattern for driving it.
2. **No frontend-backend contract test pattern existed.** The 14-rule Copilot KPI checklist covers within-frontend quality (accessibility, motion, normalizers) but has zero rules about cross-boundary contracts (does the client call routes the server exposes?).
3. **The H9 governance control ("Production smoke report") did not specify browser evidence for web surfaces.** It says "numbered check table" which I delivered. It does not say "must include browser walkthrough evidence." That is a governance-layer gap, not just a Miller execution gap.
4. **Next.js-specific build-time vs runtime env var behavior was nowhere documented.** Bug 4 is a Next.js-specific footgun. No ARU pattern or handoff doc warned about it. Future web deployments would have hit it again.

### The split

Roughly 40% my execution, 60% commissioning-core gap. I should have caught bugs 2, 3, and the obvious manual walkthrough. Bugs 1 and 4 require platform-specific guardrails (Cloud Run build-args, runtime env var checks) that were not in any pattern. The whole class of defects should be prevented structurally, not caught by a vigilant Miller.

---

## 5. Corrective actions (full cross-reference)

| # | Action | Artifact | Owner |
|---|--------|----------|-------|
| 1 | Add ARU-02-P20: Browser-based E2E smoke test | `pattern-extraction.md` (updated) | Miller |
| 2 | Add Rule 15: Frontend-backend API contract test | `holden-copilot-kpi-and-rules-v2.md` (new) | Miller + Holden |
| 3 | Update H9 governance control to require browser E2E + CORS preflight + Rule 15 | `governance-handoff-model.md` (updated) | Miller |
| 4 | Update Miller charter: browser E2E mandatory for web/mobile surfaces | `.claude/agents/miller.md` (updated) | Miller |
| 5 | Backfill D2 scorecard: ARU-02-P20 as discovered-in-field, not projected | `scorecard-deployment-2.md` (updated) | Miller + Naomi |
| 6 | Fix the 5 bugs (redeploy, re-verify via Playwright) | Drummer + Bobbie | POR-146 A-track |
| 7 | Post verdict and proof-of-fix plan on POR-146 | Linear comment + doc | Miller |

---

## 6. Proof-of-fix plan (for re-validation)

Before D2 v0.1 can be re-declared "deployed," the following must all pass:

1. **Backend fixes landed:**
   - Router prefix renamed to `/documents`; upload route is `POST /documents/upload`
   - CORS `allow_origins=[<frontend staging URL>]` (specific), `allow_credentials=True`
2. **Frontend fixes landed:**
   - Dockerfile accepts `NEXT_PUBLIC_API_URL` as `ARG` + `ENV` in build stage
   - Cloud Build / deploy workflow passes the correct value at build time
3. **Rule 15 CI check green** — `scripts/contract_check.py` asserts every `api.ts` path maps to a FastAPI route
4. **Playwright E2E green** — full walkthrough: login (admin) → upload PDF → wait for classification → approve → audit trail shows event. Screenshots captured at each step and attached to POR-146.
5. **CORS preflight verification** — `curl -H "Origin: <frontend URL>" -H "Access-Control-Request-Method: POST" -X OPTIONS <backend>/documents/upload` returns 200 with matching `Access-Control-Allow-Origin` (not `*`) and `Access-Control-Allow-Credentials: true`
6. **Evidence pack attached to POR-146** — screenshots + network HAR + Rule 15 output

Only when all six clear does "deployed" re-apply.

---

## 7. Lesson for the commissioning core

The commissioning core's correctness contract is: **patterns are complete for the surface they cover.** D1's smoke was complete for mobile-plus-backend. It was silently incomplete for web-plus-backend because it assumed a non-existent frontend harness. Going forward, every reused pattern must pass a platform-compatibility check — **does this pattern cover the same integration surface on this deployment's stack?** If no, the pattern is net-new for that deployment, not adapted. That single rule would have caught P07 before it was marked green for D2.

---

*Filed by Miller. No excuses. Next deployment, browser E2E is on the gate.*
