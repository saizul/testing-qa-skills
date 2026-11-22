# Test plan template

Copy, delete sections that do not apply, keep it short.

```markdown
# Test plan: <feature>

| | |
| --- | --- |
| Ticket / PR | <links> |
| Owner | <name> |
| Target release | <date or version> |
| Status | draft / reviewed / signed off |

## Scope
- In scope: <behaviours, platforms, user types>
- Out of scope: <explicitly not tested, and why>

## Risk matrix
<paste the table from scripts/risk_matrix.py>

## Test cases

### <Area 1> (high, risk 20)
| ID | Level | Preconditions / input | Expected | Automated? |
| --- | --- | --- | --- | --- |
| PAY-1 | e2e | Guest, cart 2 items, valid Visa test card | Order confirmed, one charge, confirmation email | yes |
| PAY-2 | integration | Gateway returns 3DS challenge, user completes | Payment captured once | yes |
| PAY-3 | integration | Gateway timeout after 30 s | Order pending, no double charge on retry | yes |
| PAY-4 | unit | Amount 0.005 rounding | Rounded half-even to 0.00 / documented rule | yes |
| PAY-5 | exploratory | 30 min charter: declined cards, back button, two tabs | Notes + bugs filed | no |

### <Area 2> (medium, risk 9)
...

## Regression scope
- Existing suites to run: <unit, integration, e2e tags>
- Manual regression: <only what cannot be automated>

## Test data
- Builders/factories: <link> (deterministic; see test-data-builders)
- Accounts and roles needed: <list; never real customer data>
- Third-party sandboxes: <payment test mode, email catcher>

## Environments
- <local, preview per PR, staging>; feature flag state in each

## Entry criteria
- Acceptance criteria agreed; environments and test data ready; build deployed to staging

## Exit criteria
- All high-risk cases pass; medium-risk cases pass or have an accepted, owned exception
- No open P1/P2 defects; diff coverage >= <N>% on changed code
- Flaky tests quarantined with an owner (see flaky-test-triage)

## Rollout and monitoring
- Flag/canary plan, metrics and alerts to watch for <N> days, rollback steps

## Accepted risks and open questions
| Risk / question | Decision | Owner | Date |
| --- | --- | --- | --- |
```

## Given/When/Then for acceptance criteria

```
Given a guest with 2 items in the cart
When they pay with a card that requires 3-D Secure and complete the challenge
Then the order is confirmed, the card is charged once, and a confirmation email is sent
```

Write one scenario per rule, plus the most important failure ("When the challenge is
cancelled, Then no charge is made and the cart is kept").
