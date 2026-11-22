# Factory and fake-data libraries, deterministically

## Python: factory_boy + Faker

```python
import factory
from factory import Faker, Sequence, SubFactory, LazyAttribute


class UserFactory(factory.Factory):  # factory.django.DjangoModelFactory / alchemy.SQLAlchemyModelFactory
    class Meta:
        model = User

    id = Sequence(lambda n: n + 1)
    email = Sequence(lambda n: f"user-{n}@example.test")
    name = Faker("name")
    role = "member"


class OrderFactory(factory.Factory):
    class Meta:
        model = Order

    customer = SubFactory(UserFactory)
    total = "19.99"
    reference = LazyAttribute(lambda o: f"ORD-{o.customer.id:05d}")
```

```python
# conftest.py
import factory.random
import pytest


@pytest.fixture(autouse=True)
def _deterministic_factories():
    factory.random.reseed_random("tests")  # seeds factory_boy's Faker and fuzzy attributes
    UserFactory.reset_sequence()
```

Plain Faker: `Faker.seed(1234)` (class-level, all instances) or `fake.seed_instance(1234)`.
pytest's Faker plugin provides a `faker` fixture seeded per test (`faker_seed` fixture
to change it).

## TypeScript: fishery + @faker-js/faker

```ts
import { Factory } from 'fishery';
import { faker } from '@faker-js/faker';

export const userFactory = Factory.define<User>(({ sequence }) => ({
  id: sequence,
  email: `user-${sequence}@example.test`,
  name: faker.person.fullName(),
  role: 'member',
}));

// setup file (vitest setupFiles / jest setupFilesAfterEnv)
beforeEach(() => {
  faker.seed(1234);
  userFactory.rewindSequence();
});

const admin = userFactory.build({ role: 'admin' });
const users = userFactory.buildList(3);
```

Also seed or fix the clock if defaults use dates: `faker.setDefaultRefDate('2024-01-01T00:00:00Z')`
for `faker.date.recent()/past()`, plus `vi.setSystemTime` for code under test.

## PHP / Laravel model factories

```php
class UserFactory extends Factory
{
    public function definition(): array
    {
        return [
            'name' => fake()->name(),
            'email' => fake()->unique()->safeEmail(),
            'role' => 'member',
        ];
    }

    public function admin(): static
    {
        return $this->state(fn () => ['role' => 'admin']);
    }
}

// in a test
User::factory()->admin()->create();
User::factory()->count(3)->for($team)->create();
```

Determinism in Laravel tests:

```php
protected function setUp(): void
{
    parent::setUp();
    $this->faker->seed(1234);        // with WithFaker; or fake()->seed(1234)
    $this->freezeTime();             // or Carbon::setTestNow('2024-01-01 00:00:00')
}
```

Use `make()` (not persisted) for unit tests and `create()` only when the database matters.

## Plain PHP: fakerphp/faker

```php
$faker = \Faker\Factory::create();
$faker->seed(1234);
```

## Property-based testing (randomness on purpose)

Hypothesis (Python) and fast-check (JS) generate inputs randomly but print a seed /
falsifying example on failure. Keep that output, and add the failing example as an
explicit regression test (`@example(...)` in Hypothesis, `fc.assert(..., { examples: [...] })`).
