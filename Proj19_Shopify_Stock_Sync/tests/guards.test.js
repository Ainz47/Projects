const test = require('node:test');
const assert = require('node:assert/strict');
const { assertNoGraphqlErrors } = require('../code/guards.js');

test('a good response passes', () => {
  assert.doesNotThrow(() => assertNoGraphqlErrors({ data: { orders: { nodes: [] } } }, 'Shopify orders'));
});

test('an errors array throws, naming the step and every message', () => {
  assert.throws(
    () => assertNoGraphqlErrors({ errors: [{ message: 'Throttled' }, { message: 'Access denied' }], data: null }, 'Shopify orders'),
    /Shopify orders: Throttled; Access denied/,
  );
});

test('a response without data throws even with no errors array', () => {
  assert.throws(() => assertNoGraphqlErrors({}, 'Shopify stock'), /Shopify stock: the response had no data/);
  assert.throws(() => assertNoGraphqlErrors(null, 'Shopify stock'), /Shopify stock: the response had no data/);
});
