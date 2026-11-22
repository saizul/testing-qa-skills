#!/usr/bin/env python3
"""Score feature risk areas and turn them into a prioritised test matrix.

Input: JSON (or CSV) describing the risk areas of a feature. Each area has either
direct scores or factor scores (all 1-5):

  {"feature": "Guest checkout",
   "areas": [
     {"name": "Card payment", "impact": 5, "likelihood": 4,
      "tests": ["unit", "integration", "e2e"], "notes": "3DS flow is new"},
     {"name": "Address form",
      "impact_factors": {"users": 4, "money": 2, "data": 3, "legal": 1, "reputation": 3},
      "likelihood_factors": {"complexity": 2, "change": 3, "history": 2, "dependencies": 1, "novelty": 1}}
   ]}

CSV columns: name,impact,likelihood,tests,notes (tests separated by ";").

impact     = the worst consequence (max of impact factors)
likelihood = the average of likelihood factors, rounded half up
risk       = impact x likelihood (1-25): high >= 15, medium >= 8, low < 8

Output: the areas sorted by risk with the recommended test depth per level, as a
Markdown table ready to paste into a test plan, or JSON. Gaps (high-risk areas with no
planned tests, or missing e2e/integration coverage) are listed.

Exit codes: 0 = no gaps, 1 = gaps found, 2 = invalid input.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
from pathlib import Path

LEVELS = [
    (
        15,
        "high",
        ["unit", "integration", "e2e"],
        "unit + integration + e2e happy path and key negatives; exploratory session; run on every PR",
    ),
    (
        8,
        "medium",
        ["unit", "integration"],
        "unit + integration of the main paths and boundaries; e2e only if user-facing",
    ),
    (1, "low", ["unit"], "unit tests or a checklist item; no dedicated e2e"),
]
IMPACT_KEYS = {"users", "money", "data", "security", "legal", "reputation", "operations"}
LIKELIHOOD_KEYS = {"complexity", "change", "history", "dependencies", "novelty", "usage", "team"}
KNOWN_TESTS = {
    "unit",
    "integration",
    "contract",
    "e2e",
    "exploratory",
    "performance",
    "security",
    "accessibility",
    "visual",
    "manual",
    "migration",
    "monitoring",
}


class InputError(ValueError):
    pass


def _score(value, field: str, area: str) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError) as exc:
        raise InputError(f"{area}: {field} must be an integer 1-5, got {value!r}") from exc
    if not 1 <= v <= 5:
        raise InputError(f"{area}: {field} must be 1-5, got {v}")
    return v


def evaluate_area(raw: dict) -> dict:
    name = str(raw.get("name") or "").strip()
    if not name:
        raise InputError("every area needs a name")
    if "impact" in raw and raw["impact"] not in (None, ""):
        impact = _score(raw["impact"], "impact", name)
        impact_basis = "direct"
    elif raw.get("impact_factors"):
        f = raw["impact_factors"]
        unknown = set(f) - IMPACT_KEYS
        if unknown:
            raise InputError(f"{name}: unknown impact factor(s) {sorted(unknown)}; use {sorted(IMPACT_KEYS)}")
        impact = max(_score(v, f"impact_factors.{k}", name) for k, v in f.items())
        impact_basis = "max(" + ", ".join(f"{k}={v}" for k, v in f.items()) + ")"
    else:
        raise InputError(f"{name}: give impact or impact_factors")
    if "likelihood" in raw and raw["likelihood"] not in (None, ""):
        likelihood = _score(raw["likelihood"], "likelihood", name)
        likelihood_basis = "direct"
    elif raw.get("likelihood_factors"):
        f = raw["likelihood_factors"]
        unknown = set(f) - LIKELIHOOD_KEYS
        if unknown:
            raise InputError(
                f"{name}: unknown likelihood factor(s) {sorted(unknown)}; use {sorted(LIKELIHOOD_KEYS)}"
            )
        vals = [_score(v, f"likelihood_factors.{k}", name) for k, v in f.items()]
        likelihood = int(math.floor(sum(vals) / len(vals) + 0.5))
        likelihood_basis = "mean(" + ", ".join(f"{k}={v}" for k, v in f.items()) + ")"
    else:
        raise InputError(f"{name}: give likelihood or likelihood_factors")
    risk = impact * likelihood
    _, level, recommended, depth = next(row for row in LEVELS if risk >= row[0])
    tests = raw.get("tests") or []
    if isinstance(tests, str):
        tests = [t.strip() for t in tests.replace(",", ";").split(";") if t.strip()]
    tests = [str(t).strip().lower() for t in tests]
    gaps = []
    if not tests:
        gaps.append("no tests planned")
    else:
        missing = [r for r in recommended if r not in tests]
        if missing and level != "low":
            gaps.append("missing " + ", ".join(missing))
    unknown_tests = [t for t in tests if t not in KNOWN_TESTS]
    return {
        "name": name,
        "impact": impact,
        "likelihood": likelihood,
        "risk": risk,
        "level": level,
        "impact_basis": impact_basis,
        "likelihood_basis": likelihood_basis,
        "tests": tests,
        "recommended": recommended,
        "depth": depth,
        "gaps": gaps,
        "unknown_test_types": unknown_tests,
        "notes": str(raw.get("notes") or ""),
    }


def load(path: str) -> dict:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InputError(f"invalid JSON: {exc}") from exc
        if isinstance(data, list):
            data = {"feature": "", "areas": data}
        return data
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows or "name" not in rows[0]:
        raise InputError("CSV needs a header row with at least name,impact,likelihood")
    return {"feature": "", "areas": rows}


def markdown(feature: str, areas: list[dict]) -> str:
    out = []
    if feature:
        out.append(f"### Risk matrix: {feature}\n")
    out.append("| # | Area | Impact | Likelihood | Risk | Level | Planned tests | Gaps |")
    out.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for i, a in enumerate(areas, 1):
        gaps = "; ".join(a["gaps"]) or "-"
        tests = ", ".join(a["tests"]) or "-"
        name = a["name"].replace("|", "\\|")
        out.append(
            f"| {i} | {name} | {a['impact']} | {a['likelihood']} | {a['risk']} | "
            f"{a['level']} | {tests} | {gaps} |"
        )
    out.append("")
    out.append("Test depth by level:")
    for _, level, _, depth in LEVELS:
        out.append(f"- **{level}**: {depth}")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Score feature risk areas and print a prioritised test matrix.",
        epilog="Example: risk_matrix.py risks.json > risk-matrix.md",
    )
    p.add_argument("input", help="JSON or CSV file with risk areas, or - for stdin")
    p.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    p.add_argument("--no-fail", action="store_true", help="exit 0 even when gaps are found")
    args = p.parse_args(argv)
    try:
        data = load(args.input)
        raw_areas = data.get("areas")
        if not isinstance(raw_areas, list) or not raw_areas:
            raise InputError("input needs a non-empty 'areas' list")
        areas = [evaluate_area(a) for a in raw_areas]
    except (InputError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    areas.sort(key=lambda a: (-a["risk"], -a["impact"], a["name"]))
    gaps = [a for a in areas if a["gaps"]]
    if args.json:
        counts = {lvl: sum(1 for a in areas if a["level"] == lvl) for _, lvl, _, _ in LEVELS}
        print(json.dumps({"feature": data.get("feature", ""), "levels": counts, "areas": areas}, indent=2))
    else:
        sys.stdout.write(markdown(str(data.get("feature") or ""), areas))
        if gaps:
            print("\nGaps to resolve before sign-off:")
            for a in gaps:
                print(f"- {a['name']} ({a['level']}, risk {a['risk']}): {'; '.join(a['gaps'])}")
    return 1 if gaps and not args.no_fail else 0


if __name__ == "__main__":
    sys.exit(main())
