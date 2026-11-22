import json

import pytest

from conftest import FIXTURES, load_script, run_script

SKILL = "test-plan-writer"
SCRIPT = "risk_matrix.py"
mod = load_script(SKILL, SCRIPT)
D = FIXTURES / SKILL


def matrix(name, *args):
    r = run_script(SKILL, SCRIPT, str(D / name), *args, "--json")
    assert r.returncode in (0, 1), r.stderr
    return r.returncode, json.loads(r.stdout)


def test_scores_sorting_and_gaps():
    code, data = matrix("checkout-risks.json")
    assert code == 1
    assert data["levels"] == {"high": 2, "medium": 2, "low": 1}
    names = [a["name"] for a in data["areas"]]
    assert names[0] == "Card payment and 3-D Secure" and names[-1] == "Address autocomplete"
    by = {a["name"]: a for a in data["areas"]}
    assert by["Order total and tax rounding"]["gaps"] == ["missing integration, e2e"]
    assert by["Guest email capture"]["impact"] == 4  # max of factors
    assert by["Guest email capture"]["likelihood"] == 2  # mean 2.0
    assert by["Guest email capture"]["gaps"] == ["no tests planned"]
    assert by["Card payment and 3-D Secure"]["gaps"] == []


def test_markdown_output():
    r = run_script(SKILL, SCRIPT, str(D / "checkout-risks.json"))
    assert r.returncode == 1
    assert r.stdout.startswith("### Risk matrix: Guest checkout with saved cards")
    assert "| 1 | Card payment and 3-D Secure | 5 | 4 | 20 | high |" in r.stdout
    assert "Gaps to resolve before sign-off:" in r.stdout


def test_csv_input_no_gaps():
    code, data = matrix("risks.csv")
    assert code == 0
    assert [a["risk"] for a in data["areas"]] == [16, 4]
    assert data["areas"][0]["tests"] == ["unit", "integration", "e2e"]


def test_no_fail_flag():
    assert run_script(SKILL, SCRIPT, str(D / "checkout-risks.json"), "--no-fail").returncode == 0


@pytest.mark.parametrize(
    ("area", "message"),
    [
        ({"name": "x", "impact": 7, "likelihood": 1}, "impact must be 1-5"),
        ({"name": "x", "likelihood": 1}, "give impact or impact_factors"),
        ({"name": "x", "impact": 2}, "give likelihood or likelihood_factors"),
        ({"name": "x", "impact_factors": {"vibes": 3}, "likelihood": 1}, "unknown impact factor"),
        ({"impact": 1, "likelihood": 1}, "every area needs a name"),
        ({"name": "x", "impact": "high", "likelihood": 1}, "must be an integer"),
    ],
)
def test_validation_errors(area, message):
    with pytest.raises(mod.InputError, match=message):
        mod.evaluate_area(area)


def test_rounding_half_up_and_levels():
    a = mod.evaluate_area({"name": "x", "impact": 3, "likelihood_factors": {"complexity": 2, "change": 3}})
    assert a["likelihood"] == 3 and a["risk"] == 9 and a["level"] == "medium"
    low = mod.evaluate_area({"name": "y", "impact": 1, "likelihood": 1, "tests": "unit"})
    assert low["level"] == "low" and low["gaps"] == []


def test_stdin_list_and_errors(tmp_path):
    r = run_script(
        SKILL,
        SCRIPT,
        "-",
        "--json",
        stdin='[{"name": "a", "impact": 5, "likelihood": 5, "tests": ["unit", "integration", "e2e"]}]',
    )
    assert r.returncode == 0 and json.loads(r.stdout)["areas"][0]["level"] == "high"
    assert run_script(SKILL, SCRIPT, str(D / "invalid.json")).returncode == 2
    empty = tmp_path / "e.json"
    empty.write_text('{"areas": []}')
    assert run_script(SKILL, SCRIPT, str(empty)).returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
