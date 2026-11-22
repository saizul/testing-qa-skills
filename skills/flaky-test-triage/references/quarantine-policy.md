# Quarantine policy

A flaky test that blocks merges trains people to click "rerun". A deleted test loses
coverage. Quarantine is the middle path: the test keeps running, but cannot block.

## Rules

1. **Quarantine only with an issue.** The issue links the test, the flaky report
   excerpt (pattern, score, signature), an owner and a due date (default: 2 weeks).
2. **Keep running it** in a separate, non-blocking CI job so you can see when it is
   fixed (or gets worse).
3. **Cap the list.** If quarantine grows past ~1-2% of tests or an item passes its due
   date, it is escalated in planning. Tests in quarantine for 30+ days are fixed or
   deleted with an explicit decision.
4. **Never quarantine a `regressed` or `broken` test**: those are real failures.
5. **Leave quarantine only after 50+ consecutive passes** in the quarantine job or a
   local repeat run.

## Mechanics per runner

| Runner | Mark | Run blocking job without / quarantine job with |
| --- | --- | --- |
| pytest | `@pytest.mark.quarantine` (register the marker) | `pytest -m "not quarantine"` / `pytest -m quarantine` |
| Vitest | file suffix `.quarantine.test.ts` | add it to `test.exclude` in the blocking job's config / `vitest run quarantine` |
| Jest | file suffix `.quarantine.test.ts` | `jest --testPathIgnorePatterns quarantine` / `jest quarantine` |
| PHPUnit | `#[Group('quarantine')]` | `phpunit --exclude-group quarantine` / `phpunit --group quarantine` |
| Playwright | tag in title or `{ tag: '@quarantine' }` | `--grep-invert @quarantine` / `--grep @quarantine` |

## Retries policy (short version)

- Retries are allowed only in e2e/browser suites, max 2, and every retry is reported.
- Unit tests never retry: a flaky unit test is a bug in the test or the code.
- Track "tests that passed on retry" per week; it should trend to zero.
- See `ci-test-optimization` for the full CI retries policy.
