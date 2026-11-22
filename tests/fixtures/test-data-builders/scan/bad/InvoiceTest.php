<?php
final class InvoiceTest extends TestCase
{
    public function testNumber(): void
    {
        $n = random_int(1, 10);
        $issued = new \DateTimeImmutable();
        $today = date('Y-m-d');
        $fixed = date('Y-m-d', 1700000000);
        $name = $this->faker->name();
        $this->assertSame($n, make($n, $issued, $today, $fixed, $name));
    }
}
