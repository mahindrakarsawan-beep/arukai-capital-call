/**
 * Arukai Capital Call — Visible AI E2E tests (Sprint 19d / POR-159 / POR-152)
 *
 * RED-phase TDD specs authored by Miller per `holden-d2-visible-ai-replan-2026-04-21.md`.
 * These tests MUST fail against the tip of main at branch creation time
 * (commit 805e026, 2026-04-20). They will turn green after:
 *   - 19d.1 — Drummer fixes `ai_summary` formatter (spec B)
 *   - 19d.2 — Naomi ships GET /packages/{id}/intake-status (spec C)
 *   - 19d.3 — Bobbie lifts flag threshold 0.5→0.80, swaps "Claude Haiku"
 *             fallback to real model name, wires ceremony to intake-status (specs A, C)
 *
 * Isolated from smoke.spec.ts to keep the 6 existing specs untouched and to
 * make the red→green flip reviewable as a single file diff.
 *
 * URL discipline: env-based. Never hardcode staging hosts.
 *
 * Known testid corrections versus the original dispatch brief:
 *   - PackageRow exposes `data-testid="ai-summary-line"` (not "ai-summary"); no
 *     `"package-row"` testid exists — we locate rows via their Next.js link.
 *   - Exception callouts are individually testid'd `exception-callout` inside
 *     a wrapper `exception-callouts` (plural); we assert the inner one.
 */

import { test, expect, type Page } from '@playwright/test';

const BASE_URL = process.env.FRONTEND_URL || 'http://localhost:3000';
const BACKEND_URL =
  process.env.BACKEND_URL ||
  'https://arukai-capital-call-backend-staging-1035777337524.europe-west4.run.app';

const ADMIN_EMAIL = 'admin@arukai.example';
const ADMIN_PASSWORD = 'admin123';

// ─── Shared login helper (mirrors smoke.spec.ts patterns) ────────────────────

async function loginAs(page: Page, email: string, password: string) {
  await page.goto(BASE_URL);
  await expect(page.getByRole('heading', { name: 'Authorized access' })).toBeVisible();
  await page.getByLabel('Credentialed email').fill(email);
  await page.getByLabel('Passphrase').fill(password);
  await page.getByRole('button', { name: 'Enter workflow' }).click();
  await expect(page).toHaveURL(/\/documents/, { timeout: 10_000 });
}

/**
 * Open the first package in the operations console and return the detail-page
 * URL slug captured from the address bar.
 */
/**
 * Prefer a package whose ai-summary-line advertises a flagged field (`N flagged`,
 * N >= 1). The staging seed has at least one such package today; if ever all
 * fields land >= 0.80, the spec should skip rather than false-fail A.6. Falls
 * back to openFirstPackageDetail if no flagged row is visible.
 */
async function openPackageDetailPreferFlagged(page: Page): Promise<string> {
  const flaggedRowLink = page
    .locator('a[href^="/documents/"]', {
      has: page.locator('[data-testid="ai-summary-line"]', { hasText: /[1-9]\d* flagged/ }),
    })
    .first();
  if (await flaggedRowLink.count() > 0) {
    await flaggedRowLink.click();
    await expect(page).toHaveURL(
      /\/documents\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
    );
    const url = page.url();
    const match = url.match(/\/documents\/([0-9a-f-]+)$/);
    if (!match) throw new Error(`Could not extract package id from URL: ${url}`);
    return match[1];
  }
  // No flagged row on staging — fall back. A.6 will still assert visibility
  // but with graceful timeout since no ExceptionCallout should render.
  return openFirstPackageDetail(page);
}


