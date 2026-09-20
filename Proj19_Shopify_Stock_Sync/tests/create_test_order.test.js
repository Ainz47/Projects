const test = require('node:test');
const assert = require('node:assert/strict');
const { parseEnv, assertTarget, createClient, getAccessToken } = require('../tools/shopify.js');
const { parseArgs, buildOrderInput, createTestOrder, TAG } = require('../tools/create_test_order.js');

test('parseEnv reads KEY=VALUE lines and skips comments and blanks', () => {
  assert.deepEqual(parseEnv('# note\nA=1\n\nB = two words \r\nC=x=y\n'), { A: '1', B: 'two words', C: 'x=y' });
});

test('the target guard refuses a store that does not match, with fixed wording', () => {
  assert.doesNotThrow(() => assertTarget('jhurald05', 'jhurald05'));
  assert.throws(() => assertTarget('jhurald05', 'other'), /does not match/);
  assert.throws(() => assertTarget('jhurald05', undefined), /--to/);
});

test('parseArgs reads --to, --email and repeated --sku CODE:QTY (quantity defaults to 1)', () => {
  const a = parseArgs(['--to', 'jhurald05', '--email', 'me@example.com', '--sku', 'A-1:2', '--sku', 'B-2']);
  assert.deepEqual(a, { to: 'jhurald05', email: 'me@example.com', lines: [{ sku: 'A-1', quantity: 2 }, { sku: 'B-2', quantity: 1 }] });
});

test('parseArgs rejects a missing email, no lines, and a bad quantity', () => {
  assert.throws(() => parseArgs(['--to', 's', '--sku', 'A-1']), /--email/);
  assert.throws(() => parseArgs(['--to', 's', '--email', 'a@b.co']), /--sku/);
  assert.throws(() => parseArgs(['--to', 's', '--email', 'a@b.co', '--sku', 'A-1:0']), /quantity/);
});

test('the order input is tagged, pending payment, and decrements inventory', () => {
  const { order, options } = buildOrderInput(
    { email: 'me@example.com', lines: [{ sku: 'A-1', quantity: 2 }] },
    { 'A-1': 'gid://shopify/ProductVariant/1' },
  );
  assert.equal(TAG, 'proj19-test');
  assert.deepEqual(order.tags, ['proj19-test']);
  assert.equal(order.email, 'me@example.com');
  assert.deepEqual(order.lineItems, [{ variantId: 'gid://shopify/ProductVariant/1', quantity: 2 }]);
  assert.equal(order.financialStatus, 'PENDING');
  assert.equal(options.inventoryBehaviour, 'DECREMENT_OBEYING_POLICY');
  assert.equal(options.sendReceipt, false);
});

const fakeClient = (responses) => {
  const calls = [];
  return { calls, graphql: async (query, variables) => { calls.push({ query, variables }); return responses.shift(); } };
};

test('createTestOrder looks each SKU up by exact match, creates the order, returns its name', async () => {
  const client = fakeClient([
    { productVariants: { nodes: [{ id: 'gid://shopify/ProductVariant/10', sku: 'A-10' }, { id: 'gid://shopify/ProductVariant/1', sku: 'A-1' }] } },
    { orderCreate: { order: { id: 'gid://shopify/Order/5', name: '#1005' }, userErrors: [] } },
  ]);
  const order = await createTestOrder(client, { email: 'me@example.com', lines: [{ sku: 'A-1', quantity: 1 }] });
  assert.deepEqual(order, { id: 'gid://shopify/Order/5', name: '#1005' });
  assert.equal(client.calls[1].variables.order.lineItems[0].variantId, 'gid://shopify/ProductVariant/1');
});

test('createTestOrder fails before creating anything when a SKU is not found', async () => {
  const client = fakeClient([{ productVariants: { nodes: [] } }]);
  await assert.rejects(createTestOrder(client, { email: 'a@b.co', lines: [{ sku: 'NOPE', quantity: 1 }] }), /NOPE/);
  assert.equal(client.calls.length, 1);
});

test('createTestOrder throws Shopify\'s user errors', async () => {
  const client = fakeClient([
    { productVariants: { nodes: [{ id: 'gid://shopify/ProductVariant/1', sku: 'A-1' }] } },
    { orderCreate: { order: null, userErrors: [{ field: ['order'], message: 'Bad input' }] } },
  ]);
  await assert.rejects(createTestOrder(client, { email: 'a@b.co', lines: [{ sku: 'A-1', quantity: 1 }] }), /Bad input/);
});

test('getAccessToken posts the client credentials as a form and returns the token', async () => {
  let seen;
  const fetchImpl = async (url, init) => { seen = { url, init }; return { ok: true, json: async () => ({ access_token: 'tok' }) }; };
  assert.equal(await getAccessToken({ shop: 'jhurald05', clientId: 'id', clientSecret: 'secret', fetchImpl }), 'tok');
  assert.equal(seen.url, 'https://jhurald05.myshopify.com/admin/oauth/access_token');
  assert.match(String(seen.init.body), /grant_type=client_credentials/);
});

test('the client sends the token header and throws on GraphQL errors', async () => {
  let headers;
  const fetchImpl = async (url, init) => { headers = init.headers; return { ok: true, json: async () => ({ errors: [{ message: 'nope' }] }) }; };
  const client = createClient({ shop: 'jhurald05', token: 'tok', fetchImpl });
  await assert.rejects(client.graphql('query { shop { id } }'), /nope/);
  assert.equal(headers['X-Shopify-Access-Token'], 'tok');
});
