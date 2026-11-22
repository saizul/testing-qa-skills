# Test data patterns

| Pattern | Looks like | Good for | Watch out |
| --- | --- | --- | --- |
| Builder function with overrides | `build_user(role="admin")` | Most unit and integration tests | Keep defaults valid and boring |
| Fluent builder | `aUser().withRole('admin').build()` | Complex objects with invariants, Java/C#/PHP style | More code per field |
| Factory library | factory_boy, fishery, Laravel factories | Persistence, associations, traits/states | Hidden DB writes; slow if every test creates graphs |
| Object mother | `Users.admin()`, `Orders.paidWithRefund()` | Named, reused scenarios | Grows into a god object; keep it small |
| Static fixture files | `fixtures/countries.json` | Large stable reference data | Drift from the schema; hard to see what a test needs |
| Seed scripts | `db:seed --class=DemoSeeder` | e2e/demo environments | Not a substitute for per-test data |

## Defaults that stay deterministic

| Field kind | Default |
| --- | --- |
| id / foreign key | sequence `n` (1, 2, 3...) |
| UUID | `00000000-0000-4000-8000-{n:012d}` or `uuid.UUID(int=n)` |
| email | `user-{n}@example.test` |
| name / free text | `"name {n}"` or a fixed realistic value |
| status / enum | a fixed valid value (`"active"`) |
| money | fixed decimal (`"19.99"`), never float for money in assertions |
| timestamps | `EPOCH + n days`, EPOCH = 2024-01-01T00:00:00Z |
| booleans | the most common real value |
| lists | empty, or one built child |

## Traits / variants

Model common variants as named helpers on top of the builder, not as new defaults:

```python
def build_paid_order(**kw):
    return build_order(status="paid", paid_at="2024-01-02T00:00:00Z", **kw)
```

```ts
export const buildAdmin = (o: Partial<User> = {}) => buildUser({ role: 'admin', ...o });
```

## Associations

- Build children inline by default (`line_items=[build_line_item()]`).
- Let tests pass an existing parent to avoid duplicates: `build_order(customer=alice)`.
- For DB factories, prefer `create` only where persistence is needed and `build`/`make`
  (not saved) for pure unit tests.

## Anti-patterns

- Mystery guest: a test depends on data created far away (global seed, shared fixture
  file) and you cannot see why it passes. Create what the test needs in the test.
- Shared mutable fixtures across tests (module-level dict modified by a test).
- Random data in assertions (`assert order.email == fake.email()`).
- Factories that call external services or send email on create.
