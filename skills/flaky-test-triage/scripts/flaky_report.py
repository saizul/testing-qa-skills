#!/usr/bin/env python3
"""Rank flaky tests from JUnit XML reports of several runs of the same suite.

Each file (or each directory, with --run-per-dir) is one run, in the order given.
Works with JUnit XML from pytest, Jest (jest-junit), Vitest, PHPUnit, Playwright,
Maven Surefire/Gradle (including <flakyFailure> reruns) and most CI tools.

A test is classified per run as pass, fail, error or skip. Across runs it is:
  flaky       passed in some runs and failed in others with 2+ outcome flips,
              or passed only after a rerun inside one run (<flakyFailure>)
  regressed   passed, then failed consistently from some run on (one flip)
  fixed       failed, then passed consistently (one flip)
  broken      failed in every run where it ran
  stable      passed (or was skipped) in every run

Exit codes: 0 = nothing matching --fail-on, 1 = matching tests found, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

FAIL_TAGS = ("failure", "error")
RERUN_TAGS = ("flakyFailure", "flakyError")
CAUSE_HINTS = [
    ("timeout", re.compile(r"time(d)?\s?out|exceeded|deadline", re.I), "timing / slow dependency"),
    (
        "ui-wait",
        re.compile(r"waiting for (locator|selector)|not visible|detached|stale element|toBeVisible", re.I),
        "UI not ready: use web-first assertions instead of fixed waits",
    ),
    (
        "network",
        re.compile(r"ECONNREFUSED|ECONNRESET|connection (refused|reset)|socket hang up|EADDRINUSE", re.I),
        "network / port / service not ready",
    ),
    (
        "concurrency",
        re.compile(r"deadlock|lock wait|database is locked|race|concurrent", re.I),
        "shared state or parallel workers",
    ),
    (
        "ordering",
        re.compile(r"already exists|duplicate key|unique constraint|not empty", re.I),
        "test order / leftover data",
    ),
    (
        "time",
        re.compile(r"\b(date|timezone|tz|dst|midnight|clock)\b", re.I),
        "wall clock, timezone or date boundary",
    ),
    ("randomness", re.compile(r"\b(random|seed|shuffle)\b", re.I), "unseeded randomness"),
    ("memory", re.compile(r"out of memory|heap|OOM|MemoryError", re.I), "resource exhaustion"),
]


def _signature(message: str) -> str:
    """Normalise a failure message so the same root cause groups together."""
    msg = (message or "").strip().splitlines()[0] if message and message.strip() else ""
    msg = re.sub(r"0x[0-9a-fA-F]+", "<hex>", msg)
    msg = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<uuid>", msg)
    msg = re.sub(r"\d+(\.\d+)?", "N", msg)
    return msg[:160]


def _hint(text: str) -> list[str]:
    return [label for key, rx, label in CAUSE_HINTS if rx.search(text or "")]


def case_id(case: ET.Element) -> str:
    cls = case.get("classname") or case.get("class") or ""
    name = case.get("name") or "?"
    return f"{cls}::{name}" if cls else name


def parse_report(path: Path) -> dict[str, dict]:
    """Return {test_id: {"outcome", "time", "message", "rerun_flaky"}} for one file."""
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise ValueError(f"{path}: invalid XML: {exc}") from exc
    results: dict[str, dict] = {}
    for case in tree.getroot().iter("testcase"):
        tid = case_id(case)
        outcome, message, rerun = "pass", "", False
        for child in case:
            tag = child.tag
            if tag in FAIL_TAGS:
                outcome = "fail" if tag == "failure" else "error"
                message = child.get("message") or (child.text or "")
            elif tag == "skipped" and outcome == "pass":
                outcome = "skip"
            elif tag in RERUN_TAGS:
                rerun = True
                message = message or child.get("message") or (child.text or "")
        try:
            duration = float(case.get("time") or 0)
        except ValueError:
            duration = 0.0
        prev = results.get(tid)
        # The same id twice in one report (e.g. retries written as separate cases):
        # a pass after a failure means the test needed a retry -> flaky in this run.
        if prev is not None:
            if prev["outcome"] in ("fail", "error") and outcome == "pass":
                rerun, message = True, prev["message"]
            elif outcome in ("skip", "pass") and prev["outcome"] in ("fail", "error"):
                outcome, message = prev["outcome"], prev["message"]
            duration += prev["time"]
            rerun = rerun or prev["rerun_flaky"]
        results[tid] = {"outcome": outcome, "time": duration, "message": message, "rerun_flaky": rerun}
    return results


def collect_runs(paths: list[str], run_per_dir: bool) -> list[tuple[str, dict[str, dict]]]:
    runs: list[tuple[str, dict[str, dict]]] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files = sorted(p.rglob("*.xml"))
            if run_per_dir:
                merged: dict[str, dict] = {}
                for f in files:
                    merged.update(parse_report(f))
                runs.append((str(p), merged))
            else:
                runs.extend((str(f), parse_report(f)) for f in files)
        elif p.is_file():
            runs.append((str(p), parse_report(p)))
        else:
            raise ValueError(f"{raw}: no such file or directory")
    return runs


def analyse(runs: list[tuple[str, dict[str, dict]]], min_runs: int = 2) -> list[dict]:
    ids: list[str] = []
    seen = set()
    for _, res in runs:
        for tid in res:
            if tid not in seen:
                seen.add(tid)
                ids.append(tid)
    tests = []
    for tid in ids:
        seq = []  # outcomes in run order, skips and absences dropped
        times, messages, rerun_runs = [], [], 0
        for _, res in runs:
            r = res.get(tid)
            if r is None or r["outcome"] == "skip":
                continue
            failed = r["outcome"] in ("fail", "error")
            seq.append("F" if failed else "P")
            times.append(r["time"])
            if r["rerun_flaky"]:
                rerun_runs += 1
            if failed or r["rerun_flaky"]:
                messages.append(r["message"])
        n = len(seq)
        fails = seq.count("F")
        passes = n - fails
        flips = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
        if n == 0:
            status = "skipped"
        elif rerun_runs or (fails and passes and flips >= 2):
            status = "flaky"
        elif fails and passes and flips == 1:
            status = "regressed" if seq[0] == "P" else "fixed"
        elif fails == n:
            status = "broken"
        else:
            status = "stable"
        if status == "flaky" and n < min_runs and not rerun_runs:
            status = "insufficient-data"
        sigs: dict[str, int] = {}
        for m in messages:
            s = _signature(m)
            sigs[s] = sigs.get(s, 0) + 1
        top_sigs = sorted(sigs.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        joined = "\n".join(messages)
        fail_rate = fails / n if n else 0.0
        # 1.0 = fails half the time and flips every run; 0 = deterministic.
        flip_rate = flips / (n - 1) if n > 1 else 0.0
        score = round(
            (4 * fail_rate * (1 - fail_rate)) * 0.5 + flip_rate * 0.5 + (0.25 if rerun_runs else 0), 3
        )
        tests.append(
            {
                "id": tid,
                "status": status,
                "runs": n,
                "passes": passes,
                "failures": fails,
                "flips": flips,
                "rerun_flaky_runs": rerun_runs,
                "fail_rate": round(fail_rate, 3),
                "flakiness_score": score if status == "flaky" else 0.0,
                "pattern": "".join(seq),
                "mean_time": round(sum(times) / len(times), 3) if times else 0.0,
                "max_time": round(max(times), 3) if times else 0.0,
                "top_messages": [{"signature": s, "count": c} for s, c in top_sigs],
                "cause_hints": _hint(joined),
            }
        )
    order = {
        "flaky": 0,
        "regressed": 1,
        "broken": 2,
        "fixed": 3,
        "insufficient-data": 4,
        "stable": 5,
        "skipped": 6,
    }
    tests.sort(key=lambda t: (order[t["status"]], -t["flakiness_score"], -t["failures"], t["id"]))
    return tests


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Rank flaky tests from JUnit XML reports of several runs.",
        epilog="Example: flaky_report.py run1/junit.xml run2/junit.xml run3/junit.xml --top 10",
    )
    p.add_argument("reports", nargs="+", help="JUnit XML files or directories, one run each, oldest first")
    p.add_argument(
        "--run-per-dir", action="store_true", help="treat each directory (all *.xml inside) as one run"
    )
    p.add_argument("--min-runs", type=int, default=3, help="runs a test needs before it is called flaky")
    p.add_argument("--top", type=int, default=20, help="rows to print in text mode (default 20)")
    p.add_argument(
        "--fail-on",
        default="flaky",
        help="comma list of statuses that make the exit code 1: flaky,regressed,broken,any,none",
    )
    p.add_argument("--all", action="store_true", help="include stable tests in the output")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        runs = collect_runs(args.reports, args.run_per_dir)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not runs:
        print("error: no JUnit XML reports found", file=sys.stderr)
        return 2
    tests = analyse(runs, args.min_runs)
    counts: dict[str, int] = {}
    for t in tests:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    shown = tests if args.all else [t for t in tests if t["status"] not in ("stable", "skipped")]
    fail_on = {s.strip() for s in args.fail_on.split(",") if s.strip()}
    if "any" in fail_on:
        fail_on = {"flaky", "regressed", "broken"}
    hit = any(t["status"] in fail_on for t in tests)
    if args.json:
        out = {"runs": [name for name, _ in runs], "summary": counts, "tests": shown}
        print(json.dumps(out, indent=2))
        return 1 if hit else 0
    print(
        f"{len(runs)} runs, {len(tests)} tests: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
    )
    if not shown:
        print("No flaky, regressed or broken tests.")
    for t in shown[: args.top]:
        print(
            f"\n[{t['status'].upper()}] {t['id']}\n"
            f"  pattern {t['pattern'] or '-'}  ({t['failures']}/{t['runs']} failed, {t['flips']} flips"
            + (f", passed on rerun in {t['rerun_flaky_runs']} run(s)" if t["rerun_flaky_runs"] else "")
            + f")  score {t['flakiness_score']}  mean {t['mean_time']}s max {t['max_time']}s"
        )
        for m in t["top_messages"]:
            print(f"  {m['count']}x {m['signature']}")
        if t["cause_hints"]:
            print("  likely cause: " + "; ".join(t["cause_hints"]))
    if len(shown) > args.top:
        print(f"\n... {len(shown) - args.top} more (use --top or --json)")
    return 1 if hit else 0


if __name__ == "__main__":
    sys.exit(main())
