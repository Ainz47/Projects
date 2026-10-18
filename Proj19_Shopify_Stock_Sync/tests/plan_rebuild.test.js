const test = require('node:test');
const assert = require('node:assert/strict');
const { publishedStock, planRebuild } = require('../code/plan_rebuild.js');

const snapshot = (variants) => ({
  data: { products: { nodes: [{ variants: { nodes: variants.map(([sku, qty]) => ({ sku, inventoryQuantity: qty })) } }] } },
});
const done = (conclusion) => ({ status: 'completed', conclusion });

test('reads every SKU and its stock out of the committed catalog snapshot', () => {
  assert.deepEqual(publishedStock(snapshot([['A-1', 5], ['B-2', 0]])), { 'A-1': 5, 'B-2': 0 });
});

test('an unreadable snapshot reads as nothing published', () => {
  assert.deepEqual(publishedStock(undefined), {});
  assert.deepEqual(publishedStock({ data: {} }), {});
});

test('nothing to do when the published page already shows the synced stock', () => {
  const r = planRebuild({ 'A-1': 5 }, { 'A-1': 5 }, [done('success')]);
  assert.deepEqual(r, { dispatch: false, stale: [] });
});

test('a SKU the page shows differently is stale and needs a rebuild', () => {
  // The case this module exists for: Airtable was written, the dispatch after
  // it failed, and the retry tick sees no Airtable change to react to.
  const r = planRebuild({ 'A-1': 4, 'B-2': 0 }, { 'A-1': 5, 'B-2': 0 }, [done('success')]);
  assert.deepEqual(r, { dispatch: true, stale: ['A-1'] });
});

test('a synced SKU missing from the snapshot is stale too', () => {
  assert.deepEqual(planRebuild({ 'NEW-1': 3 }, {}, []).stale, ['NEW-1']);
});

test('a rebuild already queued or running is left to finish, not doubled', () => {
  const r = planRebuild({ 'A-1': 4 }, { 'A-1': 5 }, [{ status: 'in_progress', conclusion: null }, done('success')]);
  assert.equal(r.dispatch, false);
  assert.deepEqual(r.stale, ['A-1']);
  assert.match(r.reason, /queued or running/);
});

test('one or two failed rebuilds in a row are retried', () => {
  assert.equal(planRebuild({ 'A-1': 4 }, { 'A-1': 5 }, [done('failure'), done('failure'), done('success')]).dispatch, true);
});

test('three failed rebuilds in a row stop the retries and fail the tick loudly', () => {
  // A broken build would otherwise be re-dispatched every 5 minutes forever.
  assert.throws(
    () => planRebuild({ 'A-1': 4 }, { 'A-1': 5 }, [done('failure'), done('cancelled'), done('failure'), done('success')]),
    /refresh-catalog failed 3 times in a row/,
  );
});

test('old failures behind a success do not count against a new rebuild', () => {
  const runs = [done('success'), done('failure'), done('failure'), done('failure')];
  assert.equal(planRebuild({ 'A-1': 4 }, { 'A-1': 5 }, runs).dispatch, true);
});

test('stale SKUs come back sorted so the log line is stable', () => {
  assert.deepEqual(planRebuild({ 'B-2': 1, 'A-1': 1 }, {}, []).stale, ['A-1', 'B-2']);
});
