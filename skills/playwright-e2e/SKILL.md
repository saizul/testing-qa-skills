---
name: playwright-e2e
description: Write and stabilise Playwright Test end-to-end tests - user-facing locators (getByRole, getByLabel, getByTestId), web-first assertions, custom fixtures and page objects, authentication with storageState and setup projects, network mocking with page.route, test data isolation, trace viewer and UI mode debugging, CI config with retries, sharding and reports; plus a linter script that finds waitForTimeout, missing await on expect and on actions (click, fill, goto), non-retrying assertions, XPath and nth-child selectors, force clicks, networkidle and committed test.only. Use when the user writes, reviews or debugs Playwright tests, asks about e2e/browser tests, flaky UI tests, logging in once for all tests, or reading a Playwright trace.
license: MIT
compatibility: Python 3.8+ for the linter. Recipes target @playwright/test 1.4x-1.5x (TypeScript/JavaScript).
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Playwright e2e

Write few, valuable end-to-end tests that read like user journeys and never sleep.
Playwright auto-waits for actionability and retries web-first assertions: lean on that
instead of manual waits.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- Writing new Playwright tests or page objects/fixtures
- A Playwright test is flaky or slow; reading a trace from CI
- Setting up login once (storageState), test data, network mocks, CI sharding
- Reviewing a spec file or migrating from Cypress/Selenium patterns

## When not to use

- Component logic that a unit test can cover: `unit-test-writer`
- Only checking API response shapes: `api-contract-testing` (Playwright's `request`
  fixture is fine for API setup steps inside e2e tests)
- Ranking which tests are flaky from many CI runs: `flaky-test-triage` first

## Workflow

1. **Read the setup**: `playwright.config.ts` (baseURL, projects, retries, reporter,
   webServer, use.trace), existing fixtures (`fixtures.ts`), page objects, auth setup and
   `package.json` scripts. Match their conventions.
2. **Pick the journey and its assertions.** One test per user goal ("guest pays with a
   saved card"). Decide what proves success (heading, URL, toast, API state) and the
   most expensive failure to cover.
3. **Prepare state outside the UI**: authenticate via a setup project + `storageState`
   ([references/auth.md](references/auth.md)); create data via API calls or builders in a
   fixture, unique per test (`testInfo.workerIndex`, sequence ids); mock third parties
   with `page.route` ([references/fixtures-and-mocks.md](references/fixtures-and-mocks.md)).
4. **Write the test with stable locators**, in this priority:
   `getByRole(name)` > `getByLabel` > `getByPlaceholder` > `getByText` > `getByTestId`
   > CSS. Chain and filter (`.filter({ hasText })`, `getByRole('row').filter(...)`) instead
   of positional selectors. Details and anti-patterns: [references/locators.md](references/locators.md).
   Assert with `await expect(locator).toBeVisible() / toHaveText() / toHaveURL()`;
   every `expect` on a locator or page needs `await`.
5. **Run it headed or in UI mode while writing**:
   ```bash
   npx playwright test checkout.spec.ts --project=chromium --headed
   npx playwright test --ui                          # time-travel debugging, watch mode
   npx playwright codegen http://localhost:3000      # generate locators by clicking
   ```
6. **Lint the specs**:
   ```bash
   python3 scripts/spec_lint.py tests/e2e                    # exit 1 on medium+ findings
   python3 scripts/spec_lint.py e2e --fail-on high --json
   ```
   Fix findings; silence deliberate ones with `// spec-lint-disable-line PW010`.
   Fix `PW003` (assertion without `await`) and `PW015` (action such as `click()`,
   `fill()` or `goto()` without `await`) first: the test keeps running while the step is
   still pending, so failures show up on a later line or never.
7. **Prove stability** before calling it done:
   `npx playwright test checkout.spec.ts --repeat-each 20 --workers 4 --retries 0`.
8. **Debug failures with the trace**, not by adding waits: see
   [references/debugging.md](references/debugging.md) (`npx playwright show-trace`,
   `trace: 'on-first-retry'`, `--debug`, `page.pause()`).

## Decision points

- **Element not found / timeout**: open the trace, check the DOM snapshot at the failing
  step. Usually a wrong locator, a different page state (still loading, a dialog), or
  data not created. Fix that; do not raise the timeout.
- **Need to wait for the backend**: `await page.waitForResponse(r => r.url().includes('/api/orders') && r.ok())`
  around the action, or assert on the UI that shows the result.
- **Visual checks**: `await expect(page).toHaveScreenshot()` only on stable, masked
  regions (`mask: [locator]`), one browser, fixed viewport and fonts in CI (Docker image).
- **Cross-browser**: run all projects in CI nightly; on PRs, chromium only is a common
  trade-off. Say which you chose.
- **CI config, sharding, retries**: [references/ci.md](references/ci.md) and the
  `ci-test-optimization` skill.

## Output

The spec (and fixture/page object changes), then:

```
Added e2e/checkout.spec.ts (2 tests): guest pays with saved card; declined card shows error
State: logged in via auth.setup.ts storageState; order data via API fixture; payment provider mocked with page.route
Stability: --repeat-each 20 --workers 4: 40/40 passed, avg 3.1 s
spec_lint.py: 0 findings
```
