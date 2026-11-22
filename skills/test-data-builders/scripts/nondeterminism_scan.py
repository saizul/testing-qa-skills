#!/usr/bin/env python3
"""Find sources of non-deterministic test data: unseeded randomness, wall-clock time,
random UUIDs and unseeded Faker, in Python, JS/TS and PHP test code and fixtures.

A finding is suppressed when the same file also pins the source, for example
random.seed(...), Faker.seed(...)/fake.seed_instance(...), faker.seed(...),
vi.useFakeTimers()/jest.useFakeTimers()/vi.setSystemTime(), freezegun/time-machine,
Carbon::setTestNow(), mt_srand(...). Use --no-suppress to list everything.

Silence a line with a trailing comment containing: nondeterminism: ok

Exit codes: 0 = clean, 1 = findings, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts", ".php"}
SKIP_DIRS = {"node_modules", ".git", "vendor", ".venv", "venv", "dist", "build", "__pycache__", "coverage"}

# (id, languages, pattern, title, fix, suppressed-by pattern or None)
RULES = [
    (
        "ND001",
        "py",
        r"\brandom\.(random|randint|choice|choices|shuffle|sample|uniform|randrange)\s*\(",
        "unseeded random module",
        "use random.Random(SEED) passed into the code, or seed in a fixture",
        r"\brandom\.seed\s*\(|random\.Random\s*\(\s*\w",
    ),
    (
        "ND002",
        "py",
        r"\b(datetime\.(now|utcnow|today)|date\.today|time\.time)\s*\(",
        "wall-clock time",
        "inject a clock or freeze time (freezegun / time-machine); build dates from a fixed epoch",
        r"freeze_time|freezegun|time_machine|travel\s*\(",
    ),
    (
        "ND003",
        "py",
        r"\buuid\.uuid[14]\s*\(",
        "random UUID",
        "derive ids from a sequence: uuid.UUID(int=n) or a fixed string",
        None,
    ),
    (
        "ND004",
        "py",
        r"\bFaker\s*\(",
        "Faker without a seed",
        "call Faker.seed(1234) once (conftest) or fake.seed_instance(1234)",
        r"\bFaker\.seed\s*\(|seed_instance\s*\(|faker_seed",
    ),
    (
        "ND005",
        "js",
        r"\bMath\.random\s*\(",
        "Math.random",
        "pass a seeded PRNG into the code, or stub it: vi.spyOn(Math, 'random').mockReturnValue(0.5)",
        r"spyOn\s*\(\s*(global\.)?Math\s*,\s*['\"]random",
    ),
    (
        "ND006",
        "js",
        r"\bDate\.now\s*\(|\bnew\s+Date\s*\(\s*\)",
        "wall-clock time",
        "use vi.useFakeTimers() + vi.setSystemTime(new Date('2024-01-01T00:00:00Z')) or inject a clock",
        r"useFakeTimers\s*\(|setSystemTime\s*\(|page\.clock\.",
    ),
    (
        "ND007",
        "js",
        r"\bcrypto\.randomUUID\s*\(|\buuidv4\s*\(|\bv4\s*\(\s*\)|\bnanoid\s*\(",
        "random id",
        "build ids from a sequence in the builder",
        None,
    ),
    (
        "ND008",
        "js",
        r"\bfaker\.[a-z]+\.[a-zA-Z]+\s*\(",
        "@faker-js/faker without a seed",
        "call faker.seed(1234) in a setup file, or prefer explicit values for fields the test asserts on",
        r"\bfaker\.seed\s*\(",
    ),
    (
        "ND009",
        "php",
        r"\b(rand|mt_rand|random_int|array_rand|shuffle|str_shuffle|uniqid)\s*\(",
        "unseeded randomness",
        "use a fixed value or seed with mt_srand(1234) / Faker's ->seed(1234)",
        r"\bmt_srand\s*\(|\bsrand\s*\(|->seed\s*\(",
    ),
    (
        "ND010",
        "php",
        r"\btime\s*\(\s*\)|\bmicrotime\s*\(|\bdate\s*\(\s*['\"][^'\"]*['\"]\s*\)|"
        r"\bnew\s+\\?DateTime(Immutable)?\s*\(\s*\)|(?<![\w>:])now\s*\(\s*\)|Carbon::now\s*\(",
        "wall-clock time",
        "freeze time: Carbon::setTestNow('2024-01-01'), $this->travelTo(...), or inject a ClockInterface",
        r"setTestNow\s*\(|travelTo\s*\(|freezeTime\s*\(|MockClock",
    ),
    (
        "ND011",
        "php",
        r"\$this->faker->|\bfake\s*\(\s*\)->|Factory::create\s*\(",
        "Faker without a seed",
        "call $this->faker->seed(1234) in setUp, or set explicit values for asserted fields",
        r"->seed\s*\(",
    ),
]

LANG = {".py": "py", ".php": "php"}
IGNORE = re.compile(r"nondeterminism:\s*ok")


def lang_of(path: Path) -> str:
    return LANG.get(path.suffix, "js")


def scan_text(text: str, filename: str, lang: str, suppress: bool = True) -> list[dict]:
    out = []
    lines = text.splitlines()
    comment = "#" if lang == "py" else "//"
    for rule_id, rlang, pattern, title, fix, pinned in RULES:
        if rlang != lang:
            continue
        if suppress and pinned and re.search(pinned, text):
            continue
        rx = re.compile(pattern)
        for n, line in enumerate(lines, 1):
            code = line.split(comment, 1)[0] if comment in line else line
            if lang == "py":
                code = re.sub(r"(['\"]).*?\1", "''", code)
            if rx.search(code) and not IGNORE.search(line):
                out.append(
                    {
                        "file": filename,
                        "line": n,
                        "rule": rule_id,
                        "title": title,
                        "fix": fix,
                        "code": line.strip()[:160],
                    }
                )
    out.sort(key=lambda f: (f["file"], f["line"], f["rule"]))
    return out


def iter_files(paths: list[str]) -> list[Path]:
    files = []
    for raw in paths:
        p = Path(raw)
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files += [
                f
                for f in sorted(p.rglob("*"))
                if f.is_file() and f.suffix in EXTS and not any(x in SKIP_DIRS for x in f.parts)
            ]
        else:
            raise FileNotFoundError(raw)
    return files


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Find unseeded randomness, wall-clock time and random ids in tests and fixtures.",
        epilog="Example: nondeterminism_scan.py tests/ database/factories --json",
    )
    p.add_argument("paths", nargs="*", default=["tests"], help="files or directories (default tests)")
    p.add_argument("--no-suppress", action="store_true", help="report even when the file seeds/freezes")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        files = iter_files(args.paths)
        findings = []
        for f in files:
            text = f.read_text(encoding="utf-8", errors="replace")
            findings += scan_text(text, str(f), lang_of(f), suppress=not args.no_suppress)
    except (FileNotFoundError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"files": len(files), "findings": findings}, indent=2))
        return 1 if findings else 0
    for f in findings:
        print(f"{f['file']}:{f['line']}: {f['rule']} {f['title']}\n    {f['code']}\n    fix: {f['fix']}")
    print(f"\n{len(findings)} finding(s) in {len(files)} file(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
