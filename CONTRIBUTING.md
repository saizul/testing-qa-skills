# Contributing to testing-qa-skills

Thank you for helping! New checks, new skills, fixes, test fixtures from real-world
reports (redacted) and clearer docs are all welcome.

- [Ways to contribute](#ways-to-contribute)
- [Good first issues](#good-first-issues)
- [Development setup](#development-setup)
- [Repository layout](#repository-layout)
- [Write a new skill](#write-a-new-skill)
- [Quality bar](#quality-bar)
- [Pull request process](#pull-request-process)

## Ways to contribute

| Size | Idea |
| --- | --- |
| 10 minutes | Fix a typo, clarify a workflow step, add a FAQ entry |
| 30 minutes | Add a missing test case or a fixture that triggers a false positive |
| 1-2 hours | Add a check to an existing script (see below) |
| Half a day | Write a new skill from the template |

Comment on an issue before you start so nobody else picks the same one.

## Good first issues

Each of these is self-contained and touches one script and its test file.

1. **flaky-test-triage: Playwright JSON reporter.** Accept `--reporter=json` output and
   read its `flaky` status directly, in addition to JUnit XML.
2. **flaky-test-triage: Markdown output.** Add `--markdown` that prints the ranking as a
   table for a GitHub job summary (`$GITHUB_STEP_SUMMARY`).
3. **coverage-gap-analysis: branch coverage.** Read Cobertura `condition-coverage` and
   LCOV `BRDA` records and report changed lines with partially covered branches.
4. **coverage-gap-analysis: JaCoCo XML.** Parse `<sourcefile><line nr mi ci>` so Java and
   Kotlin projects work without a converter.
5. **playwright-e2e: new rule.** Report `page.locator('text=...')` and other legacy
   selector engines, suggesting `getByText` / `getByRole`.
6. **playwright-e2e: config check.** Add `--config playwright.config.ts` that warns when
   `forbidOnly`, `trace` or `retries` are missing.
7. **unit-test-writer: Go support.** Detect `func TestX(t *testing.T)` without `t.Error`,
   `t.Fatal` or a `testify` assertion.
8. **unit-test-writer: UT009 magic sleeps in pytest-asyncio.** Flag `await asyncio.sleep(n)`
   with `n > 0.1` in async tests separately from sync sleeps.
9. **api-contract-testing: request validation.** Validate recorded request bodies and
   query parameters against `requestBody` and `parameters`.
10. **api-contract-testing: external `$ref`.** Resolve `other.yaml#/components/...`
    relative to the spec file (local files only).
11. **test-data-builders: `--lang go`.** Generate a struct and a `NewX(opts ...func(*X))`
    builder with sequence defaults.
12. **mutation-testing-guide: PIT XML.** Parse `mutations.xml` from pitest.
13. **ci-test-optimization: `--format github-matrix`.** Print the JSON matrix for
    `strategy.matrix` so the shard count can be dynamic.
14. **New skill: `snapshot-test-review`** (see the roadmap in the README).

## Development setup

```bash
git clone https://github.com/saizul/testing-qa-skills.git
cd testing-qa-skills
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt

python tools/validate_skills.py   # SKILL.md frontmatter, sections, links, marketplace listing
ruff check . && ruff format --check .
pytest
```

A few tests use optional tools when present and skip otherwise: `git` (diff mode of
coverage_gaps.py), `node` and `php` (they execute the generated builders), PyYAML (YAML
OpenAPI fixture).

To try your changes in Claude Code, either copy a skill to `~/.claude/skills/` or add your
checkout as a local marketplace:

```bash
claude plugin marketplace add ./testing-qa-skills
claude plugin install testing-qa-skills@testing-qa-skills
```

For Codex, copy the skill folder to `~/.agents/skills/`.

## Repository layout

```
.claude-plugin/
  marketplace.json      marketplace + plugin entry listing every skill
  plugin.json           plugin manifest (name, version, author)
skills/<name>/
  SKILL.md              frontmatter + workflow (the part agents read)
  scripts/*.py          standalone helpers, Python 3.8+ stdlib only
  references/*.md       detail loaded on demand
templates/skill/        copy this to start a new skill
tests/
  test_<skill>.py       one test module per skill
  fixtures/<skill>/     inputs for those tests (ignored by ruff and pytest collection)
tools/validate_skills.py
```

## Write a new skill

1. Open a "New skill proposal" issue first so we can agree on scope.
2. Copy the template:
   ```bash
   cp -r templates/skill skills/my-new-skill
   mv skills/my-new-skill/scripts/your_script.py skills/my-new-skill/scripts/my_check.py
   ```
3. Edit `SKILL.md`:
   - `name` equals the folder name: lowercase letters, digits, single hyphens, max 64 chars.
   - `description` (max 1024 chars) says **what** it does with concrete keywords and **when**
     to use it, starting the second part with "Use when ...". This text decides whether
     the agent picks the skill, so list the phrases users actually type.
   - Required sections: `## When to use`, `## When not to use`, `## Workflow`, `## Output`.
   - Workflow steps are imperative and numbered, with exact commands, decision points and
     the point where the agent must ask before changing CI, running long jobs or
     touching shared environments.
   - Keep it under 400 lines; move tables, runbooks and long configs to `references/`.
4. Write the script: `argparse` with a useful `--help`, `--json` output, exit codes
   0 (ok) / 1 (findings) / 2 (error), read-only by default, no network unless that is the
   skill's purpose (then opt-in and only to hosts the user passes). Prefer reading the
   reports tools already write (JUnit XML, Cobertura, LCOV, HAR, JSON) over running tools.
5. Add `tests/test_my_new_skill.py` and fixtures in `tests/fixtures/my-new-skill/`. Cover
   a "bad" input, a "good" input that produces no findings, edge cases and the CLI exit codes.
6. Add the skill to `.claude-plugin/marketplace.json` (`plugins[0].skills`), the README
   skills table, the table in `AGENTS.md` and `CHANGELOG.md` under "Unreleased".
7. Run the validator, ruff and pytest.

## Quality bar

- **Evidence over opinion.** If a step is "parse this report and find X", write a script
  and test it rather than relying on the model reading a 5,000-line XML file.
- **Stack-accurate.** Commands and APIs must match current versions of the tools
  (pytest 8, Vitest 3+, Jest 29+, PHPUnit 10+, Playwright 1.4x+). Note version
  differences instead of guessing; link the official docs.
- **Safe by default.** Scripts never modify source files; generators refuse to overwrite.
  Workflows ask before editing CI or running long or costly jobs.
- **Realistic fixtures.** Redact real reports: `example.com`/`example.test` domains, fake
  names, no tokens or cookies (HAR files!), no customer data.
- **Low false positives.** If a check is often wrong, lower its severity or drop it, and
  document known false positives in the skill's references.

## Pull request process

1. Fork, create a branch, make focused commits.
2. Make sure CI passes locally (validator, ruff, pytest).
3. Fill in the pull request template.
4. A maintainer reviews within a few days. Small, focused pull requests are merged fastest.

By contributing you agree that your contributions are licensed under the MIT License.
