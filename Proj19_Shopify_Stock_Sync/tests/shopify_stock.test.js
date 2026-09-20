const test = require('node:test');
const assert = require('node:assert/strict');
const { stockFromVariants } = require('../code/shopify_stock.js');

const v = (sku, inventoryQuantity, tracked = true) => ({ sku, inventoryQuantity, inventoryItem: { tracked } });

test('returns the quantity of the variant whose SKU matches exactly', () => {
  assert.equal(stockFromVariants([v('A-1', 7), v('A-10', 99)], 'A-1'), 7);
});

test('ignores neighbours the search matched loosely', () => {
  assert.equal(stockFromVariants([v('A-10', 99)], 'A-1'), undefined);
});

test('undefined when nothing matches or there are no nodes', () => {
  assert.equal(stockFromVariants([], 'A-1'), undefined);
  assert.equal(stockFromVariants(undefined, 'A-1'), undefined);
});

test('null when stock is not tracked', () => {
  assert.equal(stockFromVariants([v('A-1', 5, false)], 'A-1'), null);
});

test('null when two variants share the SKU, so there is no single answer', () => {
  assert.equal(stockFromVariants([v('A-1', 5), v('A-1', 6)], 'A-1'), null);
});

test('null when the quantity is not a whole number', () => {
  assert.equal(stockFromVariants([v('A-1', null)], 'A-1'), null);
  assert.equal(stockFromVariants([v('A-1', 2.5)], 'A-1'), null);
});

test('zero is a real answer, not missing', () => {
  assert.equal(stockFromVariants([v('A-1', 0)], 'A-1'), 0);
});
