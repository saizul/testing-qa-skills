# Mutation testing in CI

Full runs are slow. Use a layered approach.

| When | Scope | Gate |
| --- | --- | --- |
| Pull request | files changed in the PR | survivors listed in the job summary; optional gate on changed-code score |
| Nightly / weekly | critical modules or everything | score must not drop below the stored baseline (ratchet) |
| Before a release of a critical module | that module | agreed minimum (e.g. 75%) |

## Changed files only

```bash
# Stryker
npx stryker run --mutate "$(git diff --name-only origin/main...HEAD -- 'src/**/*.ts' | grep -v '\.test\.' | paste -sd, -)"
# Stryker incremental (reuses earlier results; cache reports/stryker-incremental.json between runs)
npx stryker run --incremental

# Infection
vendor/bin/infection --git-diff-lines --git-diff-base=origin/main --threads=max --min-covered-msi=80

# mutmut: restrict paths_to_mutate to changed files (generate the config in the job)
```

## GitHub Actions sketch

```yaml
  mutation:
    if: github.event_name == 'schedule' || contains(github.event.pull_request.labels.*.name, 'mutation')
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - run: npm ci
      - run: npx stryker run
      - run: python3 tools/mutation_report.py reports/mutation/mutation.json --min-score 70 >> "$GITHUB_STEP_SUMMARY"
      - uses: actions/upload-artifact@v4
        if: always()
        with: { name: mutation-report, path: reports/mutation }
```

Pin action versions to what the repository already uses, and copy
`scripts/mutation_report.py` from this skill into the repository (`tools/`).

## Ratchet instead of a fixed threshold

Store the last score per module (artifact or a committed `mutation-baseline.json`) and
fail only when the new score is lower by more than ~1 point (noise from timeouts).
Raise the baseline when the score improves.
