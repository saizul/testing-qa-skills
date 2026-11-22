# Tool setup: mutmut, Stryker, Infection

Check the installed version's docs: options move between releases.

## mutmut (Python)

```bash
pip install mutmut
```

```toml
# pyproject.toml
[tool.mutmut]
paths_to_mutate = ["src/shop/pricing.py", "src/shop/permissions/"]
tests_dir = ["tests/unit/"]
# also_copy = ["config/"]        # extra files the tests need in mutmut's sandbox
```

```bash
mutmut run                       # runs in ./mutants; resumable
mutmut results                   # lists mutants with status ("name: survived")
mutmut show shop.pricing.x_discount__mutmut_2     # the diff of one mutant
mutmut browse                    # interactive TUI
mutmut apply <name>              # writes the mutant into your source - only to debug, then git checkout
```

mutmut 3 runs the suite under pytest and needs tests that can run from a copied
source tree (no absolute paths to the repo). Older mutmut 2 has a different CLI
(`--paths-to-mutate`, `mutmut results` grouped output, `mutmut junitxml`); upgrade or
adapt.

## Stryker (JavaScript / TypeScript)

```bash
npm init stryker@latest          # interactive: picks the test runner plugin
```

```js
// stryker.config.mjs
/** @type {import('@stryker-mutator/api/core').PartialStrykerOptions} */
export default {
  testRunner: 'vitest',                 // or 'jest', 'mocha', 'karma', 'command'
  mutate: ['src/pricing/**/*.ts', '!src/**/*.test.ts'],
  coverageAnalysis: 'perTest',
  reporters: ['clear-text', 'progress', 'html', 'json'],   // json -> reports/mutation/mutation.json
  incremental: true,                    // reuse results for unchanged code (reports/stryker-incremental.json)
  thresholds: { high: 80, low: 60, break: 50 },            // break: exit non-zero below 50
  timeoutMS: 10000,
  concurrency: 4,
};
```

```bash
npx stryker run
npx stryker run --mutate "src/pricing/discount.ts"       # one file
```

Disable a mutant in code: `// Stryker disable next-line EqualityOperator: boundary is irrelevant here`.
Stryker.NET (`dotnet stryker`) and Stryker4s share the report format.

## Infection (PHP)

```bash
composer require --dev infection/infection
```

```json5
// infection.json5
{
  "$schema": "vendor/infection/infection/resources/schema.json",
  "source": { "directories": ["src"], "excludes": ["Migrations"] },
  "logs": {
    "text": "infection.log",
    "html": "infection.html",
    "json": "infection-log.json",
    "summary": "summary.log"
  },
  "mutators": { "@default": true },
  "minMsi": 60,
  "minCoveredMsi": 80,
  "timeout": 10
}
```

```bash
XDEBUG_MODE=coverage vendor/bin/infection --threads=max
vendor/bin/infection --git-diff-filter=AM --git-diff-base=origin/main --threads=max   # changed code only
vendor/bin/infection --filter=src/Pricing --show-mutations
```

Infection reports MSI (all mutants) and Covered Code MSI (only covered mutants).
`minMsi`/`minCoveredMsi` fail the run below the threshold. Ignore a mutator per
location with the `ignore` list inside a mutator's config, or `@infection-ignore-all`
in a doc comment.

## Other ecosystems

- Java: PIT (pitest), Maven/Gradle plugins, `--withHistory` for incremental.
- Go: go-mutesting / gremlins. Rust: cargo-mutants. Ruby: mutant.
- Kotlin/Scala/C#: PIT, Stryker4s, Stryker.NET.
