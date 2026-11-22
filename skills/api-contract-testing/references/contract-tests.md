# Contract tests in the test suite

Pattern: call the endpoint in an integration test (real app, test database), then
validate status + body against the operation's response schema from the spec.

## Python

### Schemathesis (property-based, generates requests from the spec)

```bash
pip install schemathesis
schemathesis run http://localhost:8000/openapi.json --checks all     # CLI against a running app
```

```python
# tests/test_contract.py - in-process for ASGI/WSGI apps (FastAPI, Flask)
import schemathesis

from app.main import app

schema = schemathesis.openapi.from_asgi("/openapi.json", app)  # Schemathesis 4.x API


@schema.parametrize()
def test_api_matches_contract(case):
    case.call_and_validate()
```

Schemathesis 3.x used `schemathesis.from_asgi(...)`; check the installed version.
Start with read-only operations or a disposable database: it sends many requests.

### Explicit checks with openapi-core or jsonschema

```python
import json
from pathlib import Path

import jsonschema
import pytest

SPEC = json.loads(Path("openapi.json").read_text())


def response_schema(path: str, method: str, status: str) -> dict:
    schema = SPEC["paths"][path][method]["responses"][status]["content"]["application/json"]["schema"]
    # Keep "components" at the root so "#/components/schemas/..." refs resolve.
    # OpenAPI 3.1 schemas are JSON Schema 2020-12; 3.0 "nullable" needs converting first.
    return {**schema, "components": SPEC.get("components", {})}


def test_get_user_matches_contract(client, user):
    res = client.get(f"/v1/users/{user.id}")
    assert res.status_code == 200
    jsonschema.validate(res.json(), response_schema("/users/{id}", "get", "200"))
```

`openapi-core` validates full request/response pairs (path params, headers, content
type) against the spec and supports 3.0 and 3.1: prefer it for thorough checks.

## TypeScript / JavaScript

### Vitest/Jest + ajv

```ts
import Ajv from 'ajv/dist/2020';          // OpenAPI 3.1 = JSON Schema 2020-12; use 'ajv' for 3.0-ish schemas
import addFormats from 'ajv-formats';
import spec from '../openapi.json';

const ajv = new Ajv({ strict: false, allErrors: true });
addFormats(ajv);
ajv.addSchema(spec, 'openapi.json');

it('GET /users/:id matches the contract', async () => {
  const res = await request(app).get('/v1/users/42');          // supertest
  expect(res.status).toBe(200);
  const validate = ajv.getSchema('openapi.json#/components/schemas/User')!;
  expect(validate(res.body), JSON.stringify(validate.errors)).toBe(true);
});
```

Note: OpenAPI 3.0 `nullable` is not JSON Schema; convert 3.0 schemas
(`@openapi-contrib/openapi-schema-to-json-schema`) or use an OpenAPI-aware validator such
as `openapi-response-validator`, `jest-openapi` (`expect(res).toSatisfyApiSpec()`), or
`chai-openapi-response-validator`.

## PHP

### league/openapi-psr7-validator (framework-agnostic, PSR-7)

```php
$validator = (new \League\OpenAPIValidation\PSR7\ValidatorBuilder())
    ->fromYamlFile(__DIR__ . '/../openapi.yaml')
    ->getResponseValidator();
$operation = new \League\OpenAPIValidation\PSR7\OperationAddress('/users/{id}', 'get');
$validator->validate($operation, $psr7Response);   // throws on mismatch
```

### Laravel: hotmeteor/spectator

```php
Spectator::using('openapi.yaml');
$this->getJson('/api/users/1')->assertValidRequest()->assertValidResponse(200);
```

## Consumer-driven contracts (Pact)

Use when several teams own consumers and providers and the spec is not the source of
truth. The consumer writes tests against a Pact mock server, which records the
interactions it relies on into a pact file; the provider verifies those pacts in its CI
(via a Pact Broker / PactFlow), and `can-i-deploy` gates releases. Pact complements the
OpenAPI check above: OpenAPI says what is offered, pacts say what is actually used.

## Recording JSON Lines from your own tests

```python
# conftest.py - append every response made through the test client
import json, os


@pytest.fixture
def client(app_client):
    out = os.environ.get("CONTRACT_LOG")
    if not out:
        yield app_client
        return
    original = app_client.request

    def logged(method, url, *a, **kw):
        res = original(method, url, *a, **kw)
        with open(out, "a") as fh:
            fh.write(
                json.dumps(
                    {
                        "method": method,
                        "path": str(url),
                        "status": res.status_code,
                        "body": res.text,
                        "content_type": res.headers.get("content-type", ""),
                    }
                )
                + "\n"
            )
        return res

    app_client.request = logged
    yield app_client
```

Then `CONTRACT_LOG=responses.jsonl pytest tests/api && python3 scripts/validate_responses.py --spec openapi.json --jsonl responses.jsonl`.
