#!/usr/bin/env python3
"""Find common smells in unit tests: pytest, unittest, Jest/Vitest and PHPUnit.

Rules
  UT001 high    test has no assertion (passes even if the code is broken)
  UT002 high    focused test committed (it.only, fit, fdescribe, describe.only)
  UT003 medium  real sleep in a test (time.sleep, setTimeout promise, sleep/usleep)
  UT004 medium  assertion on a constant (assert True, expect(true).toBe(true), assertTrue(true))
  UT005 medium  exception swallowed in a test (except: pass, empty catch)
  UT006 low     overly broad exception expectation (pytest.raises(Exception), toThrow())
  UT007 low     skipped test without a reason
  UT008 info    debug output left in a test (print, console.log, var_dump)

Python files are analysed with the ast module; JS/TS and PHP with brace matching.
Silence a line with a trailing comment containing: lint-tests: ignore[UT003]

Exit codes: 0 = nothing at or above --fail-on, 1 = findings, 2 = error.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

SEVERITIES = ["info", "low", "medium", "high"]
TITLES = {
    "UT001": (
        "high",
        "test has no assertion",
        "assert on the outcome (return value, state, call, raised error)",
    ),
    "UT002": ("high", "focused test committed", "remove .only / fit / fdescribe so the whole suite runs"),
    "UT003": (
        "medium",
        "real sleep in a test",
        "use fake timers (vi.useFakeTimers / jest.useFakeTimers), inject a clock, or poll a condition",
    ),
    "UT004": ("medium", "assertion on a constant", "assert on the value produced by the code under test"),
    "UT005": (
        "medium",
        "exception swallowed in a test",
        "let it propagate, or assert it with pytest.raises / expect().toThrow / expectException",
    ),
    "UT006": (
        "low",
        "overly broad exception expectation",
        "expect the specific exception type and message "
        "(match= / toThrow(ErrorClass) / expectExceptionMessage)",
    ),
    "UT007": ("low", "skipped test without a reason", "add a reason and an issue link, or delete the test"),
    "UT008": (
        "info",
        "debug output in a test",
        "remove it; use assertion messages or the runner's -s/--verbose",
    ),
}
SKIP_DIRS = {"node_modules", ".git", "vendor", ".venv", "venv", "dist", "build", "__pycache__", "coverage"}
IGNORE_RX = re.compile(r"lint-tests:\s*ignore\[([A-Z0-9, ]+)\]")


def is_test_file(p: Path) -> bool:
    n = p.name
    if p.suffix == ".py":
        return n.startswith("test_") or n.endswith("_test.py")
    if p.suffix in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"):
        return bool(re.search(r"\.(test|spec)\.[mc]?[jt]sx?$", n)) or "__tests__" in p.parts
    if p.suffix == ".php":
        return n.endswith("Test.php")
    return False


def _finding(file: str, line: int, rule: str, name: str = "", code: str = "") -> dict:
    sev, title, fix = TITLES[rule]
    return {
        "file": file,
        "line": line,
        "rule": rule,
        "severity": sev,
        "title": title,
        "test": name,
        "fix": fix,
        "code": code.strip()[:160],
    }


# ---------------------------------------------------------------- Python


ASSERT_CALL = re.compile(r"^(assert|assert_|expect|verify|check|should)", re.I)


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        node = node.func
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _has_assertion(fn: ast.AST) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, ast.Call):
            name = _call_name(node)
            last = name.rsplit(".", 1)[-1]
            if ASSERT_CALL.match(last) or name in ("pytest.raises", "pytest.warns", "pytest.fail", "raises"):
                return True
            if last in ("fail", "assertRaises", "assertWarns"):
                return True
    return False


def lint_python(text: str, filename: str) -> list[dict]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [
            {
                "file": filename,
                "line": exc.lineno or 0,
                "rule": "PARSE",
                "severity": "info",
                "title": f"could not parse: {exc.msg}",
                "test": "",
                "fix": "fix the syntax error",
                "code": "",
            }
        ]
    lines = text.splitlines()
    out: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            skip_reason = None
            for dec in node.decorator_list:
                dname = _call_name(dec)
                if dname.endswith("mark.skip") or dname.endswith("unittest.skip") or dname == "skip":
                    has_reason = isinstance(dec, ast.Call) and (dec.args or dec.keywords)
                    skip_reason = bool(has_reason)
                    if not has_reason:
                        out.append(_finding(filename, dec.lineno, "UT007", node.name))
            if skip_reason is None and not _has_assertion(node):
                out.append(_finding(filename, node.lineno, "UT001", node.name, lines[node.lineno - 1]))
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    name = _call_name(sub)
                    if name in ("time.sleep", "sleep", "asyncio.sleep") and sub.args:
                        arg = sub.args[0]
                        if not (isinstance(arg, ast.Constant) and arg.value == 0):
                            out.append(
                                _finding(filename, sub.lineno, "UT003", node.name, lines[sub.lineno - 1])
                            )
                    elif name in ("print", "pprint", "pprint.pprint", "breakpoint"):
                        out.append(_finding(filename, sub.lineno, "UT008", node.name, lines[sub.lineno - 1]))
                    elif name in ("pytest.raises", "raises", "self.assertRaises") and sub.args:
                        a = sub.args[0]
                        if isinstance(a, ast.Name) and a.id in ("Exception", "BaseException"):
                            if not any(k.arg == "match" for k in sub.keywords):
                                out.append(
                                    _finding(filename, sub.lineno, "UT006", node.name, lines[sub.lineno - 1])
                                )
                    elif name.endswith("assertTrue") or name.endswith("assertFalse"):
                        if sub.args and isinstance(sub.args[0], ast.Constant):
                            out.append(
                                _finding(filename, sub.lineno, "UT004", node.name, lines[sub.lineno - 1])
                            )
                elif isinstance(sub, ast.Assert) and isinstance(sub.test, ast.Constant):
                    out.append(_finding(filename, sub.lineno, "UT004", node.name, lines[sub.lineno - 1]))
                elif isinstance(sub, ast.ExceptHandler):
                    broad = sub.type is None or (
                        isinstance(sub.type, ast.Name) and sub.type.id in ("Exception", "BaseException")
                    )
                    if broad and all(isinstance(b, (ast.Pass, ast.Continue)) for b in sub.body):
                        out.append(_finding(filename, sub.lineno, "UT005", node.name, lines[sub.lineno - 1]))
    return out


# ---------------------------------------------------------------- JS / TS / PHP helpers


def _blank_strings_and_comments(text: str, php: bool = False) -> str:
    """Replace comments and string contents with spaces, keeping offsets and newlines."""
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        two = text[i : i + 2]
        if two == "//" or (php and c == "#" and text[i : i + 2] != "#["):
            j = text.find("\n", i)
            j = n if j == -1 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif two == "/*":
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        elif c in "'\"`":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            for k in range(i + 1, min(j, n)):
                if out[k] != "\n":
                    out[k] = " "
            i = j + 1
        else:
            i += 1
    return "".join(out)


def _block_end(clean: str, start: int) -> int:
    """Index after the '}' matching the first '{' at or after start."""
    i = clean.find("{", start)
    if i == -1:
        return len(clean)
    depth = 0
    for j in range(i, len(clean)):
        if clean[j] == "{":
            depth += 1
        elif clean[j] == "}":
            depth -= 1
            if depth == 0:
                return j + 1
    return len(clean)


def _paren_end(clean: str, start: int) -> int:
    """Index after the ')' matching the '(' at start."""
    depth = 0
    for j in range(start, len(clean)):
        if clean[j] == "(":
            depth += 1
        elif clean[j] == ")":
            depth -= 1
            if depth == 0:
                return j + 1
    return len(clean)


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


JS_TEST = re.compile(r"(?<![\w.$])(it|test)(\.(each\([^)]*\)|concurrent|only|skip|todo|fails))*\s*\(")
JS_ASSERT = re.compile(
    r"\bexpect(\.\w+)?\s*\(|\bassert(\.\w+)?\s*\(|\.should\b|\bexpectTypeOf\s*\(|\bverify\w*\s*\(|"
    r"\bsinon\.assert\b|\bt\.(is|deepEqual|true|false|throws)\b"
)


def lint_js(text: str, filename: str) -> list[dict]:
    clean = _blank_strings_and_comments(text)
    lines = text.splitlines()
    out: list[dict] = []

    def add(pos, rule, name=""):
        ln = _line_of(text, pos)
        out.append(_finding(filename, ln, rule, name, lines[ln - 1] if ln <= len(lines) else ""))

    for m in re.finditer(r"(?<![\w.$])(it|test|describe)\.only\s*\(|(?<![\w.$])(fit|fdescribe)\s*\(", clean):
        add(m.start(), "UT002")
    for m in re.finditer(
        r"(?<![\w.$])(it|test|describe)\.skip\s*\(|(?<![\w.$])(xit|xdescribe|xtest)\s*\(", clean
    ):
        add(m.start(), "UT007")
    for m in JS_TEST.finditer(clean):
        if ".skip" in m.group(0) or ".todo" in m.group(0):
            continue
        paren = m.end() - 1
        end = _paren_end(clean, paren)
        body = clean[paren:end]
        brace = paren
        if "=>" not in body and "function" not in body:
            continue  # test('name') placeholder with no callback
        name_m = re.match(r"\s*['\"`]([^'\"`]*)", text[paren + 1 : paren + 200])
        name = name_m.group(1) if name_m else ""
        if not JS_ASSERT.search(body):
            add(m.start(), "UT001", name)
        for sm in re.finditer(r"new\s+Promise\s*\([^)]*\)?\s*=>\s*setTimeout|\bsleep\s*\(\s*\d", body):
            add(brace + sm.start(), "UT003", name)
        for sm in re.finditer(
            r"expect\s*\(\s*(true|false|1|0|null)\s*\)\s*\.\s*(toBe|toEqual|toBeTruthy|toBeFalsy)\s*\(", body
        ):
            add(brace + sm.start(), "UT004", name)
        for sm in re.finditer(r"catch\s*(\([^)]*\))?\s*\{\s*\}", body):
            add(brace + sm.start(), "UT005", name)
        for sm in re.finditer(r"\.(toThrow|toThrowError|rejects\.toThrow)\s*\(\s*\)", body):
            add(brace + sm.start(), "UT006", name)
        for sm in re.finditer(r"\bconsole\.(log|debug|dir)\s*\(", body):
            add(brace + sm.start(), "UT008", name)
    return out


PHP_TEST = re.compile(r"\bpublic\s+function\s+(\w+)\s*\([^)]*\)\s*(?::\s*\??[\w\\]+)?\s*\{")
PHP_ASSERT = re.compile(
    r"(\$this->|self::|static::|parent::)(assert\w*|expect\w*|fail)\s*\(|\bassert\w*\s*\(|"
    r"->(shouldReceive|expects|assert\w*)\s*\(|\bexpect\s*\("
)


def lint_php(text: str, filename: str) -> list[dict]:
    clean = _blank_strings_and_comments(text, php=True)
    lines = text.splitlines()
    out: list[dict] = []

    def add(pos, rule, name=""):
        ln = _line_of(text, pos)
        out.append(_finding(filename, ln, rule, name, lines[ln - 1] if ln <= len(lines) else ""))

    for m in PHP_TEST.finditer(text):
        name = m.group(1)
        start = m.start(1)
        prev = max(
            clean.rfind("}", 0, m.start()), clean.rfind(";", 0, m.start()), clean.rfind("{", 0, m.start())
        )
        prefix = text[prev + 1 : m.start()]
        is_test = name.startswith("test") or "#[Test]" in prefix or "@test" in prefix
        if not is_test:
            continue
        brace = m.end() - 1
        end = _block_end(clean, brace)
        body = clean[brace:end]
        raw_body = text[brace:end]
        if re.search(r"markTestSkipped\s*\(\s*\)", body):
            add(brace, "UT007", name)
            continue
        if "markTestSkipped" in body or "markTestIncomplete" in body:
            continue
        if not PHP_ASSERT.search(body):
            add(start, "UT001", name)
        for sm in re.finditer(r"\b(u?sleep)\s*\(\s*[1-9]", body):
            add(brace + sm.start(), "UT003", name)
        for sm in re.finditer(r"assert(True|False)\s*\(\s*(true|false|1|0)\s*[,)]", body, re.I):
            add(brace + sm.start(), "UT004", name)
        for sm in re.finditer(r"catch\s*\([^)]*\)\s*\{\s*\}", body):
            add(brace + sm.start(), "UT005", name)
        for sm in re.finditer(r"expectException\s*\(\s*\\?Exception::class\s*\)", raw_body):
            if "expectExceptionMessage" not in raw_body:
                add(brace + sm.start(), "UT006", name)
        for sm in re.finditer(r"\b(var_dump|print_r|dump|dd)\s*\(", body):
            add(brace + sm.start(), "UT008", name)
    return out


# ---------------------------------------------------------------- driver


def lint_file(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".py":
        found = lint_python(text, str(path))
    elif path.suffix == ".php":
        found = lint_php(text, str(path))
    else:
        found = lint_js(text, str(path))
    lines = text.splitlines()
    kept = []
    for f in found:
        ln = f["line"]
        m = IGNORE_RX.search(lines[ln - 1]) if 0 < ln <= len(lines) else None
        if m and f["rule"] in {r.strip() for r in m.group(1).split(",")}:
            continue
        kept.append(f)
    return kept


def iter_files(paths: list[str]) -> list[Path]:
    out = []
    for raw in paths:
        p = Path(raw)
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and not any(part in SKIP_DIRS for part in f.parts) and is_test_file(f):
                    out.append(f)
        else:
            raise FileNotFoundError(raw)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Find common smells in pytest, unittest, Jest/Vitest and PHPUnit tests.",
        epilog="Example: lint_tests.py tests/ src/ --fail-on high --json",
    )
    p.add_argument("paths", nargs="*", default=["."], help="test files or directories (default .)")
    p.add_argument("--fail-on", choices=SEVERITIES, default="medium", help="lowest severity that fails")
    p.add_argument("--min-severity", choices=SEVERITIES, default="info", help="lowest severity to show")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        files = iter_files(args.paths)
        findings = [f for path in files for f in lint_file(path)]
    except (FileNotFoundError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    min_idx = SEVERITIES.index(args.min_severity)
    findings = [f for f in findings if SEVERITIES.index(f["severity"]) >= min_idx]
    findings.sort(key=lambda f: (-SEVERITIES.index(f["severity"]), f["file"], f["line"], f["rule"]))
    failed = any(SEVERITIES.index(f["severity"]) >= SEVERITIES.index(args.fail_on) for f in findings)
    if args.json:
        counts: dict[str, int] = {}
        for f in findings:
            counts[f["rule"]] = counts.get(f["rule"], 0) + 1
        print(json.dumps({"files": len(files), "by_rule": counts, "findings": findings}, indent=2))
        return 1 if failed else 0
    for f in findings:
        where = f" in {f['test']}" if f["test"] else ""
        print(f"{f['file']}:{f['line']}: [{f['severity'].upper()}] {f['rule']} {f['title']}{where}")
        print(f"    fix: {f['fix']}")
    print(f"\n{len(findings)} finding(s) in {len(files)} test file(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
