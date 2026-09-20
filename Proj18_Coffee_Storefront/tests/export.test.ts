import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { normalizeProducts } from '../src/model/normalize';

const path = resolve(process.cwd(), 'data/catalog.export.json');

// The exported snapshot is what the built page shows, but the other tests read the fixture. This one keeps the
// snapshot honest: whatever was exported must normalize with nothing rejected.
test.skipIf(!existsSync(path))('the committed export normalizes with zero rejects', () => {
  const nodes = JSON.parse(readFileSync(path, 'utf8')).data.products.nodes as unknown[];
  const { products, rejected } = normalizeProducts(nodes);
  expect(rejected).toEqual([]);
  expect(products.length).toBeGreaterThan(0);
});
