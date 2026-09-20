const test = require('node:test');
const assert = require('node:assert/strict');
const { planUpdates, chunkUpdates } = require('../code/plan_updates.js');

const rows = [
  { id: 'rec1', sku: 'A-1', stock: 10 },
  { id: 'rec2', sku: 'B-2', stock: 4 },
];

test('a SKU whose stock differs becomes an update carrying the old and new number', () => {
  const r = planUpdates(['A-1'], { 'A-1': 7 }, rows);
  assert.deepEqual(r.updates, [{ recordId: 'rec1', sku: 'A-1', oldStock: 10, newStock: 7 }]);
  assert.equal(r.unchanged, 0);
});

test('a SKU that already matches is counted, not written', () => {
  const r = planUpdates(['B-2'], { 'B-2': 4 }, rows);
  assert.deepEqual(r.updates, []);
  assert.equal(r.unchanged, 1);
});

test('zero stock is written like any other number', () => {
  assert.deepEqual(planUpdates(['A-1'], { 'A-1': 0 }, rows).updates[0].newStock, 0);
});

test('an empty Airtable stock cell is updated and reports the old value as null', () => {
  const r = planUpdates(['C-3'], { 'C-3': 5 }, [{ id: 'rec3', sku: 'C-3', stock: null }]);
  assert.deepEqual(r.updates, [{ recordId: 'rec3', sku: 'C-3', oldStock: null, newStock: 5 }]);
});

test('a SKU with no Airtable row is skipped with a reason', () => {
  const r = planUpdates(['Z-9'], { 'Z-9': 3 }, rows);
  assert.deepEqual(r.skipped, [{ sku: 'Z-9', reason: 'no Airtable row' }]);
  assert.deepEqual(r.updates, []);
});

test('a SKU Shopify does not know is rejected, and so is one with no single tracked stock', () => {
  const r = planUpdates(['A-1', 'B-2'], { 'B-2': null }, rows);
  assert.deepEqual(r.rejected, [
    { sku: 'A-1', reason: 'SKU not found in Shopify' },
    { sku: 'B-2', reason: 'Shopify has no single tracked stock for this SKU' },
  ]);
});

test('negative or fractional Shopify stock is rejected', () => {
  const r = planUpdates(['A-1', 'B-2'], { 'A-1': -2, 'B-2': 1.5 }, rows);
  assert.deepEqual(r.rejected.map((x) => x.reason), [
    'Shopify stock is not a whole number of 0 or more',
    'Shopify stock is not a whole number of 0 or more',
  ]);
  assert.deepEqual(r.updates, []);
});

test('two Airtable rows with the same SKU are rejected instead of guessing which to write', () => {
  const dup = [...rows, { id: 'rec9', sku: 'A-1', stock: 1 }];
  const r = planUpdates(['A-1'], { 'A-1': 7 }, dup);
  assert.deepEqual(r.rejected, [{ sku: 'A-1', reason: 'duplicate SKU in Airtable' }]);
  assert.deepEqual(r.updates, []);
});

test('results follow the order of the SKUs given', () => {
  const r = planUpdates(['B-2', 'A-1'], { 'A-1': 1, 'B-2': 2 }, rows);
  assert.deepEqual(r.updates.map((u) => u.sku), ['B-2', 'A-1']);
});

test('no SKUs and no rows plan nothing', () => {
  assert.deepEqual(planUpdates(undefined, undefined, undefined), { updates: [], skipped: [], rejected: [], unchanged: 0 });
});

test('updates are chunked for Airtable, which takes at most 10 records a request', () => {
  const many = Array.from({ length: 23 }, (_, i) => ({ recordId: `r${i}`, sku: `S${i}`, oldStock: 0, newStock: 1 }));
  const chunks = chunkUpdates(many, 10);
  assert.deepEqual(chunks.map((c) => c.length), [10, 10, 3]);
  assert.deepEqual(chunkUpdates([], 10), []);
});
