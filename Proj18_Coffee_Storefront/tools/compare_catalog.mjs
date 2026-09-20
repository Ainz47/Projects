// Compares two catalog files and says whether they hold the same products, ignoring ids (Shopify and Airtable
// ids differ by design) and the order of tags (Shopify keeps tags as a set and returns them sorted).
// Run: npm run compare -- data/catalog.fixture.json data/catalog.export.json
import { readFileSync } from 'node:fs';
import { isDeepStrictEqual } from 'node:util';

const [aPath, bPath] = process.argv.slice(2);
if (!aPath || !bPath) {
  console.error('usage: npm run compare -- <catalog a> <catalog b>');
  process.exit(2);
}

const load = (path) =>
  JSON.parse(readFileSync(path, 'utf8')).data.products.nodes.map(({ id, variants, tags, ...rest }) => ({
    ...rest,
    tags: Array.isArray(tags) ? [...tags].sort() : tags,
    variants: variants.nodes.map(({ id: variantId, ...v }) => v),
  }));

const a = load(aPath);
const b = load(bPath);
const byHandle = new Map(b.map((p) => [p.handle, p]));
const problems = [];
for (const p of a) {
  const other = byHandle.get(p.handle);
  if (!other) {
    problems.push(`${p.handle}: missing from ${bPath}`);
    continue;
  }
  const keys = Object.keys({ ...p, ...other }).filter((k) => !isDeepStrictEqual(p[k], other[k]));
  if (keys.length > 0) problems.push(`${p.handle}: differs in ${keys.join(', ')}`);
}
for (const p of b) {
  if (!a.some((q) => q.handle === p.handle)) problems.push(`${p.handle}: only in ${bPath}`);
}

if (problems.length === 0) {
  console.log(`identical apart from ids and tag order (${a.length} products)`);
} else {
  console.log(problems.join('\n'));
  process.exit(1);
}
