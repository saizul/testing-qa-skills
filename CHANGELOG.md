# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-22

### Added

- `test-plan-writer`: risk-based test plan workflow, risk heuristics, plan template and
  `risk_matrix.py` (impact x likelihood scoring from JSON/CSV, Markdown table, gap check).
- `unit-test-writer`: pytest/unittest, Vitest/Jest and PHPUnit recipes, mocking at
  boundaries, and `lint_tests.py` (no-assertion tests, focused tests, sleeps, constant
  assertions, swallowed exceptions, broad exception expectations, skips without reason).
- `flaky-test-triage`: `flaky_report.py` ranks flaky, regressed, fixed and broken tests
  from JUnit XML of many runs (incl. Surefire flakyFailure and retried duplicates), with
  failure signatures and cause hints; root-cause checklist and quarantine policy.
- `coverage-gap-analysis`: `coverage_gaps.py` diff coverage from Cobertura, LCOV, Clover
  and coverage.py JSON with a git diff or `--base` ref; CI gate recipes.
- `playwright-e2e`: locator, auth (storageState), fixtures/mocks, debugging and CI
  references, and `spec_lint.py` with 14 rules.
- `api-contract-testing`: `validate_responses.py` validates HAR/JSON Lines responses
  against OpenAPI 3.0/3.1 schemas and reports undocumented operations and statuses;
  contract test recipes and breaking-change rules.
- `test-data-builders`: `make_builder.py` (deterministic builders for Python, TypeScript,
  PHP from a sample JSON) and `nondeterminism_scan.py`.
- `mutation-testing-guide`: mutmut, Stryker and Infection setup, survivor playbook, CI
  strategy, and `mutation_report.py` (Stryker schema, Infection log, mutmut results).
- `ci-test-optimization`: caching, parallelism, sharding and retries references, and
  `shard_plan.py` (timing-balanced shards from JUnit XML).
- Claude Code plugin marketplace manifest, `tools/validate_skills.py`, CI and release workflows.

[Unreleased]: https://github.com/saizul/testing-qa-skills/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/saizul/testing-qa-skills/releases/tag/v0.1.0
