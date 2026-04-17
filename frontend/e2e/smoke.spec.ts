/**
 * Arukai Capital Call — Playwright E2E smoke tests (ARU-02-P20 / Z1)
 *
 * Covers:
 *  1. Login as admin → operations console loads with 5 sections
 *  2. Navigate to "Begin intake" → submit PDF → verify redirect (no error)
 *  3. Document detail: 4-block layout renders (source, extracted facts, review notes, audit)
 *  4. "Attest approval" action → attestation modal opens with ceremony language
 *  5. Login as reviewer → cannot access audit ledger (role gate)
 *  6. Login as approver → can access audit ledger
 *
 * NOTE: Tests 2–4 require the backend to be running. Tests 5–6 exercise role
 * gates at the frontend level (server component redirect / access-restricted).
 *
 * The test runner sets FRONTEND_URL; default is http://localhost:3000.
 */

import { test, expect } from '@playwright/test';

const BASE_URL = process.env.FRONTEND_URL || 'http://localhost:3000';

// Seed credentials (seeded by backend lifespan / _seed_dev_users)
const ADMIN_EMAIL = 'admin@arukai.example';
const ADMIN_PASSWORD = 'admin123';
const REVIEWER_EMAIL = 'reviewer@arukai.example';
const REVIEWER_PASSWORD = 'reviewer123';
const APPROVER_EMAIL = 'approver@arukai.example';
const APPROVER_PASSWORD = 'approver123';

// ─── Helper: login via the UI ────────────────────────────────────────────────

async function loginAs(
  page: import('@playwright/test').Page,
  email: string,
  password: string
) {
  await page.goto(BASE_URL);

  // Login page: "Authorized access" heading, "Credentialed email" label, "Enter workflow" button
  await expect(page.getByRole('heading', { name: 'Authorized access' })).toBeVisible();
  await page.getByLabel('Credentialed email').fill(email);
  await page.getByLabel('Passphrase').fill(password);
  await page.getByRole('button', { name: 'Enter workflow' }).click();
}

// ─── Test 1: Admin login → operations console → 5 sections ───────────────────

test('1. admin login → operations console loads with 5 sections', async ({ page }) => {
  await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);

  // Should redirect to /documents
  await expect(page).toHaveURL(/\/documents/, { timeout: 10_000 });

  // H1: "Operations console"
  await expect(page.getByRole('heading', { name: 'Operations console' })).toBeVisible();

  // 5 sections in strict spec order
  const sectionNames = [
    'Exceptions',
    'Pending approval',
    'Needs review',
    'Active packages',
    'Recent decisions',
  ];
  for (const name of sectionNames) {
    await expect(page.getByRole('heading', { name })).toBeVisible();
  }

  // No error alerts
  await expect(
    page.locator('[role="alert"]').filter({ hasText: /Not Found|fetch failed|Failed/ })
  ).toHaveCount(0);
});

// ─── Test 2: Begin intake → submit PDF → verify redirect ─────────────────────

test('2. Begin intake → submit PDF → verify no error and redirect', async ({ page }) => {
  await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  await expect(page).toHaveURL(/\/documents/, { timeout: 10_000 });

  // Click "Begin intake" in Active packages section header or sticky mobile CTA
  await page.getByRole('link', { name: 'Begin intake' }).first().click();
  await expect(page).toHaveURL(/\/documents\/upload/);

  // H1: "Begin governed intake"
  await expect(page.getByRole('heading', { name: 'Begin governed intake' })).toBeVisible();

  // Upload fixture PDF
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles('e2e/fixtures/test-capital-call.pdf');

  // Submit: "Submit package for intake"
  await page.getByRole('button', { name: 'Submit package for intake' }).click();

  // Verify no error alert appears within 15 s (classification may take time)
  await expect(
    page.locator('[role="alert"]').filter({
      hasText: /Failed|Error|fetch failed|Method Not Allowed|Intake failed/,
    })
  ).toHaveCount(0, { timeout: 15_000 });

  // Should redirect to /documents/{id} after successful intake
  await expect(page).toHaveURL(/\/documents\/[a-zA-Z0-9_-]+$/, { timeout: 20_000 });
});