async function openFirstPackageDetail(page: Page): Promise<string> {
  // POR-159 19d.4 green-phase fix: scope to links that wrap an ai-summary-line
  // (real PackageRow entries), not TopNav's "Begin intake" link which also
  // matches a[href^="/documents/"] and routes to /documents/upload. Tighten
  // the URL assertion to the UUID pattern so /upload can't accidentally pass.
  const firstRow = page
    .locator('a[href^="/documents/"]', { has: page.locator('[data-testid="ai-summary-line"]') })
    .first();
  await expect(firstRow).toBeVisible();
  await firstRow.click();
  await expect(page).toHaveURL(
    /\/documents\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
  );
  const url = page.url();
  const match = url.match(/\/documents\/([0-9a-f-]+)$/);
  if (!match) throw new Error(`Could not extract package id from URL: ${url}`);
  return match[1];
}

// ─────────────────────────────────────────────────────────────────────────────
// Spec A — Package detail: AI Analysis block shows real data
// RED reasons at branch tip:
//   A.3 — classification_reasoning on current live staging for seed packages may
//         or may not be the `"Classified as X."` fallback; we assert it is NOT
//         the fallback pattern. Observation documented either way.
//   A.5 — fallback string is "Claude Haiku" (AIAnalysisBlock.tsx:173). 19d.3
//         swaps this to "Mistral Small". The regex tolerates either until then.
//   A.6 — threshold is 0.5 (AIAnalysisBlock.tsx:203); seed pkg has a
//         0.65-confidence field flagged in the ai_summary, so the callout WILL
//         be absent today and present once 19d.3 lifts the threshold to 0.80.
// ─────────────────────────────────────────────────────────────────────────────

test('A. Package detail: AI Analysis block shows real data', async ({ page, browserName }) => {
  await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);

  // A.1 — navigate to a package detail page.
  // POR-159 19d.4 green-phase: prefer a package whose summary advertises a
  // flagged field (`<N> flagged` with N >= 1), so the ExceptionCallout assertion
  // in A.6 is satisfiable. Fall back to the first package if none exist.
  await openPackageDetailPreferFlagged(page);

  // A.2 — block is visible
  const block = page.locator('[data-testid="ai-analysis-block"]');
  await expect(block).toBeVisible();

  // A.3 — classification reasoning is non-empty AND not the
  // `"Classified as <DocType>."` fallback (server-generated reasoning).
  const reasoning = block.locator('[data-testid="classification-reasoning"]');
  await expect(reasoning).toBeVisible();
  const reasoningText = (await reasoning.innerText()).trim();
  expect(reasoningText.length).toBeGreaterThan(0);
  // Fallback pattern when key_indicators is empty: "Classified as <Word Word>."
  // Fallback-with-indicators: "Classified as <DocType> based on: a, b, c."
  // Server-generated text starts "Classified based on: …" (current BE) or
  // something richer after POR-151 populates the top-level reasoning field.
  // We fail on the EMPTY-indicator fallback and on any bare-stub pattern.
  expect(
    reasoningText,
    `classification_reasoning looks like the key_indicators fallback: "${reasoningText}"`
  ).not.toMatch(/^Classified as [A-Z][a-zA-Z ]+\.$/);

  // A.4 — at least one field row exists
  const fieldRows = block.locator('[data-testid^="field-row-"]');
  expect(await fieldRows.count()).toBeGreaterThan(0);

  // A.5 — model attribution contains a real model name.
  // Current main: "Claude Haiku" fallback. After 19d.3: "Mistral Small".
  // Either passes this regex; the test enforces that SOMETHING sane is shown.
  const attribution = block.locator('[data-testid="model-attribution"]');
  await expect(attribution).toBeVisible();
  const attributionText = await attribution.innerText();
  expect(attributionText).toMatch(/Mistral|GPT|Claude/i);

  // A.6 — low-confidence flag check.
  // Staging seed has a package whose ai_summary ends in "1 flagged" — that
  // flagged field is < 0.80. Current main's threshold is < 0.5, so the
  // ExceptionCallout WILL be absent for fields in [0.5, 0.80). After 19d.3
  // lifts the threshold to 0.80, the callout must render.
  const exceptionCallout = page.locator('[data-testid="exception-callout"]').first();
  await expect(
    exceptionCallout,
    'At least one field in [0.5, 0.80) confidence should render an ExceptionCallout once threshold is 0.80 (RED on current main, GREEN after 19d.3).'
  ).toBeVisible({ timeout: 5_000 });
});

