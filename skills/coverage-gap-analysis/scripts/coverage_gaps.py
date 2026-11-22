#!/usr/bin/env python3
"""List changed source lines and files that no test covers (diff coverage).

Reads a coverage report and a unified diff, then reports for every changed source
file: changed executable lines, which of them are uncovered, and files that are not
in the coverage report at all (never imported or loaded by any test).

Coverage formats (auto-detected):
  Cobertura XML   coverage.py `coverage xml`, Jest/Vitest/c8/nyc `cobertura`, PHPUnit
                  `--coverage-cobertura`, JaCoCo converters, .NET coverlet
  LCOV            `lcov.info` from Jest/Vitest/c8/nyc/istanbul, genhtml inputs
  Clover XML      PHPUnit `--coverage-clover`, istanbul `clover`
  coverage.py JSON `coverage json`

Diff sources: --diff FILE (or - for stdin), or --base REF to run
`git diff --unified=0 --no-color REF...HEAD` (read-only) in --repo.

Exit codes: 0 = ok, 1 = diff coverage below --fail-under or untested files with
--fail-on-untested, 2 = error.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

DEFAULT_INCLUDE = [
    "*.py",
    "*.js",
    "*.jsx",
    "*.mjs",
    "*.cjs",
    "*.ts",
    "*.tsx",
    "*.mts",
    "*.cts",
    "*.vue",
    "*.svelte",
    "*.php",
    "*.go",
    "*.rb",
    "*.java",
    "*.kt",
    "*.cs",
    "*.rs",
]
DEFAULT_EXCLUDE = [
    "test/*",
    "tests/*",
    "*/test/*",
    "*/tests/*",
    "__tests__/*",
    "*/__tests__/*",
    "test_*.py",
    "*/test_*.py",
    "*_test.py",
    "*_test.go",
    "*.test.*",
    "*.spec.*",
    "*Test.php",
    "conftest.py",
    "*/conftest.py",
    "e2e/*",
    "*/e2e/*",
    "*.d.ts",
    "*/migrations/*",
    "docs/*",
]

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


# ---------------------------------------------------------------- coverage parsers


def _norm(path: str) -> str:
    return str(PurePosixPath(path.replace("\\", "/")))


def parse_cobertura(root: ET.Element) -> dict[str, dict[int, int]]:
    sources = [_norm(s.text.strip()) for s in root.iter("source") if s.text and s.text.strip()]
    files: dict[str, dict[int, int]] = {}
    for cls in root.iter("class"):
        fname = cls.get("filename")
        if not fname:
            continue
        lines = files.setdefault(_norm(fname), {})
        for line in cls.iter("line"):
            try:
                num, hits = int(line.get("number", "0")), int(float(line.get("hits", "0")))
            except ValueError:
                continue
            lines[num] = max(lines.get(num, 0), hits)
    # Cobertura filenames are relative to a <source> root. Add the joined form too so
    # absolute <source> paths can be matched by suffix against repository paths.
    for path in list(files):
        for src in sources:
            full = _norm(str(PurePosixPath(src) / path))
            if full != path and full not in files:
                files[full] = files[path]
    return files


def parse_clover(root: ET.Element) -> dict[str, dict[int, int]]:
    files: dict[str, dict[int, int]] = {}
    for f in root.iter("file"):
        name = f.get("path") or f.get("name")
        if not name:
            continue
        lines = files.setdefault(_norm(name), {})
        for line in f.iter("line"):
            if line.get("type") not in (None, "stmt", "cond"):
                continue  # "method" lines duplicate a statement line
            try:
                num, hits = int(line.get("num", "0")), int(line.get("count", "0"))
            except ValueError:
                continue
            lines[num] = max(lines.get(num, 0), hits)
    return files


def parse_lcov(text: str) -> dict[str, dict[int, int]]:
    files: dict[str, dict[int, int]] = {}
    current: dict[int, int] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("SF:"):
            current = files.setdefault(_norm(line[3:]), {})
        elif line.startswith("DA:") and current is not None:
            parts = line[3:].split(",")
            try:
                num, hits = int(parts[0]), int(float(parts[1]))
            except (ValueError, IndexError):
                continue
            current[num] = max(current.get(num, 0), hits)
        elif line == "end_of_record":
            current = None
    return files


def parse_coverage_json(data: dict) -> dict[str, dict[int, int]]:
    files: dict[str, dict[int, int]] = {}
    for name, info in (data.get("files") or {}).items():
        lines = {n: 1 for n in info.get("executed_lines", [])}
        for n in info.get("missing_lines", []):
            lines.setdefault(n, 0)
        files[_norm(name)] = lines
    return files


def load_coverage(path: Path) -> tuple[str, dict[str, dict[int, int]]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    head = text.lstrip()[:2000]
    if head.startswith("{"):
        try:
            return "coverage.py-json", parse_coverage_json(json.loads(text))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: invalid JSON: {exc}") from exc
    if head.startswith("<"):
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            raise ValueError(f"{path}: invalid XML: {exc}") from exc
        if root.find(".//packages") is not None or root.find(".//class") is not None:
            return "cobertura", parse_cobertura(root)
        if root.find(".//project") is not None or root.find(".//file") is not None:
            return "clover", parse_clover(root)
        raise ValueError(f"{path}: XML is neither Cobertura nor Clover")
    if re.search(r"^(TN|SF):", text, re.M):
        return "lcov", parse_lcov(text)
    raise ValueError(
        f"{path}: unknown coverage format (expected Cobertura, Clover, LCOV or coverage.py JSON)"
    )


# ---------------------------------------------------------------- diff


def parse_diff(text: str) -> dict[str, set[int]]:
    """Return {path: set of added/changed line numbers in the new file}."""
    changed: dict[str, set[int]] = {}
    current: set[int] | None = None
    new_line = 0
    for raw in text.splitlines():
        if raw.startswith("+++ "):
            target = raw[4:].split("\t", 1)[0].strip()
            if target == "/dev/null":
                current = None
                continue
            if target.startswith("b/"):
                target = target[2:]
            current = changed.setdefault(_norm(target), set())
            continue
        if raw.startswith("--- ") or raw.startswith("diff --git"):
            continue
        m = HUNK_RE.match(raw)
        if m:
            new_line = int(m.group(1))
            continue
        if current is None or not raw:
            continue
        if raw.startswith("+"):
            current.add(new_line)
            new_line += 1
        elif raw.startswith(" "):
            new_line += 1
        # "-" lines and "\ No newline" do not advance the new-file counter
    return changed


def git_diff(repo: Path, base: str) -> str:
    if base.startswith("-"):
        raise ValueError("--base must be a git ref, not an option")
    cmd = ["git", "-C", str(repo), "diff", "--unified=0", "--no-color", "--no-ext-diff", f"{base}...HEAD"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise ValueError(f"git diff failed: {proc.stderr.strip()}")
    return proc.stdout


# ---------------------------------------------------------------- matching


def match_file(changed: str, coverage: dict[str, dict[int, int]], strip: list[str]) -> str | None:
    if changed in coverage:
        return changed
    parts = PurePosixPath(changed).parts
    best, best_len = None, 0
    for cov_path in coverage:
        cand = cov_path
        for prefix in strip:
            if cand.startswith(prefix):
                cand = cand[len(prefix) :].lstrip("/")
        if cand == changed:
            return cov_path
        cparts = PurePosixPath(cand).parts
        n = 0
        while n < min(len(parts), len(cparts)) and parts[-1 - n] == cparts[-1 - n]:
            n += 1
        # Require the whole changed path to match the end of the coverage path
        # (absolute paths in reports) or vice versa (report relative to a source dir).
        if n == len(parts) or (n == len(cparts) and n >= 2):
            if n > best_len:
                best, best_len = cov_path, n
    return best


def _globmatch(path: str, patterns: list[str]) -> bool:
    name = PurePosixPath(path).name
    return any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch(name, p) for p in patterns)


def ranges(nums: list[int]) -> str:
    out = []
    start = prev = None
    for n in sorted(nums):
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append(f"{start}" if start == prev else f"{start}-{prev}")
            start = prev = n
    if start is not None:
        out.append(f"{start}" if start == prev else f"{start}-{prev}")
    return ",".join(out)


def analyse(
    coverage: dict[str, dict[int, int]],
    changed: dict[str, set[int]],
    include: list[str],
    exclude: list[str],
    strip: list[str],
    *,
    count_missing: bool = False,
) -> dict:
    files = []
    total_exec = total_cov = 0
    for path in sorted(changed):
        lines = changed[path]
        if not lines or not _globmatch(path, include) or _globmatch(path, exclude):
            continue
        cov_path = match_file(path, coverage, strip)
        if cov_path is None:
            if count_missing:
                total_exec += len(lines)
            files.append(
                {
                    "file": path,
                    "status": "not-in-report",
                    "changed_lines": len(lines),
                    "executable": None,
                    "covered": 0,
                    "uncovered_lines": ranges(sorted(lines)),
                    "diff_coverage": 0.0,
                }
            )
            continue
        data = coverage[cov_path]
        executable = sorted(n for n in lines if n in data)
        covered = [n for n in executable if data[n] > 0]
        uncovered = [n for n in executable if data[n] == 0]
        total_exec += len(executable)
        total_cov += len(covered)
        if not executable:
            status = "no-executable-changes"
        elif not covered:
            status = "untested"
        elif uncovered:
            status = "partial"
        else:
            status = "covered"
        files.append(
            {
                "file": path,
                "report_path": cov_path,
                "status": status,
                "changed_lines": len(lines),
                "executable": len(executable),
                "covered": len(covered),
                "uncovered_lines": ranges(uncovered),
                "diff_coverage": round(100.0 * len(covered) / len(executable), 1) if executable else 100.0,
                "file_coverage": round(100.0 * sum(1 for h in data.values() if h > 0) / len(data), 1)
                if data
                else 0.0,
            }
        )
    # Files absent from the report have no executable-line data. They are listed as
    # untested and only count against the percentage with --count-missing.
    pct = round(100.0 * total_cov / total_exec, 1) if total_exec else 100.0
    order = {"not-in-report": 0, "untested": 1, "partial": 2, "covered": 3, "no-executable-changes": 4}
    files.sort(key=lambda f: (order[f["status"]], -(f["executable"] or f["changed_lines"]), f["file"]))
    return {
        "diff_coverage": pct,
        "changed_executable_lines": total_exec,
        "covered_lines": total_cov,
        "untested_files": [f["file"] for f in files if f["status"] in ("not-in-report", "untested")],
        "files": files,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="List changed source lines and files that no test covers.",
        epilog="Example: coverage_gaps.py --coverage coverage.xml --base origin/main --fail-under 80",
    )
    p.add_argument(
        "--coverage", required=True, type=Path, help="Cobertura/Clover XML, lcov.info or coverage.json"
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--diff", help="unified diff file, or - for stdin (git diff -U0 works best)")
    src.add_argument("--base", help="git ref to diff against, e.g. origin/main (runs git diff, read-only)")
    p.add_argument("--repo", type=Path, default=Path("."), help="repository for --base (default .)")
    p.add_argument("--include", action="append", help="glob of source files to check (repeatable)")
    p.add_argument("--exclude", action="append", help="extra glob to ignore (repeatable, added to defaults)")
    p.add_argument("--no-default-excludes", action="store_true", help="do not ignore test files and docs")
    p.add_argument("--strip-prefix", action="append", default=[], help="prefix to drop from report paths")
    p.add_argument("--fail-under", type=float, help="exit 1 when diff coverage %% is below this")
    p.add_argument(
        "--count-missing",
        action="store_true",
        help="count every changed line of files missing from the report as uncovered",
    )
    p.add_argument(
        "--fail-on-untested", action="store_true", help="exit 1 when a changed file has no coverage"
    )
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        fmt, coverage = load_coverage(args.coverage)
        if args.diff == "-":
            diff_text = sys.stdin.read()
        elif args.diff:
            diff_text = Path(args.diff).read_text(encoding="utf-8", errors="replace")
        else:
            diff_text = git_diff(args.repo, args.base)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    include = args.include or DEFAULT_INCLUDE
    exclude = ([] if args.no_default_excludes else DEFAULT_EXCLUDE) + (args.exclude or [])
    result = analyse(
        coverage, parse_diff(diff_text), include, exclude, args.strip_prefix, count_missing=args.count_missing
    )
    result["format"] = fmt
    failed = False
    if args.fail_under is not None and result["diff_coverage"] < args.fail_under:
        failed = True
    if args.fail_on_untested and result["untested_files"]:
        failed = True
    result["passed"] = not failed
    if args.json:
        print(json.dumps(result, indent=2))
        return 1 if failed else 0
    print(
        f"Diff coverage: {result['diff_coverage']}% "
        f"({result['covered_lines']}/{result['changed_executable_lines']} changed executable lines, "
        f"{fmt} report)"
    )
    if not result["files"]:
        print("No changed source files matched (check --include / --exclude).")
    labels = {
        "not-in-report": "NOT IN REPORT",
        "untested": "UNTESTED",
        "partial": "PARTIAL",
        "covered": "covered",
        "no-executable-changes": "no executable changes",
    }
    for f in result["files"]:
        line = f"  [{labels[f['status']]}] {f['file']}"
        if f["status"] == "not-in-report":
            line += f"  {f['changed_lines']} changed lines; no test loads this file"
        elif f["executable"]:
            line += f"  {f['covered']}/{f['executable']} covered ({f['diff_coverage']}%)"
            if f["uncovered_lines"]:
                line += f"  uncovered: {f['uncovered_lines']}"
        print(line)
    missing = [f for f in result["files"] if f["status"] == "not-in-report"]
    if missing and not args.count_missing:
        print(f"Note: {len(missing)} changed file(s) are not in the report and not counted in the %.")
    if args.fail_under is not None:
        verdict = "PASS" if result["diff_coverage"] >= args.fail_under else "FAIL"
        print(f"{verdict}: threshold {args.fail_under}%")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
