#!/usr/bin/env python3
"""Find flakiness and maintainability problems in Playwright Test specs.

Scans *.spec.ts/js, *.test.ts/js, *.setup.ts/js and *.e2e.ts/js files (or the files you
pass) for patterns the Playwright docs advise against: fixed sleeps, missing await on
web-first assertions and on page/locator actions, non-retrying assertions, XPath and layout-dependent CSS
selectors, legacy ElementHandle APIs, force clicks, networkidle waits, committed
test.only and hard-coded base URLs.

Silence one line with a trailing comment:  // spec-lint-disable-line PW001
Silence a whole file with:                 // spec-lint-disable-file PW005,PW010

Exit codes: 0 = no findings at or above --fail-on, 1 = findings, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SEVERITIES = ["info", "low", "medium", "high"]
SPEC_GLOBS = ("*.spec.*", "*.test.*", "*.setup.*", "*.e2e.*")
EXTS = {".ts", ".js", ".mjs", ".cjs", ".tsx", ".jsx", ".mts", ".cts"}
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "playwright-report", "test-results", "blob-report"}

WEB_FIRST = (
    "toBeAttached|toBeChecked|toBeDisabled|toBeEditable|toBeEmpty|toBeEnabled|toBeFocused|"
    "toBeHidden|toBeInViewport|toBeVisible|toContainText|toHaveAccessibleDescription|"
    "toHaveAccessibleName|toHaveAttribute|toHaveClass|toHaveCount|toHaveCSS|toHaveId|"
    "toHaveJSProperty|toHaveRole|toHaveScreenshot|toHaveText|toHaveValue|toHaveValues|"
    "toHaveTitle|toHaveURL|toContainClass|toMatchAriaSnapshot"
)

RULES = [
    (
        "PW001",
        "high",
        re.compile(r"\.waitForTimeout\s*\("),
        "fixed sleep (waitForTimeout)",
        "wait for a condition instead: await expect(locator).toBeVisible(), "
        "await page.waitForResponse(...), or expect.poll(...)",
    ),
    (
        "PW002",
        "high",
        re.compile(r"\b(test|describe|it)(\.describe)?\.only\s*\("),
        "focused test committed (.only)",
        "remove .only; set forbidOnly: !!process.env.CI in playwright.config",
    ),
    (
        "PW004",
        "medium",
        re.compile(
            r"""expect\s*\(\s*await\s+[^;]*?\.(isVisible|isHidden|isEnabled|isDisabled|isChecked|"""
            r"""textContent|innerText|inputValue|getAttribute|count)\s*\("""
        ),
        "boolean/text snapshot assertion does not retry",
        "use a web-first matcher: toBeVisible(), toHaveText(), toHaveValue(), toHaveCount()",
    ),
    (
        "PW005",
        "medium",
        re.compile(r"""(locator|\$\$?|waitForSelector|click|fill)\s*\(\s*['"`](xpath=|//|\(//)"""),
        "XPath selector",
        "prefer getByRole / getByLabel / getByText / getByTestId",
    ),
    (
        "PW006",
        "medium",
        re.compile(r""":nth-child\(|:nth-of-type\(|\.(css|sc|jsx|emotion)-[0-9a-zA-Z]{4,}|\[class\*?="""),
        "layout- or build-dependent CSS selector",
        "use a user-facing locator or a data-testid; generated class names change between builds",
    ),
    (
        "PW007",
        "medium",
        re.compile(r"\bpage\.(\$|\$\$|\$eval|\$\$eval)\s*\("),
        "legacy ElementHandle API",
        "use page.locator(...) / getBy* locators, which auto-wait and re-query",
    ),
    (
        "PW008",
        "medium",
        re.compile(r"\bforce\s*:\s*true\b"),
        "force: true skips actionability checks",
        "find out why the element is not actionable (overlay, animation, disabled) and wait for that",
    ),
    (
        "PW009",
        "low",
        re.compile(r"""networkidle"""),
        "networkidle wait",
        "the docs discourage networkidle; assert on the element or response you need",
    ),
    (
        "PW010",
        "low",
        re.compile(r"""\.goto\s*\(\s*['"`]https?://"""),
        "hard-coded absolute URL in goto",
        "set use.baseURL in playwright.config and call page.goto('/path')",
    ),
    (
        "PW011",
        "medium",
        re.compile(r"\bpage\.waitForSelector\s*\("),
        "waitForSelector",
        "use await expect(page.getByRole(...)).toBeVisible() or locator.waitFor()",
    ),
    (
        "PW012",
        "low",
        re.compile(r"""\bsetTimeout\s*\(|new\s+Promise\s*\(\s*\(?\s*r(esolve)?\s*\)?\s*=>\s*setTimeout"""),
        "manual setTimeout in a test",
        "use auto-waiting assertions or page.clock to control time",
    ),
    (
        "PW013",
        "info",
        re.compile(
            r"""\b(test|describe)\.(skip|fixme)\s*\(\s*\)|\b(test|describe)\.(skip|fixme)\s*\(\s*['"`]"""
        ),
        "skipped/fixme test",
        "link an issue and a reason; skipped tests rot",
    ),
]

AWAIT_RX = re.compile(r"(?<![\w.])expect(\.soft)?\s*\(")
MATCHER_RX = re.compile(r"\)\s*(\.not)?\s*\.(" + WEB_FIRST + r")\s*\(")
ACTIONS = (
    "click|dblclick|fill|press|pressSequentially|type|check|uncheck|setChecked|selectOption|"
    "setInputFiles|hover|tap|focus|blur|clear|dragTo|dispatchEvent|goto|reload|goBack|goForward|"
    "waitForURL|waitForLoadState|waitForResponse|waitForRequest|setViewportSize|screenshot"
)
# A statement that starts with a page/frame/locator chain and calls an async action.
ACTION_STMT_RX = re.compile(
    r"^(page|frame|popup|newPage|context|\w*[Ll]ocator\w*|\w+(Page|Button|Link|Input|Field|Row|Dialog))\b"
    r"[^;=]*?\.(" + ACTIONS + r")\s*\("
)
LOGIN_RX = re.compile(
    r"""getByLabel\(\s*['"`]password|type=["']?password|#password|\[name=["']?password""", re.I
)


def iter_files(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if any(part in SKIP_DIRS for part in f.parts):
                    continue
                if f.is_file() and f.suffix in EXTS and any(f.match(g) for g in SPEC_GLOBS):
                    out.append(f)
        else:
            raise FileNotFoundError(raw)
    return out


def _strip_comment(line: str) -> str:
    # Drop // comments that are not inside a string (good enough for specs).
    in_str = None
    for i, ch in enumerate(line):
        if in_str:
            if ch == in_str and line[i - 1] != "\\":
                in_str = None
        elif ch in "'\"`":
            in_str = ch
        elif ch == "/" and line[i : i + 2] == "//" and (i == 0 or line[i - 1] != ":"):
            return line[:i]
    return line


def lint_text(text: str, filename: str = "<stdin>") -> list[dict]:
    findings: list[dict] = []
    file_disabled: set[str] = set()
    m = re.search(r"spec-lint-disable-file\s+([A-Z0-9, ]+)", text)
    if m:
        file_disabled = {c.strip() for c in m.group(1).split(",") if c.strip()}
    in_block = False
    is_setup = ".setup." in Path(filename).name
    login_lines = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw
        if in_block:
            if "*/" in line:
                line = line.split("*/", 1)[1]
                in_block = False
            else:
                continue
        if "/*" in line and "*/" not in line.split("/*", 1)[1]:
            line = line.split("/*", 1)[0]
            in_block = True
        disabled = set(file_disabled)
        dm = re.search(r"spec-lint-disable-line\s+([A-Z0-9, ]+)", raw)
        if dm:
            disabled |= {c.strip() for c in dm.group(1).split(",") if c.strip()}
        code = _strip_comment(line)
        if not code.strip():
            continue
        for rule_id, sev, rx, title, fix in RULES:
            if rule_id in disabled:
                continue
            if rx.search(code):
                findings.append(
                    {
                        "file": filename,
                        "line": n,
                        "rule": rule_id,
                        "severity": sev,
                        "title": title,
                        "fix": fix,
                        "code": raw.strip()[:160],
                    }
                )
        # Missing await on a web-first (async, auto-retrying) assertion.
        em = AWAIT_RX.search(code)
        if "PW003" not in disabled and em and MATCHER_RX.search(code, em.end()):
            before = code[: em.start()].rstrip()
            if not re.search(r"\b(await|return)$", before) and "Promise.all" not in code:
                findings.append(
                    {
                        "file": filename,
                        "line": n,
                        "rule": "PW003",
                        "severity": "high",
                        "title": "web-first assertion without await",
                        "fix": "add await: the assertion is async and otherwise never fails the test",
                        "code": raw.strip()[:160],
                    }
                )
        # Missing await on an action: the promise floats and the next step races it.
        stmt = code.strip()
        if "PW015" not in disabled and ACTION_STMT_RX.match(stmt) and not stmt.endswith((".then(", ",")):
            findings.append(
                {
                    "file": filename,
                    "line": n,
                    "rule": "PW015",
                    "severity": "high",
                    "title": "page/locator action without await",
                    "fix": "add await: the action runs in the background and the next line races it "
                    "(failures surface later or not at all)",
                    "code": raw.strip()[:160],
                }
            )
        if LOGIN_RX.search(code) and ".fill(" in code:
            login_lines.append(n)
    if login_lines and not is_setup and "PW014" not in file_disabled:
        findings.append(
            {
                "file": filename,
                "line": login_lines[0],
                "rule": "PW014",
                "severity": "info",
                "title": "logs in through the UI inside a spec",
                "fix": "log in once in an auth.setup.ts project and reuse storageState "
                "(see references/auth.md)",
                "code": "",
            }
        )
    return findings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Find flakiness and maintainability problems in Playwright Test specs.",
        epilog="Example: spec_lint.py tests/e2e --fail-on medium --json",
    )
    p.add_argument("paths", nargs="*", default=["."], help="spec files or directories (default .)")
    p.add_argument("--fail-on", choices=SEVERITIES, default="medium", help="lowest severity that fails")
    p.add_argument("--min-severity", choices=SEVERITIES, default="info", help="lowest severity to show")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        files = iter_files(args.paths)
    except FileNotFoundError as exc:
        print(f"error: no such file or directory: {exc}", file=sys.stderr)
        return 2
    findings: list[dict] = []
    for f in files:
        try:
            findings += lint_text(f.read_text(encoding="utf-8", errors="replace"), str(f))
        except OSError as exc:
            print(f"error: {f}: {exc}", file=sys.stderr)
            return 2
    shown_min = SEVERITIES.index(args.min_severity)
    findings = [f for f in findings if SEVERITIES.index(f["severity"]) >= shown_min]
    findings.sort(key=lambda f: (-SEVERITIES.index(f["severity"]), f["file"], f["line"]))
    fail_idx = SEVERITIES.index(args.fail_on)
    failed = any(SEVERITIES.index(f["severity"]) >= fail_idx for f in findings)
    if args.json:
        counts: dict[str, int] = {}
        for f in findings:
            counts[f["severity"]] = counts.get(f["severity"], 0) + 1
        print(json.dumps({"files": len(files), "summary": counts, "findings": findings}, indent=2))
        return 1 if failed else 0
    for f in findings:
        print(f"{f['file']}:{f['line']}: [{f['severity'].upper()}] {f['rule']} {f['title']}")
        if f["code"]:
            print(f"    {f['code']}")
        print(f"    fix: {f['fix']}")
    print(f"\n{len(findings)} finding(s) in {len(files)} spec file(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
