import { defaultSelection, isValueAvailable, pickVariant } from '../src/lib/variants';
import type { Product, Variant } from '../src/model/types';

const v = (id: string, weight: string, grind: string, inventory: number): Variant => ({
  id, title: `${weight} / ${grind}`, sku: id, priceCents: 1800, inventory, available: inventory > 0,
  options: { Weight: weight, Grind: grind },
});

const product = {
  optionNames: ['Weight', 'Grind'],
  variants: [v('1', '250g', 'Whole', 0), v('2', '250g', 'Filter', 5), v('3', '1kg', 'Whole', 9), v('4', '1kg', 'Filter', 0)],
} as unknown as Product;

test('defaultSelection starts on the first available variant', () => {
  expect(defaultSelection(product)).toEqual({ Weight: '250g', Grind: 'Filter' });
});

test('defaultSelection falls back to the first variant when nothing is available', () => {
  const soldOut = { ...product, variants: product.variants.map((x) => ({ ...x, available: false, inventory: 0 })) } as Product;
  expect(defaultSelection(soldOut)).toEqual({ Weight: '250g', Grind: 'Whole' });
});

test('pickVariant finds the exact combination or nothing', () => {
  expect(pickVariant(product, { Weight: '1kg', Grind: 'Whole' })?.id).toBe('3');
  expect(pickVariant(product, { Weight: '1kg', Grind: 'Espresso' })).toBeUndefined();
});

test('isValueAvailable checks a value against the other current choices', () => {
  const sel = { Weight: '250g', Grind: 'Filter' };
  expect(isValueAvailable(product, sel, 'Weight', '1kg')).toBe(false); // 1kg / Filter is sold out
  expect(isValueAvailable(product, sel, 'Weight', '250g')).toBe(true);
  expect(isValueAvailable(product, sel, 'Grind', 'Whole')).toBe(false); // 250g / Whole is sold out
});
