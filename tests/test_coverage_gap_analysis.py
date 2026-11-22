import json
import shutil
import subprocess

import pytest

from conftest import FIXTURES, load_script, run_script

SKILL = "coverage-gap-analysis"
SCRIPT = "coverage_gaps.py"
mod = load_script(SKILL, SCRIPT)
D = FIXTURES / SKILL
DIFF = str(D / "changes.diff")


def gaps(cov, *args):
    r = run_script(SKILL, SCRIPT, "--coverage", str(D / cov), "--diff", DIFF, *args, "--json")
    assert r.returncode in (0, 1), r.stderr
    return r.returncode, json.loads(r.stdout)


def files(data):
    return {f["file"]: f for f in data["files"]}


def test_parse_diff_added_lines_only():
    changed = mod.parse_diff((D / "changes.diff").read_text())
    assert changed["src/app/pricing.py"] == {9, 10, 11, 12, 13, 35, 36}
    assert changed["src/app/new_module.py"] == {1, 2, 3}
    assert changed["README.md"] == {1}
    assert "src/app/gone.py" not in changed


@pytest.mark.parametrize(
    ("report", "fmt", "pct", "pricing_uncovered"),
    [
        ("cobertura.xml", "cobertura", 62.5, "12,36"),
        ("lcov.info", "lcov", 50.0, "12,36"),
        ("clover.xml", "clover", 62.5, "12"),
        ("coverage.json", "coverage.py-json", 87.5, "12"),
    ],
)
def test_formats(report, fmt, pct, pricing_uncovered):
    _, data = gaps(report)
    assert data["format"] == fmt
    assert data["diff_coverage"] == pct
    f = files(data)
    assert f["src/app/pricing.py"]["uncovered_lines"] == pricing_uncovered
    assert f["src/app/new_module.py"]["status"] == "not-in-report"
    assert "tests/test_pricing.py" not in f and "README.md" not in f


def test_untested_and_ordering():
    _, data = gaps("lcov.info")
    assert [f["status"] for f in data["files"]] == ["not-in-report", "untested", "partial"]
    assert data["untested_files"] == ["src/app/new_module.py", "src/app/utils.py"]


def test_thresholds_and_count_missing():
    code, data = gaps("coverage.json", "--fail-under", "80")
    assert code == 0 and data["passed"]
    code, data = gaps("coverage.json", "--fail-under", "80", "--count-missing")
    assert code == 1 and data["diff_coverage"] == 63.6
    code, _ = gaps("coverage.json", "--fail-on-untested")
    assert code == 1


def test_include_exclude():
    _, data = gaps("cobertura.xml", "--exclude", "src/app/utils.py")
    assert "src/app/utils.py" not in files(data)
    _, data = gaps("cobertura.xml", "--no-default-excludes", "--include", "*.py")
    assert "tests/test_pricing.py" in files(data)


def test_suffix_matching():
    cov = {"/home/ci/repo/src/app/x.py": {1: 1}, "app/y.py": {1: 0}}
    assert mod.match_file("src/app/x.py", cov, []) == "/home/ci/repo/src/app/x.py"
    assert mod.match_file("src/app/y.py", cov, []) == "app/y.py"
    assert mod.match_file("other/z.py", cov, []) is None
    assert mod.match_file("x.py", {"/a/b/x.py": {}}, []) == "/a/b/x.py"


def test_ranges():
    assert mod.ranges([1, 2, 3, 5, 7, 8]) == "1-3,5,7-8"
    assert mod.ranges([]) == ""


def test_stdin_diff_and_text_output():
    r = run_script(
        SKILL,
        SCRIPT,
        "--coverage",
        str(D / "cobertura.xml"),
        "--diff",
        "-",
        "--fail-under",
        "90",
        stdin=(D / "changes.diff").read_text(),
    )
    assert r.returncode == 1
    assert "Diff coverage: 62.5%" in r.stdout
    assert "[NOT IN REPORT] src/app/new_module.py" in r.stdout
    assert "FAIL: threshold 90.0%" in r.stdout


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_base_mode_runs_git(tmp_path):
    def git(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.test")
    git("config", "user.name", "t")
    (tmp_path / "app.py").write_text("a = 1\n")
    git("add", ".")
    git("commit", "-qm", "base")
    git("checkout", "-qb", "feature")
    (tmp_path / "app.py").write_text("a = 1\nb = 2\nc = 3\n")
    git("commit", "-qam", "change")
    lcov = tmp_path / "lcov.info"
    lcov.write_text("SF:app.py\nDA:1,1\nDA:2,1\nDA:3,0\nend_of_record\n")
    r = run_script(
        SKILL, SCRIPT, "--coverage", str(lcov), "--base", "main", "--repo", str(tmp_path), "--json"
    )
    data = json.loads(r.stdout)
    assert data["diff_coverage"] == 50.0 and data["files"][0]["uncovered_lines"] == "3"
    bad = run_script(SKILL, SCRIPT, "--coverage", str(lcov), "--base", "--output=x", "--repo", str(tmp_path))
    assert bad.returncode == 2


def test_errors(tmp_path):
    junk = tmp_path / "junk.txt"
    junk.write_text("hello")
    assert run_script(SKILL, SCRIPT, "--coverage", str(junk), "--diff", DIFF).returncode == 2
    assert run_script(SKILL, SCRIPT, "--coverage", str(tmp_path / "nope.xml"), "--diff", DIFF).returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
