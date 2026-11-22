# Generating coverage reports

The script reads Cobertura XML, LCOV, Clover XML and coverage.py JSON.

## Python (coverage.py / pytest-cov)

```bash
pip install pytest-cov
pytest --cov=src --cov-branch --cov-report=xml:coverage.xml      # Cobertura
# or coverage.py directly
coverage run --source=src -m pytest && coverage xml -o coverage.xml
coverage json -o coverage.json                                    # JSON also works
```

`--cov=src` (or `[tool.coverage.run] source = ["src"]`) makes files that no test imports
appear with 0%, instead of being absent.

## Vitest

```ts
// vitest.config.ts
export default defineConfig({
  test: {
    coverage: {
      provider: 'v8',                       // npm i -D @vitest/coverage-v8
      reporter: ['text', 'lcov', 'cobertura'],
      include: ['src/**/*.{ts,tsx}'],       // report untested files too
    },
  },
});
```

```bash
npx vitest run --coverage        # writes coverage/lcov.info and coverage/cobertura-coverage.xml
```

## Jest

```bash
npx jest --coverage --coverageReporters=lcov --coverageReporters=cobertura \
  --collectCoverageFrom='src/**/*.{js,ts,tsx}'
# coverage/lcov.info, coverage/cobertura-coverage.xml
```

## c8 / nyc (any Node test runner)

```bash
npx c8 --reporter=lcov --all --src src node --test
npx nyc --reporter=cobertura --all mocha
```

## PHPUnit

Needs a coverage driver: PCOV (fast, line coverage) or Xdebug (`XDEBUG_MODE=coverage`).

```xml
<!-- phpunit.xml: list source so untested files appear -->
<source>
  <include><directory>src</directory></include>
</source>
```

```bash
XDEBUG_MODE=coverage vendor/bin/phpunit --coverage-cobertura coverage.xml
vendor/bin/phpunit --coverage-clover clover.xml
```

Older PHPUnit (< 9.4) has no Cobertura output: use `--coverage-clover`.

## Go

```bash
go test ./... -coverprofile=cover.out
go install github.com/boumenot/gocover-cobertura@latest
gocover-cobertura < cover.out > coverage.xml
```

## Java / Kotlin

JaCoCo XML is not Cobertura. Convert with a JaCoCo-to-Cobertura converter, or use the
LCOV/Cobertura output of your build plugin if available.

## .NET

```bash
dotnet test --collect:"XPlat Code Coverage"     # coverlet writes coverage.cobertura.xml
```

## Monorepos and merged reports

Run the script once per package with that package's report and `--include` for its
paths, or merge reports first (`lcov -a a.info -a b.info -o all.info`,
`coverage combine`, `reportgenerator -reporttypes:Cobertura`).
