import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { assertTargetShop, runSeed } from '../exporter/seed.mjs';

const nodes = JSON.parse(readFileSync(resolve(process.cwd(), 'data/catalog.fixture.json'), 'utf8')).data.products.nodes as any[];

type Options = { publications?: { id: string; name: string }[]; failHandle?: string };

// A stand-in for the Shopify client: answers by the shape of the query and records every call.
function fakeClient({ publications = [{ id: 'gid://shopify/Publication/1', name: 'Online Store' }], failHandle = '' }: Options = {}) {
  const calls: { kind: string; variables: any }[] = [];
  const kindOf = (query: string) =>
    query.includes('productSet') ? 'productSet' : query.includes('publishablePublish') ? 'publish' : query.includes('publications') ? 'publications' : 'locations';
  return {
    calls,
    graphql: async (query: string, variables: any = {}) => {
      const kind = kindOf(query);
      calls.push({ kind, variables });
      if (kind === 'locations') return { locations: { nodes: [{ id: 'gid://shopify/Location/9' }] } };
      if (kind === 'publications') return { publications: { nodes: publications } };
      if (kind === 'productSet') {
        const handle = variables.identifier.handle;
        if (handle === failHandle) return { productSet: { product: null, userErrors: [{ field: ['input'], message: 'Title is invalid' }] } };
        return { productSet: { product: { id: `gid://shopify/Product/${calls.length}`, handle }, userErrors: [] } };
      }
      return { publishablePublish: { userErrors: [] } };
    },
  };
}

test('checks the location and the Online Store channel before it writes anything', async () => {
  const client = fakeClient();
  await runSeed({ client, nodes });
  expect(client.calls.slice(0, 3).map((c) => c.kind)).toEqual(['locations', 'publications', 'productSet']);
});

test('writes nothing when the store has no Online Store channel', async () => {
  const client = fakeClient({ publications: [{ id: 'gid://shopify/Publication/2', name: 'Shop' }] });
  await expect(runSeed({ client, nodes })).rejects.toThrow(/Online Store/);
  expect(client.calls.some((c) => c.kind === 'productSet')).toBe(false);
});

test('upserts each product by handle with its options, variants, stock at the location and metafields', async () => {
  const client = fakeClient();
  await runSeed({ client, nodes });
  const first = client.calls.find((c) => c.kind === 'productSet')!.variables;
  expect(first.identifier).toEqual({ handle: 'yirgacheffe-washed-ethiopia' });
  const input = first.input;
  expect(input).toMatchObject({
    title: 'Yirgacheffe Washed Ethiopia',
    handle: 'yirgacheffe-washed-ethiopia',
    vendor: 'Lantern Roasters',
    productType: 'Coffee',
    status: 'ACTIVE',
    tags: nodes[0].tags,
    descriptionHtml: nodes[0].description,
  });
  expect(input.productOptions).toEqual([
    { name: 'Weight', position: 1, values: [{ name: '250g' }, { name: '1kg' }] },
    { name: 'Grind', position: 2, values: [{ name: 'Whole bean' }, { name: 'Espresso' }, { name: 'Filter' }] },
  ]);
  expect(input.variants[0]).toEqual({
    optionValues: [
      { optionName: 'Weight', name: '250g' },
      { optionName: 'Grind', name: 'Whole bean' },
    ],
    sku: 'YIRGACHE-250g-WH',
    price: '18.00',
    inventoryQuantities: [{ locationId: 'gid://shopify/Location/9', name: 'available', quantity: 15 }],
  });
  expect(input.metafields.length).toBeGreaterThan(0);
  expect(input.metafields).toEqual(nodes[0].metafields.nodes.map((m: any) => ({ ...m, type: 'single_line_text_field' })));
});

test('loads every product and variant and publishes each product to the Online Store', async () => {
  const client = fakeClient();
  const result = await runSeed({ client, nodes });
  const sets = client.calls.filter((c) => c.kind === 'productSet');
  const published = client.calls.filter((c) => c.kind === 'publish');
  expect(sets).toHaveLength(30);
  expect(sets.reduce((n, c) => n + c.variables.input.variants.length, 0)).toBe(124);
  expect(published).toHaveLength(30);
  expect(published[0]!.variables.id).toMatch(/Product/);
  expect(published[0]!.variables.input).toEqual([{ publicationId: 'gid://shopify/Publication/1' }]);
  expect(result).toEqual({ products: 30, variants: 124 });
});

test('stops at the first product Shopify rejects and names it', async () => {
  const client = fakeClient({ failHandle: nodes[2].handle });
  await expect(runSeed({ client, nodes })).rejects.toThrow(new RegExp(`${nodes[2].handle}.*Title is invalid`));
  expect(client.calls.filter((c) => c.kind === 'productSet')).toHaveLength(3);
});

test('refuses to write unless the store named on the command line is the one the settings point at', () => {
  expect(() => assertTargetShop('jhurald05', 'jhurald05')).not.toThrow();
  expect(() => assertTargetShop('jhurald05', undefined)).toThrow(/--to/);
  expect(() => assertTargetShop('jhurald05', 'other-store')).toThrow(/other-store/);
});
