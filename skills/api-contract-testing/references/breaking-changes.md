# Breaking changes in an OpenAPI document

Review every spec diff in a PR against these rules.

## Breaking for existing clients

Responses (what the server sends):
- Removing a property, or renaming it
- Making a property nullable or optional that was required and non-null
- Changing a property's type or format (`integer` -> `string`, `date` -> `date-time`)
- Adding a value to an enum that clients switch on exhaustively (often breaking for
  generated clients in strongly typed languages; announce it)
- Removing a documented status code that clients handle, or changing the error shape
- Changing the content type

Requests (what the client sends):
- Adding a new required parameter, header or body property
- Removing a parameter or property the server used to accept (clients get 400)
- Narrowing validation: lower `maxLength`, higher `minimum`, smaller enum, new `pattern`
- Changing a path, method, or the meaning of a parameter

Operations:
- Removing an operation or changing its `operationId` (generated clients rename methods)
- Changing auth requirements (`security`)

## Usually safe

- Adding an optional request property or parameter
- Adding a response property (unless clients use strict deserialisation or
  `additionalProperties: false` is part of the contract)
- Adding a new operation or a new documented status code
- Relaxing request validation
- Documentation-only changes (description, examples)

## Tools

- `oasdiff breaking base.yaml head.yaml` (oasdiff) - classifies changes and can fail CI
- `openapi-diff` (OpenAPITools), `@redocly/cli lint` for spec quality
- Compare the generated spec from the base branch with the PR branch when the spec is
  produced by code (FastAPI, NestJS, springdoc)

## Process

1. Make breaking changes additive first: add the new field, deprecate the old
   (`deprecated: true`), migrate clients, remove later.
2. Version only when needed (`/v2` or a media-type version) and keep the old version
   tested until it is retired.
3. Contract tests (validate_responses.py or the in-suite tests) run on every PR, so the
   implementation cannot drift from the updated spec.
