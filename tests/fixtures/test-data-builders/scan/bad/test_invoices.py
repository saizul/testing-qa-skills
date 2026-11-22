import random
import uuid
from datetime import datetime

from faker import Faker

fake = Faker()


def test_invoice_number():
    n = random.randint(1, 1000)
    issued = datetime.now()
    ref = uuid.uuid4()
    name = fake.name()
    assert make_invoice(n, issued, ref, name).number == n
    label = "datetime.now() inside a string is fine"
    stamp = datetime.now()  # nondeterminism: ok
