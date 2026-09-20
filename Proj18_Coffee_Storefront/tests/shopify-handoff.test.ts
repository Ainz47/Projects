import { handOffToShopify, numericVariantId } from '../src/lib/shopifyCart';

type Call = { url: string; init: any };
function fakeShopify({ addStatus = 200, addBody = {} as any } = {}) {
  const calls: Call[] = [];
  const navigated: string[] = [];
  const fetchImpl = (async (url: string, init: any) => {
    calls.push({ url, init });
    const isAdd = url === '/cart/add.js';
    return { ok: !isAdd || addStatus < 400, status: isAdd ? addStatus : 200, json: async () => (isAdd ? addBody : {}) } as Response;
  }) as unknown as typeof fetch;
  return { calls, navigated, deps: { fetchImpl, navigate: (u: string) => navigated.push(u) } };
}

const lines = [
  { variantId: '9001', qty: 2 },
  { variantId: 'gid://shopify/ProductVariant/9002', qty: 1 },
];

test('reads the numeric variant id from a plain id or a global id, and refuses anything else', () => {
  expect(numericVariantId('9001')).toBe(9001);
  expect(numericVariantId('gid://shopify/ProductVariant/9002')).toBe(9002);
  expect(numericVariantId('rec123abc')).toBeNull();
  expect(numericVariantId('')).toBeNull();
});

test('empties the Shopify cart, adds the lines, then goes to the checkout, in that order', async () => {
  const s = fakeShopify();
  await handOffToShopify(lines, s.deps);
  expect(s.calls.map((c) => c.url)).toEqual(['/cart/clear.js', '/cart/add.js']);
  expect(s.calls.every((c) => c.init.method === 'POST')).toBe(true);
  expect(s.calls[1]!.init.headers['Content-Type']).toBe('application/json');
  expect(JSON.parse(s.calls[1]!.init.body)).toEqual({ items: [{ id: 9001, quantity: 2 }, { id: 9002, quantity: 1 }] });
  expect(s.navigated).toEqual(['/checkout']);
});

test('sends nothing when a line is not a Shopify variant, for example on the GitHub page', async () => {
  const s = fakeShopify();
  await expect(handOffToShopify([{ variantId: 'recABC', qty: 1 }], s.deps)).rejects.toThrow(/not a Shopify variant/);
  expect(s.calls).toEqual([]);
  expect(s.navigated).toEqual([]);
});

test('shows Shopify\'s own message and does not navigate when the add is refused', async () => {
  const s = fakeShopify({ addStatus: 422, addBody: { description: 'All 5 of Antigua Volcanic are in your cart.' } });
  await expect(handOffToShopify(lines, s.deps)).rejects.toThrow('All 5 of Antigua Volcanic are in your cart.');
  expect(s.navigated).toEqual([]);
});

test('falls back to a plain message when the refusal has no description', async () => {
  const s = fakeShopify({ addStatus: 500 });
  await expect(handOffToShopify(lines, s.deps)).rejects.toThrow(/could not add/i);
});

test('refuses an empty cart', async () => {
  const s = fakeShopify();
  await expect(handOffToShopify([], s.deps)).rejects.toThrow(/empty/i);
  expect(s.calls).toEqual([]);
});
