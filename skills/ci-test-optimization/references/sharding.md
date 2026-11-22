# Sharding across CI jobs

## Timing-balanced shards with shard_plan.py (GitHub Actions)

Keep timings from the latest successful run on main as an artifact or in the cache, and
plan each shard from them. Copy `scripts/shard_plan.py` into the repository
(for example `tools/shard_plan.py`).

```yaml
jobs:
  tests:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        shard: [1, 2, 3, 4]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: pip install -r requirements-dev.txt
      - name: Restore timings from main
        uses: actions/cache/restore@v4
        with:
          path: timings
          key: junit-timings-${{ github.run_id }}
          restore-keys: junit-timings-
      - name: Run shard
        run: |
          git ls-files 'tests/**/test_*.py' 'tests/test_*.py' > all-tests.txt
          if ls timings/*.xml >/dev/null 2>&1; then
            python3 tools/shard_plan.py timings/*.xml --items all-tests.txt \
              --shards 4 --shard ${{ matrix.shard }} --format lines > shard.txt
          else
            # no timings yet: round-robin by file
            awk 'NR % 4 == ${{ matrix.shard }} % 4' all-tests.txt > shard.txt
          fi
          pytest -o junit_family=xunit1 --junitxml=junit-${{ matrix.shard }}.xml $(cat shard.txt)
      - uses: actions/upload-artifact@v4
        if: always()
        with: { name: junit-${{ matrix.shard }}, path: junit-${{ matrix.shard }}.xml }

  save-timings:
    if: github.ref == 'refs/heads/main' && !cancelled()
    needs: tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
        with: { pattern: junit-*, path: timings, merge-multiple: true }
      - uses: actions/cache/save@v4
        with:
          path: timings
          key: junit-timings-${{ github.run_id }}
```

Notes:

- `-o junit_family=xunit1` makes pytest write a `file` attribute so items are file
  paths. Without it, use `--by class` and run by node id, or map classnames to files.
- Jest: `jest-junit` with `addFileAttribute: "true"`; run `npx jest $(cat shard.txt)`.
- Vitest: JUnit reporter output contains the file in the suite name/classname; check a
  report and use `--by class` if there is no `file` attribute.
- PHPUnit: JUnit has `file` on testcases; run with `vendor/bin/phpunit $(cat shard.txt)`
  only if your PHPUnit version accepts several paths, otherwise generate a temporary
  `phpunit.xml` with a `<testsuite>` of `<file>` entries.
- Playwright: prefer its built-in `--shard=i/n` plus blob report merging unless shards
  are badly unbalanced.

## Runner-native sharding (count-based)

```bash
npx playwright test --shard=2/4
npx vitest run --shard=2/4
npx jest --shard=2/4
pytest --splits 4 --group 2        # pytest-split (uses its own .test_durations file)
```

pytest-split and Knapsack-style tools also balance by duration; `shard_plan.py` is a
dependency-free alternative that works for any runner producing JUnit XML.

## GitLab CI

```yaml
tests:
  parallel: 4
  script:
    - python3 tools/shard_plan.py timings/*.xml --items all-tests.txt --shards "$CI_NODE_TOTAL" --shard "$CI_NODE_INDEX" --format lines > shard.txt
    - pytest $(cat shard.txt) --junitxml=junit.xml
  artifacts:
    reports:
      junit: junit.xml
```

## How many shards?

`--target-minutes M --overhead-seconds S` returns the smallest shard count whose longest
shard plus per-shard setup fits M minutes, or tells you the slowest single item makes the
target unreachable (split that file first). Beyond that point each extra shard only adds
setup minutes and cost.
