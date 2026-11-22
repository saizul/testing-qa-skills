---
name: test-plan-writer
description: Write a risk-based test plan from a feature description, ticket, PRD or pull request - identifies risk areas, scores impact x likelihood with a script, picks test levels (unit, integration, contract, e2e, exploratory, performance, security, accessibility), lists concrete test cases with boundaries and negative paths, entry/exit criteria, test data and environments, and flags high-risk areas with no planned tests. Use when the user asks for a test plan, test strategy, QA plan, test cases or acceptance tests for a feature, "what should we test", "how risky is this change", or wants a release sign-off checklist.
license: MIT
compatibility: Python 3.8+ for the risk scoring script. Works for any stack.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Test plan writer

Turn a feature description into a short, risk-ordered test plan that a team can execute
and review. Depth follows risk: the riskiest areas get the most and earliest testing.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Write a test plan for <feature/ticket/PR>", "what should we test before release?"
- Turning acceptance criteria or a PRD into test cases
- Deciding which test levels a change needs (unit vs integration vs e2e)
- Release readiness / sign-off checklists for a feature

## When not to use

- Writing the test code itself: use `unit-test-writer`, `playwright-e2e` or
  `api-contract-testing` after the plan exists
- Org-wide QA process or tooling selection with no concrete feature in scope
- Load test design in depth (this skill only flags when performance testing is needed)

## Workflow

1. **Gather the inputs.** Read the feature description, acceptance criteria, linked
   designs, the diff or touched modules (if a PR exists), and past incidents in the area.
   Ask at most three clarifying questions, only for gaps that change the plan: who the
   users are, what money/data is involved, what is out of scope, the release date.
2. **List risk areas**, not test cases yet. Walk the checklist in
   [references/risk-heuristics.md](references/risk-heuristics.md): data in/out,
   money, auth and permissions, state transitions, integrations, concurrency, migrations,
   configuration/flags, compatibility, accessibility, observability. Name each area as a
   behaviour ("Card payment with 3-D Secure"), 5-15 areas for a typical feature.
3. **Score each area** 1-5 for impact (worst consequence) and likelihood (complexity,
   amount of change, defect history, dependencies, novelty). Use the scales in
   [references/risk-heuristics.md](references/risk-heuristics.md). State your
   assumptions next to any score you guessed.
4. **Draft the planned test types per area**, then run the scorer to sort and check gaps:
   ```bash
   python3 scripts/risk_matrix.py risks.json            # Markdown table + gaps, exit 1 on gaps
   python3 scripts/risk_matrix.py risks.json --json     # machine-readable
   python3 scripts/risk_matrix.py risks.csv --no-fail   # CSV: name,impact,likelihood,tests,notes
   ```
   Input format is in the script's `--help`. Write `risks.json` to a scratch location
   unless the user wants it committed. Fix every gap the script reports (add tests or
   record an explicit, owned decision to accept the risk).
5. **Write test cases for high and medium areas.** For each: preconditions, steps or the
   input, expected result, level (unit/integration/e2e/manual). Cover the happy path,
   boundaries (0, 1, max, max+1, empty, unicode, time zones), invalid input, permission
   denied, dependency failure (timeout, 500, slow), retries/idempotency, and concurrency
   where relevant. Prefer the lowest level that can catch the bug; reserve e2e for user
   journeys that cross components.
6. **Add the plan sections** from [references/test-plan-template.md](references/test-plan-template.md):
   scope and out of scope, environments, test data (link `test-data-builders`), entry and
   exit criteria, regression scope, who runs exploratory sessions, rollout and monitoring
   (feature flag, canary, alerts to watch).
7. **Review the plan with the user.** Point out the top three risks, assumptions you made
   and anything that needs a decision (accepted risks, missing environments).

## Decision points

- **No acceptance criteria?** Write them first as Given/When/Then and confirm with the user.
- **Tiny change (one function, no UI)?** Skip the full template: give a risk line, the
  unit tests to add and the regression tests to run.
- **Risk 20-25 with no automated path** (third-party UI, hardware): plan a manual script
  plus production monitoring and a rollback plan, and say so.
- **Legal/compliance impact** (payments, PII, accessibility law): mark impact 5 and add
  the specific checks (PCI scope, data retention, WCAG 2.2 AA).

## Output

A Markdown test plan, typically 1-3 pages:

```
# Test plan: Guest checkout with saved cards
Scope: ... Out of scope: ...
## Risk matrix            (table from risk_matrix.py, highest risk first)
## Test cases             (grouped by area; ID, level, steps/input, expected)
## Test data & environments
## Entry / exit criteria   (e.g. exit: all high-risk cases pass, no open P1/P2, diff coverage >= 80%)
## Rollout & monitoring
## Open questions / accepted risks (owner, date)
```

End with a three-line summary: top risks, total cases by level, blockers.
