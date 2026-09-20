// Loads the fixture catalog into an Airtable base, creating the Products and Variants tables if they are missing.
// Run: npm run seed:airtable   (add -- --allow-existing to write into tables that already hold rows)
import { readFileSync } from 'node:fs';
import { createClient } from './client.mjs';
import { readConfig } from './config.mjs';
import { runSeed } from './seed.mjs';

try {
  const client = createClient(readConfig());
  const nodes = JSON.parse(readFileSync(new URL('../data/catalog.fixture.json', import.meta.url), 'utf8')).data.products.nodes;
  const result = await runSeed({ client, nodes, allowExisting: process.argv.includes('--allow-existing'), log: console.log });
  console.log(`seeded ${result.products} products and ${result.variants} variants`);
} catch (err) {
  console.error(`seed failed: ${err.message}`);
  process.exit(1);
}
