import { test, expect } from './fixtures';

test.describe('checkout', () => {
  test('pays with a saved card', async ({ page, cartWithItems }) => {
    await page.goto('/cart');
    await page.getByRole('button', { name: 'Pay now' }).click();
    await expect(page.getByRole('heading', { name: 'Thank you' })).toBeVisible();
    await expect.soft(page.getByTestId('order-total')).toHaveText('$42.00');
    const response = await page.request.get('/api/orders/latest');
    expect(await response.json()).toMatchObject({ status: 'paid' });
    await Promise.all([expect(page.getByText('a')).toBeVisible(), expect(page.getByText('b')).toBeVisible()]);
    /* page.waitForTimeout(100) inside a block comment
       is ignored */
    const url = 'https://example.com//path'; // string with // inside
  });
});
