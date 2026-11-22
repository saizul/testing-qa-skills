#!/usr/bin/env python3
"""Generate a deterministic test data builder from a sample JSON object.

Give it one realistic example of an entity (an API response, a DB row exported as
JSON) and it writes a builder for Python, TypeScript or PHP:

  * every field gets a valid, deterministic default derived from a sequence number
    (ids 1, 2, 3...; emails user-1@example.test; dates offset from a fixed epoch)
  * callers override only the fields a test cares about
  * nested objects become nested builders; arrays of objects build one element
  * no random values, no wall-clock time, no network: the same call returns the
    same data on every machine, so failures reproduce

The generated code is printed (or written with --out, never overwriting unless
--force). Review it, rename fields' defaults to domain-meaningful values, commit it.

Exit codes: 0 = ok, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EPOCH = "2024-01-01T00:00:00Z"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+$")
URL_RE = re.compile(r"^https?://")
ENUM_KEY_RE = re.compile(
    r"(^|_)(status|state|type|kind|role|currency|country|locale|lang|language|category|plan|tier|mode|"
    r"level|unit|gender|channel|source)$",
    re.I,
)


def label(key: str) -> str:
    """Field name made safe to embed in a generated string literal."""
    return re.sub(r"[^A-Za-z0-9 _-]", "", key).replace("_", " ").strip() or "value"


def pascal(name: str) -> str:
    parts = re.split(r"[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])", name)
    out = "".join(p[:1].upper() + p[1:] for p in parts if p)
    return out if out and out[0].isalpha() else f"X{out}"


def snake(name: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    return s if s and not s[0].isdigit() else f"f_{s}"


def singular(name: str) -> str:
    if name.endswith("ies"):
        return name[:-3] + "y"
    if name.endswith("ses") or name.endswith("xes"):
        return name[:-2]
    if name.endswith("s") and not name.endswith("ss"):
        return name[:-1]
    return name + "Item"


def classify(key: str, value) -> str:
    """Return a kind used to choose a deterministic default."""
    k = key.lower()
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "id" if k == "id" or k.endswith("_id") or key.endswith("Id") else "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        if UUID_RE.match(value):
            return "uuid"
        if EMAIL_RE.match(value) or "email" in k:
            return "email"
        if DATETIME_RE.match(value):
            return "datetime"
        if DATE_RE.match(value):
            return "date"
        if URL_RE.match(value):
            return "url"
        if ENUM_KEY_RE.search(snake(key)) and len(value) <= 32:
            return "enum"
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return "str"


class Entity:
    def __init__(self, name: str, sample: dict):
        self.name = pascal(name)
        self.fields: list[tuple[str, str, object, Entity | None]] = []
        self.children: list[Entity] = []
        for key, value in sample.items():
            kind = classify(key, value)
            child = None
            if kind == "object" and value:
                child = Entity(pascal(key), value)
                self.children.append(child)
            elif kind == "list" and value and isinstance(value[0], dict):
                child = Entity(pascal(singular(key)), value[0])
                self.children.append(child)
            self.fields.append((key, kind, value, child))

    def all_entities(self) -> list[Entity]:
        out: list[Entity] = []
        for c in self.children:
            out += c.all_entities()
        out.append(self)
        return out


# ---------------------------------------------------------------- Python


def py_default(key: str, kind: str, value, child: Entity | None, ent: Entity) -> str:
    slug = snake(ent.name).replace("_", "-")
    if kind == "id":
        return "n"
    if kind in ("int", "enum"):
        return repr(value)
    if kind == "float":
        return repr(value)
    if kind == "bool":
        return repr(value)
    if kind == "null":
        return "None"
    if kind == "uuid":
        return 'f"00000000-0000-4000-8000-{n:012d}"'
    if kind == "email":
        return f'f"{slug}-{{n}}@example.test"'
    if kind == "datetime":
        return '(EPOCH + timedelta(days=n)).isoformat().replace("+00:00", "Z")'
    if kind == "date":
        return "(EPOCH + timedelta(days=n)).date().isoformat()"
    if kind == "url":
        return f'f"https://example.test/{slug}/{{n}}"'
    if kind == "str":
        return f'f"{label(key)} {{n}}"'
    if kind == "object":
        return f"build_{snake(child.name)}()" if child else "{}"
    if kind == "list":
        if child:
            return f"[build_{snake(child.name)}()]"
        return "[]" if not value else repr(value)
    return "None"


def render_python(root: Entity) -> str:
    lines = [
        '"""Deterministic test data builders. Generated by make_builder.py; edit freely."""',
        "",
        "from __future__ import annotations",
        "",
        "import itertools",
        "from datetime import datetime, timedelta, timezone",
        "from typing import Any",
        "",
        "EPOCH = datetime(2024, 1, 1, tzinfo=timezone.utc)",
        "_seq = itertools.count(1)",
        "",
        "",
        "def reset_sequences() -> None:",
        '    """Call from a fixture so every test sees ids 1, 2, 3... regardless of order."""',
        "    global _seq",
        "    _seq = itertools.count(1)",
        "",
    ]
    for ent in root.all_entities():
        fn = f"build_{snake(ent.name)}"
        lines += [
            "",
            f"def {fn}(**overrides: Any) -> dict[str, Any]:",
            f'    """A valid {ent.name}. Pass only the fields your test is about."""',
            "    n = next(_seq)",
            "    data: dict[str, Any] = {",
        ]
        for key, kind, value, child in ent.fields:
            lines.append(f"        {key!r}: {py_default(key, kind, value, child, ent)},")
        lines += [
            "    }",
            "    unknown = set(overrides) - set(data)",
            "    if unknown:",
            f'        raise TypeError(f"{fn}: unknown field(s) {{sorted(unknown)}}")',
            "    data.update(overrides)",
            "    return data",
            "",
        ]
    root_fn = f"build_{snake(root.name)}"
    lines += [
        "",
        f"def build_{snake(root.name)}_list(count: int, **overrides: Any) -> list[dict[str, Any]]:",
        f"    return [{root_fn}(**overrides) for _ in range(count)]",
        "",
    ]
    return "\n".join(lines).replace("\n\n\n\n", "\n\n\n")


# ---------------------------------------------------------------- TypeScript


def ts_type(kind: str, value, child: Entity | None) -> str:
    if kind in ("id", "int", "float"):
        return "number"
    if kind == "bool":
        return "boolean"
    if kind == "null":
        return "unknown | null"
    if kind == "object":
        return child.name if child else "Record<string, unknown>"
    if kind == "list":
        if child:
            return f"{child.name}[]"
        if value and isinstance(value[0], str):
            return "string[]"
        if value and isinstance(value[0], (int, float)) and not isinstance(value[0], bool):
            return "number[]"
        return "unknown[]"
    return "string"


def ts_default(key: str, kind: str, value, child: Entity | None, ent: Entity) -> str:
    slug = snake(ent.name).replace("_", "-")
    if kind == "id":
        return "n"
    if kind in ("int", "float", "enum"):
        return json.dumps(value)
    if kind == "bool":
        return "true" if value else "false"
    if kind == "null":
        return "null"
    if kind == "uuid":
        return "`00000000-0000-4000-8000-${String(n).padStart(12, '0')}`"
    if kind == "email":
        return f"`{slug}-${{n}}@example.test`"
    if kind == "datetime":
        return "new Date(EPOCH + n * DAY).toISOString()"
    if kind == "date":
        return "new Date(EPOCH + n * DAY).toISOString().slice(0, 10)"
    if kind == "url":
        return f"`https://example.test/{slug}/${{n}}`"
    if kind == "str":
        return f"`{label(key)} ${{n}}`"
    if kind == "object":
        return f"build{child.name}()" if child else "{}"
    if kind == "list":
        if child:
            return f"[build{child.name}()]"
        return json.dumps(value) if value else "[]"
    return "null"


def _ts_key(key: str) -> str:
    return key if re.match(r"^[A-Za-z_$][\w$]*$", key) else json.dumps(key)


def render_ts(root: Entity) -> str:
    lines = [
        "// Deterministic test data builders. Generated by make_builder.py; edit freely.",
        "",
        "const EPOCH = Date.UTC(2024, 0, 1);",
        "const DAY = 24 * 60 * 60 * 1000;",
        "let seq = 0;",
        "const next = () => ++seq;",
        "",
        "/** Call in beforeEach so every test sees ids 1, 2, 3... regardless of order. */",
        "export function resetSequences(): void {",
        "  seq = 0;",
        "}",
    ]
    for ent in root.all_entities():
        lines += ["", f"export interface {ent.name} {{"]
        for key, kind, value, child in ent.fields:
            lines.append(f"  {_ts_key(key)}: {ts_type(kind, value, child)};")
        lines += [
            "}",
            "",
            f"export function build{ent.name}(overrides: Partial<{ent.name}> = {{}}): {ent.name} {{",
            "  const n = next();",
            "  return {",
        ]
        for key, kind, value, child in ent.fields:
            lines.append(f"    {_ts_key(key)}: {ts_default(key, kind, value, child, ent)},")
        lines += ["    ...overrides,", "  };", "}"]
    lines += [
        "",
        f"export const build{root.name}List = (count: number, overrides: Partial<{root.name}> = {{}}) =>",
        f"  Array.from({{ length: count }}, () => build{root.name}(overrides));",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- PHP


def php_default(key: str, kind: str, value, child: Entity | None, ent: Entity) -> str:
    slug = snake(ent.name).replace("_", "-")
    if kind == "id":
        return "$n"
    if kind in ("int", "float"):
        return json.dumps(value)
    if kind == "enum":
        return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
    if kind == "bool":
        return "true" if value else "false"
    if kind == "null":
        return "null"
    if kind == "uuid":
        return "sprintf('00000000-0000-4000-8000-%012d', $n)"
    if kind == "email":
        return f'"{slug}-{{$n}}@example.test"'
    if kind == "datetime":
        return "self::epoch()->modify(\"+{$n} days\")->format('Y-m-d\\TH:i:s\\Z')"
    if kind == "date":
        return "self::epoch()->modify(\"+{$n} days\")->format('Y-m-d')"
    if kind == "url":
        return f'"https://example.test/{slug}/{{$n}}"'
    if kind == "str":
        return f'"{label(key)} {{$n}}"'
    if kind == "object":
        return f"self::{lcfirst(child.name)}()" if child else "[]"
    if kind == "list":
        if child:
            return f"[self::{lcfirst(child.name)}()]"
        return "[" + ", ".join(json.dumps(v) for v in value) + "]" if value else "[]"
    return "null"


def lcfirst(s: str) -> str:
    return s[:1].lower() + s[1:]


def render_php(root: Entity) -> str:
    lines = [
        "<?php",
        "",
        "declare(strict_types=1);",
        "",
        "namespace Tests\\Support;",
        "",
        "/** Deterministic test data builders. Generated by make_builder.py; edit freely. */",
        f"final class {root.name}Factory",
        "{",
        "    private static int $seq = 0;",
        "",
        "    /** Call from setUp() so every test sees ids 1, 2, 3... regardless of order. */",
        "    public static function resetSequences(): void",
        "    {",
        "        self::$seq = 0;",
        "    }",
        "",
        "    private static function epoch(): \\DateTimeImmutable",
        "    {",
        "        return new \\DateTimeImmutable('2024-01-01T00:00:00Z');",
        "    }",
    ]
    for ent in root.all_entities():
        lines += [
            "",
            "    /** @param array<string, mixed> $overrides */",
            f"    public static function {lcfirst(ent.name)}(array $overrides = []): array",
            "    {",
            "        $n = ++self::$seq;",
            "        $data = [",
        ]
        for key, kind, value, child in ent.fields:
            lines.append(f"            {json.dumps(key)} => {php_default(key, kind, value, child, ent)},")
        lines += [
            "        ];",
            "        $unknown = array_diff_key($overrides, $data);",
            "        if ($unknown !== []) {",
            "            throw new \\InvalidArgumentException(",
            "                'Unknown field(s): ' . implode(', ', array_keys($unknown))",
            "            );",
            "        }",
            "",
            "        return array_replace($data, $overrides);",
            "    }",
        ]
    lines += ["}", ""]
    return "\n".join(lines)


RENDERERS = {"python": render_python, "ts": render_ts, "php": render_php}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Generate a deterministic test data builder from a sample JSON object.",
        epilog="Example: make_builder.py user.json --name User --lang ts --out tests/builders/user.ts",
    )
    p.add_argument(
        "sample", help="JSON file with one example object (or a list; the first item is used), - = stdin"
    )
    p.add_argument("--name", help="entity name (default: file name)")
    p.add_argument("--lang", choices=sorted(RENDERERS), default="python")
    p.add_argument("--out", type=Path, help="write to this file instead of stdout")
    p.add_argument("--force", action="store_true", help="overwrite --out if it exists")
    p.add_argument(
        "--json", action="store_true", help="print the inferred field kinds as JSON instead of code"
    )
    args = p.parse_args(argv)
    try:
        text = sys.stdin.read() if args.sample == "-" else Path(args.sample).read_text(encoding="utf-8")
        sample = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if isinstance(sample, list):
        sample = sample[0] if sample else {}
    if not isinstance(sample, dict) or not sample:
        print("error: the sample must be a non-empty JSON object", file=sys.stderr)
        return 2
    name = args.name or (Path(args.sample).stem if args.sample != "-" else "Entity")
    root = Entity(name, sample)
    if args.json:
        out = {ent.name: {key: kind for key, kind, _, _ in ent.fields} for ent in root.all_entities()}
        print(json.dumps(out, indent=2))
        return 0
    code = RENDERERS[args.lang](root)
    if args.out:
        if args.out.exists() and not args.force:
            print(f"error: {args.out} exists (use --force to overwrite)", file=sys.stderr)
            return 2
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(code, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
