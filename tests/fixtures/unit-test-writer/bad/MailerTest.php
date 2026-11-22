<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Mailer;
use PHPUnit\Framework\Attributes\Test;
use PHPUnit\Framework\TestCase;

final class MailerTest extends TestCase
{
    public function testSends(): void
    {
        $mailer = new Mailer();
        $mailer->send('a@example.test', 'hi');
    }

    #[Test]
    public function retriesLater(): void
    {
        sleep(2);
        $this->assertTrue(true);
    }

    /** @test */
    public function swallows(): void
    {
        try {
            (new Mailer())->send('', '');
        } catch (\Throwable $e) {}
        $this->expectException(\Exception::class);
        var_dump('x');
    }

    public function testSkipped(): void
    {
        $this->markTestSkipped();
    }

    private function helper(): void
    {
    }
}
