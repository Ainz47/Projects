import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { runSeedImages } from '../exporter/seed-images.mjs';
import { COLLECTIONS, FEATURED, runSeedCollections } from '../exporter/seed-collections.mjs';

const nodes = JSON.parse(readFileSync(resolve(process.cwd(), 'data/catalog.fixture.json'), 'utf8')).data.products.nodes as any[];
const ONLINE = { id: 'gid://shopify/Publication/1', name: 'Online Store' };

type Call = { kind: string; variables: any };

// A stand-in store that keeps state, so a second run can be shown to change nothing. It answers by the shape of the query.
function fakeStore({ handles = nodes.map((n) => n.handle), publications = [ONLINE], frontpage = true } = {}) {
  const calls: Call[] = [];
  const products = new Map(handles.map((h, i) => [h, { id: `gid://shopify/Product/${i + 1}`, handle: h, media: 0 }]));
  const collections = new Map<string, { id: string; handle: string; products: string[] }>();
  if (frontpage) collections.set('frontpage', { id: 'gid://shopify/Collection/1', handle: 'frontpage', products: [] });
  const kindOf = (q: string) =>
    ['stagedUploadsCreate', 'productUpdate', 'collectionCreate', 'collectionAddProducts', 'publishablePublish', 'publications', 'collectionByIdentifier', 'collections(', 'products('].find((k) =>
      q.includes(k),
    ) ?? 'unknown';
  return {
    calls,
    products,
    collections,
    graphql: async (query: string, variables: any = {}) => {
      const kind = kindOf(query);
      calls.push({ kind, variables });
      switch (kind) {
        case 'products(':
          return {
            products: {
              pageInfo: { hasNextPage: false, endCursor: null },
              nodes: [...products.values()].map((p) => ({ id: p.id, handle: p.handle, mediaCount: { count: p.media } })),
            },
          };
        case 'stagedUploadsCreate':
          return {
            stagedUploadsCreate: {
              stagedTargets: variables.input.map((i: any) => ({ url: `https://upload.test/${i.filename}`, resourceUrl: `https://cdn.test/${i.filename}`, parameters: [{ name: 'key', value: i.filename }] })),
              userErrors: [],
            },
          };
        case 'productUpdate': {
          const p = [...products.values()].find((x) => x.id === variables.product.id)!;
          if (p.handle === 'kiambu-aa-kenya' && failKiambu.on) return { productUpdate: { product: null, userErrors: [{ field: ['media'], message: 'Image could not be read' }] } };
          p.media += variables.media.length;
          return { productUpdate: { product: { id: p.id }, userErrors: [] } };
        }
        case 'publications':
          return { publications: { nodes: publications } };
        case 'collections(':
          return { collections: { nodes: [...collections.values()].map(({ id, handle }) => ({ id, handle })) } };
        case 'collectionCreate': {
          const c = { id: `gid://shopify/Collection/${collections.size + 1}`, handle: variables.input.handle, products: [] as string[] };
          collections.set(c.handle, c);
          return { collectionCreate: { collection: { id: c.id }, userErrors: [] } };
        }
        case 'collectionByIdentifier': {
          const c = collections.get(variables.handle);
          return { collectionByIdentifier: c ? { id: c.id, products: { nodes: c.products.map((id) => ({ id })) } } : null };
        }
        case 'collectionAddProducts': {
          const c = [...collections.values()].find((x) => x.id === variables.id)!;
          c.products.push(...variables.productIds);
          return { collectionAddProducts: { userErrors: [] } };
        }
        case 'publishablePublish':
          return { publishablePublish: { userErrors: [] } };
      }
      throw new Error(`fake store got an unexpected query: ${query.slice(0, 40)}`);
    },
  };
}
const failKiambu = { on: false };
beforeEach(() => {
  failKiambu.on = false;
});

const png = Buffer.from([0x89, 0x50, 0x4e, 0x47]);
function imageDeps() {
  const rendered: string[] = [];
  const uploaded: { url: string; filename: string; body: Buffer }[] = [];
  return {
    rendered,
    uploaded,
    render: async (node: any) => {
      rendered.push(node.handle);
      return png;
    },
    upload: async (target: any, body: Buffer, filename: string) => {
      uploaded.push({ url: target.url, filename, body });
    },
  };
}

