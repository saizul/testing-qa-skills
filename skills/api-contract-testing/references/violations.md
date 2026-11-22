# Triage of contract violations

| Violation | Usual cause | Fix |
| --- | --- | --- |
| `missing required property 'x'` | Serializer omits nulls; field renamed; spec marks an optional field as required | Return `x: null` and mark it nullable, or drop it from `required` |
| `expected string, got null` | Nullable in the database but not in the spec | 3.0: `nullable: true`; 3.1: `type: [string, "null"]` |
| `expected integer, got string` | IDs/decimals serialised as strings (bigints, money) | Pick one: document `type: string` with a format, or change serialisation |
| `is not one of [...]` | New enum value added in code | New enum values can break strict clients: announce or version, then update the spec |
| `is not a valid date-time` | Missing time zone, space instead of `T`, epoch number | Serialise RFC 3339 with offset (`2026-11-21T10:00:00Z`) |
| `property is not allowed` | Extra field with `additionalProperties: false` | Remove the field (check it is not sensitive) or document it |
| `writeOnly property returned` | Password/secret field in a response serializer | Remove it from responses: security bug |
| `matches 2 schemas in oneOf` | Overlapping variants without a discriminator | Add a `discriminator` and a required type field, or use `anyOf` |
| `undocumented-status 500` | Unhandled exception | Fix the bug; document the error shape for real error statuses |
| `undocumented-status 401/403/404/422/429` | Errors never documented | Add them (or `default`) with an error schema (RFC 9457 problem+json) |
| `undocumented-path` | Endpoint missing from the spec, wrong `servers` base path, or a non-API URL in the HAR | Document it, fix `servers`, or filter with `--only /api/` |
| `content type ... is not documented` | `text/html` error page from a proxy, or `application/problem+json` not declared | Declare the content type or fix the proxy |
| `response has no documented content; body not checked` | No schema for that response | Add a schema so the contract can be tested |

## Spec or code?

Ask what current clients do. If generated clients or mobile apps already handle the
actual behaviour, the spec is wrong: update it as a documented change. If clients follow
the spec and would break, the code is wrong. When in doubt, check the git history of both
and ask the API owner.
