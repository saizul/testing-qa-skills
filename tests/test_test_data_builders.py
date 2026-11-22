import importlib.util
import json
import shutil
import subprocess
import sys

import pytest

from conftest import FIXTURES, load_script, run_script

SKILL = "test-data-builders"
BUILDER = "make_builder.py"
SCAN = "nondeterminism_scan.py"
mb = load_script(SKILL, BUILDER)
ns = load_script(SKILL, SCAN)
D = FIXTURES / SKILL
ORDER = str(D / "order.json")


def generate(lang, *extra):
    r = run_script(SKILL, BUILDER, ORDER, "--name", "Order", "--lang", lang, *extra)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_field_kinds():
    r = run_script(SKILL, BUILDER, ORDER, "--json")
    kinds = json.loads(r.stdout)
    assert kinds["Order"] == {
        "id": "id",
        "uuid": "uuid",
        "customerId": "id",
        "email": "email",
        "status": "enum",
        "total": "float",
        "quantity": "int",
        "gift": "bool",
        "coupon": "null",
        "placed_at": "datetime",
        "ship_by": "date",
        "receipt_url": "url",
        "tags": "list",
        "shipping_address": "object",
        "line_items": "list",
    }
    assert set(kinds) == {"ShippingAddress", "LineItem", "Order"}


def test_python_builder_runs_and_is_deterministic(tmp_path):
    out = tmp_path / "builders.py"
    r = run_script(SKILL, BUILDER, ORDER, "--name", "Order", "--out", str(out))
    assert r.returncode == 0
    spec = importlib.util.spec_from_file_location("gen_builders", out)
    m = importlib.util.module_from_spec(spec)
    sys.modules["gen_builders"] = m
    spec.loader.exec_module(m)
    first = m.build_order(status="refunded")
    m.reset_sequences()
    second = m.build_order(status="refunded")
    assert first == second
    assert first["id"] == 1 and first["email"] == "order-1@example.test"
    assert first["uuid"] == "00000000-0000-4000-8000-000000000001"
    assert first["placed_at"] == "2024-01-02T00:00:00Z" and first["ship_by"] == "2024-01-02"
    assert first["status"] == "refunded" and first["tags"] == ["vip", "holiday"]
    assert first["shipping_address"]["city"] == "city 2"
    assert len(m.build_order_list(3)) == 3
    with pytest.raises(TypeError):
        m.build_order(nope=1)


def test_out_refuses_overwrite(tmp_path):
    out = tmp_path / "b.py"
    out.write_text("keep")
    r = run_script(SKILL, BUILDER, ORDER, "--out", str(out))
    assert r.returncode == 2 and out.read_text() == "keep"
    assert run_script(SKILL, BUILDER, ORDER, "--out", str(out), "--force").returncode == 0


def test_ts_output_shape():
    code = generate("ts")
    assert "export interface Order {" in code
    assert "export function buildOrder(overrides: Partial<Order> = {}): Order {" in code
    assert "line_items: LineItem[];" in code and "tags: string[];" in code
    assert 'status: "paid",' in code


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_ts_builder_runs_with_node(tmp_path):
    js = generate("ts")
    src = tmp_path / "b.ts"
    src.write_text(js)
    runner = tmp_path / "run.ts"
    runner.write_text(
        "import { buildOrder, resetSequences } from './b.ts';\n"
        "const a = buildOrder(); resetSequences(); const b = buildOrder();\n"
        "console.log(JSON.stringify(a) === JSON.stringify(b), a.id, a.placed_at);\n"
    )
    r = subprocess.run(["node", str(runner)], capture_output=True, text=True, check=False, timeout=60)
    if r.returncode != 0 and (
        "Unknown file extension" in r.stderr or "ERR_UNKNOWN_FILE_EXTENSION" in r.stderr
    ):
        pytest.skip("this node version cannot run TypeScript directly")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["true", "1", "2024-01-02T00:00:00.000Z"]


def test_php_output(tmp_path):
    code = generate("php")
    assert "final class OrderFactory" in code
    assert "public static function order(array $overrides = []): array" in code
    assert "\"status\" => 'paid'," in code
    if shutil.which("php"):
        f = tmp_path / "OrderFactory.php"
        f.write_text(code)
        lint = subprocess.run(["php", "-l", str(f)], capture_output=True, text=True, check=False)
        assert lint.returncode == 0, lint.stdout + lint.stderr


def test_list_input_and_errors(tmp_path):
    p = tmp_path / "users.json"
    p.write_text('[{"id": 1, "name": "Ada"}]')
    r = run_script(SKILL, BUILDER, str(p))
    assert r.returncode == 0 and "def build_users(" in r.stdout
    empty = tmp_path / "e.json"
    empty.write_text("{}")
    assert run_script(SKILL, BUILDER, str(empty)).returncode == 2
    bad = tmp_path / "bad.json"
    bad.write_text("{")
    assert run_script(SKILL, BUILDER, str(bad)).returncode == 2
    assert run_script(SKILL, BUILDER, "-", stdin='{"Weird Key!": "x"}').returncode == 0


def test_name_helpers():
    assert mb.pascal("line_items") == "LineItems"
    assert mb.pascal("shippingAddress") == "ShippingAddress"
    assert mb.snake("customerId") == "customer_id"
    assert mb.singular("categories") == "category"
    assert mb.singular("addresses") == "address"
    assert mb.label("a'b\"c{d}") == "abcd"


def scan(*args):
    r = run_script(SKILL, SCAN, *args, "--json")
    assert r.returncode in (0, 1), r.stderr
    return r.returncode, json.loads(r.stdout)


def test_scan_bad():
    code, data = scan(str(D / "scan" / "bad"))
    assert code == 1
    got = sorted((f["file"].rsplit("/", 1)[-1], f["line"], f["rule"]) for f in data["findings"])
    assert got == [
        ("InvoiceTest.php", 6, "ND009"),
        ("InvoiceTest.php", 7, "ND010"),
        ("InvoiceTest.php", 8, "ND010"),
        ("InvoiceTest.php", 10, "ND011"),
        ("invoice.test.ts", 4, "ND007"),
        ("invoice.test.ts", 5, "ND006"),
        ("invoice.test.ts", 6, "ND006"),
        ("invoice.test.ts", 7, "ND005"),
        ("invoice.test.ts", 8, "ND008"),
        ("test_invoices.py", 7, "ND004"),
        ("test_invoices.py", 11, "ND001"),
        ("test_invoices.py", 12, "ND002"),
        ("test_invoices.py", 13, "ND003"),
    ]


def test_scan_good_suppressed_by_seeds_and_frozen_time():
    code, data = scan(str(D / "scan" / "good"))
    assert code == 0 and data["findings"] == []
    code, data = scan(str(D / "scan" / "good"), "--no-suppress")
    assert code == 1 and {f["rule"] for f in data["findings"]} >= {"ND002", "ND006", "ND010"}


def test_scan_text_and_errors(tmp_path):
    r = run_script(SKILL, SCAN, str(D / "scan" / "bad" / "test_invoices.py"))
    assert r.returncode == 1 and "ND003 random UUID" in r.stdout
    assert run_script(SKILL, SCAN, str(tmp_path / "missing")).returncode == 2
    assert run_script(SKILL, SCAN, "--help").returncode == 0
    assert run_script(SKILL, BUILDER, "--help").returncode == 0
    assert ns.lang_of(__import__("pathlib").Path("a.tsx")) == "js"
