<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\InvalidAddress;
use App\Mailer;
use App\Transport;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\Attributes\Test;
use PHPUnit\Framework\TestCase;

final class MailerTest extends TestCase
{
    #[Test]
    public function it_sends_through_the_transport(): void
    {
        $transport = $this->createMock(Transport::class);
        $transport->expects($this->once())->method('deliver')->with('a@example.test');

        (new Mailer($transport))->send('a@example.test', 'hi');
    }

    public function testRejectsInvalidAddress(): void
    {
        $this->expectException(InvalidAddress::class);
        $this->expectExceptionMessage('not-an-address');

        (new Mailer($this->createStub(Transport::class)))->send('not-an-address', 'hi');
    }

    public function testSkippedWithReason(): void
    {
        $this->markTestSkipped('needs SMTP sandbox, see #7');
    }

    public static function subjects(): array
    {
        return [['hi'], ['hello {name}']];
    }

    #[DataProvider('subjects')]
    public function testSubjects(string $subject): void
    {
        self::assertNotSame('', $subject);
    }
}