describe('seed images', () => {
  test('finds every product in the store before it writes anything', async () => {
    const store = fakeStore({ handles: nodes.slice(1).map((n) => n.handle) });
    await expect(runSeedImages({ client: store, nodes, ...imageDeps() })).rejects.toThrow(/yirgacheffe-washed-ethiopia.*seed:shopify/);
    expect(store.calls.some((c) => ['stagedUploadsCreate', 'productUpdate'].includes(c.kind))).toBe(false);
  });

  test('renders, uploads and attaches one image per product, with the product title as alt text', async () => {
    const store = fakeStore();
    const deps = imageDeps();
    const result = await runSeedImages({ client: store, nodes, ...deps });
    expect(result).toEqual({ added: 30, skipped: 0 });
    expect(deps.rendered).toHaveLength(30);
    expect(deps.uploaded[0]).toMatchObject({ filename: 'yirgacheffe-washed-ethiopia.png', url: 'https://upload.test/yirgacheffe-washed-ethiopia.png', body: png });
    const first = store.calls.filter((c) => ['stagedUploadsCreate', 'upload', 'productUpdate'].includes(c.kind)).slice(0, 2);
    expect(first.map((c) => c.kind)).toEqual(['stagedUploadsCreate', 'productUpdate']);
    const update = store.calls.find((c) => c.kind === 'productUpdate')!.variables;
    expect(update.media).toEqual([{ originalSource: 'https://cdn.test/yirgacheffe-washed-ethiopia.png', mediaContentType: 'IMAGE', alt: 'Yirgacheffe Washed Ethiopia' }]);
  });

  test('a second run adds nothing: products that already have media are skipped', async () => {
    const store = fakeStore();
    await runSeedImages({ client: store, nodes, ...imageDeps() });
    const again = imageDeps();
    const result = await runSeedImages({ client: store, nodes, ...again });
    expect(result).toEqual({ added: 0, skipped: 30 });
    expect(again.rendered).toHaveLength(0);
  });

  test('names the product when Shopify rejects an image, and keeps the ones already attached', async () => {
    const store = fakeStore();
    failKiambu.on = true;
    await expect(runSeedImages({ client: store, nodes, ...imageDeps() })).rejects.toThrow(/kiambu-aa-kenya: Image could not be read/);
    expect(store.products.get('huila-reserve-colombia')!.media).toBe(1);
  });
});

describe('seed collections', () => {
  test('creates each collection with its rules and publishes it to the Online Store', async () => {
    const store = fakeStore();
    await runSeedCollections({ client: store, nodes });
    expect([...store.collections.keys()].sort()).toEqual(['brewing-gear', 'coffee', 'dark-roast', 'frontpage', 'light-roast', 'medium-roast']);
    const creates = store.calls.filter((c) => c.kind === 'collectionCreate').map((c) => c.variables.input);
    expect(creates.find((c: any) => c.handle === 'coffee')).toMatchObject({
      title: 'Coffee',
      ruleSet: { appliedDisjunctively: false, rules: [{ column: 'TYPE', relation: 'EQUALS', condition: 'Coffee' }] },
    });
    const gear = creates.find((c: any) => c.handle === 'brewing-gear');
    expect(gear.ruleSet.appliedDisjunctively).toBe(true);
    expect(gear.ruleSet.rules.map((r: any) => r.condition).sort()).toEqual(['Accessory', 'Dripper', 'Grinder', 'Kettle']);
    expect(creates.find((c: any) => c.handle === 'light-roast').ruleSet.rules).toEqual([{ column: 'TAG', relation: 'EQUALS', condition: 'light-roast' }]);
    expect(store.calls.filter((c) => c.kind === 'publishablePublish')).toHaveLength(COLLECTIONS.length);
  });

  test('puts the featured products on the front page collection, only the ones missing', async () => {
    const store = fakeStore();
    store.collections.get('frontpage')!.products.push(store.products.get(FEATURED[0])!.id);
    await runSeedCollections({ client: store, nodes });
    const add = store.calls.find((c) => c.kind === 'collectionAddProducts')!.variables;
    expect(add.productIds).toHaveLength(FEATURED.length - 1);
    expect(add.productIds).not.toContain(store.products.get(FEATURED[0])!.id);
  });

  test('a second run creates and adds nothing', async () => {
    const store = fakeStore();
    await runSeedCollections({ client: store, nodes });
    const before = store.calls.length;
    await runSeedCollections({ client: store, nodes });
    const later = store.calls.slice(before).map((c) => c.kind);
    expect(later).not.toContain('collectionCreate');
    expect(later).not.toContain('collectionAddProducts');
  });

  test('writes nothing when the Online Store channel or the front page collection is missing', async () => {
    const noChannel = fakeStore({ publications: [{ id: 'gid://shopify/Publication/2', name: 'Shop' }] });
    await expect(runSeedCollections({ client: noChannel, nodes })).rejects.toThrow(/Online Store/);
    expect(noChannel.calls.some((c) => c.kind === 'collectionCreate')).toBe(false);
    const noFront = fakeStore({ frontpage: false });
    await expect(runSeedCollections({ client: noFront, nodes })).rejects.toThrow(/frontpage/);
    expect(noFront.calls.some((c) => c.kind === 'collectionCreate')).toBe(false);
  });

  test('every featured handle exists in the catalog', () => {
    const handles = new Set(nodes.map((n) => n.handle));
    for (const h of FEATURED) expect(handles.has(h)).toBe(true);
  });
});
