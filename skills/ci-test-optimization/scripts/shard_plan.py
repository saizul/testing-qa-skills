#!/usr/bin/env python3
"""Plan balanced CI test shards from JUnit XML timings.

Reads one or more JUnit XML reports (pytest, Jest/Vitest, PHPUnit, Playwright,
Surefire, Go via go-junit-report), sums durations per test file (or class, or test),
and assigns them to N shards with longest-processing-time-first bin packing, which is
within 4/3 of the optimal makespan. Unknown items (new files with no timing) get the
median duration so they are still distributed.

Typical use in CI (shard K of N, 1-based):
  pytest $(python3 shard_plan.py timings/*.xml --items tests.txt --shards 4 --shard 2 --format lines)

It also reports the total and slowest tests, the imbalance of the plan, and how many
shards you need to hit a wall-clock target (--target-minutes).

Exit codes: 0 = ok, 1 = plan imbalance above --max-imbalance, 2 = error.
"""

from __future__ import annotations

import argparse
import heapq
import json
import statistics
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _file_of(case: ET.Element, suite: ET.Element | None) -> str | None:
    for el in (case, suite):
        if el is not None and el.get("file"):
            return el.get("file").replace("\\", "/")
    return None


def read_timings(paths: list[Path], by: str) -> tuple[dict[str, float], list[tuple[str, float]]]:
    """Return ({item: seconds}, [(test id, seconds)]). Repeated reports are averaged."""
    per_report: list[dict[str, float]] = []
    tests: dict[str, float] = {}
    for path in paths:
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            raise ValueError(f"{path}: invalid XML: {exc}") from exc
        items: dict[str, float] = {}
        parents = {child: parent for parent in root.iter() for child in parent}
        for case in root.iter("testcase"):
            suite = parents.get(case)
            try:
                t = float(case.get("time") or 0)
            except ValueError:
                t = 0.0
            suite_name = suite.get("name") if suite is not None else ""
            cls = case.get("classname") or case.get("class") or suite_name or ""
            name = case.get("name") or "?"
            fname = _file_of(case, suite)
            if by == "file":
                key = fname or cls
            elif by == "class":
                key = cls or fname or name
            else:
                key = f"{fname or cls}::{name}"
            items[key] = items.get(key, 0.0) + t
            tid = f"{cls}::{name}"
            tests[tid] = max(tests.get(tid, 0.0), t)
        per_report.append(items)
    merged: dict[str, list[float]] = {}
    for rep in per_report:
        for k, v in rep.items():
            merged.setdefault(k, []).append(v)
    # The same item in several reports (several CI runs) -> mean; distinct shards'
    # reports normally contain disjoint items, so this is a plain union for them.
    timings = {k: sum(v) / len(v) for k, v in merged.items()}
    slowest = sorted(tests.items(), key=lambda kv: -kv[1])
    return timings, slowest


def plan(items: dict[str, float], shards: int) -> list[dict]:
    bins = [(0.0, i) for i in range(shards)]
    heapq.heapify(bins)
    assigned: list[list[str]] = [[] for _ in range(shards)]
    totals = [0.0] * shards
    for name, t in sorted(items.items(), key=lambda kv: (-kv[1], kv[0])):
        load, idx = heapq.heappop(bins)
        assigned[idx].append(name)
        totals[idx] = load + t
        heapq.heappush(bins, (totals[idx], idx))
    return [
        {
            "shard": i + 1,
            "seconds": round(totals[i], 2),
            "count": len(assigned[i]),
            "items": sorted(assigned[i]),
        }
        for i in range(shards)
    ]


