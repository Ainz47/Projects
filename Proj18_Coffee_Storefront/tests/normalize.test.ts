import { normalizeProducts } from '../src/model/normalize';

const variant = (over: Record<string, unknown> = {}) => ({
  id: 'gid://shopify/ProductVariant/1',
  title: '250g / Whole bean',
  sku: 'SKU-1',
  price: '18.50',
  inventoryQuantity: 12,
  selectedOptions: [
    { name: 'Weight', value: '250g' },
    { name: 'Grind', value: 'Whole bean' },
  ],
  ...over,
});

const node = (over: Record<string, unknown> = {}) => ({
  id: 'gid://shopify/Product/1',
  title: 'Yirgacheffe Washed',
  handle: 'yirgacheffe-washed',
  vendor: 'Lantern Roasters',
  productType: 'Coffee',
  tags: ['single-origin', 'fruity'],
  description: 'Bright and floral.',
  options: [
    { name: 'Weight', values: ['250g', '1kg'] },
    { name: 'Grind', values: ['Whole bean', 'Filter'] },
  ],
  variants: { nodes: [variant()] },
  metafields: {
    nodes: [
      { namespace: 'custom', key: 'origin', value: 'Ethiopia' },
      { namespace: 'custom', key: 'roast', value: 'Light' },
    ],
  },
  ...over,
});

test('maps a valid node to a Product', () => {
  const { products, rejected } = normalizeProducts([node()]);
  expect(rejected).toEqual([]);
  const p = products[0]!;
  expect(p.handle).toBe('yirgacheffe-washed');
  expect(p.type).toBe('Coffee');
  expect(p.origin).toBe('Ethiopia');
  expect(p.roast).toBe('Light');
  expect(p.optionNames).toEqual(['Weight', 'Grind']);
  expect(p.optionValues.Weight).toEqual(['250g', '1kg']);
  expect(p.variants[0]).toMatchObject({ priceCents: 1850, inventory: 12, available: true });
  expect(p.variants[0]!.options).toEqual({ Weight: '250g', Grind: 'Whole bean' });
});

test('computes price range, availability and low stock', () => {
  const vs = [
    variant({ id: 'v1', price: '10.00', inventoryQuantity: 0 }),
    variant({ id: 'v2', price: '30.00', inventoryQuantity: 3 }),
  ];
  const { products } = normalizeProducts([node({ variants: { nodes: vs } })]);
  const p = products[0]!;
  expect([p.minCents, p.maxCents]).toEqual([1000, 3000]);
  expect(p.available).toBe(true);
  expect(p.lowStock).toBe(true);
});

test('a product with every variant at zero is unavailable and not low stock', () => {
  const vs = [variant({ inventoryQuantity: 0 })];
  const p = normalizeProducts([node({ variants: { nodes: vs } })]).products[0]!;
  expect(p.available).toBe(false);
  expect(p.lowStock).toBe(false);
});

test('a missing origin or roast metafield becomes null', () => {
  const p = normalizeProducts([node({ metafields: { nodes: [] } })]).products[0]!;
  expect(p.origin).toBeNull();
  expect(p.roast).toBeNull();
});

test.each([
  ['missing title', { title: '' }, 'missing title'],
  ['bad handle', { handle: 'Has Spaces' }, 'invalid handle'],
  ['no variants', { variants: { nodes: [] } }, 'no variants'],
  ['bad price', { variants: { nodes: [variant({ price: 'abc' })] } }, 'invalid price'],
  ['no inventory count', { variants: { nodes: [variant({ inventoryQuantity: null })] } }, 'inventory'],
])('rejects a node with %s and says why', (_name, over, fragment) => {
  const { products, rejected } = normalizeProducts([node(over)]);
  expect(products).toEqual([]);
  expect(rejected).toHaveLength(1);
  expect(rejected[0]!.reason).toContain(fragment);
});

test('rejects a duplicate handle but keeps the first', () => {
  const { products, rejected } = normalizeProducts([node(), node({ id: 'gid://shopify/Product/2' })]);
  expect(products).toHaveLength(1);
  expect(rejected[0]!.reason).toContain('duplicate handle');
});

test('rejects non-object entries without throwing', () => {
  const { products, rejected } = normalizeProducts([null, 42, 'x']);
  expect(products).toEqual([]);
  expect(rejected).toHaveLength(3);
});

test('a product keeps its collections, drops malformed entries, and has none when the store sent none', () => {
  const sent = node({ collections: [{ handle: 'light-roast', title: 'Light roast' }, { handle: 'coffee' }, { handle: 'Not A Handle', title: 'x' }, null, 'coffee'] });
  expect(normalizeProducts([sent]).products[0]!.collections).toEqual([
    { handle: 'light-roast', title: 'Light roast' },
    { handle: 'coffee', title: 'coffee' },
  ]);
  expect(normalizeProducts([node()]).products[0]!.collections).toEqual([]);
});