// ─── Test 3: Document detail — 4-block layout ────────────────────────────────

test('3. Document detail: 4-block layout renders', async ({ page }) => {
  await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  await expect(page).toHaveURL(/\/documents/, { timeout: 10_000 });

  // Navigate to first document in list (any row)
  const firstRow = page.locator('a[href^="/documents/"]').first();
  await firstRow.click();
  await expect(page).toHaveURL(/\/documents\/[a-zA-Z0-9_-]+$/);

  // Block 1: Source document
  await expect(
    page.getByRole('heading', { name: 'Source document' })
  ).toBeVisible();

  // Block 2: Extracted facts
  await expect(
    page.getByRole('heading', { name: 'Extracted facts' })
  ).toBeVisible();

  // Block 3: Review notes
  await expect(
    page.getByRole('heading', { name: 'Review notes' })
  ).toBeVisible();

  // Block 4: Audit trail
  await expect(
    page.getByRole('heading', { name: 'Audit trail' })
  ).toBeVisible();
});

// ─── Test 4: Attest approval → modal opens ───────────────────────────────────

test('4. Attest approval → attestation modal opens with ceremony language', async ({ page }) => {
  await loginAs(page, APPROVER_EMAIL, APPROVER_PASSWORD);
  await expect(page).toHaveURL(/\/documents/, { timeout: 10_000 });

  // Navigate to any package routed for approval; if none, skip gracefully
  const attestLink = page.locator('a[href^="/documents/"]').first();
  if (!(await attestLink.isVisible())) {
    test.skip(true, 'No packages in list — cannot test attestation modal');
    return;
  }
  await attestLink.click();
  await expect(page).toHaveURL(/\/documents\/[a-zA-Z0-9_-]+$/);

  // Look for "Attest decision" or "Record attestation" action button
  // The PackageDetailActions component renders "Attest approval" for approvers
  const attestButton = page.getByRole('button', {
    name: /Attest (approval|decision)|Record attestation/i,
  });

  if (!(await attestButton.isVisible())) {
    test.skip(true, 'Package not in routed_for_approval state — cannot test attestation modal');
    return;
  }
  await attestButton.click();

  // Modal should open with ceremony language
  // AttestationModal renders an overlay/dialog
  const modal = page.locator('[role="dialog"], [data-testid="attestation-modal"]');
  await expect(modal).toBeVisible({ timeout: 5_000 });

  // Ceremony language: "attest" or "Attest" appears in the modal
  await expect(modal.getByText(/[Aa]ttest/)).toBeVisible();
});

// ─── Test 5: Reviewer cannot access audit ledger ─────────────────────────────

test('5. Reviewer cannot access audit ledger (role gate)', async ({ page }) => {
  await loginAs(page, REVIEWER_EMAIL, REVIEWER_PASSWORD);
  await expect(page).toHaveURL(/\/documents/, { timeout: 10_000 });

  // Navigate directly to /audit
  await page.goto(`${BASE_URL}/audit`);

  // Should see access-restricted message per spec §S5 / audit/page.tsx
  await expect(
    page.getByText(/Access restricted/i)
  ).toBeVisible({ timeout: 5_000 });

  // Must NOT see the filter bar or export button that admins/approvers see
  await expect(
    page.getByRole('button', { name: /Export ledger|Apply|Load more/i })
  ).toHaveCount(0);
});

// ─── Test 6: Approver can access audit ledger ────────────────────────────────

test('6. Approver can access audit ledger', async ({ page }) => {
  await loginAs(page, APPROVER_EMAIL, APPROVER_PASSWORD);
  await expect(page).toHaveURL(/\/documents/, { timeout: 10_000 });

  // Navigate to /audit
  await page.goto(`${BASE_URL}/audit`);

  // H1: "Audit ledger"
  await expect(
    page.getByRole('heading', { name: 'Audit ledger' })
  ).toBeVisible({ timeout: 5_000 });

  // Role label visible
  await expect(
    page.getByText(/Visible to admins and approvers only/i)
  ).toBeVisible();

  // Should NOT see "Access restricted" (which reviewers see)
  await expect(page.getByText(/Access restricted/i)).toHaveCount(0);
});
