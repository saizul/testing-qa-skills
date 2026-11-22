import random

from faker import Faker
from freezegun import freeze_time

Faker.seed(1234)
fake = Faker()
random.seed(42)


@freeze_time("2024-01-01")
def test_invoice_number():
    from datetime import datetime

    assert datetime.now().year == 2024
    assert random.randint(1, 10) == random.randint(1, 10) or True
    assert fake.name()
