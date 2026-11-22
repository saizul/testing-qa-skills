---
name: unit-test-writer
description: Write and review fast, readable unit tests for pytest, unittest, Vitest, Jest and PHPUnit - arrange-act-assert structure, table-driven/parametrized cases, fixtures and setup, mocking only at boundaries (HTTP, clock, filesystem, randomness, third-party SDKs), fake timers, async code, exceptions, and a linter script that finds tests without assertions, committed .only/fit, real sleeps, constant assertions, swallowed exceptions and skipped tests without reasons. Use when the user asks to write, add, improve or review unit tests, increase coverage for a function or class, test a bug fix, mock a dependency, or asks why a test is brittle or slow.
license: MIT
compatibility: Python 3.8+ for the lint script. Test examples target pytest 8, Vitest 3/Jest 29+, PHPUnit 10-12.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Unit test writer

Write tests that fail for one reason, run in milliseconds and survive refactoring.
Test behaviour through the public interface; mock only what crosses a process boundary.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Write tests for this function/class/module", "add a regression test for this bug"
- "Increase coverage of X" (pair with `coverage-gap-analysis` to find what is untested)
- Reviewing a test file: brittle mocks, slow tests, unclear names, missing edge cases
- Choosing between fixture, factory, mock, stub, fake or spy

## When not to use

- Browser journeys: `playwright-e2e`. HTTP response shape checks: `api-contract-testing`
- Tests that need a real database or queue are integration tests: same principles, but use
  real services in containers rather than mocks (see [references/mocking.md](references/mocking.md))
- Deciding *what* to test for a whole feature: `test-plan-writer`

## Workflow

1. **Detect the stack** before writing anything: read `pyproject.toml`/`pytest.ini`/
   `setup.cfg`, `package.json` (vitest or jest, `"type": "module"`), `vitest.config.*`,
   `jest.config.*`, `phpunit.xml(.dist)`, `composer.json`. Match the existing test
   layout, naming, assertion style and helpers; read two existing tests first.
2. **List behaviours, not methods.** For the unit under test write a short list: normal
   cases, boundaries (0, 1, many, max, empty, None/null, unicode), invalid input, error
   paths from dependencies, and state changes. For a bug fix, the first test reproduces
   the bug and fails before the fix.
3. **Decide the seams.** Real collaborators by default. Replace with a fake/stub only:
   network/HTTP, clock and timers, randomness/UUIDs, filesystem outside a temp dir,
   environment variables, third-party SDKs, slow or non-deterministic processes. Do not
   mock the unit's own private helpers or value objects. Details and examples:
   [references/mocking.md](references/mocking.md).
4. **Write the tests** using arrange-act-assert with one behaviour per test and a name
   that states the expectation (`test_total_applies_10_percent_over_100`,
   `it('rejects an expired coupon')`). Use parametrization for tables of inputs. Stack
   recipes:
   - pytest / unittest: [references/pytest.md](references/pytest.md)
   - Vitest / Jest: [references/vitest-jest.md](references/vitest-jest.md)
   - PHPUnit: [references/phpunit.md](references/phpunit.md)
5. **Run only the new tests, then the file, then the suite**:
   ```bash
   pytest tests/test_pricing.py -q            # or: pytest -k discount -x
   npx vitest run src/cart.test.ts            # or: npx jest src/cart.test.ts
   vendor/bin/phpunit --filter MailerTest
   ```
   Make each new test fail once on purpose (break the assertion or the code) to prove
   it can fail, then restore.
6. **Lint the tests** for common smells:
   ```bash
   python3 scripts/lint_tests.py tests/                 # exit 1 on medium+ findings
   python3 scripts/lint_tests.py src/ --fail-on high --json
   ```
   Fix findings or silence a deliberate one with `# lint-tests: ignore[UT003]`
   (`// lint-tests: ignore[UT003]` in JS/PHP) plus a reason.
7. **Report**: what behaviours are now covered, anything you could not test and why
   (hidden global state, missing seam), and suggested refactors to make it testable.

## Rules of thumb

- One reason to fail per test; several asserts are fine if they check one outcome.
- No logic in tests (no loops/ifs computing the expected value); use literal expectations.
- Deterministic: freeze time, seed or inject randomness, no network, no shared mutable state
  between tests, no reliance on test order. Use `test-data-builders` for data.
- Assert on outcomes (return value, state, emitted call to a boundary), not on how many
  times an internal helper was called.
- Prefer specific exception assertions: `pytest.raises(ValueError, match="negative")`,
  `toThrow(CartError)`, `expectException(InvalidAddress::class)`.
- Keep a unit test under ~50 ms. Slow tests are a design smell (real I/O or sleeps).

## Output

The new or changed test file(s), then a short summary:

```
Added 7 tests in tests/test_pricing.py (all pass, 0.04 s):
  - discount boundaries 99.99 / 100 / 100.01 (parametrized)
  - negative total raises DiscountError
  - rounding uses ROUND_HALF_EVEN (regression for #241, failed before the fix)
Mocked: payment gateway HTTP client only. lint_tests.py: 0 findings.
Not covered: currency conversion (needs an injectable rates provider; suggested refactor below).
```
