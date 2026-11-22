#!/usr/bin/env python3
"""Validate recorded API responses against an OpenAPI 3.0/3.1 document.

Inputs (offline, nothing is sent anywhere):
  --har FILE      browser / proxy / Playwright HAR recording
  --jsonl FILE    one exchange per line: {"method", "path" or "url", "status", "body",
                  optional "content_type"}; body may be a JSON value or a JSON string
  --method/--path/--status/--body FILE   a single response

For every exchange the script finds the operation (path template + method), the
response object (exact status, then 2XX-style range, then default), and validates the
JSON body against its schema. It also reports undocumented operations and status
codes, and which documented operations/statuses the recording exercised.

Supported schema keywords: $ref (local), type (incl. 3.1 type arrays), nullable,
enum, const, properties, required, additionalProperties, patternProperties, items,
prefixItems, minItems, maxItems, uniqueItems, minLength, maxLength, pattern,
format (date-time, date, time, email, uuid, uri, ipv4, ipv6, int32, int64),
minimum, maximum, exclusiveMinimum, exclusiveMaximum (3.0 and 3.1 forms),
multipleOf, minProperties, maxProperties, allOf, anyOf, oneOf, not, readOnly/writeOnly.

YAML specs need PyYAML (pip install pyyaml); JSON specs need nothing.
Exit codes: 0 = all responses conform, 1 = violations, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit

METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
FORMAT_RE = {
    "uuid": re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"),
    "email": re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
    "uri": re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:\S*$"),
    "time": re.compile(r"^\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$"),
    "ipv4": re.compile(r"^((25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(25[0-5]|2[0-4]\d|1?\d?\d)$"),
}


class SpecError(Exception):
    pass


def load_document(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml") or not text.lstrip().startswith(("{", "[")):
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise SpecError(
                f"{path}: YAML needs PyYAML (pip install pyyaml), or convert it to JSON first"
            ) from exc
        return yaml.safe_load(text)
    return json.loads(text)


# ---------------------------------------------------------------- schema validation


class Validator:
    def __init__(self, spec: dict, check_formats: bool = True, strict_additional: bool = False):
        self.spec = spec
        self.check_formats = check_formats
        self.strict_additional = strict_additional
        self.v31 = str(spec.get("openapi", "")).startswith("3.1")

    def resolve(self, schema):
        seen = 0
        while isinstance(schema, dict) and "$ref" in schema:
            ref = schema["$ref"]
            if not ref.startswith("#/"):
                raise SpecError(f"only local $ref is supported, got {ref!r} (bundle the spec first)")
            node = self.spec
            for part in ref[2:].split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                if not isinstance(node, dict) or part not in node:
                    raise SpecError(f"unresolvable $ref {ref!r}")
                node = node[part]
            # OpenAPI 3.1 allows siblings next to $ref; merge them over the target.
            extra = {k: v for k, v in schema.items() if k != "$ref"}
            schema = {**node, **extra} if extra and isinstance(node, dict) else node
            seen += 1
            if seen > 50:
                raise SpecError(f"$ref cycle at {ref!r}")
        return schema

    @staticmethod
    def _type_of(value) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "integer" if value.is_integer() else "number"
        if isinstance(value, str):
            return "string"
        if isinstance(value, list):
            return "array"
        return "object"

    def validate(self, value, schema, path: str = "$") -> list[str]:
        schema = self.resolve(schema)
        if schema is True or schema is None or schema == {}:
            return []
        if schema is False:
            return [f"{path}: no value is allowed here"]
        errs: list[str] = []
        actual = self._type_of(value)

        types = schema.get("type")
        if isinstance(types, str):
            types = [types]
        if types is not None:
            allowed = set(types)
            if schema.get("nullable") is True:
                allowed.add("null")
            ok = actual in allowed or (actual == "integer" and "number" in allowed)
            if not ok:
                return [f"{path}: expected {'/'.join(sorted(allowed))}, got {actual}"]
        elif value is None and schema.get("nullable") is not True and not self.v31:
            # 3.0 without type: null is still only valid when nullable
            if any(k in schema for k in ("properties", "items", "enum")):
                return [f"{path}: null is not allowed (set nullable: true)"]

        if "enum" in schema and value not in schema["enum"]:
            if not (value is None and schema.get("nullable") is True):
                errs.append(f"{path}: {value!r} is not one of {schema['enum']!r}")
        if "const" in schema and value != schema["const"]:
            errs.append(f"{path}: expected constant {schema['const']!r}")

        if actual == "string":
            errs += self._string(value, schema, path)
        elif actual in ("integer", "number"):
            errs += self._number(value, schema, path)
        elif actual == "array":
            errs += self._array(value, schema, path)
        elif actual == "object":
            errs += self._object(value, schema, path)

        for sub in schema.get("allOf", []):
            errs += self.validate(value, sub, path)
        if "anyOf" in schema and not any(not self.validate(value, s, path) for s in schema["anyOf"]):
            errs.append(f"{path}: does not match any schema in anyOf")
        if "oneOf" in schema:
            matches = sum(1 for s in schema["oneOf"] if not self.validate(value, s, path))
            if matches != 1:
                errs.append(f"{path}: matches {matches} schemas in oneOf (expected exactly 1)")
        if "not" in schema and not self.validate(value, schema["not"], path):
            errs.append(f"{path}: must not match the 'not' schema")
        return errs

    def _string(self, value: str, schema: dict, path: str) -> list[str]:
        errs = []
        if "minLength" in schema and len(value) < schema["minLength"]:
            errs.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errs.append(f"{path}: longer than maxLength {schema['maxLength']}")
        if "pattern" in schema:
            try:
                if not re.search(schema["pattern"], value):
                    errs.append(f"{path}: does not match pattern {schema['pattern']!r}")
            except re.error:
                pass  # ECMA-only regex syntax: skip rather than report a false failure
        fmt = schema.get("format")
        if self.check_formats and fmt and not self._format_ok(fmt, value):
            errs.append(f"{path}: {value!r} is not a valid {fmt}")
        return errs

    @staticmethod
    def _format_ok(fmt: str, value: str) -> bool:
        if fmt == "date-time":
            v = value.replace("z", "Z")
            if not re.match(r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$", v):
                return False
            try:
                datetime.fromisoformat(re.sub(r"\.\d+", "", v).replace("Z", "+00:00"))
            except ValueError:
                return False
            return True
        if fmt == "date":
            try:
                date.fromisoformat(value)
            except ValueError:
                return False
            return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", value))
        if fmt == "ipv6":
            return ":" in value and bool(re.match(r"^[0-9A-Fa-f:.]+$", value))
        rx = FORMAT_RE.get(fmt)
        return bool(rx.match(value)) if rx else True

    def _number(self, value, schema: dict, path: str) -> list[str]:
        errs = []
        fmt = schema.get("format")
        if self.check_formats and fmt in ("int32", "int64") and isinstance(value, (int, float)):
            bits = 31 if fmt == "int32" else 63
            if not (-(2**bits) <= value <= 2**bits - 1):
                errs.append(f"{path}: {value} is out of range for {fmt}")
        if "minimum" in schema:
            excl = schema.get("exclusiveMinimum") is True
            if value < schema["minimum"] or (excl and value == schema["minimum"]):
                errs.append(f"{path}: {value} is below the minimum {schema['minimum']}")
        if "maximum" in schema:
            excl = schema.get("exclusiveMaximum") is True
            if value > schema["maximum"] or (excl and value == schema["maximum"]):
                errs.append(f"{path}: {value} is above the maximum {schema['maximum']}")
        em, eM = schema.get("exclusiveMinimum"), schema.get("exclusiveMaximum")
        if isinstance(em, (int, float)) and not isinstance(em, bool) and value <= em:
            errs.append(f"{path}: {value} must be greater than {em}")
        if isinstance(eM, (int, float)) and not isinstance(eM, bool) and value >= eM:
            errs.append(f"{path}: {value} must be less than {eM}")
        mult = schema.get("multipleOf")
        if mult:
            q = value / mult
            if not math.isclose(q, round(q), abs_tol=1e-9):
                errs.append(f"{path}: {value} is not a multiple of {mult}")
        return errs

    def _array(self, value: list, schema: dict, path: str) -> list[str]:
        errs = []
        if "minItems" in schema and len(value) < schema["minItems"]:
            errs.append(f"{path}: fewer than minItems {schema['minItems']}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errs.append(f"{path}: more than maxItems {schema['maxItems']}")
        if schema.get("uniqueItems"):
            seen = [json.dumps(v, sort_keys=True) for v in value]
            if len(seen) != len(set(seen)):
                errs.append(f"{path}: items are not unique")
        prefix = schema.get("prefixItems") or []
        for i, item in enumerate(value):
            if i < len(prefix):
                errs += self.validate(item, prefix[i], f"{path}[{i}]")
            elif "items" in schema and isinstance(schema["items"], (dict, bool)):
                errs += self.validate(item, schema["items"], f"{path}[{i}]")
        return errs

    def _object(self, value: dict, schema: dict, path: str) -> list[str]:
        errs = []
        props = schema.get("properties") or {}
        for name in schema.get("required") or []:
            if name not in value:
                prop = self.resolve(props.get(name, {}))
                if isinstance(prop, dict) and prop.get("writeOnly"):
                    continue  # writeOnly properties are never in responses
                errs.append(f"{path}: missing required property '{name}'")
        if "minProperties" in schema and len(value) < schema["minProperties"]:
            errs.append(f"{path}: fewer than minProperties {schema['minProperties']}")
        if "maxProperties" in schema and len(value) > schema["maxProperties"]:
            errs.append(f"{path}: more than maxProperties {schema['maxProperties']}")
        patterns = schema.get("patternProperties") or {}
        additional = schema.get("additionalProperties")
        if additional is None and self.strict_additional and props:
            additional = False
        for key, item in value.items():
            sub_path = f"{path}.{key}" if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key) else f"{path}[{key!r}]"
            if key in props:
                prop = self.resolve(props[key])
                if isinstance(prop, dict) and prop.get("writeOnly"):
                    errs.append(f"{sub_path}: writeOnly property returned in a response")
                errs += self.validate(item, prop, sub_path)
                continue
            matched = False
            for pat, sub in patterns.items():
                if re.search(pat, key):
                    matched = True
                    errs += self.validate(item, sub, sub_path)
            if matched:
                continue
            if additional is False:
                errs.append(f"{sub_path}: property is not allowed (additionalProperties: false)")
            elif isinstance(additional, dict):
                errs += self.validate(item, additional, sub_path)
        return errs


# ---------------------------------------------------------------- operation lookup


def compile_paths(spec: dict) -> list[tuple[re.Pattern, str, int]]:
    out = []
    for template in spec.get("paths") or {}:
        literal = len(re.sub(r"\{[^}]+\}", "", template))
        rx = "^" + re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(template)) + "/?$"
        out.append((re.compile(rx), template, literal))
    # Prefer the most literal template: /users/me before /users/{id}
    out.sort(key=lambda t: -t[2])
    return out


def server_prefixes(spec: dict) -> list[str]:
    prefixes = []
    for s in spec.get("servers") or []:
        url = re.sub(r"\{[^}]+\}", "x", str(s.get("url", "")))
        p = urlsplit(url).path if "://" in url else url
        p = p.rstrip("/")
        if p and p not in prefixes:
            prefixes.append(p)
    return sorted(prefixes, key=len, reverse=True)


def find_operation(spec, compiled, prefixes, method: str, raw_path: str):
    path = urlsplit(raw_path).path if "://" in raw_path else raw_path.split("?", 1)[0]
    candidates = [path] + [path[len(p) :] or "/" for p in prefixes if path.startswith(p)]
    for cand in candidates:
        for rx, template, _ in compiled:
            if rx.match(cand):
                item = spec["paths"][template] or {}
                op = item.get(method.lower())
                return template, op
    return None, None


def find_response(op: dict, status: int):
    responses = op.get("responses") or {}
    for key in (str(status), f"{str(status)[0]}XX", f"{str(status)[0]}xx", "default"):
        if key in responses:
            return key, responses[key]
    return None, None


def pick_media(content: dict, content_type: str):
    if not content:
        return None, None
    ct = (content_type or "").split(";", 1)[0].strip().lower()
    if ct and ct in content:
        return ct, content[ct]
    for key, media in content.items():
        if ct and key.endswith("/*") and ct.startswith(key[:-1]):
            return key, media
    for key, media in content.items():
        if key == "application/json" or key.endswith("+json"):
            return key, media
    if "*/*" in content:
        return "*/*", content["*/*"]
    return None, None


# ---------------------------------------------------------------- inputs


def _parse_body(body):
    if isinstance(body, str):
        if not body.strip():
            return None, False
        try:
            return json.loads(body), True
        except json.JSONDecodeError:
            return body, False
    return body, body is not None


def read_har(path: Path) -> list[dict]:
    har = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for entry in (har.get("log") or {}).get("entries") or []:
        req, resp = entry.get("request") or {}, entry.get("response") or {}
        content = resp.get("content") or {}
        text = content.get("text")
        if text is not None and content.get("encoding") == "base64":
            import base64

            try:
                text = base64.b64decode(text).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                text = None
        out.append(
            {
                "method": req.get("method", "GET"),
                "path": req.get("url", "/"),
                "status": int(resp.get("status") or 0),
                "body": text,
                "content_type": content.get("mimeType", ""),
            }
        )
    return out


def read_jsonl(path: Path) -> list[dict]:
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SpecError(f"{path}:{n}: invalid JSON: {exc}") from exc
        out.append(
            {
                "method": rec.get("method", "GET"),
                "path": rec.get("path") or rec.get("url") or "/",
                "status": int(rec.get("status") or 0),
                "body": rec.get("body"),
                "content_type": rec.get("content_type", "application/json"),
            }
        )
    return out


def check_exchanges(spec: dict, exchanges: list[dict], validator: Validator, url_filter: str | None = None):
    compiled = compile_paths(spec)
    prefixes = server_prefixes(spec)
    results = []
    exercised: set[tuple[str, str, str]] = set()
    for i, ex in enumerate(exchanges):
        if url_filter and url_filter not in ex["path"]:
            continue
        method = ex["method"].lower()
        rec = {"index": i, "method": method.upper(), "path": ex["path"], "status": ex["status"]}
        template, op = find_operation(spec, compiled, prefixes, method, ex["path"])
        if template is None:
            rec.update(result="undocumented-path", errors=["no path template in the spec matches"])
            results.append(rec)
            continue
        rec["operation"] = f"{method.upper()} {template}"
        if op is None:
            rec.update(
                result="undocumented-method", errors=[f"{method.upper()} is not defined for {template}"]
            )
            results.append(rec)
            continue
        key, response = find_response(op, ex["status"])
        if response is None:
            documented = ", ".join(sorted((op.get("responses") or {}).keys()))
            rec.update(
                result="undocumented-status",
                errors=[f"status {ex['status']} is not documented (documented: {documented})"],
            )
            results.append(rec)
            continue
        exercised.add((method.upper(), template, key))
        response = validator.resolve(response)
        content = response.get("content") or {}
        body, is_json = _parse_body(ex.get("body"))
        if not content:
            if body not in (None, ""):
                rec.update(
                    result="ok", errors=[], note="response has no documented content; body not checked"
                )
            else:
                rec.update(result="ok", errors=[])
            results.append(rec)
            continue
        media_key, media = pick_media(content, ex.get("content_type", ""))
        if media is None:
            rec.update(
                result="fail",
                errors=[f"content type {ex.get('content_type')!r} is not documented for {key}"],
            )
            results.append(rec)
            continue
        schema = media.get("schema")
        if schema is None or not (media_key.endswith("json") or media_key == "*/*"):
            rec.update(result="ok", errors=[], note=f"{media_key}: no JSON schema to check")
            results.append(rec)
            continue
        if not is_json:
            rec.update(result="fail", errors=["body is empty or not valid JSON"])
            results.append(rec)
            continue
        errors = validator.validate(body, schema)
        rec.update(result="fail" if errors else "ok", errors=errors[:50], response_key=key)
        results.append(rec)
    documented = set()
    for template, item in (spec.get("paths") or {}).items():
        for m in METHODS:
            if isinstance(item, dict) and m in item:
                for k in item[m].get("responses") or {}:
                    documented.add((m.upper(), template, str(k)))
    coverage = {
        "documented_responses": len(documented),
        "exercised_responses": len(exercised & documented),
        "not_exercised": sorted(f"{m} {t} {k}" for m, t, k in documented - exercised),
    }
    return results, coverage


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Validate recorded API responses against an OpenAPI 3.0/3.1 document.",
        epilog="Example: validate_responses.py --spec openapi.json --har session.har --json",
    )
    p.add_argument("--spec", required=True, type=Path, help="OpenAPI document (JSON, or YAML with PyYAML)")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--har", type=Path, help="HAR file to check")
    src.add_argument("--jsonl", type=Path, help="JSON Lines file of exchanges")
    src.add_argument(
        "--body", type=Path, help="single response body file (use with --method/--path/--status)"
    )
    p.add_argument("--method", default="GET")
    p.add_argument("--path", help="request path for --body, e.g. /v1/users/42")
    p.add_argument("--status", type=int, default=200)
    p.add_argument("--content-type", default="application/json")
    p.add_argument("--only", help="only check exchanges whose URL contains this text (e.g. /api/)")
    p.add_argument("--no-formats", action="store_true", help="do not check string formats")
    p.add_argument(
        "--strict-additional",
        action="store_true",
        help="treat objects without additionalProperties as additionalProperties: false",
    )
    p.add_argument(
        "--allow-undocumented", action="store_true", help="undocumented paths/statuses do not fail"
    )
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        spec = load_document(args.spec)
        if not isinstance(spec, dict) or not str(spec.get("openapi", "")).startswith("3."):
            raise SpecError(f"{args.spec}: not an OpenAPI 3.x document (Swagger 2.0 is not supported)")
        if args.har:
            exchanges = read_har(args.har)
        elif args.jsonl:
            exchanges = read_jsonl(args.jsonl)
        else:
            if not args.path:
                raise SpecError("--body needs --path")
            exchanges = [
                {
                    "method": args.method,
                    "path": args.path,
                    "status": args.status,
                    "body": args.body.read_text(encoding="utf-8"),
                    "content_type": args.content_type,
                }
            ]
        validator = Validator(
            spec, check_formats=not args.no_formats, strict_additional=args.strict_additional
        )
        results, coverage = check_exchanges(spec, exchanges, validator, args.only)
    except (SpecError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    failing = {"fail"} | (
        set()
        if args.allow_undocumented
        else {"undocumented-path", "undocumented-method", "undocumented-status"}
    )
    bad = [r for r in results if r["result"] in failing]
    summary: dict[str, int] = {}
    for r in results:
        summary[r["result"]] = summary.get(r["result"], 0) + 1
    if args.json:
        print(json.dumps({"summary": summary, "results": results, "coverage": coverage}, indent=2))
        return 1 if bad else 0
    print(
        f"{len(results)} responses checked: "
        + ", ".join(f"{k} {v}" for k, v in sorted(summary.items()))
        + f"; {coverage['exercised_responses']}/{coverage['documented_responses']}"
        + " documented responses exercised"
    )
    for r in results:
        if r["result"] == "ok":
            continue
        label = r.get("operation") or r["method"]
        print(f"\n[{r['result'].upper()}] {label} -> {r['status']}  ({r['path']})")
        for e in r["errors"][:10]:
            print(f"  - {e}")
        if len(r["errors"]) > 10:
            print(f"  ... {len(r['errors']) - 10} more")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
