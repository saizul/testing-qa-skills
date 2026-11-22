---
name: api-contract-testing
description: Check that an API's real responses match its OpenAPI 3.0/3.1 contract - a script validates recorded responses (HAR files, JSON Lines, or a single body) against the response schemas, reporting schema violations with JSON paths, undocumented paths, methods and status codes, and which documented responses were exercised; plus recipes for contract tests in pytest, Vitest/Jest and PHPUnit, Schemathesis property-based testing, consumer-driven contracts (Pact) and breaking-change rules. Use when the user wants contract tests, asks whether the API matches the OpenAPI spec or swagger, sees clients break after a backend change, wants to validate responses against a schema, or record and check API traffic.
license: MIT
compatibility: Python 3.8+ (standard library). YAML specs need PyYAML (or convert to JSON). Only local $ref; bundle multi-file specs first.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# API contract testing

The OpenAPI document is a promise to clients. Contract tests check the implementation
keeps it: every response a client can get has the documented status, content type and
shape. They run fast and catch breaking changes before consumers do.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Does our API match the OpenAPI spec?", "add contract tests for the users endpoints"
- A frontend/mobile client broke after a backend deploy
- Validating recorded traffic (HAR from the browser, Playwright, a proxy) against the spec
- Setting up Schemathesis or Pact, or reviewing a spec change for breaking changes

## When not to use

- Business logic correctness behind the endpoint: unit/integration tests
- Load or latency testing
- Designing a new API from scratch (contract testing assumes a spec exists)

## Workflow

1. **Locate the contract and its version.** Find `openapi.yaml|json` (or the generated
   one: FastAPI `/openapi.json`, NestJS Swagger, `l5-swagger`/Scribe in Laravel,
   springdoc). Note `openapi: 3.0.x` vs `3.1.x` (nullable vs `type: [.., "null"]`). If it
   is split across files, bundle it first (`npx @redocly/cli bundle openapi.yaml -o openapi.json`).
   Swagger 2.0 must be converted to 3.x first.
2. **Get real responses** without touching production data:
   - Run the API locally or in a test environment and record a HAR: Playwright
     `recordHar` / `page.routeFromHAR(..., { update: true })`, browser devtools "Save all as
     HAR", or a proxy.
   - Or write JSON Lines from existing integration tests: one object per response
     `{"method","path","status","body","content_type"}`.
   HAR files can contain cookies and tokens: keep them out of git and out of chat.
3. **Validate**:
   ```bash
   python3 scripts/validate_responses.py --spec openapi.json --har session.har
   python3 scripts/validate_responses.py --spec openapi.yaml --jsonl responses.jsonl --json
   python3 scripts/validate_responses.py --spec openapi.json --body user.json \
       --method GET --path /v1/users/42 --status 200
   ```
   Useful flags: `--only /api/` (ignore assets in a HAR), `--strict-additional` (treat
   objects without `additionalProperties` as closed, catches undocumented fields),
   `--no-formats`, `--allow-undocumented`. The server URL path (e.g. `/v1`) is stripped
   automatically. Exit 1 on any violation.
4. **Triage each finding**: is the spec wrong or the implementation wrong? Typical
   causes and fixes are in [references/violations.md](references/violations.md). Fix the
   code when clients rely on the documented shape; fix the spec when the code is right
   and clients already depend on the actual behaviour (and treat it as a contract change).
5. **Make it permanent** with contract tests in the project's test suite:
   [references/contract-tests.md](references/contract-tests.md) has pytest (jsonschema /
   openapi-core / Schemathesis), Vitest/Jest (ajv, jest-openapi) and PHPUnit
   (league/openapi-psr7-validator, Spectator) recipes, and a Pact outline for
   consumer-driven contracts between teams.
6. **Guard the spec itself** against breaking changes in PRs (removed fields, new required
   request fields, narrowed enums, removed status codes): rules in
   [references/breaking-changes.md](references/breaking-changes.md).

## Decision points

- **Undocumented status (500, 401, 429)**: document error responses (or a `default`
  error schema) so clients can handle them; a 500 in recorded traffic is also a bug.
- **Undocumented field in a response**: harmless for most clients, but a leak risk (for
  example `password_hash`). Run with `--strict-additional` on sensitive resources.
- **`oneOf` matches 0 or 2 schemas**: the schemas overlap or a discriminator is missing.
  Fix the spec; validators and generated clients disagree on overlapping `oneOf`.
- **Formats** (`date-time`, `email`, `uuid`) are checked by default; generated clients
  often parse them, so a wrong format is a real break.

## Output

```
9 responses checked: ok 4, fail 2, undocumented-path 1, undocumented-method 1, undocumented-status 1
6/7 documented responses exercised (not exercised: POST /users 201)
FAIL GET /users/{id} -> 200
  $.role: 'owner' is not one of ['admin', 'member']   -> enum missing value; spec or code?
  $.password: writeOnly property returned in a response -> security: remove from serializer
Undocumented: GET /orders (path), PATCH /users/{id} (method), GET /users/{id} -> 500
Next: fix serializer, add 'owner' to the enum after checking clients, add default error schema
```
