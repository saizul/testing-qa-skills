# Fixtures, page objects, data and network mocks

## Custom fixtures

```ts
// tests/fixtures.ts
import { test as base, expect } from '@playwright/test';
import { CheckoutPage } from './pages/checkout-page';

type Fixtures = {
  checkout: CheckoutPage;
  cartWithItems: { id: string };
};

export const test = base.extend<Fixtures>({
  checkout: async ({ page }, use) => {
    await use(new CheckoutPage(page));
  },
  cartWithItems: async ({ request }, use, testInfo) => {
    // create data through the API, unique per test
    const res = await request.post('/api/test/carts', {
      data: { items: ['SKU-1', 'SKU-2'], owner: `e2e-${testInfo.workerIndex}-${testInfo.testId}` },
    });
    expect(res.ok()).toBeTruthy();
    const cart = await res.json();
    await use(cart);
    await request.delete(`/api/test/carts/${cart.id}`);     // teardown
  },
});
export { expect };
```

Worker-scoped fixtures (`{ scope: 'worker' }`) run once per worker: good for a seeded
account per worker. Use `{ auto: true }` for fixtures every test needs (e.g. failing on
console errors).

## Page objects (thin)

```ts
export class CheckoutPage {
  constructor(private readonly page: Page) {}
  readonly payButton = () => this.page.getByRole('button', { name: 'Pay now' });

  async goto() { await this.page.goto('/checkout'); }
  async payWithSavedCard(last4: string) {
    await this.page.getByRole('radio', { name: `Card ending ${last4}` }).check();
    await this.payButton().click();
  }
}
```

Keep assertions in tests (or expose locators for them); page objects hold locators and
actions, not test logic.

## Network mocking

```ts
test('shows an error when the payment provider declines', async ({ page }) => {
  await page.route('**/api/payments', (route) =>
    route.fulfill({ status: 402, json: { code: 'card_declined' } }),
  );
  await page.goto('/checkout');
  await page.getByRole('button', { name: 'Pay now' }).click();
  await expect(page.getByRole('alert')).toHaveText(/declined/i);
});

// modify a real response
await page.route('**/api/products', async (route) => {
  const response = await route.fetch();
  const json = await response.json();
  await route.fulfill({ response, json: [...json, { id: 999, name: 'Out of stock item', stock: 0 }] });
});

// block third-party noise
await page.route(/(analytics|hotjar|intercom)/, (route) => route.abort());

// replay from a HAR recorded once
await page.routeFromHAR('tests/hars/products.har', { url: '**/api/**', update: false });
```

Mock third parties you do not control; keep your own backend real in e2e tests (that is
the point of e2e). Cover the third-party contract separately (`api-contract-testing`).

## Time

```ts
await page.clock.setFixedTime(new Date('2024-02-29T10:00:00Z'));   // Date.now() fixed, timers run
await page.clock.install({ time: new Date('2024-02-29T10:00:00Z') });
await page.clock.fastForward('30:00');                             // skip 30 minutes
```

## Test isolation checklist

- Each test gets a fresh browser context (cookies/storage) by default; keep it that way.
- No test depends on another test's data or order (`fullyParallel: true` exposes this).
- Unique names/emails per test: `` `e2e-${testInfo.workerIndex}-${Date.now()}` `` is
  acceptable for uniqueness in e2e data (not for asserted values).
- Clean up in fixture teardown, or use a disposable environment/database per CI run.
