<?php
final class InvoiceTest extends TestCase
{
    protected function setUp(): void
    {
        Carbon::setTestNow('2024-01-01 00:00:00');
        mt_srand(1234);
        $this->faker->seed(1234);
    }

    public function testNumber(): void
    {
        $this->assertSame(1, make(mt_rand(1, 10), Carbon::now(), now(), $this->faker->name()));
    }
}