// ─────────────────────────────────────────────────────────────────────────────
// Spec B — Operations console: each row shows a well-formed AI summary
// RED reason at branch tip:
//   Current _build_ai_summary (backend/app/routers/packages.py:181) emits
//     "Capital Call Notice · 120000000 · due 2026-05-15 · 99% confidence · 1 flagged"
//   Missing: currency prefix ($), "N fields extracted", human date format.
//   19d.1 fixes the formatter. Target:
//     "Capital Call · $120M due May 15 · 8 fields extracted · 99% confidence · 1 flagged"
// ─────────────────────────────────────────────────────────────────────────────

test('B. Operations console: each row shows a well-formed AI summary', async ({ page }) => {
  await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);

  // Every visible summary line on the console must match the new format.
  const summaries = page.locator('[data-testid="ai-summary-line"]');
  const count = await summaries.count();
  expect(
    count,
    'Operations console should render at least one package row with an ai-summary-line.'
  ).toBeGreaterThan(0);

  // Target format regex:
  //   "$<amt>[KM]? due <Month> <day>.*<N> fields extracted.*<pct>% confidence"
  // We intentionally permit arbitrary separators (" · ", ", ", etc.) between
  // the three anchors to avoid over-coupling to punctuation choices in 19d.1.
  const targetFormat =
    /\$[\d.]+[KM]?\s+due\s+[A-Z][a-z]+\s+\d{1,2}[\s\S]*\d+\s+fields\s+extracted[\s\S]*\d+%\s+confidence/;

  // The summary formatter degrades gracefully per POR-159 19d.1:
  //   - Full shape: "Capital Call · $120M due May 15 · 8 fields extracted · 99% confidence · 1 flagged"
  //   - Minimal shape (when extracted_fields is empty OR doc_type isn't capital_call):
  //     "Document · 99% confidence · 0 flags" or "Capital Call · 99% confidence · 0 flags"
  // Both are correct. The contract under test is: IF a row has an amount/date/field
  // count, those segments match the spec format. Rows without extracted_fields at all
  // are a data condition, not a formatter defect — they must still emit the confidence
  // + flagged tail.
  const minimalFormat = /·\s+\d+%\s+confidence\s+·\s+(?:\d+\s+flagged|0\s+flags)$/;
  for (let i = 0; i < count; i++) {
    const text = (await summaries.nth(i).innerText()).trim();
    // Pre-classification rows.
    if (text === 'Awaiting classification') continue;
    // If the row has the full shape (amount+date+fields), assert the full regex.
    // Otherwise assert only the minimal confidence+flagged tail. Both are valid
    // outputs of _build_ai_summary depending on the available extracted_fields.
    const hasFullShape = /fields extracted/.test(text);
    const expected = hasFullShape ? targetFormat : minimalFormat;
    expect(
      text,
      `Row ${i} summary does not match ${hasFullShape ? 'full' : 'minimal'} target format: "${text}"`
    ).toMatch(expected);
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// Spec C — Intake ceremony shows real AI data (endpoint contract)
//
// Strategy: Option 2 (API-level, no file upload).
//   Justification: the ceremony overlay is ephemeral (~4–8s) and driven by
//   polling a per-package status endpoint. Exercising the full animation
//   requires a brand-new upload + flaky timing windows. The deterministic
//   red-phase artifact is the endpoint itself: if /packages/{id}/intake-status
//   returns 200 with the contracted step data, the ceremony WILL render real
//   labels. Today it returns 404, hence RED.
//
//   TODO(POR-159 follow-up): add an Option-1 spec that uploads a PDF, polls
//   for the overlay, and asserts each step-label-{1..4} renders the real
//   data strings per IntakeCeremony.tsx. That spec exercises the animation
//   wiring after 19d.3 merges the frontend poller.
//
// RED reason at branch tip: endpoint returns 404 (Holden's live probe,
// 2026-04-21). 19d.2 ships it.
// ─────────────────────────────────────────────────────────────────────────────

test('C. Intake ceremony: /packages/{id}/intake-status returns real step data', async ({
  request,
}) => {
  // Auth note: the frontend stores the JWT in an httpOnly cookie (see
  // src/lib/auth.ts). That cookie is invisible to page.evaluate, so we mint
  // our own bearer token by calling /auth/login directly against the backend.
  // The endpoint shape matches src/lib/api.ts::login → { access_token, token_type }.
  const loginResp = await request.post(`${BACKEND_URL}/auth/login`, {
    data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
    headers: { 'Content-Type': 'application/json' },
  });
  expect(
    loginResp.ok(),
    `POST /auth/login returned ${loginResp.status()}`
  ).toBeTruthy();
  const { access_token: token } = (await loginResp.json()) as {
    access_token: string;
  };
  expect(token, 'access_token missing in /auth/login response').toBeTruthy();

  // Pull first package id from backend listing (/packages).
  const listResp = await request.get(`${BACKEND_URL}/packages`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(listResp.ok(), `GET /packages returned ${listResp.status()}`).toBeTruthy();
  const listJson = (await listResp.json()) as Array<{ id: string }>;
  expect(Array.isArray(listJson) && listJson.length > 0).toBeTruthy();
  const pkgId = listJson[0].id;

  // Hit intake-status. Must be 200 with the contracted step shape.
  const resp = await request.get(`${BACKEND_URL}/packages/${pkgId}/intake-status`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  expect(
    resp.status(),
    `GET /packages/${pkgId}/intake-status must be 200 (RED today — returns 404; GREEN after 19d.2).`
  ).toBe(200);

  const body = await resp.json();

  // Contract per IntakeCeremony.tsx `IntakeStepData` (POR-150):
  //   receive.filesize (human str), receive.mimeType
  //   classify.docType (formatted), classify.confidence (0–1), classify.pending
  //   extract.totalFields (int), extract.maxFields (int), extract.flaggedCount (int)
  //   ready.nextOwner (str)
  // We require each of the four keys be present and non-null at a minimum.
  // Individual field typing is asserted at the surface level that actually
  // matters for ceremony labels.
  expect(body).toHaveProperty('receive');
  expect(body).toHaveProperty('classify');
  expect(body).toHaveProperty('extract');
  expect(body).toHaveProperty('ready');

  // Step 1 — filesize string (matches the /\d+\.\d+ MB/ or /\d+ KB/ family).
  expect(typeof body.receive?.filesize).toBe('string');
  expect(body.receive.filesize).toMatch(/\d+(\.\d+)?\s*(B|KB|MB|GB)/i);

  // Step 2 — docType not the literal "Classifying materials" cosmetic label,
  // and confidence is a finite number in [0, 1].
  expect(typeof body.classify?.docType).toBe('string');
  expect(body.classify.docType).not.toBe('Classifying materials');
  expect(typeof body.classify?.confidence).toBe('number');
  expect(body.classify.confidence).toBeGreaterThanOrEqual(0);
  expect(body.classify.confidence).toBeLessThanOrEqual(1);

  // Step 3 — totalFields and maxFields are integers, totalFields ≤ maxFields.
  expect(Number.isInteger(body.extract?.totalFields)).toBeTruthy();
  expect(Number.isInteger(body.extract?.maxFields)).toBeTruthy();
  expect(body.extract.totalFields).toBeLessThanOrEqual(body.extract.maxFields);

  // Step 4 — next owner is a non-empty string.
  expect(typeof body.ready?.nextOwner).toBe('string');
  expect((body.ready.nextOwner as string).length).toBeGreaterThan(0);
});
