---
name: mutation-testing-guide
description: Decide when mutation testing is worth it and run it well with mutmut (Python), Stryker (JavaScript/TypeScript, also C# and Scala) or Infection (PHP) - scope to critical or changed code, incremental and CI modes, time budgets, and a script that parses Stryker mutation.json (mutation-testing-report-schema), Infection JSON logs and mutmut results into a mutation score per file, a list of surviving mutants with the original code and replacement, and a --min-score gate. Explains how to turn each survivor into a better assertion or test. Use when the user asks about mutation testing, mutation score, MSI, surviving or escaped mutants, whether tests actually catch bugs, or test quality beyond coverage.
license: MIT
compatibility: Python 3.8+ (standard library) for the report script. Tools - mutmut 3.x, StrykerJS 8-9, Infection 0.27+ - are installed in the project.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Mutation testing guide

Coverage shows which lines ran; mutation testing shows whether the tests would notice
if those lines were wrong. A tool makes small changes (mutants) to the code, runs the
tests, and reports mutants that survive. Each survivor is a missing or weak assertion.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Are our tests any good?", "coverage is 90% but bugs still get through"
- Setting up mutmut, Stryker or Infection, or reading their reports
- Hardening tests for critical modules (pricing, permissions, parsers, money)
- A mutation score gate in CI, or explaining a dropped MSI

## When not to use

- No fast, reliable unit test suite yet: fix that first (mutation testing multiplies
  test runtime and amplifies flakiness)
- Whole-codebase runs on every PR of a large project: scope it (see below)
- UI/e2e suites: far too slow to mutate against

## Workflow

1. **Decide if and where.** Good targets: pure logic with branches and arithmetic,
   high-risk modules, code changed in the PR. Poor targets: glue code, generated code,
   logging, UI. Agree the scope with the user, and estimate the cost first: mutants are
   roughly 5-15 per 10 lines, and each runs the tests that cover it.
2. **Check prerequisites**: the suite passes reliably (run it twice), runs in minutes,
   and has coverage per test available (Stryker `coverageAnalysis: 'perTest'`, Infection
   uses PHPUnit coverage, mutmut 3 records which tests cover which functions).
3. **Configure the tool** for the scope, using
   [references/tools.md](references/tools.md): mutmut (`[tool.mutmut]` in
   `pyproject.toml`), Stryker (`stryker.config.mjs`, `mutate` globs, `incremental`),
   Infection (`infection.json5`, `source.directories`, `--git-diff-filter`). Start with
   one module.
4. **Run it** (ask before long runs; give an estimate):
   ```bash
   mutmut run && mutmut results > mutmut-results.txt
   npx stryker run                                  # writes reports/mutation/mutation.json with the json reporter
   vendor/bin/infection --threads=max               # "logs": {"json": "infection-log.json"} in infection.json5
   ```
5. **Summarise and rank survivors**:
   ```bash
   python3 scripts/mutation_report.py reports/mutation/mutation.json
   python3 scripts/mutation_report.py infection-log.json --min-score 70 --top 30
   python3 scripts/mutation_report.py mutmut-results.txt --no-coverage --json
   python3 scripts/mutation_report.py mutation.json --only src/pricing
   ```
   Score = (killed + timeout) / (killed + timeout + survived + no coverage). Compile
   errors and ignored mutants do not count.
6. **Work through survivors file by file** using
   [references/survivors.md](references/survivors.md): for each, write down which
   behaviour the mutant changes, then add or tighten an assertion that fails on the
   mutant. For mutmut, inspect a mutant with `mutmut show <name>`. Mark genuinely
   equivalent mutants (same behaviour) as ignored with the tool's mechanism rather than
   writing pointless tests.
7. **Rerun on the module** to confirm the survivors are killed, then decide on CI:
   [references/ci.md](references/ci.md) (incremental on changed files, nightly full run,
   score gate that ratchets).

## Decision points

- **NoCoverage mutants**: no test runs that code. That is a coverage gap: write a test
  (see `coverage-gap-analysis`) before worrying about assertions.
- **Many Timeout mutants**: usually loops mutated into infinite loops: fine (counted as
  detected). If runs are too slow, lower the tool's timeout factor.
- **Survivor in logging/error message text**: low value; exclude that mutator or file.
- **Score target**: no universal number. 60-80% on critical modules is a solid start;
  ratchet upwards. Never chase 100%.

## Output

```
Mutation score src/pricing: 50.0% (killed 2, timeout 1, survived 2, no coverage 1)
Surviving mutants worth a test:
  1. src/pricing.js:2  EqualityOperator `total > 100` -> `total >= 100`
     -> no test at exactly 100; add boundary case discount(100) === 100
  2. src/report.js:1   ArrowFunction body removed -> title() result never asserted
Equivalent / accepted: none. Added 3 assertions; rerun score 100% (6/6).
```
