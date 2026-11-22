import json

from conftest import FIXTURES, load_script, run_script

SKILL = "unit-test-writer"
SCRIPT = "lint_tests.py"
mod = load_script(SKILL, SCRIPT)
D = FIXTURES / SKILL


def lint(*args):
    r = run_script(SKILL, SCRIPT, *args, "--json")
    assert r.returncode in (0, 1), r.stderr
    return r.returncode, json.loads(r.stdout)


def found(data, suffix):
    return sorted((f["rule"], f["line"]) for f in data["findings"] if f["file"].endswith(suffix))


def test_python_bad():
    _, data = lint(str(D / "bad" / "test_orders.py"))
    assert found(data, "test_orders.py") == [
        ("UT001", 8),
        ("UT003", 13),
        ("UT004", 18),
        ("UT005", 24),
        ("UT006", 30),
        ("UT007", 34),
        ("UT008", 41),
    ]


def test_js_bad():
    _, data = lint(str(D / "bad" / "cart.test.ts"))
    assert found(data, "cart.test.ts") == [
        ("UT001", 5),
        ("UT002", 4),
        ("UT002", 32),
        ("UT003", 10),
        ("UT004", 15),
        ("UT005", 19),
        ("UT006", 24),
        ("UT007", 28),
        ("UT008", 25),
    ]


def test_php_bad():
    _, data = lint(str(D / "bad" / "MailerTest.php"))
    assert found(data, "MailerTest.php") == [
        ("UT001", 13),
        ("UT003", 22),
        ("UT004", 23),
        ("UT005", 31),
        ("UT006", 32),
        ("UT007", 37),
        ("UT008", 33),
    ]
    names = {f["test"] for f in data["findings"]}
    assert "helper" not in names  # private non-test method ignored
    assert {"testSends", "retriesLater", "swallows"} <= names  # #[Test] and @test detected


def test_good_files_are_clean():
    code, data = lint(str(D / "good"))
    assert code == 0 and data["findings"] == [] and data["files"] == 3


def test_directory_discovery_and_exit_codes():
    code, data = lint(str(D / "bad"))
    assert code == 1 and data["files"] == 3
    assert run_script(SKILL, SCRIPT, str(D / "bad"), "--fail-on", "high").returncode == 1
    _, data = lint(str(D / "bad"), "--min-severity", "high")
    assert {f["rule"] for f in data["findings"]} == {"UT001", "UT002"}


def test_ignore_comment(tmp_path):
    p = tmp_path / "test_x.py"
    p.write_text(
        "import time\n\ndef test_a():\n    time.sleep(1)  # lint-tests: ignore[UT003]\n    assert time.time()\n"
    )
    assert mod.lint_file(p) == []


def test_is_test_file():
    from pathlib import Path

    assert mod.is_test_file(Path("tests/test_a.py"))
    assert mod.is_test_file(Path("a_test.py"))
    assert not mod.is_test_file(Path("conftest.py"))
    assert mod.is_test_file(Path("src/x.spec.tsx"))
    assert mod.is_test_file(Path("src/__tests__/x.js"))
    assert mod.is_test_file(Path("tests/Unit/FooTest.php"))
    assert not mod.is_test_file(Path("src/Foo.php"))


def test_python_syntax_error_reported(tmp_path):
    p = tmp_path / "test_bad.py"
    p.write_text("def test_x(:\n")
    assert [f["rule"] for f in mod.lint_file(p)] == ["PARSE"]


def test_js_assertion_helpers_count():
    src = "it('a', () => { assert.equal(f(), 1); });\nit('b', async () => { await expect(p).resolves.toBe(1) });\n"
    assert mod.lint_js(src, "a.test.js") == []


def test_text_output_and_errors(tmp_path):
    r = run_script(SKILL, SCRIPT, str(D / "bad"))
    assert "UT001 test has no assertion in test_places_order" in r.stdout
    assert run_script(SKILL, SCRIPT, str(tmp_path / "missing")).returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
