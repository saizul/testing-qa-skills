# Risk heuristics

## Where bugs hide: area checklist

Walk this list against the feature and keep the areas that apply.

| Area | Ask |
| --- | --- |
| Input and validation | What can users type, paste, upload? Empty, huge, unicode, emoji, RTL, leading zeros, injection strings? |
| Output and formatting | Money, dates, time zones, locales, rounding, truncation, pluralisation |
| Money | Totals, tax, currency conversion, refunds, partial payments, double charge, idempotency keys |
| Auth and permissions | Who can see/do this? Other tenant's data (IDOR)? Expired session? Role changes mid-session? |
| State and lifecycle | Valid transitions, back button, refresh, resubmit, cancel half-way, retries |
| Data | Migrations, backfills, nullable columns, existing rows that violate new rules, deletes and cascades |
| Integrations | Third-party API down, slow, 429, changed schema, webhooks out of order or duplicated |
| Concurrency | Two tabs, two users, double click, race between job and request, locks |
| Async work | Queues, cron, emails: delivered once? retried? what if the worker crashes mid-way? |
| Configuration | Feature flags on/off/partial, env vars missing, defaults |
| Compatibility | Browsers, mobile viewports, API clients on old versions, backwards-compatible responses |
| Performance | N+1 queries, large lists, pagination, cold caches, timeouts |
| Security | Secrets in logs, CSRF, XSS, SSRF via URLs, file upload types, rate limits |
| Accessibility | Keyboard only, screen reader labels, focus order, colour contrast, error announcements |
| Observability | Will we know it broke? Logs, metrics, alerts, dashboards |

## Impact scale (worst realistic consequence)

| Score | Meaning |
| --- | --- |
| 5 | Money lost or charged wrongly, data loss or leak, security breach, legal/compliance breach, total outage |
| 4 | Core journey blocked for many users; workaround is hard; support load spikes |
| 3 | Feature degraded for some users; workaround exists |
| 2 | Cosmetic or minor inconvenience on a secondary path |
| 1 | Barely noticeable; internal only |

Impact factors for the script (`impact_factors`, impact = max): `users`, `money`, `data`,
`security`, `legal`, `reputation`, `operations`.

## Likelihood scale

| Score | Meaning |
| --- | --- |
| 5 | New, complex code with many branches, new dependency or team new to the area; history of defects |
| 4 | Significant change to existing complex code, or a new integration |
| 3 | Moderate change; some edge cases; partially covered by existing tests |
| 2 | Small change in well-tested code |
| 1 | Trivial or config-only change with strong existing tests |

Likelihood factors (`likelihood_factors`, likelihood = rounded mean): `complexity`,
`change`, `history`, `dependencies`, `novelty`, `usage`, `team`.

## Level -> depth

| Risk (I x L) | Level | Depth |
| --- | --- | --- |
| 15-25 | high | Unit + integration + e2e for the journey, negative paths, exploratory session, monitoring/alert, run on every PR |
| 8-14 | medium | Unit + integration for main paths and boundaries; e2e only if it is a user journey |
| 1-7 | low | Unit tests or a checklist item |

## Choosing the lowest useful level

- Pure logic (pricing, validation, parsing): unit tests, table-driven, many boundaries.
- Code + database / queue / filesystem: integration tests against real instances
  (containers) rather than mocks of your own persistence layer.
- Service-to-service: contract tests (schema validation, consumer-driven contracts).
- Cross-component user journey: a few e2e tests, happy path + the most expensive failure.
- Things automation cannot judge (copy, layout feel, new UX): timed exploratory sessions
  with a charter ("Explore guest checkout with slow 3G and a declined card to discover
  confusing error states").

## Test design techniques (pick per area)

- **Equivalence partitions + boundaries**: for every numeric/length/date input.
- **Decision tables**: for rules with several conditions (discount = member AND total > 100 OR coupon).
- **State transition**: for lifecycles (order: created -> paid -> shipped -> refunded).
- **Pairwise**: for many independent options (browser x locale x payment method).
- **Error guessing / past incidents**: read the last incidents and bug tickets for the area.
