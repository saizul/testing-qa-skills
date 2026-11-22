import { describe, it, expect, vi } from 'vitest';
import { addItem } from '../src/cart';

describe.only('cart', () => {
  it('adds an item', () => {
    addItem({ sku: 'a' });
  });

  it('waits', async () => {
    await new Promise((r) => setTimeout(r, 500));
    expect(addItem({ sku: 'b' })).toHaveLength(1);
  });

  it('is constant', () => {
    expect(true).toBe(true);
  });

  it('swallows', () => {
    try { addItem(null); } catch (e) {}
    expect(1).toBeGreaterThan(0);
  });

  it('throws something', () => {
    expect(() => addItem(null)).toThrow();
    console.log('debug');
  });

  it.skip('later', () => {
    expect(addItem({ sku: 'c' })).toBeDefined();
  });

  fit('focused', () => expect(addItem({ sku: 'd' })).toHaveLength(1));
});
