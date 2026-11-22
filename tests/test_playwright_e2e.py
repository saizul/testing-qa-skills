import json

from conftest import FIXTURES, load_script, run_script

SKILL = "playwright-e2e"
SCRIPT = "spec_lint.py"
mod = load_script(SKILL, SCRIPT)
D = FIXTURES / SKILL


def lint(*args):
    r = run_script(SKILL, SCRIPT, *args, "--json")
    assert r.returncode in (0, 1), r.stderr
    return r.returncode, json.loads(r.stdout)


def test_bad_spec_rules():
    code, data = lint(str(D / "bad"))
    assert code == 1
    assert data["files"] == 1  # node_modules is skipped
    rules = {(f["rule"], f["line"]) for f in data["findings"]}
    assert rules == {
        ("PW002", 3),
        ("PW010", 4),
        ("PW001", 5),
        ("PW005", 6),
        ("PW006", 7),
        ("PW008", 7),
        ("PW007", 8),
        ("PW003", 9),
        ("PW004", 10),
        ("PW009", 11),
        ("PW011", 12),
        ("PW014", 13),
        ("PW013", 18),
    }


def test_good_specs_clean_including_setup_login():
    code, data = lint(str(D / "good"))
    assert code == 0 and data["findings"] == [] and data["files"] == 2


def test_missing_await_variants():
    def rules(src):
        return [f["rule"] for f in mod.lint_text(src, "x.spec.ts")]

    assert rules("  expect(page.getByText('a')).toBeVisible();") == ["PW003"]
    assert rules("  expect(page).not.toHaveURL('/x');") == ["PW003"]
    assert rules("  await expect(page.getByText('a')).toBeVisible();") == []
    assert rules("  return expect(locator).toHaveText('a');") == []
    assert rules("  expect(value).toBe(3);") == []
    assert rules("  expect.soft(page.getByText('a')).toHaveText('b');") == ["PW003"]


def test_disable_comments():
    src = "// spec-lint-disable-file PW010\nawait page.goto('https://example.com');\nawait page.waitForTimeout(1); // spec-lint-disable-line PW001\n"
    assert mod.lint_text(src, "a.spec.ts") == []


def test_comments_and_strings_ignored():
    src = "/* page.waitForTimeout(1)\n still comment */\nconst u = 'http://x//y'; // page.waitForTimeout(5)\n"
    assert mod.lint_text(src, "a.spec.ts") == []


def test_fail_on_and_min_severity():
    assert run_script(SKILL, SCRIPT, str(D / "bad"), "--fail-on", "high").returncode == 1
    _, data = lint(str(D / "bad"), "--min-severity", "high")
    assert {f["severity"] for f in data["findings"]} == {"high"}
    single = D / "bad" / "checkout.spec.ts"
    code, data = lint(str(single), "--min-severity", "info", "--fail-on", "high")
    assert code == 1


def test_text_output_and_errors(tmp_path):
    r = run_script(SKILL, SCRIPT, str(D / "bad"))
    assert "PW001 fixed sleep" in r.stdout and "13 finding(s) in 1 spec file(s)" in r.stdout
    assert run_script(SKILL, SCRIPT, str(tmp_path / "missing")).returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
