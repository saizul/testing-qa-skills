# Triage: which coverage gaps deserve tests

Rank each uncovered range by what it does, not by how many lines it has.

| Kind of code | Example | Action |
| --- | --- | --- |
| Business rules with branches | discounts, permissions, state transitions, validation | **Test now** (unit, table-driven, boundaries) |
| Error handling and recovery | retry on 429, rollback, fallback, timeout path | **Test now** (stub the failing dependency) |
| Security-relevant | auth checks, input sanitising, access to other tenants | **Test now**, including the negative case |
| Data transformation | mapping API -> domain, serialisation, money formatting | Test (unit or contract) |
| Glue / wiring | controller calling a service, DI setup | Covered by one integration or e2e test; do not unit test each line |
| Logging, metrics, debug output | `logger.info(...)` | Accept |
| Generated code, migrations, vendored files | protobuf stubs, ORM migrations | Exclude in config |
| Defensive "cannot happen" branches | `else: raise AssertionError` | Accept, or test if cheap |
| Dead code | unreachable after the change | Delete it |

## Questions to ask per gap

1. If this line had a bug, who would notice and when? (customer, alert, never)
2. Is there a cheaper level to test it? (a pure function extracted from a handler)
3. Is it uncovered because it is hard to reach (needs a seam), or just forgotten?
4. Is it covered by e2e/integration tests that were not part of this coverage run?
   (Coverage from different suites can be merged; otherwise say so.)

## Typical thresholds

- Diff coverage gate: 80% for application code, 90%+ for libraries and money/security
  modules. 100% gates encourage assertion-free tests.
- No global-percentage gate on legacy code; ratchet instead (fail only if it decreases).
- Pair the gate with mutation testing on critical modules to check the tests assert things.
