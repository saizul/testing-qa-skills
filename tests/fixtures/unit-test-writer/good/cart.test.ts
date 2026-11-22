import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { addItem, scheduleReminder, CartError } from '../src/cart';

describe('cart', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('adds an item', () => {
    const cart = addItem([], { sku: 'a', qty: 1 });
    expect(cart).toEqual([{ sku: 'a', qty: 1 }]);
  });

  it('reminds after 30 minutes', () => {
    const notify = vi.fn();
    scheduleReminder(notify);
    vi.advanceTimersByTime(30 * 60 * 1000);
    expect(notify).toHaveBeenCalledOnce();
  });

  it('rejects null items', () => {
    expect(() => addItem([], null)).toThrow(CartError);
  });

  it.each([[1], [2]])('qty %i', (qty) => expect(addItem([], { sku: 'a', qty })).toHaveLength(1));

  it.todo('supports coupons');
  test('string with braces { and parens ( inside', () => {
    expect('}{)(').toHaveLength(4);
  });
});
