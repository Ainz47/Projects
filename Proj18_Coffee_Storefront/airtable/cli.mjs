// Writes data/catalog.export.json from an Airtable base. Needs AIRTABLE_TOKEN and AIRTABLE_BASE_ID; the npm script
// loads them from .env.local. Nothing here prints or writes the credential.
import { writeFileSync } from 'node:fs';
import { createClient } from './client.mjs';
import { readConfig } from './config.mjs';
import { recordsToNodes } from './map.mjs';
import { PRODUCTS, VARIANTS } from './schema.mjs';

try {
  const client = createClient(readConfig());
  const products = await client.listAll(PRODUCTS);
  const variants = await client.listAll(VARIANTS);
  const nodes = recordsToNodes({ products, variants });
  const out = { data: { products: { nodes } } };
  writeFileSync(new URL('../data/catalog.export.json', import.meta.url), JSON.stringify(out, null, 2) + '\n');
  console.log(`exported ${nodes.length} products (${variants.length} variants) to data/catalog.export.json`);
} catch (err) {
  console.error(`export failed: ${err.message}`);
  process.exit(1);
}
