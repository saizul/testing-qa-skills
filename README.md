# testing-qa-skills

[![CI](https://github.com/saizul/testing-qa-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/saizul/testing-qa-skills/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/saizul/testing-qa-skills?sort=semver)](https://github.com/saizul/testing-qa-skills/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/saizul/testing-qa-skills?style=social)](https://github.com/saizul/testing-qa-skills/stargazers)

**Agent Skills that help Claude Code and Codex write, fix and speed up your tests - with real evidence instead of guesses.**

Nine skills for the testing work every team repeats: planning what to test, writing unit
and e2e tests, finding flaky tests, closing coverage gaps on a PR, checking an API
against its OpenAPI contract, building deterministic test data, measuring test quality
with mutation testing, and making CI faster. Each skill is a step-by-step workflow plus a
tested, standard-library-only Python script, so the agent works from parsed reports
(JUnit XML, Cobertura, LCOV, HAR, mutation.json) rather than skimming files.

- **Stack-aware.** pytest and unittest, Vitest and Jest, PHPUnit, Playwright, plus
  Stryker, mutmut and Infection. Recipes for GitHub Actions and GitLab CI.
- **Evidence first.** Scripts read the reports your tools already produce and output
  text for humans or `--json` for agents, with exit codes you can use as CI gates.
- **Tested.** 130+ tests with fixtures for every script, run on Python 3.11-3.13 in CI.
- **No dependencies.** Python 3.8+ standard library only (PyYAML optional for YAML
  OpenAPI specs). Copy a script into your repository and run it.
- **Read-only by default.** Scripts never modify your code; generators refuse to
  overwrite files unless you pass `--force`.

## Skills

| Skill | What it does | Try asking |
| --- | --- | --- |
| [test-plan-writer](skills/test-plan-writer/SKILL.md) | Risk areas, impact x likelihood scoring script, test levels per risk, concrete cases, entry/exit criteria, gap check | "Write a test plan for guest checkout with saved cards" |
| [unit-test-writer](skills/unit-test-writer/SKILL.md) | Arrange-act-assert tests for pytest, Vitest/Jest, PHPUnit; fixtures; mocking only at boundaries; linter for assertion-free tests, `.only`, sleeps, swallowed errors | "Add unit tests for `pricing.py`, including the rounding bug from #241" |
| [flaky-test-triage](skills/flaky-test-triage/SKILL.md) | Parses JUnit XML from many runs, ranks flaky / regressed / broken tests with failure signatures and cause hints; root-cause checklist; quarantine policy | "These 12 CI runs have random failures. Which tests are flaky and why?" |
| [coverage-gap-analysis](skills/coverage-gap-analysis/SKILL.md) | Diff coverage from Cobertura, LCOV, Clover or coverage.json + git diff: uncovered changed lines, files no test loads, `--fail-under` gate | "What in this PR is not covered by tests?" |
| [playwright-e2e](skills/playwright-e2e/SKILL.md) | Stable locators, web-first assertions, fixtures, storageState auth, network mocks, trace viewer, CI sharding; spec linter for `waitForTimeout`, missing `await`, XPath | "Write a Playwright test for checkout and log in only once" |
| [api-contract-testing](skills/api-contract-testing/SKILL.md) | Validates HAR / JSON Lines responses against OpenAPI 3.0/3.1 schemas; undocumented paths and statuses; contract test recipes; breaking-change rules | "Does our API actually match openapi.yaml? Here is a HAR" |
| [test-data-builders](skills/test-data-builders/SKILL.md) | Generates deterministic builders (Python, TypeScript, PHP) from a sample JSON; scans for unseeded random, Faker, `Date.now`, `uuid4` | "Create test data builders for Order and stop tests failing on dates" |
| [mutation-testing-guide](skills/mutation-testing-guide/SKILL.md) | When and how to run mutmut, Stryker, Infection; parses their reports into a score per file and surviving mutants; how to kill survivors | "Coverage is 90% but bugs slip through. Set up mutation testing for pricing" |
| [ci-test-optimization](skills/ci-test-optimization/SKILL.md) | Caching, parallelism, affected-tests selection, timing-balanced sharding from JUnit XML, retries policy | "CI takes 25 minutes. Split the tests across 4 runners evenly" |

## Install

### Claude Code: plugin marketplace (recommended)

```text
/plugin marketplace add saizul/testing-qa-skills
/plugin install testing-qa-skills@testing-qa-skills
```

Or from your shell:

```bash
claude plugin marketplace add saizul/testing-qa-skills
claude plugin install testing-qa-skills@testing-qa-skills
```

Plugin skills are namespaced, e.g. `/testing-qa-skills:flaky-test-triage`. Claude also
picks them up automatically when your request matches a skill's description. Update later
with `/plugin marketplace update testing-qa-skills`.

### Claude Code: copy the skills

```bash
git clone https://github.com/saizul/testing-qa-skills.git
# all projects (personal skills)
mkdir -p ~/.claude/skills && cp -r testing-qa-skills/skills/* ~/.claude/skills/
# or just one project
mkdir -p .claude/skills && cp -r testing-qa-skills/skills/playwright-e2e .claude/skills/
```

Each release also has one zip per skill and an all-skills zip under
[Releases](https://github.com/saizul/testing-qa-skills/releases).

### Codex CLI

Codex reads skills from `~/.agents/skills` (all repositories) and `.agents/skills` in a
repository (from the current directory up to the repository root):

```bash
git clone https://github.com/saizul/testing-qa-skills.git
mkdir -p ~/.agents/skills && cp -r testing-qa-skills/skills/* ~/.agents/skills/
# or for one repository
mkdir -p .agents/skills && cp -r testing-qa-skills/skills/unit-test-writer .agents/skills/
```

Codex also ships a `$skill-installer` skill that can install skills from a GitHub
repository; ask it to install from `saizul/testing-qa-skills`. Skill locations and the
installer are described in the [Codex skills documentation](https://developers.openai.com/codex/skills);
check it if your Codex version behaves differently. [AGENTS.md](AGENTS.md) explains how
Codex and other agents should use these skills.

### Any other agent

The skills follow the open [Agent Skills format](https://agentskills.io/specification):
a folder with `SKILL.md` (YAML frontmatter + instructions), `scripts/` and `references/`.
Point your agent at the folder, or run the scripts yourself; every script has `--help`.

## Usage examples

```text
> Our main branch went red 4 times this week and green on rerun. JUnit artifacts are in runs/.
  (flaky-test-triage: ranks 3 flaky tests, groups 5 failures under one "ECONNREFUSED :6379"
   signature, traces it to a Redis container without a health check, proposes the fix and
   a quarantine issue for the one test it cannot fix today.)

> What's untested in this branch? coverage.xml is from `pytest --cov`.
  (coverage-gap-analysis: 62% diff coverage, new_module.py never imported by a test,
   the `subtotal > 100` discount branch never executed; writes the 3 missing tests.)

> Write e2e tests for the refund flow in Playwright.
  (playwright-e2e: reuses the auth setup project, creates the order via API in a fixture,
   mocks the payment provider with page.route, runs --repeat-each 20, spec_lint clean.)
```

Run the scripts directly too:

```bash
python3 skills/flaky-test-triage/scripts/flaky_report.py runs/*/junit.xml --top 10
python3 skills/coverage-gap-analysis/scripts/coverage_gaps.py --coverage coverage.xml --base origin/main --fail-under 80
python3 skills/api-contract-testing/scripts/validate_responses.py --spec openapi.json --har session.har
python3 skills/ci-test-optimization/scripts/shard_plan.py junit/*.xml --shards 4 --shard 1 --format lines
python3 skills/mutation-testing-guide/scripts/mutation_report.py reports/mutation/mutation.json --min-score 70
python3 skills/test-data-builders/scripts/make_builder.py order.json --name Order --lang ts
```

## How skills work

At startup the agent loads only each skill's `name` and `description` (about 100 tokens
each). When your request matches a description, it reads that skill's `SKILL.md`: the
workflow, decision points and output format. Longer material lives in `references/` and is
read only when a step needs it. Scripts run as normal commands, so their output is exact
and repeatable.

```
skills/<skill-name>/
  SKILL.md          frontmatter (name, description) + workflow
  scripts/          standalone Python 3 helpers (stdlib only, --help, --json)
  references/       recipes, checklists, CI snippets
```

## FAQ

**Will the agent edit my CI configuration or run long jobs on its own?**
The skills tell it to ask first before changing CI files, enabling paid runners, running
long mutation-testing jobs or writing to shared test environments. Your agent's own
permission settings still apply on top.

**Does anything leave my machine?**
No. Scripts work offline on files you give them and send no telemetry. The only external
command is `git diff` in `coverage_gaps.py --base`, which is read-only.

**Which languages are covered?**
Python, JavaScript/TypeScript and PHP in depth; the report parsers (JUnit XML, Cobertura,
LCOV, Stryker's mutation-testing schema) also work for Java, Go, .NET and others.

**My HAR file has cookies and tokens in it.**
The validator only reads method, URL, status and response body. Keep HAR files out of git
(the repository `.gitignore` already ignores them at the root) and do not paste them into chat.

**Why not just raise retries?**
Retries hide flakiness and cost minutes. `flaky-test-triage` and `ci-test-optimization`
give a retries policy that keeps the signal visible while you fix root causes.

## Roadmap

Ideas for new skills (great first contributions; see [CONTRIBUTING.md](CONTRIBUTING.md)):

- `snapshot-test-review` - find oversized, unstable or never-updated snapshots (Jest/Vitest, syrupy)
- `accessibility-testing` - axe-core in Playwright/Vitest, WCAG 2.2 checklist, triage of violations
- `load-test-planner` - k6/Locust scenario from an OpenAPI spec with thresholds and ramp profiles
- `test-suite-health` - one report from JUnit XML: slowest, most skipped, never-failing tests
- `property-based-testing` - Hypothesis / fast-check recipes and shrinking explained
- `go-test-writer` - table-driven Go tests, `testing/synctest`, testcontainers-go
- `contract-diff` - OpenAPI breaking-change detector script (complements api-contract-testing)
- `visual-regression` - Playwright screenshots, masking, thresholds, Docker-stable rendering

## Contributing

Contributions are welcome: new checks, new skills, fixes and better docs. Read
[CONTRIBUTING.md](CONTRIBUTING.md) for the skill template, the quality bar and how to run
the validator and tests:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python tools/validate_skills.py && ruff check . && ruff format --check . && pytest
```

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md) and report security issues
privately as described in [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) (c) Saizul Amin
