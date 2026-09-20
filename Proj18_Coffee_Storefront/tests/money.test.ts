import { formatMoney, priceLabel } from '../src/lib/money';
import type { Product } from '../src/model/types';

test('formats cents as US dollars', () => {
  expect(formatMoney(1850)).toBe('$18.50');
  expect(formatMoney(0)).toBe('$0.00');
  expect(formatMoney(129900)).toBe('$1,299.00');
});

test('priceLabel shows a single price or a From price', () => {
  expect(priceLabel({ minCents: 900, maxCents: 900 } as Product)).toBe('$9.00');
  expect(priceLabel({ minCents: 1800, maxCents: 6500 } as Product)).toBe('From $18.00');
});
