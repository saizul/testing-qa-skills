---
name: coverage-gap-analysis
description: Find what a change leaves untested - a script reads Cobertura XML, LCOV, Clover XML or coverage.py JSON plus a git diff and reports diff coverage, uncovered changed line ranges per file, and changed source files no test loads at all, with a --fail-under gate for CI. Covers generating coverage for pytest, Vitest, Jest, PHPUnit and Go, and deciding which gaps deserve tests. Use when the user asks what is untested in a PR or branch, wants diff/patch coverage, asks why coverage dropped, wants a coverage gate in CI, or asks where to add tests first.
license: MIT
compatibility: Python 3.8+ (standard library). git for --base mode. Coverage reports come from your test runner.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Coverage gap analysis

Coverage says what ran, not what was checked. Use it to find **changed code no test
executes**, then decide which of those gaps matter. Gate on diff coverage (new code),
not on a global percentage.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "What in this PR is not tested?", "diff coverage", "patch coverage"
- "Coverage dropped from 84% to 79%, why?"
- Adding a coverage gate to CI that does not punish legacy code
- Picking where to add tests first in an unfamiliar codebase

## When not to use

- Judging test *quality* (assertions that catch bugs): `mutation-testing-guide`
- Writing the missing tests: `unit-test-writer` (this skill tells you where)
- Hosted coverage services already configured (Codecov, Coveralls, SonarQube): read
  their PR comment first; use this skill when you need it offline or without uploads

## Workflow

1. **Produce a coverage report** for the test suite on the PR branch, in one of the
   supported formats. Commands per stack: [references/generate-coverage.md](references/generate-coverage.md).
   Include all source files (for example `--cov=src`, `coverage.include` in Vitest,
   `<source><include>` in PHPUnit), otherwise files no
   test imports are silently missing rather than reported at 0%.
2. **Run the gap analysis** against the base branch:
   ```bash
   git fetch origin main
   python3 scripts/coverage_gaps.py --coverage coverage.xml --base origin/main
   python3 scripts/coverage_gaps.py --coverage coverage/lcov.info --base origin/main --fail-under 80
   git diff -U0 origin/main...HEAD > pr.diff
   python3 scripts/coverage_gaps.py --coverage clover.xml --diff pr.diff --json
   ```
   Defaults include common source extensions and exclude tests, e2e, migrations, docs and
   `.d.ts`. Adjust with `--include '*.py'`, `--exclude 'src/generated/*'`,
   `--no-default-excludes`. If report paths are absolute (CI checkouts), matching is by
   path suffix; add `--strip-prefix /home/runner/work/app/app/` if names collide.
3. **Read the result by status**, in this order:
   - `NOT IN REPORT`: changed file that no test loaded. Either a new module with no
     tests, or the report config excludes it. Check step 1, then treat as untested.
     Add `--count-missing` to count these lines in the percentage.
   - `UNTESTED`: in the report, but none of the changed executable lines ran.
   - `PARTIAL`: some changed lines ran; the uncovered ranges are listed.
   - `covered` / `no executable changes` (comments, imports, types only).
4. **Triage each gap** with [references/triage.md](references/triage.md): is it logic
   with branches, error handling, glue, or generated/trivial code? Recommend tests for
   the first two; accept or exclude the rest with a reason. Open the file at the
   uncovered ranges and say which behaviour is untested ("the `subtotal > 100` branch",
   "the retry after 429"), not just the line numbers.
5. **Propose tests** (or write them with `unit-test-writer`) for the high-value gaps,
   rerun the suite with coverage and rerun the script to confirm the gaps closed.
6. **For a CI gate**, use the snippet in [references/ci-gate.md](references/ci-gate.md):
   diff coverage `--fail-under 80` (typical) plus `--fail-on-untested` for new files.
   Ask before editing CI configuration.

## Decision points

- **Coverage dropped globally but diff coverage is high**: deleted well-tested code or
  newly included files lowered the average; not a testing regression. Say so.
- **Branch coverage**: the script uses line data. A line with an `if` that ran only one
  way counts as covered; check `branch-rate` / `BRDA` lines in the report for critical
  logic, or rely on mutation testing.
- **Generated code, migrations, config**: exclude with `--exclude`, and exclude them in
  the coverage tool config too, so global numbers stay meaningful.

## Output

```
Diff coverage: 62.5% (5/8 changed executable lines; cobertura) - below the 80% gate
  NOT IN REPORT  src/app/new_module.py     3 changed lines; no test loads this file
  PARTIAL        src/app/pricing.py        4/6 covered, uncovered 12,36
                 -> the 10% discount branch (subtotal > 100) and rounding() are never executed
  PARTIAL        src/app/utils.py          1/2 covered, uncovered 6
Recommended tests (highest value first):
  1. pricing: discount boundary 100 / 100.01 (unit, parametrized)
  2. new_module.hello: one unit test, or exclude if it is a stub
Accepted: utils.slug line 6 - trivial passthrough
```
