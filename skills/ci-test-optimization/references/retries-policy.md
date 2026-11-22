# Retries policy

Retries trade signal for green builds. Use them deliberately and keep them visible.

## Policy (adapt and adopt)

1. **Unit and integration tests: no retries.** A flaky test at this level is a bug in
   the test or the code. Fix or quarantine it.
2. **e2e/browser tests: at most 2 retries in CI, 0 locally.** Browsers, networks and
   containers add real noise; retries buy time to fix root causes.
3. **Every retry is reported.** A test that passed on retry is marked flaky in the
   report (Playwright does this; for others, publish the count in the job summary) and
   counted per week. The target trend is zero.
4. **Flaky over threshold goes to quarantine**: a test flaky in more than ~2% of runs
   over a week gets an issue, an owner and a quarantine tag (see `flaky-test-triage`).
5. **Never retry whole jobs automatically** ("rerun failed jobs" on red): it hides
   infrastructure problems and doubles cost. Manual reruns are fine and should be rare.
6. **Never add retries to make a new test pass.** New tests must pass 20+ repeated runs
   before merge.

## Configuration

| Runner | Retries | How flaky results are reported |
| --- | --- | --- |
| Playwright | `retries: process.env.CI ? 2 : 0` | "flaky" status in HTML/JSON/blob reports |
| Vitest | `retry: 0` (set per test only with a linked issue: `{ retry: 2 }`) | final status only: track separately |
| Jest | `jest.retryTimes(2, { logErrorsBeforeRetry: true })` in a setup file for e2e projects only | logs errors before retry |
| pytest | `pytest-rerunfailures`: `@pytest.mark.flaky(reruns=2)` on quarantined tests only | "R" in the summary, `--reruns` output |
| PHPUnit | no built-in retry; do not add one for unit tests | - |
| Surefire | `-Dsurefire.rerunFailingTestsCount=2` | `<flakyFailure>` in XML, "Flakes:" in summary |

## Metrics to watch

- Tests that passed on retry per week (by test) - from `flaky_report.py` or the runner
- Main-branch pass rate on first attempt
- p50/p90 pipeline duration and queue time
- Runner minutes per merged PR
