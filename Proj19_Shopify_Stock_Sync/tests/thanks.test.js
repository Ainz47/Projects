const test = require('node:test');
const assert = require('node:assert/strict');
const { THANK_YOU_TAG, planThankYous, thankYouEmail } = require('../code/thanks.js');

const order = (over) => ({ id: 'gid://shopify/Order/1', name: '#1001', email: 'me@example.com', tags: [], ...over });

test('an order with an allowed, untagged email is sent', () => {
  const r = planThankYous([order()], ['me@example.com']);
  assert.deepEqual(r.send, [{ orderId: 'gid://shopify/Order/1', name: '#1001', email: 'me@example.com' }]);
  assert.deepEqual(r.skip, []);
});

test('an already-thanked order is skipped, not resent', () => {
  const r = planThankYous([order({ tags: ['proj19-test', THANK_YOU_TAG] })], ['me@example.com']);
  assert.deepEqual(r.skip, [{ orderId: 'gid://shopify/Order/1', reason: 'already thanked' }]);
  assert.deepEqual(r.send, []);
});

test('an email not on the allow-list is skipped, case-insensitively matched against the list', () => {
  const r = planThankYous([order({ email: 'stranger@example.com' })], ['Me@Example.com']);
  assert.deepEqual(r.skip, [{ orderId: 'gid://shopify/Order/1', reason: 'email is not on the allow-list' }]);
  const allowed = planThankYous([order({ email: 'ME@EXAMPLE.COM' })], ['me@example.com']);
  assert.deepEqual(allowed.send, [{ orderId: 'gid://shopify/Order/1', name: '#1001', email: 'ME@EXAMPLE.COM' }]);
});

test('an order with no email is skipped with a reason, never sent', () => {
  const r = planThankYous([order({ email: '' }), order({ email: null })], ['me@example.com']);
  assert.deepEqual(r.skip, [
    { orderId: 'gid://shopify/Order/1', reason: 'no email address' },
    { orderId: 'gid://shopify/Order/1', reason: 'no email address' },
  ]);
});

test('an empty allow-list skips everyone instead of emailing anyone', () => {
  const r = planThankYous([order()], []);
  assert.deepEqual(r.skip, [{ orderId: 'gid://shopify/Order/1', reason: 'email is not on the allow-list' }]);
});

test('no orders and no allow-list plan nothing', () => {
  assert.deepEqual(planThankYous(undefined, undefined), { send: [], skip: [] });
});

test('the fixed template names the order and never asks the model for wording', () => {
  const email = thankYouEmail('#1001');
  assert.match(email.subject, /#1001/);
  assert.match(email.text, /#1001/);
  assert.match(email.text, /demo/i);
});
