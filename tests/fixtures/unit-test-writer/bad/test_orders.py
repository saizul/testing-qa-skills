import time

import pytest

from shop.orders import place_order


def test_places_order():
    place_order(user_id=1, items=["sku-1"])


def test_waits_for_queue():
    time.sleep(2)
    assert place_order(user_id=1, items=[]) is not None


def test_constant():
    assert True


def test_swallows():
    try:
        place_order(user_id=None, items=[])
    except Exception:
        pass
    assert 1 == 1


def test_broad_raises():
    with pytest.raises(Exception):
        place_order(user_id=None, items=[])


@pytest.mark.skip
def test_later():
    assert place_order(1, [])


def test_debug():
    result = place_order(1, ["a"])
    print(result)
    assert result.total == 10


def test_ignored_sleep():
    time.sleep(1)  # lint-tests: ignore[UT003]
    assert place_order(1, ["a"])
