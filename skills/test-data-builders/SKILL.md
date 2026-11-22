---
name: test-data-builders
description: Create deterministic test data - a generator script turns a sample JSON object into a builder/factory for Python, TypeScript or PHP (sequence-based ids, emails and dates from a fixed epoch, nested builders, override only what the test needs), and a scanner finds non-determinism in tests and fixtures (unseeded random, Faker without seed, Math.random, Date.now, datetime.now, uuid4, rand, time()). Covers factory_boy, Faker seeding, fishery, @faker-js/faker, Laravel model factories, database seeding, fixtures vs builders, and per-test isolation. Use when the user needs test data, factories, fixtures, seeds, fake data, object mothers or builders, or when tests fail because of random data, dates or ids.
license: MIT
compatibility: Python 3.8+ (standard library). Generated builders need nothing beyond the language's standard library.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Test data builders

Every test should state only the data that matters to it and get valid, deterministic
defaults for the rest. Same inputs, same data, every run, on every machine.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Create factories/builders for User and Order", "we need test fixtures/seed data"
- Tests are hard to read because of large inline JSON or copy-pasted setup
- Failures that depend on random data, the current date or generated ids
- Seeding a database for integration/e2e tests or a demo environment

## When not to use

- Production data anonymisation/masking or copying production data to test (needs a
  data-protection review, not a builder)
- Load-test data volumes (millions of rows): use the database's bulk tools
- Property-based testing, where randomness is the point (Hypothesis, fast-check):
  there, keep the seed printed on failure instead of removing randomness

## Workflow

1. **Find what exists.** Look for factories (`factories.py`, factory_boy,
   `database/factories/*Factory.php`, `fishery`, `test/builders`), fixtures
   (`conftest.py`, `fixtures/*.json`), seeders, and how tests create data today.
   Extend the existing approach instead of adding a second one.
2. **Choose the shape** using [references/patterns.md](references/patterns.md):
   builder function with overrides (default), factory library when the project already
   uses one or needs DB persistence/associations, static fixture file only for large,
   rarely changing reference data (country list, product catalogue snapshot).
3. **Generate a starting builder** from one realistic sample (an API response, a DB row
   exported as JSON, with personal data replaced):
   ```bash
   python3 scripts/make_builder.py sample-order.json --name Order --lang python
   python3 scripts/make_builder.py user.json --name User --lang ts --out tests/builders/user.ts
   python3 scripts/make_builder.py user.json --name User --lang php --out tests/Support/UserFactory.php
   python3 scripts/make_builder.py user.json --json        # just show inferred field kinds
   ```
   It never overwrites a file without `--force`. Review the output: give defaults
   domain meaning (a valid status, a realistic price), mark which fields tests usually
   override, and delete fields tests never need.
4. **Make determinism explicit**: reset sequences per test (`reset_sequences()` in an
   autouse fixture / `beforeEach` / `setUp`), seed Faker once if the project uses it,
   freeze time for date-dependent tests. Library recipes:
   [references/libraries.md](references/libraries.md).
5. **Scan for non-determinism** in tests and factories:
   ```bash
   python3 scripts/nondeterminism_scan.py tests/                      # exit 1 on findings
   python3 scripts/nondeterminism_scan.py tests/ database/factories --json
   python3 scripts/nondeterminism_scan.py tests/ --no-suppress        # ignore seeds/freezes in the file
   ```
   A finding is skipped when the same file seeds or freezes the source. Fix the rest, or
   mark a deliberate use with `# nondeterminism: ok` and a reason.
6. **Isolate data between tests**: transaction rollback per test, unique values from
   sequences, per-worker databases/schemas for parallel runs. Seeds for integration/e2e:
   [references/seeding.md](references/seeding.md).
7. **Refactor one or two existing tests** to use the builders and show the before/after
   so the team sees the pattern.

## Rules

- Defaults must be valid: `build_order()` with no arguments passes validation.
- Tests set every value they assert on, even if it equals the default
  (`build_user(role="admin")` before asserting admin behaviour).
- No randomness in values a test asserts on. Unique-but-unasserted values (emails, names)
  come from a sequence, not from `random`.
- Dates come from a fixed epoch or a frozen clock, never from `now()`.
- Keep personal data out: use `example.test`/`example.com` emails and obviously fake names.

## Output

The builder/factory file(s) plus a short note:

```
Added tests/builders.py: build_order(), build_line_item(), build_shipping_address()
  - ids/uuids/emails from one sequence, reset by the autouse fixture in tests/conftest.py
  - dates from EPOCH 2024-01-01T00:00:00Z
Refactored tests/test_checkout.py (3 tests) to use builders: -84 lines
nondeterminism_scan.py: 0 findings (was 6: datetime.now x3, uuid4 x2, unseeded Faker)
```
