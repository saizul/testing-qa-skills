import pytest

from shop.pricing import apply_discount, DiscountError


@pytest.fixture
def cart():
    return {"items": [{"sku": "a", "price": 50}, {"sku": "b", "price": 70}]}


def test_applies_ten_percent_over_100(cart):
    # Arrange
    total = sum(i["price"] for i in cart["items"])
    # Act
    result = apply_discount(total)
    # Assert
    assert result == pytest.approx(108.0)


@pytest.mark.parametrize("total,expected", [(0, 0), (99.99, 99.99), (100, 100)])
def test_no_discount_at_or_below_100(total, expected):
    assert apply_discount(total) == expected


def test_rejects_negative_totals():
    with pytest.raises(DiscountError, match="negative"):
        apply_discount(-1)


@pytest.mark.skip(reason="waiting for currency support, see #12")
def test_currency():
    assert apply_discount(1, currency="EUR") == 1


class TestUnittestStyle:
    def test_uses_mock(self, mocker):
        sender = mocker.Mock()
        apply_discount(150, notify=sender)
        sender.send.assert_called_once_with(135.0)
