# AGENTS.md

Guidance for Codex CLI and other coding agents that use or work on this repository.

## Using the skills

The skills live in `skills/<name>/SKILL.md` and follow the Agent Skills format. Codex
discovers them when they are copied to `~/.agents/skills/` or `.agents/skills/` (see
README "Install"). If you are reading this file inside the repository instead:

1. Pick the skill whose `description` matches the user's request:

   | Request is about | Skill |
   | --- | --- |
   | test plan, test strategy, what to test, acceptance tests, release sign-off | `test-plan-writer` |
   | writing or reviewing unit tests, mocks, fixtures (pytest, Vitest, Jest, PHPUnit) | `unit-test-writer` |
   | flaky / intermittent tests, passes locally fails in CI, quarantine | `flaky-test-triage` |
   | untested code in a PR, diff coverage, coverage dropped, coverage gate | `coverage-gap-analysis` |
   | Playwright, e2e or browser tests, traces, storageState login | `playwright-e2e` |
   | API matches OpenAPI/swagger, contract tests, HAR validation | `api-contract-testing` |
   | test data, factories, fixtures, seeds, random or date-dependent failures | `test-data-builders` |
   | mutation testing, mutation score/MSI, mutmut, Stryker, Infection | `mutation-testing-guide` |
   | slow CI, sharding, parallel tests, caching, retries policy | `ci-test-optimization` |

2. Read that `SKILL.md` completely and follow its Workflow section in order.
3. Paths such as `scripts/x.py` and `references/y.md` are relative to the skill folder.
   `${CLAUDE_SKILL_DIR}` in the text means that folder; Codex does not expand it.
4. Read files in `references/` only when a workflow step points to them.

## Rules (apply to every skill)

- Run the read-only scripts and the project's own test commands without asking.
- Ask before: editing CI configuration, enabling paid or larger runners, starting runs
  that take more than a few minutes (full mutation testing, hundreds of repeats),
  downloading CI artifacts, or writing to any shared environment or database.
- Never overwrite existing files with generated code without the user's agreement
  (`make_builder.py` refuses unless `--force` is passed).
- Never paste secrets, cookies or tokens (HAR files, `.env`, storage state files) into the
  conversation; summarise instead. Keep them out of git.
- Prove new tests can fail (break the assertion or the code once) and that new e2e tests
  are stable (repeat runs) before calling the work done.

## Working on this repository

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python tools/validate_skills.py   # frontmatter, sections, links, marketplace listing
ruff check . && ruff format --check .
pytest
```

- Scripts: Python 3.8+ standard library only, `#!/usr/bin/env python3`, `argparse` with
  `--help`, `--json` where output is structured, exit 0/1/2 (ok / findings / error).
- Every script needs tests in `tests/test_<skill_with_underscores>.py` with fixtures in
  `tests/fixtures/<skill>/`. Fixtures are sample inputs (reports, specs, deliberately bad
  test files); ruff and pytest ignore `tests/fixtures/`. Use `example.com`/`example.test`
  and never commit real keys, tokens or customer data.
- Keep each `SKILL.md` under 400 lines; move detail to `references/`.
- A new skill must be added to `.claude-plugin/marketplace.json` (`plugins[0].skills`), the
  README table, the table above and `CHANGELOG.md`. The validator enforces the manifest.
