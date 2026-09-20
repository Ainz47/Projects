const test = require('node:test');
const assert = require('node:assert/strict');
const { planOrdersQuery, OVERLAP_MS, MAX_ORDERS } = require('../code/plan_orders_query.js');

const NOW = Date.parse('2026-09-20T14:00:00Z');

test('the overlap is 10 minutes and a tick reads at most 250 orders', () => {
  assert.equal(OVERLAP_MS, 10 * 60 * 1000);
  assert.equal(MAX_ORDERS, 250);
});

test('a first run starts one overlap before now and backfills no history', () => {
  const q = planOrdersQuery(null, NOW);
  assert.equal(q.since, '2026-09-20T13:50:00.000Z');
  assert.equal(q.search, 'updated_at:>=2026-09-20T13:50:00.000Z');
  assert.equal(q.first, 250);
});

test('a later run starts one overlap before the cursor', () => {
  assert.equal(planOrdersQuery('2026-09-20T13:30:00.000Z', NOW).since, '2026-09-20T13:20:00.000Z');
});

test('a cursor in the future is clamped to now', () => {
  assert.equal(planOrdersQuery('2026-09-20T15:00:00.000Z', NOW).since, '2026-09-20T13:50:00.000Z');
});

test('an unreadable cursor is treated as no cursor', () => {
  for (const bad of ['garbage', '', undefined]) {
    assert.equal(planOrdersQuery(bad, NOW).since, '2026-09-20T13:50:00.000Z');
  }
});
