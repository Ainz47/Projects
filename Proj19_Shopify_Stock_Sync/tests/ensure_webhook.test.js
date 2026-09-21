const test = require('node:test');
const assert = require('node:assert/strict');
const { needsWebhookRegistration } = require('../code/ensure_webhook.js');

test('no subscriptions at all means one is needed', () => {
  assert.equal(needsWebhookRegistration([], 'https://hook.make.com/abc'), true);
  assert.equal(needsWebhookRegistration(undefined, 'https://hook.make.com/abc'), true);
});

test('an existing subscription for the same URL means none is needed', () => {
  assert.equal(needsWebhookRegistration([{ callbackUrl: 'https://hook.make.com/abc' }], 'https://hook.make.com/abc'), false);
});

test('a subscription for a different URL still means one is needed', () => {
  assert.equal(needsWebhookRegistration([{ callbackUrl: 'https://hook.make.com/old' }], 'https://hook.make.com/abc'), true);
});

test('a malformed entry is tolerated, not a crash', () => {
  assert.equal(needsWebhookRegistration([{}, { callbackUrl: null }], 'https://hook.make.com/abc'), true);
});
