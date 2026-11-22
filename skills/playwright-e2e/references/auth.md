# Authentication: log in once, reuse storage state

## Setup project (recommended)

```ts
// tests/auth.setup.ts
import { test as setup, expect } from '@playwright/test';

const authFile = 'playwright/.auth/user.json';

setup('authenticate', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill(process.env.E2E_USER_EMAIL!);
  await page.getByLabel('Password').fill(process.env.E2E_USER_PASSWORD!);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('navigation')).toContainText('Account');   // logged in
  await page.context().storageState({ path: authFile });
});
```

```ts
// playwright.config.ts
export default defineConfig({
  projects: [
    { name: 'setup', testMatch: /.*\.setup\.ts/ },
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], storageState: 'playwright/.auth/user.json' },
      dependencies: ['setup'],
    },
  ],
});
```

Add `playwright/.auth` to `.gitignore`: the file contains session cookies.

Credentials come from environment variables or the CI secret store, never from the
spec file. Use dedicated test accounts on a test environment.

## Faster: authenticate via API

```ts
setup('authenticate', async ({ request }) => {
  await request.post('/api/login', {
    data: { email: process.env.E2E_USER_EMAIL, password: process.env.E2E_USER_PASSWORD },
  });
  await request.storageState({ path: authFile });
});
```

## Several roles

```ts
// one setup test per role writing playwright/.auth/admin.json, member.json
test.describe('admin area', () => {
  test.use({ storageState: 'playwright/.auth/admin.json' });
  test('can refund', async ({ page }) => { /* ... */ });
});

test('admin and member see each other', async ({ browser }) => {
  const admin = await browser.newContext({ storageState: 'playwright/.auth/admin.json' });
  const member = await browser.newContext({ storageState: 'playwright/.auth/member.json' });
  // ...
  await admin.close(); await member.close();
});
```

## Tests that modify the account

If tests change server-side state of the shared user (settings, cart), give each worker
its own account (`testInfo.parallelIndex` -> `user-${index}@example.test`) with a
worker-scoped fixture, or reset state in a `beforeEach` via the API.

## Logged-out tests

```ts
test.use({ storageState: { cookies: [], origins: [] } });
```

## Session storage

`storageState` saves cookies and localStorage (and IndexedDB with
`storageState({ indexedDB: true })` in recent versions), not sessionStorage. Apps that
keep tokens in sessionStorage need an `addInitScript` that restores them.
