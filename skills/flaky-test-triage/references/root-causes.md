# Flaky test root causes checklist

Work top to bottom; the first items cause most flakiness.

## 1. Async and timing

- [ ] Fixed sleeps (`time.sleep`, `setTimeout`, `waitForTimeout`, `usleep`) waiting for
      something to happen. Replace with a wait on the condition (poll with timeout,
      web-first assertion, `waitForResponse`, event/callback).
- [ ] Un-awaited promises: `expect(...).resolves` or Playwright `expect(locator)...`
      without `await`; fire-and-forget calls whose errors land in a later test.
- [ ] Timeouts close to the real duration (test takes 4.8 s, timeout 5 s). Check
      `max_time` in the report against the configured timeout.
- [ ] Debounce/throttle/animation in UI tests: wait for the settled state, or disable
      animations (`reducedMotion: 'reduce'`, CSS `animation: none` in test builds).
- [ ] Background jobs/queues: test asserts before the worker finishes. Run jobs
      synchronously in tests, or wait for the job's completion signal.

## 2. Shared state and test order

- [ ] Global/module state mutated by one test (singletons, caches, env vars, `Date`
      mocks, feature flags) and not restored. Reset in teardown; prefer injection.
- [ ] Database rows left by another test (unique constraint errors, unexpected counts).
      Use transactions rolled back per test, unique data per test (sequence ids), or a
      fresh schema per worker.
- [ ] Parallel workers sharing one database, port, temp file, or external account.
      Namespace by worker id (`PYTEST_XDIST_WORKER`, `VITEST_POOL_ID`, `TEST_PARALLEL_INDEX`
      in Playwright as `testInfo.parallelIndex`).
- [ ] Order dependence: run with random order (`pytest -p randomly`, `vitest --sequence.shuffle`,
      `phpunit --order-by=random`) and in reverse to expose it.
- [ ] Mocks not restored: `vi.restoreAllMocks()` / `jest.restoreAllMocks()` in `afterEach`,
      `mocker` fixture in pytest (auto-restores), `Mockery::close()`.

## 3. Time and environment

- [ ] Wall clock: tests near midnight, month end, DST change, leap day, or year end.
      Freeze time and construct dates from a fixed epoch.
- [ ] Time zone and locale differences between CI (UTC, `C.UTF-8`) and laptops.
      Set `TZ=UTC` explicitly, format with explicit locale.
- [ ] Floating point comparisons: use approx/closeTo/delta.
- [ ] Hash/set/dict ordering assumptions; unordered query results without `ORDER BY`.
- [ ] File system: case sensitivity (macOS vs Linux), path separators, line endings.

## 4. Randomness and generated data

- [ ] Unseeded random/Faker data occasionally hits an edge (empty string, duplicate
      email, name with apostrophe). Seed it, or use explicit values for asserted fields.
      `test-data-builders/scripts/nondeterminism_scan.py` finds these.
- [ ] Random UUIDs in sorted output or snapshots.

## 5. External dependencies

- [ ] Real network calls (third-party sandboxes, DNS, package registries). Stub at the
      HTTP boundary; cover the real integration with a few contract tests.
- [ ] Service not ready: database or app container accepting connections later than the
      test starts (`ECONNREFUSED`). Use health checks / wait-for-ready, not sleeps.
- [ ] Rate limits (429) from shared test accounts.

## 6. Resources

- [ ] CPU starvation with too many workers on a small runner: tests time out under load.
      Lower workers (`-n 2`, `--workers=2`, `--maxWorkers=50%`) and compare.
- [ ] Memory leaks across a long run (OOM, heap errors late in the suite).
- [ ] Port exhaustion / `EADDRINUSE` when servers are started per test: use port 0.

## 7. UI-specific (browser tests)

- [ ] Selectors that match more than one element or depend on layout (`nth-child`).
- [ ] Assertions on transient states (spinners) or on values read once instead of
      retrying assertions.
- [ ] Viewport-dependent layouts; fonts and images loading late in screenshots.
- [ ] Login through the UI in every test (rate limiting, slow): reuse storage state.

## Reproduction commands

```bash
# pytest: one test 200 times, stop on first failure (pytest-repeat)
pytest "tests/test_checkout.py::test_pay_with_card" --count 200 -x -p no:randomly
# with others, random order, parallel
pytest tests/test_checkout.py -p randomly -n 4 --count 20
# Vitest: per-test option, or the shell loop below
#   it('adds an item', { repeats: 100 }, () => { ... })
# Playwright
npx playwright test checkout.spec.ts --repeat-each 50 --workers 4
# PHPUnit (use the shell loop; --repeat is not available in every PHPUnit version)
for i in $(seq 1 100); do vendor/bin/phpunit --filter testRetries || break; done
# Any runner: shell loop
for i in $(seq 1 50); do <test command> || { echo "failed on run $i"; break; }; done
```
