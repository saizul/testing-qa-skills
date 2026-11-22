# Playwright in CI

## Config baseline

```ts
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,       // tune to the runner's CPUs
  reporter: process.env.CI
    ? [['blob'], ['junit', { outputFile: 'test-results/junit.xml' }], ['github']]
    : [['list'], ['html']],
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    timezoneId: 'UTC',
    locale: 'en-US',
  },
  projects: [
    { name: 'setup', testMatch: /.*\.setup\.ts/ },
    { name: 'chromium', use: { ...devices['Desktop Chrome'], storageState: 'playwright/.auth/user.json' }, dependencies: ['setup'] },
  ],
  webServer: {
    command: 'npm run start',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
```

Retries in CI hide flakiness unless you watch the "flaky" count in the report; treat
every flaky test as a bug (see `flaky-test-triage`).

## GitHub Actions with sharding

```yaml
jobs:
  e2e:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        shard: [1, 2, 3, 4]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm }
      - run: npm ci
      - run: npx playwright install --with-deps chromium
      - run: npx playwright test --shard=${{ matrix.shard }}/4
      - uses: actions/upload-artifact@v4
        if: ${{ !cancelled() }}
        with:
          name: blob-report-${{ matrix.shard }}
          path: blob-report
          retention-days: 7

  merge-reports:
    if: ${{ !cancelled() }}
    needs: e2e
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22 }
      - run: npm ci
      - uses: actions/download-artifact@v4
        with: { path: all-blob-reports, pattern: blob-report-*, merge-multiple: true }
      - run: npx playwright merge-reports --reporter html ./all-blob-reports
      - uses: actions/upload-artifact@v4
        with: { name: playwright-report, path: playwright-report, retention-days: 14 }
```

Pin action versions to what the repository already uses. Cache browsers only if
install time matters; the official docs recommend installing per run.

## Useful CLI flags

`--project=chromium`, `--grep @smoke`, `--grep-invert @slow`, `--last-failed`,
`--only-changed=origin/main` (recent versions), `--repeat-each 20`, `--workers 1`,
`--max-failures 10`, `--update-snapshots`.

## Docker for consistent screenshots

Run screenshot tests in the official image matching your Playwright version
(`mcr.microsoft.com/playwright:v<version>-noble`) both locally and in CI so fonts and
rendering match.
