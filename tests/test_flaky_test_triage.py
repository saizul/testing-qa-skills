import json

from conftest import FIXTURES, load_script, run_script

SKILL = "flaky-test-triage"
SCRIPT = "flaky_report.py"
mod = load_script(SKILL, SCRIPT)
D = FIXTURES / SKILL
RUNS = [str(D / f"run{i}.xml") for i in range(1, 6)]


def report(*args):
    r = run_script(SKILL, SCRIPT, *args, "--json")
    assert r.returncode in (0, 1), r.stderr
    return r.returncode, json.loads(r.stdout)


def by_id(data):
    return {t["id"]: t for t in data["tests"]}


def test_classifies_five_runs():
    code, data = report(*RUNS, "--all")
    assert code == 1
    assert data["summary"] == {"flaky": 2, "stable": 1, "regressed": 1, "broken": 1, "fixed": 1, "skipped": 1}
    t = by_id(data)
    pay = t["tests.test_checkout::test_pay_with_card"]
    assert pay["status"] == "flaky" and pay["pattern"] == "PFPFP" and pay["flips"] == 4
    assert pay["cause_hints"] == ["timing / slow dependency"]
    assert pay["top_messages"][0] == {
        "signature": "TimeoutError: timed out after Nms waiting for gateway <hex>",
        "count": 2,
    }
    assert t["tests.test_users::test_signup"]["status"] == "regressed"
    assert t["tests.test_reports::test_export"]["status"] == "fixed"
    assert t["tests.test_users::test_legacy_import"]["status"] == "broken"
    assert t["tests.test_users::test_optional"]["status"] == "skipped"


def test_flaky_ranked_first_by_score():
    _, data = report(*RUNS)
    assert [x["id"] for x in data["tests"][:2]] == [
        "tests.test_checkout::test_pay_with_card",
        "tests.test_search::test_autocomplete",
    ]
    assert data["tests"][0]["flakiness_score"] > data["tests"][1]["flakiness_score"]
    assert all(x["status"] != "stable" for x in data["tests"])


def test_rerun_elements_and_duplicate_cases_count_as_flaky():
    code, data = report(str(D / "surefire-rerun.xml"), str(D / "phpunit.xml"))
    t = by_id(data)
    assert t["com.example.CartTest::addsItem"]["status"] == "flaky"
    assert t["com.example.CartTest::addsItem"]["rerun_flaky_runs"] == 1
    retried = t["Tests.Unit.MailerTest::testRetries"]
    assert retried["status"] == "flaky"
    assert "network / port / service not ready" in retried["cause_hints"]
    assert code == 1


def test_min_runs_marks_insufficient_data():
    _, data = report(*RUNS[:2], "--min-runs", "3", "--all")
    statuses = {x["status"] for x in data["tests"]}
    assert "flaky" not in statuses


def test_fail_on_controls_exit_code():
    assert run_script(SKILL, SCRIPT, *RUNS, "--fail-on", "none").returncode == 0
    assert run_script(SKILL, SCRIPT, *RUNS, "--fail-on", "broken").returncode == 1
    stable_only = [str(D / "run1.xml")]
    assert run_script(SKILL, SCRIPT, *stable_only, "--fail-on", "any").returncode == 1  # broken in run 1


def test_directory_input_and_run_per_dir(tmp_path):
    for i in range(1, 4):
        d = tmp_path / f"run{i}"
        d.mkdir()
        (d / "junit.xml").write_text((D / f"run{i}.xml").read_text())
    _, data = report(str(tmp_path), "--run-per-dir")
    assert len(data["runs"]) == 1  # the parent dir is one run
    _, data = report(*(str(tmp_path / f"run{i}") for i in range(1, 4)), "--run-per-dir")
    assert len(data["runs"]) == 3


def test_text_output():
    r = run_script(SKILL, SCRIPT, *RUNS, "--top", "1")
    assert r.returncode == 1
    assert "[FLAKY] tests.test_checkout::test_pay_with_card" in r.stdout
    assert "likely cause: timing / slow dependency" in r.stdout
    assert "more (use --top or --json)" in r.stdout


def test_errors_exit_2(tmp_path):
    assert run_script(SKILL, SCRIPT, str(D / "broken.xml")).returncode == 2
    assert run_script(SKILL, SCRIPT, str(tmp_path / "missing.xml")).returncode == 2
    assert run_script(SKILL, SCRIPT, str(tmp_path)).returncode == 2  # empty dir


def test_signature_normalisation():
    assert mod._signature("took 1234ms at 0xdeadbeef id 3f2b8c1e-9a4d-4e2b-8f1a-2c3d4e5f6a7b") == (
        "took Nms at <hex> id <uuid>"
    )
    assert mod._signature("") == ""


def test_help():
    r = run_script(SKILL, SCRIPT, "--help")
    assert r.returncode == 0 and "JUnit" in r.stdout
