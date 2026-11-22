---
name: ci-test-optimization
description: Make CI test runs faster and more trustworthy - measure where time goes, cache dependencies and build outputs, parallelise within a job (pytest-xdist, Vitest/Jest workers, Playwright workers, ParaTest), shard across jobs with a script that balances test files by JUnit XML timings (LPT bin packing, unknown files get the median, suggested shard count for a target wall time), run only affected tests on PRs, fail fast ordering, and a retries/quarantine policy that does not hide flakiness. GitHub Actions and GitLab CI examples. Use when the user says CI is slow, wants to split or shard tests, parallelise a test suite, cache node_modules/pip/composer, set a retry policy, or reduce pipeline minutes.
license: MIT
compatibility: Python 3.8+ (standard library) for the shard planner. CI examples for GitHub Actions and GitLab CI.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# CI test optimization

Fast feedback without lying: cut wall-clock time with measurement, caching, parallelism
and sharding, and keep retries from masking real failures.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "CI takes 25 minutes", "split our tests across 4 runners", "parallelise pytest/Jest"
- Caching dependencies, browsers or build outputs between runs
- Deciding a retries policy, or which tests to run on PRs vs nightly
- Shards with very uneven durations

## When not to use

- Individual flaky tests: `flaky-test-triage`
- Making one slow test faster (algorithmic or fixture problem): profile it directly
- Build system migrations (Bazel, Nx, Turborepo adoption) beyond test selection

## Workflow

1. **Measure first.** Get the pipeline timeline (setup, install, build, test, upload)
   from the last 5-10 runs on main, and JUnit XML with per-test times. Quick local
   views: `pytest --durations=25`, `npx vitest run --reporter=verbose`,
   `vendor/bin/phpunit --log-junit junit.xml`. Write down the baseline (p50 and p90 wall
   time) so the result can be compared.
2. **Remove waste before adding machines**, in this order (details in
   [references/caching-and-selection.md](references/caching-and-selection.md)):
   - Cache dependency downloads (pip/uv, npm/pnpm, composer, Playwright browsers) keyed
     by the lockfile.
   - Do not rebuild what did not change (build artifact passed between jobs).
   - Fail fast: lint and unit tests before integration and e2e; `--maxfail`/`-x`/
     `--bail` on PR runs if the team agrees.
   - Run only affected tests on PRs (`vitest --changed`, `jest --changedSince`,
     `nx affected`, path filters), with a full run on main/nightly.
   - Fix the slowest tests: the top 10 often take a third of the time (real sleeps,
     per-test database creation, UI login per test).
3. **Parallelise inside a job** to use all CPU cores of the runner:
   [references/parallelism.md](references/parallelism.md) (pytest-xdist `-n auto`,
   Vitest/Jest workers, Playwright `workers`, ParaTest for PHPUnit). Isolate shared
   resources per worker (databases, ports, temp dirs) or tests will become flaky.
4. **Shard across jobs** when one runner is not enough. Plan balanced shards from timing
   data instead of splitting by file count:
   ```bash
   python3 scripts/shard_plan.py junit/*.xml --shards 4                      # plan + slowest tests
   python3 scripts/shard_plan.py junit/*.xml --shards 4 --target-minutes 8   # how many shards for 8 min?
   python3 scripts/shard_plan.py junit/*.xml --items all-tests.txt --shards 4 --shard 2 --format lines
   python3 scripts/shard_plan.py junit/*.xml --by class --shards 6 --json --max-imbalance 15
   ```
   `--items` lists every current test file (`git ls-files 'tests/**/test_*.py'`) so new
   files with no timing still get scheduled (median duration) and deleted files drop out.
   Report paths may need `--strip-prefix`. Wire it into CI with the matrix examples in
   [references/sharding.md](references/sharding.md); refresh timings from main regularly.
   Runner-native sharding (`playwright --shard`, `vitest --shard`, `jest --shard`) is
   simpler but splits by count, not duration.
5. **Set the retries policy** from [references/retries-policy.md](references/retries-policy.md):
   retries only for e2e, at most 2, always reported, with a quarantine path.
6. **Show the before/after** with the same metric as step 1 and the cost (runner minutes).
   Ask before changing CI configuration files or enabling paid runner sizes.

## Decision points

- **Setup dominates** (install 6 min, tests 2 min): caching and prebuilt images first;
  more shards would multiply the setup cost.
- **One huge test file** sets the floor: `shard_plan.py` reports it as not reachable;
  split the file or shard `--by class`/`--by test`.
- **Parallel runs fail but serial pass**: shared state. Fix isolation, do not drop
  parallelism.
- **Shard count**: each shard pays the setup overhead; use `--overhead-seconds` with
  `--target-minutes` to find the knee instead of guessing.

## Output

```
Baseline: p50 18m40s (install 4m10s, build 2m, tests 12m30s) on main, last 10 runs
Changes:
  1. Cache npm + Playwright browsers (lockfile key): install 4m10s -> 50s
  2. pytest -n auto on 4-core runner: unit 6m -> 1m50s
  3. e2e sharded 4 ways by timing (shard_plan.py, imbalance 6%): 6m30s -> 1m55s
  4. Retries: e2e only, 2 max, flaky count reported in job summary
Result: p50 7m05s (-62%), runner minutes +18% (4 e2e shards)
```
