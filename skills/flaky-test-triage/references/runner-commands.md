# Getting JUnit XML from several runs

Write each run to its own file or directory; pass them to `flaky_report.py` oldest first.

## pytest

```bash
for i in $(seq 1 10); do
  pytest -q -p no:cacheprovider --junitxml="runs/run-$i.xml" || true
done
python3 scripts/flaky_report.py runs/run-*.xml
```

Note the shell glob sorts `run-10` before `run-2`; use `run-01`..`run-10` (`printf -v i '%02d'`)
or list the files explicitly when order matters (it only affects regressed/fixed labels).

Retry plugins: `pytest-rerunfailures` (`--reruns 2`) reports only the final outcome in
JUnit by default, so a flaky test that passed on rerun looks green. Prefer separate runs
for measurement.

## Vitest

```bash
npx vitest run --reporter=junit --outputFile="runs/run-$i.xml"
```

With `retry` configured, Vitest reports the final result; measure with retries off.

## Jest

```bash
npm i -D jest-junit
JEST_JUNIT_OUTPUT_DIR=runs JEST_JUNIT_OUTPUT_NAME="run-$i.xml" npx jest --ci --reporters=default --reporters=jest-junit
```

## PHPUnit

```bash
vendor/bin/phpunit --log-junit "runs/run-$i.xml"
```

## Playwright

```ts
// playwright.config.ts
reporter: [['list'], ['junit', { outputFile: 'test-results/junit.xml' }]],
```

```bash
PLAYWRIGHT_JUNIT_OUTPUT_NAME="runs/run-$i.xml" npx playwright test --reporter=junit --retries=0
```

Playwright's own HTML report and `--reporter=json` also label tests "flaky" when they
pass on retry; the JUnit reporter is what this script reads.

## Maven Surefire / Gradle

Surefire with `-Dsurefire.rerunFailingTestsCount=2` writes `<flakyFailure>` and
`<rerunFailure>` elements into `target/surefire-reports/TEST-*.xml`. One run is enough:

```bash
mvn test -Dsurefire.rerunFailingTestsCount=2
python3 scripts/flaky_report.py target/surefire-reports --run-per-dir --min-runs 1
```

Gradle writes JUnit XML to `build/test-results/test/`. With the test-retry plugin a
retried test is normally listed once per execution (failure, then success); the script
counts a fail-then-pass of the same id within one report as flaky.

## GitHub Actions artifacts

```bash
# list recent runs on main and download their junit artifacts (needs gh auth)
gh run list --branch main --workflow ci.yml --limit 20 --json databaseId -q '.[].databaseId' |
  while read id; do gh run download "$id" --name junit --dir "runs/$id" || true; done
python3 scripts/flaky_report.py runs/* --run-per-dir
```

Downloading artifacts touches your GitHub account: confirm the repository and run count
with the user first.
