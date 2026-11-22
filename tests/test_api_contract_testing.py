import json

import pytest

from conftest import FIXTURES, load_script, run_script

SKILL = "api-contract-testing"
SCRIPT = "validate_responses.py"
mod = load_script(SKILL, SCRIPT)
D = FIXTURES / SKILL
SPEC = json.loads((D / "openapi.json").read_text())
SPEC31 = json.loads((D / "openapi31.json").read_text())


def check(*args):
    r = run_script(SKILL, SCRIPT, *args, "--json")
    assert r.returncode in (0, 1), r.stderr
    return r.returncode, json.loads(r.stdout)


def test_har_results_and_coverage():
    code, data = check("--spec", str(D / "openapi.json"), "--har", str(D / "session.har"))
    assert code == 1
    assert data["summary"] == {
        "ok": 4,
        "fail": 2,
        "undocumented-path": 1,
        "undocumented-method": 1,
        "undocumented-status": 1,
    }
    assert data["coverage"] == {
        "documented_responses": 7,
        "exercised_responses": 6,
        "not_exercised": ["POST /users 201"],
    }
    bad = next(r for r in data["results"] if r["path"].endswith("/users/7") and r["method"] == "GET")
    assert bad["operation"] == "GET /users/{id}"
    errors = "\n".join(bad["errors"])
    for needle in (
        "$.id: 0 is below the minimum 1",
        "not a valid email",
        "'owner' is not one of",
        "not a valid date-time",
        "$.password: writeOnly property returned",
        "$.extra: property is not allowed",
        "$.tags: items are not unique",
    ):
        assert needle in errors
    # 4XX range response + problem+json with charset parameter
    post = next(r for r in data["results"] if r["method"] == "POST")
    assert post["response_key"] == "4XX" and post["errors"] == ["$: missing required property 'message'"]


def test_literal_path_beats_template():
    compiled = mod.compile_paths(SPEC)
    template, op = mod.find_operation(SPEC, compiled, ["/v1"], "get", "/v1/users/me")
    assert template == "/users/me" and op is not None
    template, _ = mod.find_operation(SPEC, compiled, ["/v1"], "get", "https://api.example.com/v1/users/5?x=1")
    assert template == "/users/{id}"


def test_allow_undocumented_and_only_filter():
    code, data = check(
        "--spec",
        str(D / "openapi.json"),
        "--har",
        str(D / "session.har"),
        "--allow-undocumented",
        "--only",
        "/users/me",
    )
    assert code == 0 and data["summary"] == {"ok": 1}


def test_jsonl_and_body_string():
    code, data = check("--spec", str(D / "openapi.json"), "--jsonl", str(D / "exchanges.jsonl"))
    assert code == 1
    assert data["results"][1]["errors"] == ["$.total: -1 is below the minimum 0"]


def test_single_body_mode():
    args = ["--spec", str(D / "openapi.json"), "--path", "/v1/users/42", "--method", "GET"]
    assert run_script(SKILL, SCRIPT, *args, "--body", str(D / "good-user.json")).returncode == 0
    r = run_script(SKILL, SCRIPT, *args, "--body", str(D / "bad-user.json"))
    assert r.returncode == 1 and "[FAIL] GET /users/{id} -> 200" in r.stdout


def test_openapi_31_keywords():
    args = ["--spec", str(D / "openapi31.json"), "--path", "/items/1"]
    assert run_script(SKILL, SCRIPT, *args, "--body", str(D / "item-good.json")).returncode == 0
    code, data = check(*args, "--body", str(D / "item-bad.json"))
    errors = data["results"][0]["errors"]
    assert "$.id: 'nope' is not a valid uuid" in errors
    assert "$.note: expected null/string, got integer" in errors
    assert "$.price: 0 must be greater than 0" in errors
    assert "$.kind: matches 0 schemas in oneOf (expected exactly 1)" in errors
    assert "$.dims[1]: expected number, got string" in errors
    assert "$.dims: more than maxItems 2" in errors


@pytest.mark.parametrize(
    ("value", "schema", "ok"),
    [
        (5, {"type": "integer", "multipleOf": 5}, True),
        (7, {"type": "integer", "multipleOf": 5}, False),
        (1.5, {"type": "integer"}, False),
        (2.0, {"type": "integer"}, True),
        (True, {"type": "integer"}, False),
        (3, {"type": "number", "minimum": 3, "exclusiveMinimum": True}, False),
        ("ab", {"type": "string", "minLength": 3}, False),
        ("abc", {"type": "string", "pattern": "^a"}, True),
        (None, {"type": "string", "nullable": True}, True),
        (None, {"type": "string"}, False),
        ({"a": 1}, {"type": "object", "maxProperties": 0}, False),
        ({"x-1": 1}, {"type": "object", "patternProperties": {"^x-": {"type": "string"}}}, False),
        ([1, 2], {"type": "array", "minItems": 3}, False),
        ("b", {"anyOf": [{"const": "a"}, {"const": "b"}]}, True),
        ("c", {"not": {"const": "c"}}, False),
        ({"a": 1}, {"allOf": [{"required": ["a"]}, {"required": ["b"]}]}, False),
        ("2026-02-30", {"type": "string", "format": "date"}, False),
        ("2026-11-21T10:00:00+05:30", {"type": "string", "format": "date-time"}, True),
        ("2026-11-21T10:00:00", {"type": "string", "format": "date-time"}, False),
        (2**40, {"type": "integer", "format": "int32"}, False),
        ("[", {"type": "string", "pattern": "("}, True),  # invalid regex in spec is skipped
    ],
)
def test_schema_keywords(value, schema, ok):
    v = mod.Validator({"openapi": "3.0.3"})
    assert (v.validate(value, schema) == []) is ok


def test_strict_additional_and_no_formats():
    v = mod.Validator({"openapi": "3.0.3"}, strict_additional=True, check_formats=False)
    schema = {"type": "object", "properties": {"a": {"type": "string", "format": "email"}}}
    assert v.validate({"a": "x", "b": 1}, schema) == [
        "$.b: property is not allowed (additionalProperties: false)"
    ]


def test_ref_errors():
    v = mod.Validator({"openapi": "3.0.3", "components": {}})
    with pytest.raises(mod.SpecError):
        v.validate(1, {"$ref": "#/components/schemas/Missing"})
    with pytest.raises(mod.SpecError):
        v.validate(1, {"$ref": "other.yaml#/X"})


def test_yaml_spec_if_pyyaml_available(tmp_path):
    body = tmp_path / "ping.json"
    body.write_text('{"ok": "yes"}')
    r = run_script(SKILL, SCRIPT, "--spec", str(D / "openapi.yaml"), "--body", str(body), "--path", "/ping")
    try:
        import yaml  # noqa: F401
    except ImportError:
        assert r.returncode == 2 and "PyYAML" in r.stderr
    else:
        assert r.returncode == 1 and "expected boolean, got string" in r.stdout


def test_input_errors(tmp_path):
    swagger = tmp_path / "swagger.json"
    swagger.write_text('{"swagger": "2.0"}')
    assert run_script(SKILL, SCRIPT, "--spec", str(swagger), "--har", str(D / "session.har")).returncode == 2
    assert (
        run_script(
            SKILL, SCRIPT, "--spec", str(D / "openapi.json"), "--body", str(D / "good-user.json")
        ).returncode
        == 2
    )
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{not json}\n")
    assert run_script(SKILL, SCRIPT, "--spec", str(D / "openapi.json"), "--jsonl", str(bad)).returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
