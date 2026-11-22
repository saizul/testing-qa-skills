#!/usr/bin/env python3
"""Summarise a mutation testing run and list the surviving mutants worth a test.

Input formats (auto-detected):
  mutation-testing-report-schema JSON   Stryker (JS/TS, C#, Scala) `json` reporter
                                        (reports/mutation/mutation.json), and any tool
                                        that writes the same schema
  Infection JSON log                    PHP Infection `logs.json` (infection-log.json)
  mutmut results text                   `mutmut results` output (mutmut 3: "name: status")

Mutation score = killed (incl. timeouts) / (killed + survived + no coverage).
Compile/runtime errors and ignored mutants are excluded, as Stryker does.

Exit codes: 0 = score >= --min-score (or no gate), 1 = below the gate, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DETECTED = {"Killed", "Timeout"}
UNDETECTED = {"Survived", "NoCoverage"}


def _empty_stats() -> dict:
    return {"killed": 0, "timeout": 0, "survived": 0, "no_coverage": 0, "errors": 0, "ignored": 0}


def _score(st: dict) -> float | None:
    valid = st["killed"] + st["timeout"] + st["survived"] + st["no_coverage"]
    if not valid:
        return None
    return round(100.0 * (st["killed"] + st["timeout"]) / valid, 2)


def _add(st: dict, status: str) -> None:
    key = {
        "Killed": "killed",
        "Timeout": "timeout",
        "Survived": "survived",
        "NoCoverage": "no_coverage",
        "CompileError": "errors",
        "RuntimeError": "errors",
        "Ignored": "ignored",
        "Pending": "ignored",
    }.get(status)
    if key:
        st[key] += 1


def parse_stryker(data: dict) -> tuple[dict, list[dict]]:
    files: dict[str, dict] = {}
    survivors: list[dict] = []
    for name, f in (data.get("files") or {}).items():
        st = files.setdefault(name, _empty_stats())
        source_lines = (f.get("source") or "").splitlines()
        for m in f.get("mutants") or []:
            status = m.get("status", "")
            _add(st, status)
            if status in UNDETECTED:
                line = ((m.get("location") or {}).get("start") or {}).get("line", 0)
                original = source_lines[line - 1].strip() if 0 < line <= len(source_lines) else ""
                survivors.append(
                    {
                        "file": name,
                        "line": line,
                        "status": "survived" if status == "Survived" else "no-coverage",
                        "mutator": m.get("mutatorName", ""),
                        "replacement": m.get("replacement", ""),
                        "original": original[:160],
                        "covered_by": len(m.get("coveredBy") or []),
                    }
                )
    return files, survivors


def parse_infection(data: dict) -> tuple[dict, list[dict]]:
    files: dict[str, dict] = {}
    survivors: list[dict] = []
    groups = [
        ("killed", "Killed"),
        ("timeouted", "Timeout"),
        ("escaped", "Survived"),
        ("uncovered", "NoCoverage"),
        ("errored", "RuntimeError"),
        ("syntaxErrors", "CompileError"),
        ("ignored", "Ignored"),
    ]
    for key, status in groups:
        for item in data.get(key) or []:
            mut = item.get("mutator") or {}
            name = mut.get("originalFilePath", "?")
            st = files.setdefault(name, _empty_stats())
            _add(st, status)
            if status in UNDETECTED:
                diff = item.get("diff") or ""
                removed = [
                    ln[1:].strip()
                    for ln in diff.splitlines()
                    if ln.startswith("-") and not ln.startswith("---")
                ]
                added = [
                    ln[1:].strip()
                    for ln in diff.splitlines()
                    if ln.startswith("+") and not ln.startswith("+++")
                ]
                survivors.append(
                    {
                        "file": name,
                        "line": mut.get("originalStartLine", 0),
                        "status": "survived" if status == "Survived" else "no-coverage",
                        "mutator": mut.get("mutatorName", ""),
                        "replacement": (added[0] if added else "")[:160],
                        "original": (removed[0] if removed else "")[:160],
                        "covered_by": None,
                    }
                )
    if not files and data.get("stats"):
        # Older logs may contain only stats: report totals without per-file detail.
        s = data["stats"]
        files["(all files)"] = {
            "killed": s.get("killedCount", 0),
            "timeout": s.get("timeOutCount", 0),
            "survived": s.get("escapedCount", 0),
            "no_coverage": s.get("notCoveredCount", 0),
            "errors": s.get("errorCount", 0) + s.get("syntaxErrorCount", 0),
            "ignored": s.get("ignoredCount", 0) + s.get("skippedCount", 0),
        }
    return files, survivors


MUTMUT_RX = re.compile(r"^\s*([\w.]+?)__mutmut_(\d+)\s*:\s*([a-z ]+?)\s*$")
MUTMUT_STATUS = {
    "killed": "Killed",
    "survived": "Survived",
    "no tests": "NoCoverage",
    "timeout": "Timeout",
    "suspicious": "Timeout",
    "skipped": "Ignored",
    "not checked": "Pending",
    "segfault": "RuntimeError",
    "caught by type check": "Killed",
}


def parse_mutmut(text: str) -> tuple[dict, list[dict]]:
    files: dict[str, dict] = {}
    survivors: list[dict] = []
    for line in text.splitlines():
        m = MUTMUT_RX.match(line)
        if not m:
            continue
        qual, num, raw_status = m.group(1), m.group(2), m.group(3).strip()
        status = MUTMUT_STATUS.get(raw_status)
        if status is None:
            continue
        # "pkg.module.x_func" -> module "pkg.module", function "func"
        module, _, func = qual.rpartition(".")
        func = re.sub("^x[\u01c1_]?", "", func).replace("\u01c1", ".")
        name = module or qual
        st = files.setdefault(name, _empty_stats())
        _add(st, status)
        if status in UNDETECTED:
            survivors.append(
                {
                    "file": name,
                    "line": 0,
                    "status": "survived" if status == "Survived" else "no-coverage",
                    "mutator": f"{func} #{num}",
                    "replacement": "",
                    "original": f"run: mutmut show {qual}__mutmut_{num}",
                    "covered_by": None,
                }
            )
    return files, survivors


def load(path: Path) -> tuple[str, dict, list[dict]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    stripped = text.lstrip()
    if stripped.startswith("{"):
        data = json.loads(text)
        if "files" in data and isinstance(data["files"], dict):
            return "stryker-schema", *parse_stryker(data)
        if "stats" in data or "escaped" in data or "killed" in data:
            return "infection", *parse_infection(data)
        raise ValueError(
            f"{path}: JSON is neither a mutation-testing-report-schema report nor an Infection log"
        )
    if MUTMUT_RX.search(text) or "__mutmut_" in text:
        return "mutmut", *parse_mutmut(text)
    raise ValueError(f"{path}: unknown format (expected Stryker/Infection JSON or `mutmut results` output)")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Summarise a mutation testing run and list surviving mutants.",
        epilog="Example: mutation_report.py reports/mutation/mutation.json --min-score 70 --top 15",
    )
    p.add_argument(
        "report", type=Path, help="mutation.json, infection log JSON, or a file with `mutmut results`"
    )
    p.add_argument("--min-score", type=float, help="exit 1 when the overall mutation score is lower")
    p.add_argument("--top", type=int, default=20, help="surviving mutants to print (default 20)")
    p.add_argument("--only", help="only files whose path contains this text")
    p.add_argument(
        "--no-coverage", action="store_true", help="also list NoCoverage mutants (default: survived only)"
    )
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        fmt, files, survivors = load(args.report)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.only:
        files = {k: v for k, v in files.items() if args.only in k}
        survivors = [s for s in survivors if args.only in s["file"]]
    total = _empty_stats()
    for st in files.values():
        for k in total:
            total[k] += st[k]
    score = _score(total)
    per_file = sorted(
        ({"file": k, **v, "score": _score(v)} for k, v in files.items()),
        key=lambda f: (f["score"] if f["score"] is not None else 101, -f["survived"], f["file"]),
    )
    listed = [s for s in survivors if args.no_coverage or s["status"] == "survived"]
    listed.sort(key=lambda s: (s["file"], s["line"]))
    failed = args.min_score is not None and (score is None or score < args.min_score)
    if args.json:
        print(
            json.dumps(
                {
                    "format": fmt,
                    "score": score,
                    "totals": total,
                    "files": per_file,
                    "survivors": listed,
                    "passed": not failed,
                },
                indent=2,
            )
        )
        return 1 if failed else 0
    print(
        f"Mutation score: {score if score is not None else 'n/a'}%  ({fmt}; "
        f"killed {total['killed']}, timeout {total['timeout']}, survived {total['survived']}, "
        f"no coverage {total['no_coverage']}, errors {total['errors']}, ignored {total['ignored']})"
    )
    print("\nWeakest files:")
    for f in per_file[:10]:
        sc = f"{f['score']}%" if f["score"] is not None else "n/a"
        print(f"  {sc:>7}  {f['file']}  (survived {f['survived']}, no coverage {f['no_coverage']})")
    if listed:
        print(f"\nSurviving mutants ({len(listed)}):")
        for s in listed[: args.top]:
            loc = f"{s['file']}:{s['line']}" if s["line"] else s["file"]
            change = (
                f"  `{s['original']}` -> `{s['replacement']}`" if s["replacement"] else f"  {s['original']}"
            )
            print(f"  [{s['status']}] {loc}  {s['mutator']}{change}")
        if len(listed) > args.top:
            print(f"  ... {len(listed) - args.top} more (use --top or --json)")
    if args.min_score is not None:
        print(f"\n{'FAIL' if failed else 'PASS'}: minimum score {args.min_score}%")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
