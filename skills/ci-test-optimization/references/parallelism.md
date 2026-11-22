# Parallelism inside one job

Check the runner's cores first with `nproc` in a CI step: hosted runner sizes differ
between public and private repositories and between plans.

## pytest-xdist

```bash
pip install pytest-xdist
pytest -n auto                    # one worker per CPU
pytest -n 4 --dist loadfile       # keep tests of a file on one worker (shared module fixtures)
pytest -n 4 --dist loadgroup      # @pytest.mark.xdist_group("db") tests run on the same worker
```

Per-worker isolation:

```python
@pytest.fixture(scope="session")
def database_url(worker_id):  # "gw0", "gw1", ... or "master" without xdist
    name = f"app_test_{worker_id}"
    create_database(name)
    yield f"postgresql://localhost/{name}"
    drop_database(name)
```

pytest-django creates `test_<db>_gw0` etc. automatically.

## Vitest

```ts
// vitest.config.ts
test: {
  pool: 'threads',                  // or 'forks' (default in recent versions; safer for native modules)
  maxWorkers: 4,
  fileParallelism: true,            // files in parallel; tests within a file run sequentially unless concurrent
}
```

`process.env.VITEST_POOL_ID` identifies the worker for resource isolation.

## Jest

```bash
npx jest --maxWorkers=50%         # CI default is cores-1; on 2-core runners try --maxWorkers=2
npx jest --runInBand              # serial, for debugging shared-state issues
```

`process.env.JEST_WORKER_ID` (1-based) for per-worker resources.

## Playwright

```ts
fullyParallel: true,              // tests within a file in parallel too
workers: process.env.CI ? 4 : undefined,
```

Each worker gets `testInfo.workerIndex` / `testInfo.parallelIndex`
(`TEST_PARALLEL_INDEX` env) for per-worker accounts and data.

## PHPUnit: ParaTest

```bash
composer require --dev brianium/paratest
vendor/bin/paratest --processes=4
vendor/bin/paratest --processes=4 --functional     # parallel per test method
```

Laravel: `php artisan test --parallel` (ParaTest underneath, creates a database per
process with `_test_1`, `_test_2` suffixes).

## Go, Java

`go test -p 4 ./...` (packages) and `t.Parallel()` (tests); Maven Surefire
`-T 1C` / `forkCount`, Gradle `maxParallelForks`.

## Why parallel runs break

Shared database rows, fixed ports, shared temp files, global singletons, tests that
assume order. Fix with per-worker namespacing, `port 0`, `tmp_path`, and the checklist in
the `flaky-test-triage` skill.
