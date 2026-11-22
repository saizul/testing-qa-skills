import { faker } from '@faker-js/faker';

it('formats', () => {
  const id = crypto.randomUUID();
  const at = new Date();
  const ts = Date.now();
  const r = Math.random();
  const name = faker.person.firstName();
  expect(format({ id, at, ts, r, name })).toBeTruthy();
});
