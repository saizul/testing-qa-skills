import { test, expect } from '@playwright/test';

test.only('checkout works', async ({ page }) => {
  await page.goto('https://shop.example.com/cart');
  await page.waitForTimeout(3000);
  await page.click('//button[@id="pay"]');
  await page.locator('.css-1x2y3z4 > div:nth-child(2)').click({ force: true });
  const el = await page.$('#total');
  expect(page.getByText('Thanks')).toBeVisible();
  expect(await page.getByRole('alert').isVisible()).toBe(true);
  await page.waitForLoadState('networkidle');
  await page.waitForSelector('.done');
  await page.getByLabel('Password').fill('not-a-real-password');
  // await page.waitForTimeout(1000);  comments are ignored
  await page.waitForTimeout(500); // spec-lint-disable-line PW001
});

test.skip('later', async () => {});
