# Locators and assertions

## Priority

```ts
page.getByRole('button', { name: 'Place order' })        // 1. role + accessible name
page.getByLabel('Email')                                 // 2. form fields by label
page.getByPlaceholder('Search products')                 // 3.
page.getByText('Order confirmed')                        // 4. non-interactive text
page.getByAltText('Company logo'); page.getByTitle('Close')
page.getByTestId('order-total')                          // 5. explicit contract (data-testid)
page.locator('css=...')                                  // last resort
```

Role locators double as an accessibility check: if you cannot find a button by role and
name, screen reader users cannot either.

Change the test id attribute in config if the app uses another one:
`use: { testIdAttribute: 'data-qa' }`.

## Narrowing without positions

```ts
const row = page.getByRole('row').filter({ hasText: 'Order #1042' });
await row.getByRole('button', { name: 'Refund' }).click();

page.getByRole('listitem').filter({ has: page.getByRole('heading', { name: 'Pro plan' }) });
page.getByRole('dialog').getByRole('button', { name: 'Confirm' });   // scope to the dialog
page.getByRole('link', { name: 'Docs', exact: true });
page.getByRole('button').and(page.getByTitle('Subscribe'));
page.getByRole('button', { name: 'New' }).or(page.getByText('Create'));
```

`first()`, `last()`, `nth(i)` are positional: use only for genuinely ordered lists, and
assert the order explicitly.

## Web-first assertions (auto-retrying, must be awaited)

```ts
await expect(page.getByRole('heading', { name: 'Thank you' })).toBeVisible();
await expect(page).toHaveURL(/\/orders\/\d+$/);
await expect(page.getByTestId('cart-count')).toHaveText('3');
await expect(page.getByRole('row')).toHaveCount(5);
await expect(page.getByLabel('Email')).toHaveValue('ada@example.test');
await expect(page.getByRole('button', { name: 'Pay' })).toBeEnabled();
await expect.soft(page.getByTestId('tax')).toHaveText('$4.20');   // continue on failure
await expect.poll(async () => (await api.get('/orders/1')).status()).toBe(200);
await expect(async () => { /* block retried until it passes */ }).toPass({ timeout: 10_000 });
```

## Anti-patterns -> fixes

| Anti-pattern | Why it flakes | Fix |
| --- | --- | --- |
| `await page.waitForTimeout(2000)` | too short on slow CI, wasted time locally | `await expect(x).toBeVisible()`, `waitForResponse` |
| `expect(page.getByText('Saved')).toBeVisible()` without `await` | promise ignored, test never fails | `await expect(...)` |
| `expect(await el.isVisible()).toBe(true)` | evaluated once, no retry | `await expect(el).toBeVisible()` |
| `expect(await el.textContent()).toBe('3')` | same | `await expect(el).toHaveText('3')` |
| `'//div[3]/span'`, `'div:nth-child(2) > .css-1x2y'` | breaks on layout/build changes | role/label/test id locators |
| `page.$('#id')`, `page.$$eval(...)` | ElementHandles go stale | `page.locator()`, `getBy*` |
| `click({ force: true })` | hides real overlay/disabled bugs | wait for the blocker to go away |
| `waitForLoadState('networkidle')` | polling/analytics keep the network busy | assert on the element you need |
| `page.goto('https://staging...')` | hard-coded env | `use.baseURL`, `page.goto('/path')` |
| `waitForSelector('.done')` | old API | `await expect(locator).toBeVisible()` / `locator.waitFor()` |
| Login steps in every test | slow, rate-limited | storageState setup project |
| `test.only` committed | CI runs one test | `forbidOnly: !!process.env.CI` |
