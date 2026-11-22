---
name: flaky-test-triage
description: Find, rank and fix flaky tests - a script parses JUnit XML from several CI runs or reruns (pytest, Jest, Vitest, PHPUnit, Playwright, Surefire/Gradle incl. flakyFailure) and classifies each test as flaky, regressed, fixed, broken or stable with a flakiness score, failure-message signatures and likely-cause hints; plus a root-cause checklist (timing, async waits, shared state, test order, time zones, randomness, network, resource limits) and a quarantine policy. Use when the user says tests are flaky, intermittent, pass locally but fail in CI, fail only sometimes, need retries, or asks which tests to quarantine or fix first.
license: MIT
compatibility: Python 3.8+ (standard library). Needs JUnit XML reports; every major test runner can write them.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Flaky test triage

Measure flakiness from evidence (several runs of the same commit), fix the worst
offenders at the root, and quarantine the rest with an owner. Retries hide flakiness;
they are a temporary bandage, not a fix.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "This test is flaky", "passes locally, fails in CI", "random failures"
- Deciding which tests to quarantine, retry or fix first
- Investigating a red build that went green on rerun
- After enabling parallelism or random order, when new failures appear

## When not to use

- A test fails every time: it is broken, not flaky; debug it directly
- Making the whole suite faster: `ci-test-optimization`
- Playwright-specific waiting problems once the flaky test is known: `playwright-e2e`
  has the locator and auto-wait fixes

## Workflow

1. **Collect evidence.** Get JUnit XML from at least 5 runs of the same commit (more is
   better; 20 for rare flakes). Sources, cheapest first:
   - CI artifacts from recent runs on the main branch (one directory per run).
   - Rerun locally in a loop: see [references/runner-commands.md](references/runner-commands.md)
     for pytest (`--count` from pytest-repeat), Vitest/Jest and PHPUnit (shell loop),
     Playwright (`--repeat-each`) with JUnit output enabled.
   - A single run with retries enabled also works: Surefire `<flakyFailure>` elements and
     a test id that appears twice (fail then pass) are counted as flaky.
2. **Rank.**
   ```bash
   python3 scripts/flaky_report.py runs/run-*/junit.xml            # oldest run first
   python3 scripts/flaky_report.py runs/ --run-per-dir --min-runs 5 --top 15
   python3 scripts/flaky_report.py runs/*.xml --json > flaky.json
   python3 scripts/flaky_report.py runs/*.xml --fail-on flaky,broken  # CI gate
   ```
   Statuses: `flaky` (passes and fails, 2+ flips, or passed on retry), `regressed`
   (P...PF...F: a real break, find the commit), `fixed`, `broken`, `stable`. The score
   (0-1.25) is higher when a test fails about half the time and flips often.
3. **Group by signature.** The report normalises failure messages (numbers, hex, UUIDs)
   so one root cause shows as one signature across many tests. Fix shared causes first:
   one fixture or service can make dozens of tests flaky.
4. **Diagnose the top tests** with the checklist in
   [references/root-causes.md](references/root-causes.md). Reproduce before you fix:
   rerun the single test 50-200 times, then with the full file, then with random order
   and parallel workers. A test that only fails with others is order- or state-dependent.
5. **Fix the root cause**, not the symptom: replace sleeps with condition waits, isolate
   data per test, freeze time, seed randomness, await all promises, stub the network.
   Never "fix" by increasing a timeout unless the operation is legitimately slower.
6. **Quarantine what cannot be fixed today** using the policy in
   [references/quarantine-policy.md](references/quarantine-policy.md): tag/skip with an
   issue link and owner, keep running it in a non-blocking job, and set a deadline.
7. **Verify**: rerun the fixed test at least 50 times (same command as step 4) and rerun
   `flaky_report.py`; the test should now be `stable`.

## Decision points

- **`regressed` pattern** (PPPFFF): not flakiness. Bisect the commits between the last
  pass and first failure (`git bisect run <test command>`).
- **Fails only in CI**: compare CPU count, time zone, locale, env vars, service versions,
  file system case sensitivity, and parallelism between CI and local.
- **Many tests flaky at once after an infra change**: suspect the shared environment
  (database container start-up, port collisions, rate limits) before individual tests.
- **Retries already on**: keep them for now but make the report visible (Playwright
  marks tests "flaky"; Surefire writes flakyFailure) and track the count to zero.

## Output

```
Runs analysed: 12 (main @ 3f2c1ab, 2026-11-14..21)
Flaky (3): 
  1. tests.test_checkout::test_pay_with_card  PFPFPPFPPFPP  score 0.93
     5x "TimeoutError: timed out after Nms waiting for gateway" -> timing / slow dependency
     Root cause: real gateway sandbox call; fix: stub with respx, add contract test
  2. ...
Regressed (1): tests.test_users::test_signup since run 9 -> bisect 41a0e2c..3f2c1ab
Quarantined: test_autocomplete (issue #312, owner @search-team, due 2026-12-05)
```

Then the concrete code changes for each fixed test.
