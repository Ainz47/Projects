import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { AirtableDataError, nodesToRecords, recordsToNodes } from '../airtable/map.mjs';

const nodes = JSON.parse(readFileSync(resolve(process.cwd(), 'data/catalog.fixture.json'), 'utf8')).data.products.nodes as any[];

const stripIds = (list: any[]) =>
  list.map((n) => ({ ...n, id: undefined, variants: { nodes: n.variants.nodes.map((v: any) => ({ ...v, id: undefined })) } }));

// What Airtable would hold after the seed: record ids assigned and link cells filled.
function asAirtable(list: any[]) {
  const built = nodesToRecords(list);
  const products = built.products.map((p: any, i: number) => ({ id: `recP${i}`, fields: p.fields }));
  const variants = built.variants.map((v: any, i: number) => ({
    id: `recV${i}`,
    fields: { ...v.fields, Product: [`recP${v.productIndex}`] },
  }));
  return { products, variants };
}

const product = (id: string, over: Record<string, unknown> = {}) => ({
  id,
  fields: { Title: 'Kiln Roast', Handle: 'kiln-roast', 'Option 1 Name': 'Weight', Position: 1, ...over },
});
const variant = (id: string, productId: string, over: Record<string, unknown> = {}) => ({
  id,
  fields: { SKU: 'K-250', Product: [productId], 'Option 1': '250g', Price: 18, Stock: 5, Position: 1, ...over },
});
const failure = (fn: () => unknown) => {
  try {
    fn();
  } catch (e) {
    return e as Error;
  }
  return undefined;
};

test('the fixture survives a round trip through Airtable records, ids aside', () => {
  const { products, variants } = asAirtable(nodes);
  // Airtable promises no order, so hand the mapper both lists reversed.
  const back = recordsToNodes({ products: [...products].reverse(), variants: [...variants].reverse() });
  expect(stripIds(back)).toEqual(stripIds(nodes));
});

test('the seed side never writes an empty cell', () => {
  const { products, variants } = nodesToRecords(nodes);
  for (const rec of [...products, ...variants]) {
    for (const [key, value] of Object.entries(rec.fields)) {
      expect(value, key).not.toBe('');
      expect(value, key).not.toBeUndefined();
    }
  }
  // Gear has no origin or roast, so those cells are left out rather than written empty.
  expect(products.some((p: any) => !('Origin' in p.fields))).toBe(true);
});

test('the seed side refuses what the layout cannot hold', () => {
  const three = { ...nodes[0], options: [{ name: 'A' }, { name: 'B' }, { name: 'C' }] };
  expect(() => nodesToRecords([three])).toThrow(/one or two options/);
  const comma = { ...nodes[0], tags: ['dark, roasted'] };
  expect(() => nodesToRecords([comma])).toThrow(/contains a comma/);
});

test('a valid product and variant map to one node', () => {
  const out = recordsToNodes({ products: [product('recP1')], variants: [variant('recV1', 'recP1')] });
  expect(out).toEqual([
    {
      id: 'recP1',
      title: 'Kiln Roast',
      handle: 'kiln-roast',
      vendor: '',
      productType: '',
      tags: [],
      description: '',
      options: [{ name: 'Weight', values: ['250g'] }],
      variants: {
        nodes: [
          {
            id: 'recV1',
            title: '250g',
            sku: 'K-250',
            price: '18.00',
            inventoryQuantity: 5,
            selectedOptions: [{ name: 'Weight', value: '250g' }],
          },
        ],
      },
      metafields: { nodes: [] },
    },
  ]);
});

test('products and variants come out in Position order, not the order Airtable returned them', () => {
  const out = recordsToNodes({
    products: [product('recP2', { Title: 'B', Handle: 'b', Position: 2 }), product('recP1', { Title: 'A', Handle: 'a', Position: 1 })],
    variants: [
      variant('recV2', 'recP1', { 'Option 1': '1kg', Position: 2 }),
      variant('recV1', 'recP1', { 'Option 1': '250g', Position: 1 }),
      variant('recV3', 'recP2'),
    ],
  }) as any[];
  expect(out.map((n) => n.handle)).toEqual(['a', 'b']);
  expect(out[0].variants.nodes.map((v: any) => v.title)).toEqual(['250g', '1kg']);
  expect(out[0].options).toEqual([{ name: 'Weight', values: ['250g', '1kg'] }]);
});

const badVariants: [string, Record<string, unknown>, RegExp][] = [
  ['a variant with no product link', { Product: [] }, /Variants recV1: Product must link to exactly one product, found 0/],
  ['a price stored as text', { Price: '18.00' }, /Variants recV1: Price must be a number/],
  ['a negative price', { Price: -1 }, /Variants recV1: Price must be a number/],
  ['a fractional stock count', { Stock: 2.5 }, /Variants recV1: Stock must be a whole number/],
  ['a negative stock count', { Stock: -3 }, /Variants recV1: Stock must be a whole number/],
  ['a missing position', { Position: undefined }, /Variants recV1: Position must be a whole number/],
  ['a missing option value', { 'Option 1': undefined }, /Variants recV1: Option 1 is empty/],
  ['an option value with no option name', { 'Option 2': 'Whole bean' }, /Variants recV1: Option 2 has a value/],
];

test.each(badVariants)('rejects %s and names the record', (_label, over, pattern) => {
  expect(() => recordsToNodes({ products: [product('recP1')], variants: [variant('recV1', 'recP1', over)] })).toThrow(pattern);
});

test('rejects a link to a product that is not in the table', () => {
  expect(() => recordsToNodes({ products: [product('recP1')], variants: [variant('recV1', 'recNOPE')] })).toThrow(
    /Variants recV1: Product links to recNOPE/,
  );
});

test('rejects a product with no title, handle, first option, position or variants, and says so for each', () => {
  const err = failure(() =>
    recordsToNodes({
      products: [product('recP1', { Title: '', Handle: undefined, 'Option 1 Name': undefined, Position: undefined })],
      variants: [],
    }),
  );
  expect(err).toBeInstanceOf(AirtableDataError);
  for (const pattern of [/Products recP1: Title is empty/, /Handle is empty/, /Option 1 Name is empty/, /Position must be a whole number/, /has no variants/]) {
    expect(err?.message).toMatch(pattern);
  }
});

test('reports every problem in one error, not just the first', () => {
  const err = failure(() =>
    recordsToNodes({
      products: [product('recP1')],
      variants: [variant('recV1', 'recP1', { Price: 'x' }), variant('recV2', 'recP1', { Stock: -1 })],
    }),
  ) as AirtableDataError;
  expect(err.problems).toHaveLength(2);
  expect(err.message).toMatch(/2 problems/);
  expect(err.message).toMatch(/recV1/);
  expect(err.message).toMatch(/recV2/);
});
