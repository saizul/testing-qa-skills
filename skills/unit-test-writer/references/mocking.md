# Mocking at boundaries

## Vocabulary

| Double | What it does | Use for |
| --- | --- | --- |
| Dummy | Fills a parameter, never used | Required constructor args |
| Stub | Returns canned answers | Rates provider, feature flags, config |
| Fake | Working lightweight implementation | In-memory repository, fake clock, local S3 (MinIO) |
| Spy | Records calls for later assertions | Logger, event bus |
| Mock | Pre-programmed expectations that fail the test | Outgoing commands: send email, charge card |

Rule: **stub queries, mock commands**. Assert that a command was sent across a boundary
(email sent, payment charged); do not assert that a query was called (just stub its answer).

## Where the boundaries are

Replace these:

- Network: HTTP APIs, SMTP, payment gateways, cloud SDKs (use MSW/responses/respx/Http::fake)
- Time: `now()`, timers, sleeps (fake timers, injected clock, freezegun, Carbon::setTestNow)
- Randomness and ids: random, UUIDs, tokens (inject a seeded generator or a sequence)
- Process environment: env vars, CLI args, current directory
- Filesystem outside a temporary directory
- Slow or non-deterministic subprocesses

Keep these real:

- The unit's own helpers, value objects, DTOs, pure functions
- Data structures and the standard library
- Your own database layer in integration tests: use a real database in a container
  (Testcontainers, docker compose service, SQLite only if production is SQLite)

## Smells

- Mock returns a mock returns a mock: the code under test knows too much; introduce a
  port/interface and fake it.
- Asserting call order or exact call counts of internal collaborators: couples the test
  to implementation; assert on the result instead.
- Patching the wrong import path in Python (`patch("requests.post")` when the module did
  `from requests import post`): patch `"mymodule.post"`.
- Mocking types you do not own deep inside your code: wrap the SDK in a thin adapter,
  test the adapter with an integration/contract test, fake the adapter elsewhere.
- Snapshot of a mock's calls: brittle; check the one argument that matters.

## Making code testable (suggest these refactors)

- Pass dependencies in (constructor/function parameter) instead of importing singletons.
- Accept a `clock` / `now` function and a `rng` parameter with production defaults.
- Separate pure decision logic from I/O ("functional core, imperative shell"): the core
  gets fast table tests, the shell gets a few integration tests.
