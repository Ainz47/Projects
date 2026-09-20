// Dresses the store that `seed:shopify` filled: a picture for each product and the collections.
// Run: npm run seed:store -- images|collections|all --to <store>   (the store must be named here as well as in .env.local)
// The pictures are the demo page's generated art, rendered to PNG, so the store and the page look alike.
import { readFileSync } from 'node:fs';
import { Resvg } from '@resvg/resvg-js';
import { createServer } from 'vite';
import { getAccessToken } from './auth.mjs';
import { createClient } from './client.mjs';
import { assertTargetShop } from './seed.mjs';
import { runSeedCollections } from './seed-collections.mjs';
import { runSeedImages } from './seed-images.mjs';

const STEPS = ['images', 'collections', 'all'];
const IMAGE_WIDTH = 1600;

// The art module is TypeScript, so it is loaded through Vite, the same pipeline that builds the page.
async function loadArt(nodes) {
  const vite = await createServer({ appType: 'custom', server: { middlewareMode: true }, logLevel: 'error' });
  const { artFor } = await vite.ssrLoadModule('/src/art/index.ts');
  const { normalizeProducts } = await vite.ssrLoadModule('/src/model/normalize.ts');
  const byHandle = new Map(normalizeProducts(nodes).products.map((p) => [p.handle, p]));
  const render = async (node) => {
    const product = byHandle.get(node.handle);
    if (!product) throw new Error(`${node.handle}: the catalog normalizer rejected this product, so it has no art`);
    return new Resvg(artFor(product), { fitTo: { mode: 'width', value: IMAGE_WIDTH } }).render().asPng();
  };
  return { render, close: () => vite.close() };
}

// Shopify's staged upload target takes a multipart form: its own parameters first, then the file.
async function upload(target, body, filename) {
  const form = new FormData();
  for (const { name, value } of target.parameters) form.append(name, value);
  form.append('file', new Blob([body], { type: 'image/png' }), filename);
  const res = await fetch(target.url, { method: 'POST', body: form });
  if (!res.ok) throw new Error(`${filename}: the image upload failed with HTTP ${res.status}`);
}

try {
  const step = process.argv[2];
  if (!STEPS.includes(step)) throw new Error(`Pass one of ${STEPS.join(', ')} as the first argument`);
  const shop = process.env.SHOPIFY_SHOP;
  const flag = process.argv.indexOf('--to');
  assertTargetShop(shop, flag === -1 ? undefined : process.argv[flag + 1]);
  const token = await getAccessToken({
    shop,
    clientId: process.env.SHOPIFY_CLIENT_ID,
    clientSecret: process.env.SHOPIFY_CLIENT_SECRET,
  });
  const nodes = JSON.parse(readFileSync(new URL('../data/catalog.fixture.json', import.meta.url), 'utf8')).data.products.nodes;
  const client = createClient({ shop, token });

  if (step === 'images' || step === 'all') {
    const art = await loadArt(nodes);
    try {
      const result = await runSeedImages({ client, nodes, render: art.render, upload, log: console.log });
      console.log(`images: ${result.added} added, ${result.skipped} already had one`);
    } finally {
      await art.close();
    }
  }
  if (step === 'collections' || step === 'all') {
    const result = await runSeedCollections({ client, nodes, log: console.log });
    console.log(`collections: ${result.created} created, ${result.existing} already there, ${result.featuredAdded} featured products added`);
  }
} catch (err) {
  console.error(`seed:store failed: ${err.message}`);
  process.exit(1);
}