def shards_for_target(items: dict[str, float], target_s: float, overhead_s: float, max_shards: int = 64):
    """Smallest shard count whose longest shard (+ overhead) fits the target, or None."""
    if not items or max(items.values()) + overhead_s > target_s:
        return None
    for n in range(1, max_shards + 1):
        if max(s["seconds"] for s in plan(items, n)) + overhead_s <= target_s:
            return n
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Plan balanced CI test shards from JUnit XML timings.",
        epilog="Example: shard_plan.py reports/*.xml --shards 4 --shard 1 --format lines",
    )
    p.add_argument("reports", nargs="+", type=Path, help="JUnit XML files with timings (any number)")
    p.add_argument("--by", choices=["file", "class", "test"], default="file", help="unit to distribute")
    p.add_argument("--shards", type=int, default=4, help="number of shards (default 4)")
    p.add_argument("--shard", type=int, help="print only this shard (1-based)")
    p.add_argument("--items", type=Path, help="file listing every current item (one per line)")
    p.add_argument("--strip-prefix", default="", help="prefix to remove from item names (e.g. /app/)")
    p.add_argument("--target-minutes", type=float, help="suggest the shard count for this wall-clock target")
    p.add_argument("--overhead-seconds", type=float, default=60, help="per-shard setup cost (default 60)")
    p.add_argument("--max-imbalance", type=float, help="exit 1 if (max-min)/mean shard time %% is higher")
    p.add_argument("--top", type=int, default=10, help="slowest tests to show (default 10)")
    p.add_argument("--format", choices=["text", "json", "lines"], default="text")
    p.add_argument("--json", action="store_true", help="same as --format json")
    args = p.parse_args(argv)
    if args.json:
        args.format = "json"
    if args.shards < 1 or (args.shard is not None and not 1 <= args.shard <= args.shards):
        print("error: need --shards >= 1 and 1 <= --shard <= --shards", file=sys.stderr)
        return 2
    try:
        missing = [str(r) for r in args.reports if not r.is_file()]
        if missing:
            raise ValueError(f"no such file: {', '.join(missing)}")
        timings, slowest = read_timings(args.reports, args.by)
        if args.strip_prefix:
            timings = {
                (k[len(args.strip_prefix) :] if k.startswith(args.strip_prefix) else k): v
                for k, v in timings.items()
            }
        unknown: list[str] = []
        removed = 0
        if args.items:
            wanted = [ln.strip() for ln in args.items.read_text(encoding="utf-8").splitlines() if ln.strip()]
            median = statistics.median(timings.values()) if timings else 1.0
            new = {}
            for w in wanted:
                if w in timings:
                    new[w] = timings[w]
                else:
                    new[w] = median
                    unknown.append(w)
            removed = len(set(timings) - set(wanted))
            timings = new
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not timings:
        print("error: no test timings found", file=sys.stderr)
        return 2
    shards = plan(timings, args.shards)
    loads = [s["seconds"] for s in shards]
    mean = sum(loads) / len(loads)
    imbalance = round(100.0 * (max(loads) - min(loads)) / mean, 1) if mean else 0.0
    result = {
        "by": args.by,
        "items": len(timings),
        "total_seconds": round(sum(timings.values()), 2),
        "shards": shards,
        "makespan_seconds": max(loads),
        "imbalance_pct": imbalance,
        "unknown_items": unknown,
        "dropped_items": removed,
        "slowest_tests": [{"test": t, "seconds": round(s, 2)} for t, s in slowest[: args.top]],
    }
    if args.target_minutes:
        result["suggested_shards"] = shards_for_target(
            timings, args.target_minutes * 60, args.overhead_seconds
        )
    failed = args.max_imbalance is not None and imbalance > args.max_imbalance
    if args.format == "lines":
        chosen = shards if args.shard is None else [shards[args.shard - 1]]
        for s in chosen:
            for item in s["items"]:
                print(item)
        return 1 if failed else 0
    if args.format == "json":
        if args.shard is not None:
            result["shards"] = [shards[args.shard - 1]]
        print(json.dumps(result, indent=2))
        return 1 if failed else 0
    print(
        f"{result['items']} {args.by} items, {result['total_seconds']}s total -> {args.shards} shards, "
        f"longest {result['makespan_seconds']}s, imbalance {imbalance}%"
    )
    for s in shards if args.shard is None else [shards[args.shard - 1]]:
        print(f"  shard {s['shard']}: {s['seconds']}s, {s['count']} items")
    if unknown:
        print(f"  {len(unknown)} item(s) without timing got the median duration")
    if "suggested_shards" in result:
        n = result["suggested_shards"]
        advice = (
            f"{n} shard(s)"
            if n
            else "not reachable by sharding; the slowest item alone takes "
            f"{max(timings.values()):.0f}s, split it"
        )
        print(f"Target {args.target_minutes} min with {args.overhead_seconds}s overhead per shard: {advice}")
    if slowest:
        print("Slowest tests:")
        for t in result["slowest_tests"]:
            print(f"  {t['seconds']:>8.2f}s  {t['test']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
