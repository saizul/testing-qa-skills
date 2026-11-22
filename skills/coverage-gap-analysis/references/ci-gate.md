# Diff coverage gate in CI

Copy `scripts/coverage_gaps.py` into the repository (for example `tools/coverage_gaps.py`)
or vendor this skill; it has no dependencies.

## GitHub Actions

```yaml
  coverage-gate:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0                     # the base commit must be available
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements-dev.txt
      - run: pytest --cov=src --cov-report=xml:coverage.xml
      - name: Diff coverage
        run: |
          python3 tools/coverage_gaps.py --coverage coverage.xml \
            --base "origin/${{ github.base_ref }}" --fail-under 80 --fail-on-untested
```

Pin action versions to what your repository already uses.

## GitLab CI

```yaml
coverage-gate:
  stage: test
  script:
    - git fetch origin "$CI_MERGE_REQUEST_TARGET_BRANCH_NAME"
    - npx vitest run --coverage
    - python3 tools/coverage_gaps.py --coverage coverage/lcov.info
        --base "origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME" --fail-under 80
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

## Notes

- `--base X` diffs `X...HEAD` (merge base), so commits that landed on main after the
  branch was cut are not counted against the PR.
- Shallow clones break the merge base: use `fetch-depth: 0` or fetch the base branch.
- Post the text output as a PR comment only if the team wants it; the exit code is the gate.
- Keep the threshold in one place (a CI variable) and raise it gradually.
