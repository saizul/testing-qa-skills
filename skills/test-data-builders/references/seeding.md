# Seeding and isolation for integration and e2e tests

## Isolation strategies (best first)

1. **Transaction per test, rolled back**: fastest. pytest-django `db` fixture, Laravel
   `DatabaseTransactions`/`RefreshDatabase`, Rails transactional tests, a custom
   SQLAlchemy fixture with nested transactions. Does not work when the app under test
   runs in another process (e2e): use 2 or 3.
2. **Unique data per test** on a shared database: every row a test creates has a unique
   key from a sequence or the test id; tests never count "all rows".
3. **Database per worker**: `test_db_{worker}` created from a template
   (`CREATE DATABASE test_1 TEMPLATE test_template` in PostgreSQL), or a schema per worker.
4. **Fresh container per CI job**: Testcontainers / docker compose service; seed once.

## Seed layers

| Layer | Contents | Loaded |
| --- | --- | --- |
| Schema | migrations | once per database |
| Reference data | countries, currencies, plans, feature flags | once, read-only in tests |
| Scenario data | users with roles, carts, orders for e2e journeys | per suite or per test via API/fixture |
| Test-local data | what one test asserts on | inside the test (builders) |

Keep scenario seeds small and named (`seed_checkout_scenario()`), idempotent (upsert by
natural key), and deterministic (fixed ids/emails, no `now()`).

## Example: idempotent seed script

```python
# scripts/seed_e2e.py - safe to run repeatedly against a test database only
import os, sys

if not os.environ.get("DATABASE_URL", "").endswith("_test"):
    sys.exit("refusing to seed: DATABASE_URL does not point at a *_test database")

with session() as s:
    s.merge(User(id=1, email="buyer@example.test", role="member"))
    s.merge(User(id=2, email="admin@example.test", role="admin"))
    s.merge(Product(id=10, sku="SKU-1", price="19.99", stock=100))
    s.commit()
```

Guard every seed or cleanup script against running on a non-test database, and ask the
user before running anything that writes to a shared environment.

## e2e data via API

Prefer creating e2e data through the application's API (or a test-only endpoint enabled
only in test environments) inside a Playwright/Cypress fixture, with teardown. It keeps
data valid by construction and avoids coupling tests to table layouts.
