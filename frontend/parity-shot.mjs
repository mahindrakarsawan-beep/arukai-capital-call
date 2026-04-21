// Design-vs-code parity screenshots — Sprint 19d retroactive UAT
// Pulls the 3 live surfaces on staging that correspond to Figma nodes
// 61:2 (package detail), 57:2 (operations console), 58:2 (intake ceremony)
// in the a6mMsiXmnSdQTQ4qQYS6X2 file.

import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const BACKEND =
  "https://arukai-capital-call-backend-staging-1035777337524.europe-west4.run.app";
const FRONTEND =
  "https://arukai-capital-call-frontend-staging-1035777337524.europe-west4.run.app";
const OUT = "/home/sawan/dispatches/parity-shots";

const ADMIN = { email: "admin@arukai.example", password: "admin123" };

async function login(page) {
  await page.goto(`${FRONTEND}/`);
  await page.fill('input[name="email"]', ADMIN.email);
  await page.fill('input[name="password"]', ADMIN.password);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/documents(\/|$)/, { timeout: 15_000 });
}

async function firstPackageId(page) {
  // grab a package id from the API via cookie auth
  const resp = await page.request.get(`${BACKEND}/packages`, {
    headers: { Authorization: await extractToken(page) },
  });
  const data = await resp.json();
  const items = Array.isArray(data) ? data : data.items ?? [];
  // prefer one with "1 flagged" in ai_summary so AIAnalysisBlock shows ExceptionCallout
  const flagged = items.find((p) => /\b[1-9]\d* flagged\b/.test(p.ai_summary ?? ""));
  return (flagged ?? items[0])?.id;
}

async function extractToken(page) {
  const res = await page.request.get(`${FRONTEND}/api/token`);
  const j = await res.json();
  return `Bearer ${j.token}`;
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1024 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();

  // ── Staging sign-in ─────────────────────────────────────────────────────────
  console.log("login…");
  await login(page);

  // ── 57:2 Operations Console ─────────────────────────────────────────────────
  console.log("shot: console (57:2)");
  await page.goto(`${FRONTEND}/documents`);
  await page.waitForLoadState("networkidle");
  await page.waitForSelector('[data-testid="ai-summary-line"]', { timeout: 10_000 });
  await page.screenshot({ path: path.join(OUT, "57-console.png"), fullPage: true });

  // ── 61:2 Package Detail (AI Analysis block) ────────────────────────────────
  console.log("shot: detail (61:2)");
  const pkgId = await firstPackageId(page);
  if (!pkgId) throw new Error("no packages on staging");
  console.log("  pkg:", pkgId);
  await page.goto(`${FRONTEND}/documents/${pkgId}`);
  await page.waitForLoadState("networkidle");
  await page.waitForSelector('[data-testid="ai-analysis-block"]', { timeout: 10_000 });
  await page.screenshot({ path: path.join(OUT, "61-detail.png"), fullPage: true });

  // ── 58:2 Intake Ceremony ────────────────────────────────────────────────────
  // Ceremony auto-dismisses after ~1.2s. Best reproduction: upload a PDF, then
  // screenshot mid-ceremony. Use a tiny valid PDF from the repo if present, else
  // fall back to a placeholder. Take multiple frames ~300ms apart so we capture
  // the working/done cards at different progress points.
  console.log("shot: ceremony (58:2)");
  try {
    await page.goto(`${FRONTEND}/documents/upload`);
    await page.waitForLoadState("networkidle");

    // Tiny PDF bytes — minimal valid single-page PDF. Good enough for intake to accept.
    const tinyPdf = Buffer.from(
      "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 72 72]>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000053 00000 n\n0000000101 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n154\n%%EOF\n",
      "latin1"
    );
    const tmpPath = "/tmp/parity-shot-intake.pdf";
    fs.writeFileSync(tmpPath, tinyPdf);

    // Fill the form + submit
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(tmpPath);
    const titleInput = page.locator('input[type="text"]').first();
    if (await titleInput.count()) {
      await titleInput.fill("parity-shot-ceremony");
    }
    await Promise.all([
      page.waitForSelector('[data-testid="intake-ceremony"], [role="status"]', {
        timeout: 20_000,
      }).catch(() => null),
      page.click('button[type="submit"]'),
    ]);

    // Capture 3 frames of ceremony progression
    for (const [i, delay] of [[0, 250], [1, 700], [2, 1200]]) {
      await page.waitForTimeout(delay);
      await page.screenshot({
        path: path.join(OUT, `58-ceremony-${i}.png`),
        fullPage: false,
      });
    }
  } catch (e) {
    console.log("  ceremony capture failed:", e.message);
    await page.screenshot({ path: path.join(OUT, "58-ceremony-ERROR.png"), fullPage: false });
  }

  await browser.close();
  console.log("done");
  console.log("outputs:", fs.readdirSync(OUT).join(", "));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
