# Debugging: traces, UI mode, inspector

## Record traces

```ts
// playwright.config.ts
use: {
  trace: 'on-first-retry',          // CI: trace only when a test is retried
  screenshot: 'only-on-failure',
  video: 'retain-on-failure',
},
```

Locally: `npx playwright test --trace on`. Traces land in `test-results/<test>/trace.zip`
and are attached to the HTML report.

## Open a trace

```bash
npx playwright show-report                     # HTML report; click a test -> Trace
npx playwright show-trace test-results/checkout-pays/trace.zip
```

Or drop the zip on https://trace.playwright.dev (runs in the browser; the file is not
uploaded to a server, but check your policy before using it with production-like data).

What to read in the trace, in order:

1. **Actions list**: the failing step and how long each step waited.
2. **Before / After DOM snapshots** for that step: is the element there? Hidden? Covered
   by a dialog or spinner? Different text than the locator expects?
3. **Console** tab: app errors (often the real cause).
4. **Network** tab: failed or slow API calls (500, 401 because storage state expired).
5. **Source** and **Call** tabs: the locator that was used and what it resolved to.

## Interactive debugging

```bash
npx playwright test checkout.spec.ts:42 --debug      # Inspector, step through, pick locators
npx playwright test --ui                             # watch mode + time travel
PWDEBUG=1 npx playwright test checkout.spec.ts
```

Insert `await page.pause()` to stop at a point (remove before committing).

## Common failure signatures

| Error | Likely cause |
| --- | --- |
| `Timeout ... waiting for getByRole('button', { name: 'Pay' })` | Wrong name/role, page not in expected state, element inside an iframe (`page.frameLocator(...)`) |
| `strict mode violation: ... resolved to 2 elements` | Locator too broad: scope it (`.filter`, parent locator, `exact: true`) |
| `element is not visible` / `is outside of the viewport` | Hidden by CSS/animation, wrong viewport size |
| `element intercepts pointer events` | Overlay, cookie banner, toast on top: close or wait for it |
| `Target page, context or browser has been closed` | Missing `await` somewhere earlier in the test |
| `net::ERR_CONNECTION_REFUSED` | App not started: check `webServer` config and its `url`/`port` |
| Passes locally, fails in CI | Viewport, fonts, CPU (fewer workers), time zone (`timezoneId`), data from previous runs |
