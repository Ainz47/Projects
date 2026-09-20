// Writes data/catalog.export.json from a real store. Needs SHOPIFY_SHOP, SHOPIFY_CLIENT_ID and
// SHOPIFY_CLIENT_SECRET in the environment. Never prints or stores the access token.
import { writeFileSync } from 'node:fs';
import { getAccessToken } from './auth.mjs';
import { createClient, fetchAllProducts } from './client.mjs';

try {
  const shop = process.env.SHOPIFY_SHOP;
  const token = await getAccessToken({
    shop,
    clientId: process.env.SHOPIFY_CLIENT_ID,
    clientSecret: process.env.SHOPIFY_CLIENT_SECRET,
  });
  const nodes = await fetchAllProducts(createClient({ shop, token }));
  const out = { data: { products: { nodes } } };
  writeFileSync(new URL('../data/catalog.export.json', import.meta.url), JSON.stringify(out, null, 2) + '\n');
  console.log(`exported ${nodes.length} products to data/catalog.export.json`);
} catch (err) {
  console.error(`export failed: ${err.message}`);
  process.exit(1);
}
