import {
  CART_KEY, cartDetail, cartReducer, loadLines, reconcile, saveLines, shippingProgress, type CartLine,
} from '../src/lib/cart';
import type { Product } from '../src/model/types';

const product = {
  handle: 'a', title: 'Alpha',
  variants: [
    { id: 'v1', title: '250g', priceCents: 2000, inventory: 5, available: true },
    { id: 'v2', title: '1kg', priceCents: 7000, inventory: 0, available: false },
  ],
} as unknown as Product;

const add = (lines: CartLine[], qty: number, max = 5) =>
  cartReducer(lines, { type: 'add', variantId: 'v1', handle: 'a', qty, max });

test('add creates a line and merges later adds', () => {
  const once = add([], 2);
  expect(once).toEqual([{ variantId: 'v1', handle: 'a', qty: 2 }]);
  expect(add(once, 1)[0]!.qty).toBe(3);
});

test('add never goes past stock, and adds nothing when there is none', () => {
  expect(add(add([], 4), 4)[0]!.qty).toBe(5);
  expect(add([], 1, 0)).toEqual([]);
});

test('set clamps to stock and removes at zero; remove and clear work', () => {
  const lines = add([], 2);
  expect(cartReducer(lines, { type: 'set', variantId: 'v1', qty: 99, max: 5 })[0]!.qty).toBe(5);
  expect(cartReducer(lines, { type: 'set', variantId: 'v1', qty: 0, max: 5 })).toEqual([]);
  expect(cartReducer(lines, { type: 'remove', variantId: 'v1' })).toEqual([]);
  expect(cartReducer(lines, { type: 'clear' })).toEqual([]);
});

test('reconcile drops missing or sold-out variants and clamps quantities', () => {
  const lines: CartLine[] = [
    { variantId: 'v1', handle: 'a', qty: 9 },
    { variantId: 'v2', handle: 'a', qty: 1 },
    { variantId: 'gone', handle: 'a', qty: 1 },
    { variantId: 'v1', handle: 'nope', qty: 1 },
  ];
  expect(reconcile(lines, [product])).toEqual([{ variantId: 'v1', handle: 'a', qty: 5 }]);
});

test('cartDetail totals the cart', () => {
  const d = cartDetail([{ variantId: 'v1', handle: 'a', qty: 3 }], [product]);
  expect(d.count).toBe(3);
  expect(d.subtotalCents).toBe(6000);
  expect(d.lines[0]).toMatchObject({ productTitle: 'Alpha', variantTitle: '250g', unitCents: 2000, lineCents: 6000, max: 5 });
});

test('shippingProgress reports what is left for free shipping', () => {
  expect(shippingProgress(1500)).toEqual({ remainingCents: 4500, ratio: 0.25 });
  expect(shippingProgress(9000)).toEqual({ remainingCents: 0, ratio: 1 });
});

test('the cart round-trips through storage under the versioned key', () => {
  const store = new Map<string, string>();
  const storage = { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v) };
  const lines = [{ variantId: 'v1', handle: 'a', qty: 2 }];
  expect(saveLines(lines, () => storage)).toBe(true);
  expect(store.has(CART_KEY)).toBe(true);
  expect(loadLines(() => storage)).toEqual(lines);
});

test('loadLines survives corrupt data, wrong shapes and storage that throws', () => {
  const bad = (raw: string | null) => () => ({ getItem: () => raw });
  expect(loadLines(bad('not json'))).toEqual([]);
  expect(loadLines(bad('{"a":1}'))).toEqual([]);
  expect(loadLines(bad('[{"variantId":1,"handle":"a","qty":2}]'))).toEqual([]);
  expect(loadLines(bad('[{"variantId":"v","handle":"a","qty":0}]'))).toEqual([]);
  expect(loadLines(() => ({ getItem: () => { throw new Error('blocked'); } }))).toEqual([]);
  // Reading window.localStorage itself can throw (blocked site data), before getItem is ever called.
  expect(loadLines(() => { throw new Error('access denied'); })).toEqual([]);
  expect(saveLines([], () => ({ setItem: () => { throw new Error('quota'); } }))).toBe(false);
  expect(saveLines([], () => { throw new Error('access denied'); })).toBe(false);
});
