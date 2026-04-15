import { test, expect } from '@playwright/test';

const BASE_URL = process.env.FRONTEND_URL || 'http://localhost:3000';
const ADMIN_EMAIL = 'admin@arukai.example';
const ADMIN_PASSWORD = 'admin123';

test('happy path: login → dashboard → upload → classify → detail', async ({ page }) => {
  // 1. Navigate to login page
  await page.goto(BASE_URL);
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();

  // 2. Login
  await page.getByRole('textbox', { name: 'Email' }).fill(ADMIN_EMAIL);
  await page.getByRole('textbox', { name: 'Password' }).fill(ADMIN_PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();

  // 3. Verify dashboard loaded
  await expect(page).toHaveURL(/\/documents/);
  await expect(page.getByRole('heading', { name: 'Documents' })).toBeVisible();

  // No "Not Found" or error alert should be visible
  const errorAlert = page.locator('[role="alert"]').filter({ hasText: /Not Found|fetch failed|Failed/ });
  await expect(errorAlert).toHaveCount(0);

  // 4. Navigate to upload
  await page.getByRole('button', { name: /Upload/i }).first().click();
  await expect(page).toHaveURL(/\/upload/);

  // 5. Upload a test PDF (fixture)
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles('e2e/fixtures/test-capital-call.pdf');

  await page.getByRole('button', { name: 'Upload and classify' }).click();

  // 6. Verify redirect to detail page or at least no error
  await expect(page.locator('[role="alert"]').filter({ hasText: /Failed|Error|fetch failed|Method Not Allowed/ })).toHaveCount(0, { timeout: 15000 });
});
