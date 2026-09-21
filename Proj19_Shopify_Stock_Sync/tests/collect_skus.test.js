const test = require('node:test');
const assert = require('node:assert/strict');
const { collectSkus, skuOrderNames } = require('../code/collect_skus.js');
const { ORDERS_QUERY, STOCK_QUERY } = require('../code/queries.js');

const order = (...skus) => ({ id: 'o', lineItems: { nodes: skus.map((sku) => ({ sku, quantity: 1 })) } });

test('returns each SKU once, trimmed and sorted', () => {
  assert.deepEqual(collectSkus([order('B-2', ' A-1 '), order('A-1', 'C-3')]), ['A-1', 'B-2', 'C-3']);
});

test('skips lines with no usable SKU (custom items, null, blanks, non-strings)', () => {
  assert.deepEqual(collectSkus([order(null, '', '   ', undefined, 42, 'A-1')]), ['A-1']);
});

test('tolerates missing pieces and no orders at all', () => {
  assert.deepEqual(collectSkus([null, {}, { lineItems: null }, { lineItems: { nodes: null } }]), []);
  assert.deepEqual(collectSkus(undefined), []);
  assert.deepEqual(collectSkus([]), []);
});

test('the orders query asks for every field the sync reads, oldest first', () => {
  for (const field of ['id', 'name', 'email', 'updatedAt', 'tags', 'lineItems', 'sku', 'quantity']) {
    assert.ok(ORDERS_QUERY.includes(field), `orders query is missing ${field}`);
  }
  assert.match(ORDERS_QUERY, /\$first: Int!/);
  assert.match(ORDERS_QUERY, /\$search: String!/);
  assert.match(ORDERS_QUERY, /sortKey: UPDATED_AT/);
  assert.match(ORDERS_QUERY, /reverse: false/);
});

test('the stock query asks for sku, quantity and whether stock is tracked', () => {
  for (const field of ['productVariants', 'sku', 'inventoryQuantity', 'inventoryItem', 'tracked']) {
    assert.ok(STOCK_QUERY.includes(field), `stock query is missing ${field}`);
  }
  assert.match(STOCK_QUERY, /\$search: String!/);
});

const orderNamed = (name, ...skus) => ({ name, lineItems: { nodes: skus.map((sku) => ({ sku, quantity: 1 })) } });

test('skuOrderNames maps each SKU to the order that carried it', () => {
  assert.deepEqual(skuOrderNames([orderNamed('#1001', 'A-1', 'B-2')]), { 'A-1': '#1001', 'B-2': '#1001' });
});

test('two orders touching the same SKU in one tick join their names', () => {
  assert.deepEqual(skuOrderNames([orderNamed('#1001', 'A-1'), orderNamed('#1002', 'A-1')]), { 'A-1': '#1001; #1002' });
});

test('tolerates missing names, missing lines, and no orders at all', () => {
  assert.deepEqual(skuOrderNames([{ lineItems: { nodes: [{ sku: 'A-1' }] } }, null, undefined]), {});
  assert.deepEqual(skuOrderNames(undefined), {});
});
