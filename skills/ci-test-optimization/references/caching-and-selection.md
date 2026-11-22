# Caching and test selection

## Dependency caches (GitHub Actions)

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: "3.12"
    cache: pip                              # or: pipenv, poetry
    cache-dependency-path: requirements*.txt

- uses: actions/setup-node@v4
  with:
    node-version: 22
    cache: npm                              # or pnpm / yarn (lockfile-keyed)

- name: Composer cache
  uses: actions/cache@v4
  with:
    path: ~/.cache/composer
    key: composer-${{ runner.os }}-${{ hashFiles('composer.lock') }}
    restore-keys: composer-${{ runner.os }}-

- name: Playwright browsers
  uses: actions/cache@v4
  id: pw-cache
  with:
    path: ~/.cache/ms-playwright
    key: pw-${{ runner.os }}-${{ hashFiles('package-lock.json') }}
- run: npx playwright install --with-deps chromium
  if: steps.pw-cache.outputs.cache-hit != 'true'
- run: npx playwright install-deps chromium
  if: steps.pw-cache.outputs.cache-hit == 'true'
```

uv: `astral-sh/setup-uv` with `enable-cache: true`. Pin action versions to what the
repository already uses.

## GitLab CI

```yaml
default:
  cache:
    key:
      files: [package-lock.json]
    paths: [.npm/]
  before_script:
    - npm ci --cache .npm --prefer-offline
```

## Tool caches worth keeping

- `.pytest_cache` is small and mostly for `--lf`; not useful in CI.
- Jest `cacheDirectory` / Vitest's cache: modest gains for transforms on big TS codebases.
- Type-check and lint caches (`.ruff_cache`, `.eslintcache`, `tsc --incremental` buildinfo).
- Docker layer cache for service images you build (`cache-from: type=gha`).

## Build once, test many

Build in one job, upload the artifact (`actions/upload-artifact`), download it in each
test shard. Never rebuild per shard.

## Running only affected tests on PRs

| Tool | Command |
| --- | --- |
| Vitest | `vitest run --changed origin/main` (uses the module graph) |
| Jest | `jest --changedSince=origin/main` |
| Playwright | `playwright test --only-changed=origin/main` (recent versions) |
| pytest | `pytest-testmon` (`--testmon`, needs its data file cached), or path-based selection |
| Monorepos | `nx affected -t test`, `turbo run test --filter=...[origin/main]`, Bazel |
| Any | CI path filters: run the backend suite only if `backend/**` changed |

Always keep a full run on the main branch (and nightly), because selection can miss
dependencies (config files, fixtures, dynamic imports).

## Order for fast feedback

1. Lint, format, type-check (seconds to a minute)
2. Unit tests (parallel)
3. Integration tests (services)
4. e2e (sharded), visual, performance

Use `needs:` so expensive stages do not start when cheap ones fail, unless the team
prefers the full signal on every run.
