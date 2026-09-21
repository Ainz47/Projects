const test = require('node:test');
const assert = require('node:assert/strict');
const { stockLogRows } = require('../code/stock_log_rows.js');

const NOW = '2026-09-21T09:00:00.000Z';
const updates = [
  { recordId: 'rec1', sku: 'A-1', oldStock: 10, newStock: 7 },
  { recordId: 'rec2', sku: 'B-2', oldStock: null, newStock: 3 },
];

test('one row per update, timestamped and sourced, with the order name looked up by SKU', () => {
  const rows = stockLogRows(updates, { 'A-1': '#1001', 'B-2': '#1002; #1003' }, 'n8n', NOW);
  assert.deepEqual(rows, [
    { timestamp: NOW, sku: 'A-1', old_stock: 10, new_stock: 7, source: 'n8n', order_name: '#1001' },
    { timestamp: NOW, sku: 'B-2', old_stock: null, new_stock: 3, source: 'n8n', order_name: '#1002; #1003' },
  ]);
});

test('a SKU with no matching order name gets an empty string, not undefined', () => {
  assert.equal(stockLogRows(updates, {}, 'n8n', NOW)[0].order_name, '');
});

test('no updates makes no rows', () => {
  assert.deepEqual(stockLogRows([], {}, 'n8n', NOW), []);
  assert.deepEqual(stockLogRows(undefined, {}, 'make', NOW), []);
});

test('the source is carried through unchanged (make or n8n)', () => {
  assert.equal(stockLogRows(updates, {}, 'make', NOW)[0].source, 'make');
});
