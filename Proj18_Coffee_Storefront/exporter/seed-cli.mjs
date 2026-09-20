// Loads the fixture catalog into the Shopify store named in SHOPIFY_SHOP, creating or updating each product by handle.
// Run: npm run seed:shopify -- --to <store>   (the store must be named here as well as in .env.local)
import { readFileSync } from 'node:fs';
import { getAccessToken } from './auth.mjs';
import { createClient } from './client.mjs';
import { assertTargetShop, runSeed } from './seed.mjs';

try {
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
  const result = await runSeed({ client, nodes, log: console.log });
  console.log(`seeded ${result.products} products and ${result.variants} variants into ${shop}`);
} catch (err) {
  console.error(`seed failed: ${err.message}`);
  process.exit(1);
}
