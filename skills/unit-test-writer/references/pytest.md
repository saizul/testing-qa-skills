# pytest recipes

## Layout and config

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
markers = ["slow: takes more than 1 s", "integration: needs services"]
```

`tests/conftest.py` holds shared fixtures; fixtures in a subfolder's `conftest.py` apply
to that folder only.

## Arrange-act-assert with parametrize

```python
import pytest

from shop.pricing import apply_discount, DiscountError


@pytest.mark.parametrize(
    ("total", "expected"),
    [
        pytest.param(0, 0, id="zero"),
        pytest.param(99.99, 99.99, id="just-below-threshold"),
        pytest.param(100, 100, id="threshold-not-discounted"),
        pytest.param(100.01, 90.009, id="just-above-threshold"),
    ],
)
def test_discount_applies_only_above_100(total, expected):
    assert apply_discount(total) == pytest.approx(expected)


def test_negative_total_is_rejected():
    with pytest.raises(DiscountError, match="negative"):
        apply_discount(-1)
```

## Fixtures

```python
@pytest.fixture
def cart():
    return Cart(items=[Item("a", 50), Item("b", 70)])


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session  # teardown runs after the test
        session.rollback()
```

- Scope: default `function`. Use `scope="session"` only for expensive, read-only setup.
- Built-ins worth knowing: `tmp_path`, `monkeypatch`, `capsys`, `caplog`, `request`.
- Factory fixture when tests need variants:
  ```python
  @pytest.fixture
  def make_user():
      def _make(**overrides):
          return User(**{"name": "Ada", "role": "member", **overrides})

      return _make
  ```

## Mocking boundaries

```python
def test_sends_receipt(monkeypatch):
    sent = []
    monkeypatch.setattr("shop.receipts.smtp_send", lambda to, body: sent.append(to))
    send_receipt(order_id=1)
    assert sent == ["ada@example.test"]


def test_gateway_timeout_marks_order_pending(mocker):  # pytest-mock
    gateway = mocker.Mock()
    gateway.charge.side_effect = TimeoutError
    order = checkout(cart, gateway=gateway)
    assert order.status == "pending"
    gateway.charge.assert_called_once()
```

- Patch where the name is **looked up**, not where it is defined
  (`mocker.patch("shop.receipts.requests.post")` if `shop/receipts.py` does `import requests`).
- Use `autospec=True` (`mocker.create_autospec(Client)`) so wrong call signatures fail.
- HTTP: `responses` (requests) or `respx` (httpx) instead of hand-made mocks.

## Time, randomness, environment

```python
from freezegun import freeze_time  # or time-machine


@freeze_time("2024-02-29 23:59:59")
def test_leap_day_rollover():
    assert next_billing_date() == date(2024, 3, 29)


def test_reads_api_url(monkeypatch):
    monkeypatch.setenv("API_URL", "http://api.test")
    assert load_config().api_url == "http://api.test"
```

Inject `random.Random(42)` or a clock function instead of patching modules where you can.

## Async

```python
import pytest


@pytest.mark.asyncio  # pytest-asyncio; or anyio's @pytest.mark.anyio
async def test_fetch_user(httpx_mock):
    httpx_mock.add_response(json={"id": 1})
    assert (await fetch_user(1)).id == 1
```

## unittest style (when the project uses it)

```python
class DiscountTest(unittest.TestCase):
    def setUp(self):
        self.cart = Cart(items=[Item("a", 120)])

    def test_discount(self):
        self.assertAlmostEqual(apply_discount(self.cart.total), 108.0)

    def test_negative(self):
        with self.assertRaisesRegex(DiscountError, "negative"):
            apply_discount(-1)
```

pytest runs unittest classes too; do not mix styles inside one file.

## Useful flags

`pytest -x` stop at first failure, `--lf` rerun last failures, `-k expr` select,
`-p no:randomly` disable random order plugin, `--durations=10` slowest tests,
`-n auto` parallel (pytest-xdist), `--cov=src --cov-report=xml` coverage (pytest-cov).
