# Vitest and Jest recipes

Vitest's API mirrors Jest's: replace `vi` with `jest` for Jest. Differences are noted.

## Structure and table tests

```ts
import { describe, it, expect } from 'vitest';      // Jest: globals, or import from '@jest/globals'
import { applyDiscount, DiscountError } from './pricing';

describe('applyDiscount', () => {
  it.each([
    { total: 0, expected: 0 },
    { total: 99.99, expected: 99.99 },
    { total: 100, expected: 100 },
    { total: 200, expected: 180 },
  ])('returns $expected for $total', ({ total, expected }) => {
    expect(applyDiscount(total)).toBeCloseTo(expected);
  });

  it('rejects negative totals', () => {
    expect(() => applyDiscount(-1)).toThrow(DiscountError);
    expect(() => applyDiscount(-1)).toThrow(/negative/);
  });
});
```

## Setup and fixtures

```ts
let cart: Cart;
beforeEach(() => {
  cart = new Cart([{ sku: 'a', price: 50 }]);
});
```

Vitest also has `test.extend` fixtures (same idea as Playwright):

```ts
import { test as base } from 'vitest';
const test = base.extend<{ cart: Cart }>({
  cart: async ({}, use) => {
    const cart = new Cart();
    await use(cart);
    cart.clear();
  },
});
```

## Mocking boundaries

```ts
import { vi } from 'vitest';
import * as http from './http';

it('marks the order pending when the gateway times out', async () => {
  const charge = vi.fn().mockRejectedValue(new Error('ETIMEDOUT'));
  const order = await checkout(cart, { gateway: { charge } });     // injected dependency
  expect(order.status).toBe('pending');
  expect(charge).toHaveBeenCalledOnce();      // Jest: toHaveBeenCalledTimes(1)
});

vi.mock('./mailer', () => ({ sendMail: vi.fn().mockResolvedValue({ id: 'm1' }) }));
// Jest: jest.mock('./mailer', () => ({ sendMail: jest.fn() }))

vi.spyOn(http, 'get').mockResolvedValue({ status: 200, body: [] });
afterEach(() => vi.restoreAllMocks());
```

- `vi.mock` calls are hoisted to the top of the file; reference outer variables through
  `vi.hoisted(() => ...)`. In Jest, variables used inside `jest.mock` factories must be
  prefixed `mock`.
- HTTP in Node: prefer MSW (`setupServer` from `msw/node`) over mocking `fetch` by hand.
- ESM + Jest needs `--experimental-vm-modules` and `jest.unstable_mockModule`; Vitest
  handles ESM natively.

## Fake timers and dates

```ts
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2024-01-01T00:00:00Z'));
});
afterEach(() => vi.useRealTimers());

it('reminds after 30 minutes', () => {
  const notify = vi.fn();
  scheduleReminder(notify);
  vi.advanceTimersByTime(30 * 60 * 1000);       // Jest: jest.advanceTimersByTime
  expect(notify).toHaveBeenCalledOnce();
});
```

For promises scheduled by timers use `await vi.advanceTimersByTimeAsync(ms)`
(Jest: `await jest.advanceTimersByTimeAsync(ms)`).

## Async

```ts
it('loads the user', async () => {
  await expect(loadUser(1)).resolves.toMatchObject({ id: 1 });
  await expect(loadUser(-1)).rejects.toThrow(NotFoundError);
});
```

Always `await` or `return` the promise; an un-awaited `expect(...).resolves` never fails.

## React / DOM components

Use Testing Library and query by role: `screen.getByRole('button', { name: /save/i })`,
`await userEvent.click(...)`, `expect(...).toBeInTheDocument()` (jest-dom). Avoid
snapshot tests of large trees; snapshot only small, stable output.

## Useful commands

`npx vitest run` (CI mode), `npx vitest --changed`, `npx vitest run -t "discount"`,
`npx vitest run --coverage` (v8 provider), `npx jest --watch`, `npx jest -t name`,
`npx jest --coverage --coverageReporters=cobertura`.
