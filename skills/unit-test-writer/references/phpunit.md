# PHPUnit recipes (PHPUnit 10-12)

PHPUnit 10+ uses PHP 8 attributes. Doc-comment annotations (`@test`, `@dataProvider`)
are deprecated in 11 and removed in 12, so use attributes in new code.

## Structure

```php
<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Pricing;
use App\DiscountError;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\Attributes\Test;
use PHPUnit\Framework\TestCase;

final class PricingTest extends TestCase
{
    public static function totals(): iterable
    {
        yield 'zero' => [0.0, 0.0];
        yield 'just below threshold' => [99.99, 99.99];
        yield 'threshold' => [100.0, 100.0];
        yield 'above threshold' => [200.0, 180.0];
    }

    #[Test]
    #[DataProvider('totals')]
    public function it_discounts_only_above_100(float $total, float $expected): void
    {
        self::assertEqualsWithDelta($expected, (new Pricing())->apply($total), 0.001);
    }

    public function testRejectsNegativeTotals(): void
    {
        $this->expectException(DiscountError::class);
        $this->expectExceptionMessage('negative');

        (new Pricing())->apply(-1);
    }
}
```

Data providers must be `public static` in PHPUnit 10+.

## Setup

`setUp(): void` / `tearDown(): void` per test; `setUpBeforeClass()` for expensive
read-only setup. Keep fixtures small; use builder/factory helpers (see test-data-builders).

## Test doubles at boundaries

```php
// Stub: returns canned values, no expectations
$rates = $this->createStub(RatesProvider::class);
$rates->method('rate')->willReturn(1.1);

// Mock: verifies the call to a boundary
$transport = $this->createMock(Transport::class);
$transport->expects($this->once())
    ->method('deliver')
    ->with('a@example.test', $this->stringContains('Receipt'));

(new Mailer($transport))->sendReceipt('a@example.test', $order);
```

- Use `createStub()` for pure stand-ins and `createMock()` only when you verify a call;
  recent PHPUnit releases report mock objects that have no expectations configured.
- Final classes cannot be doubled: depend on an interface, or use a fake implementation.
- Mockery (`Mockery::mock(...)->shouldReceive(...)`) is common in Laravel projects;
  call `Mockery::close()` in `tearDown` (Laravel's TestCase does it for you).

## Time

Inject `Psr\Clock\ClockInterface` (symfony/clock `MockClock`) or, in Laravel/Carbon code,
`Carbon::setTestNow('2024-01-01 00:00:00')` and reset with `Carbon::setTestNow()` in
`tearDown`. Laravel tests can use `$this->travelTo(...)` / `$this->freezeTime()`.

## Laravel specifics

- `Http::fake([...])`, `Mail::fake()`, `Queue::fake()`, `Event::fake()`, `Storage::fake('s3')`
  replace boundaries; assert with `Mail::assertSent(...)` etc.
- Model factories: `User::factory()->create(['role' => 'admin'])`; use
  `RefreshDatabase` or `DatabaseTransactions` for isolation.

## Useful commands

```bash
vendor/bin/phpunit --filter 'PricingTest::it_discounts'   # one test
vendor/bin/phpunit --testsuite Unit --stop-on-failure
vendor/bin/phpunit --coverage-cobertura coverage.xml       # needs Xdebug or PCOV
vendor/bin/phpunit --order-by=random                       # catch order dependence
```
