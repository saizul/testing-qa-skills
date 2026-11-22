import json

from conftest import FIXTURES, load_script, run_script

SKILL = "ci-test-optimization"
SCRIPT = "shard_plan.py"
mod = load_script(SKILL, SCRIPT)
D = FIXTURES / SKILL
SHARDS = [str(D / "shard1.xml"), str(D / "shard2.xml")]


def plan(*args):
    r = run_script(SKILL, SCRIPT, *args, "--json")
    assert r.returncode in (0, 1), r.stderr
    return r.returncode, json.loads(r.stdout)


def test_by_file_balanced():
    _, data = plan(*SHARDS, "--shards", "3")
    assert data["items"] == 6 and data["total_seconds"] == 189.0
    assert [s["seconds"] for s in data["shards"]] == [65.0, 61.0, 63.0]
    assert data["shards"][0]["items"] == ["tests/test_checkout.py"]
    assert data["imbalance_pct"] == 6.3
    assert data["slowest_tests"][0] == {"test": "tests.test_checkout.TestCheckout::test_pay", "seconds": 65.0}
    every = sorted(i for s in data["shards"] for i in s["items"])
    assert len(every) == len(set(every)) == 6


def test_lpt_plan_function():
    shards = mod.plan({"a": 10, "b": 7, "c": 5, "d": 4, "e": 3, "f": 1}, 2)
    assert sorted(s["seconds"] for s in shards) == [15.0, 15.0]


def test_repeated_reports_are_averaged():
    _, data = plan(*SHARDS, str(D / "previous-run.xml"), "--shards", "1")
    # previous run is 1.2x slower -> mean is 1.1x
    assert data["total_seconds"] == 207.9


def test_items_file_adds_unknown_and_drops_deleted():
    _, data = plan(*SHARDS, "--items", str(D / "items.txt"), "--shards", "2")
    assert data["unknown_items"] == ["tests/test_new_feature.py"]
    assert data["dropped_items"] == 1  # tests/test_auth.py no longer listed
    names = {i for s in data["shards"] for i in s["items"]}
    assert "tests/test_auth.py" not in names and "tests/test_new_feature.py" in names


def test_lines_format_for_one_shard():
    r = run_script(SKILL, SCRIPT, *SHARDS, "--shards", "3", "--shard", "1", "--format", "lines")
    assert r.returncode == 0 and r.stdout.split() == ["tests/test_checkout.py"]
    all_lines = run_script(SKILL, SCRIPT, *SHARDS, "--shards", "3", "--format", "lines").stdout.split()
    assert len(all_lines) == 6


def test_by_class_and_test():
    _, data = plan(*SHARDS, "--by", "class", "--shards", "2")
    assert (
        data["items"] == 6
        and "tests.test_api.TestUsers" in data["shards"][0]["items"] + data["shards"][1]["items"]
    )
    _, data = plan(*SHARDS, "--by", "test", "--shards", "2")
    assert data["items"] == 10


def test_jest_suite_file_attribute():
    _, data = plan(str(D / "jest-junit.xml"), "--shards", "2")
    items = sorted(i for s in data["shards"] for i in s["items"])
    assert items == ["src/cart.test.ts", "src/search.test.ts"]
    assert data["imbalance_pct"] == 40.0


def test_target_minutes_and_imbalance_gate():
    _, data = plan(*SHARDS, "--shards", "2", "--target-minutes", "3", "--overhead-seconds", "30")
    assert data["suggested_shards"] == 2  # 1 shard: 189 + 30 > 180 s; 2 shards: 98 + 30 <= 180 s
    _, data = plan(*SHARDS, "--target-minutes", "4", "--overhead-seconds", "30")
    assert data["suggested_shards"] == 1
    _, data = plan(*SHARDS, "--target-minutes", "1", "--overhead-seconds", "30")
    assert data["suggested_shards"] is None  # 65 s file + 30 s > 60 s
    assert run_script(SKILL, SCRIPT, *SHARDS, "--shards", "3", "--max-imbalance", "5").returncode == 1
    assert run_script(SKILL, SCRIPT, *SHARDS, "--shards", "3", "--max-imbalance", "10").returncode == 0


def test_strip_prefix(tmp_path):
    x = tmp_path / "abs.xml"
    x.write_text(
        '<testsuite><testcase classname="a" name="t" file="/app/tests/test_a.py" time="2"/></testsuite>'
    )
    _, data = plan(str(x), "--shards", "1", "--strip-prefix", "/app/")
    assert data["shards"][0]["items"] == ["tests/test_a.py"]


def test_text_and_errors(tmp_path):
    r = run_script(SKILL, SCRIPT, *SHARDS, "--shards", "2", "--target-minutes", "1")
    assert "not reachable by sharding" in r.stdout and "Slowest tests:" in r.stdout
    assert run_script(SKILL, SCRIPT, *SHARDS, "--shards", "2", "--shard", "3").returncode == 2
    assert run_script(SKILL, SCRIPT, str(tmp_path / "none.xml")).returncode == 2
    bad = tmp_path / "bad.xml"
    bad.write_text("<testsuite>")
    assert run_script(SKILL, SCRIPT, str(bad)).returncode == 2
    empty = tmp_path / "empty.xml"
    empty.write_text("<testsuites/>")
    assert run_script(SKILL, SCRIPT, str(empty)).returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
