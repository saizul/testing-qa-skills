import json

import pytest

from conftest import FIXTURES, load_script, run_script

SKILL = "mutation-testing-guide"
SCRIPT = "mutation_report.py"
mod = load_script(SKILL, SCRIPT)
D = FIXTURES / SKILL


def report(name, *args):
    r = run_script(SKILL, SCRIPT, str(D / name), *args, "--json")
    assert r.returncode in (0, 1), r.stderr
    return r.returncode, json.loads(r.stdout)


def test_stryker_schema():
    _, data = report("mutation.json")
    assert data["format"] == "stryker-schema"
    assert data["score"] == 50.0
    assert data["totals"] == {
        "killed": 2,
        "timeout": 1,
        "survived": 2,
        "no_coverage": 1,
        "errors": 1,
        "ignored": 1,
    }
    assert [f["file"] for f in data["files"]] == ["src/report.js", "src/pricing.js"]
    s = data["survivors"]
    assert [x["status"] for x in s] == ["survived", "survived"]
    assert s[0] == {
        "file": "src/pricing.js",
        "line": 2,
        "status": "survived",
        "mutator": "EqualityOperator",
        "replacement": "total >= 100",
        "original": "if (total > 100) {",
        "covered_by": 1,
    }


def test_no_coverage_flag_lists_uncovered():
    _, data = report("mutation.json", "--no-coverage")
    assert any(x["status"] == "no-coverage" and x["covered_by"] == 0 for x in data["survivors"])


def test_infection_log():
    _, data = report("infection-log.json")
    assert data["format"] == "infection"
    assert data["score"] == 66.67
    assert data["survivors"][0]["original"] == "if ($qty > 10) {"
    assert data["survivors"][0]["replacement"] == "if ($qty >= 10) {"
    assert data["survivors"][0]["line"] == 14


def test_infection_stats_only(tmp_path):
    p = tmp_path / "log.json"
    p.write_text(
        json.dumps({"stats": {"killedCount": 8, "escapedCount": 2, "notCoveredCount": 0, "timeOutCount": 0}})
    )
    _, data = report_path(p)
    assert data["score"] == 80.0 and data["files"][0]["file"] == "(all files)"


def report_path(p, *args):
    r = run_script(SKILL, SCRIPT, str(p), *args, "--json")
    return r.returncode, json.loads(r.stdout)


def test_mutmut_results():
    _, data = report("mutmut-results.txt", "--no-coverage")
    assert data["format"] == "mutmut"
    assert data["score"] == 66.67
    assert data["totals"]["ignored"] == 1  # "not checked"
    names = [s["mutator"] for s in data["survivors"]]
    assert names == ["discount #2", "Cart.total #1"]
    assert data["survivors"][0]["original"] == "run: mutmut show shop.pricing.x_discount__mutmut_2"


@pytest.mark.parametrize(("gate", "code"), [("40", 0), ("70", 1)])
def test_min_score_gate(gate, code):
    r = run_script(SKILL, SCRIPT, str(D / "mutation.json"), "--min-score", gate)
    assert r.returncode == code
    assert ("PASS" if code == 0 else "FAIL") in r.stdout


def test_only_filter_and_text():
    code, data = report("mutation.json", "--only", "pricing")
    assert data["score"] == 75.0 and [f["file"] for f in data["files"]] == ["src/pricing.js"]
    r = run_script(SKILL, SCRIPT, str(D / "mutation.json"), "--top", "1")
    assert "Mutation score: 50.0%" in r.stdout and "... 1 more" in r.stdout


def test_score_helper():
    st = mod._empty_stats()
    assert mod._score(st) is None
    st.update(killed=3, survived=1)
    assert mod._score(st) == 75.0


def test_errors(tmp_path):
    junk = tmp_path / "x.txt"
    junk.write_text("nothing here")
    assert run_script(SKILL, SCRIPT, str(junk)).returncode == 2
    other = tmp_path / "x.json"
    other.write_text('{"hello": 1}')
    assert run_script(SKILL, SCRIPT, str(other)).returncode == 2
    assert run_script(SKILL, SCRIPT, str(tmp_path / "missing.json")).returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
