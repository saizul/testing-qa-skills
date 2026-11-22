import { faker } from '@faker-js/faker';
import { beforeEach, vi } from 'vitest';

faker.seed(1234);
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2024-01-01T00:00:00Z'));
});

it('formats', () => {
  expect(format({ at: new Date(), name: faker.person.firstName() })).toBeTruthy();
});
