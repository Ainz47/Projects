const test = require('node:test');
const assert = require('node:assert/strict');
const { summarize, summarizeStock } = require('../code/weekly.js');

const NOW = Date.parse('2026-09-21T09:00:00.000Z');
const daysAgo = (d) => new Date(NOW - d * 24 * 60 * 60 * 1000).toISOString();

test('counts only the last 7 days, by tier', () => {
  const rows = [
    { timestamp: daysAgo(1), tier: 'hot', company: 'A', reason: 'fits' },
    { timestamp: daysAgo(2), tier: 'warm', company: 'B', reason: 'vague' },
    { timestamp: daysAgo(6.9), tier: 'cold', company: 'C', reason: 'spam' },
    { timestamp: daysAgo(8), tier: 'hot', company: 'Old', reason: 'too old' },
  ];
  const s = summarize(rows, NOW);
  assert.equal(s.total, 3);
  assert.deepEqual(s.counts, { hot: 1, warm: 1, cold: 1, needs_review: 0, rejected: 0 });
  assert.deepEqual(s.hotLeads, [{ company: 'A', reason: 'fits' }]);
});

test('unknown or missing tiers count as needs_review; bad timestamps are skipped', () => {
  const rows = [
    { timestamp: daysAgo(1), tier: 'toString' },
    { timestamp: daysAgo(1) },
    { timestamp: 'garbage', tier: 'hot' },
    { tier: 'hot' },
  ];
  const s = summarize(rows, NOW);
  assert.equal(s.total, 2);
  assert.equal(s.counts.needs_review, 2);
  assert.equal(s.counts.hot, 0);
});

test('an empty sheet yields a zero summary, not an error', () => {
  const s = summarize([{}], NOW);
  assert.equal(s.total, 0);
  assert.deepEqual(s.hotLeads, []);
});

test('summarizeStock counts only the last 7 days of stock rows', () => {
  const rows = [
    { timestamp: daysAgo(1), sku: 'A-1', new_stock: 3 },
    { timestamp: daysAgo(2), sku: 'B-2', new_stock: 5 },
    { timestamp: daysAgo(8), sku: 'C-3', new_stock: 0 },
  ];
  const s = summarizeStock(rows, NOW);
  assert.equal(s.changes, 2);
  assert.deepEqual(s.soldOut, []);
});

test('a row with new_stock 0 inside the window is a sold-out SKU, sorted and deduped', () => {
  const rows = [
    { timestamp: daysAgo(1), sku: 'B-2', new_stock: 0 },
    { timestamp: daysAgo(2), sku: 'A-1', new_stock: 0 },
    { timestamp: daysAgo(3), sku: 'A-1', new_stock: 0 },
  ];
  const s = summarizeStock(rows, NOW);
  assert.equal(s.changes, 3);
  assert.deepEqual(s.soldOut, ['A-1', 'B-2']);
});

test('an empty stock log yields a zero summary, not an error', () => {
  const s = summarizeStock([{}], NOW);
  assert.equal(s.changes, 0);
  assert.deepEqual(s.soldOut, []);
});
