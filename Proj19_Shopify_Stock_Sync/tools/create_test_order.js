// Creates a tagged test order in the dev store, decrementing inventory like a real one.
// Run: node tools/create_test_order.js --to jhurald05 --email you@example.com --sku CODE:2 [--sku CODE2]
const fs = require('node:fs');
const path = require('node:path');
const { parseEnv, assertTarget, getAccessToken, createClient } = require('./shopify.js');

const TAG = 'proj19-test';

const VARIANT_QUERY = `query Variant($search: String!) {
  productVariants(first: 20, query: $search) { nodes { id sku } }
}`;

const ORDER_CREATE = `mutation OrderCreate($order: OrderCreateOrderInput!, $options: OrderCreateOptionsInput) {
  orderCreate(order: $order, options: $options) {
    order { id name }
    userErrors { field message }
  }
}`;

function parseArgs(argv) {
  const args = { to: undefined, email: undefined, lines: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const flag = argv[i];
    if (flag === '--to') args.to = argv[++i];
    else if (flag === '--email') args.email = argv[++i];
    else if (flag === '--sku') {
      const [sku, qty = '1'] = String(argv[++i]).split(':');
      const quantity = Number(qty);
      if (!sku || !Number.isInteger(quantity) || quantity < 1) throw new Error('Each --sku needs CODE or CODE:QTY with a whole quantity of 1 or more');
      args.lines.push({ sku, quantity });
    }
  }
  if (!args.email) throw new Error('Pass --email <address> for the order');
  if (args.lines.length === 0) throw new Error('Pass at least one --sku CODE:QTY');
  return args;
}

function buildOrderInput({ email, lines }, variantIds) {
  return {
    order: {
      email,
      tags: [TAG],
      financialStatus: 'PENDING',
      lineItems: lines.map(({ sku, quantity }) => ({ variantId: variantIds[sku], quantity })),
    },
    options: { inventoryBehaviour: 'DECREMENT_OBEYING_POLICY', sendReceipt: false, sendFulfillmentReceipt: false },
  };
}

async function createTestOrder(client, { email, lines }) {
  const variantIds = {};
  for (const { sku } of lines) {
    const data = await client.graphql(VARIANT_QUERY, { search: `sku:"${sku.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"` });
    const hit = data.productVariants.nodes.find((v) => v.sku === sku);
    if (!hit) throw new Error(`SKU ${sku} was not found in the store; no order was created`);
    variantIds[sku] = hit.id;
  }
  const data = await client.graphql(ORDER_CREATE, buildOrderInput({ email, lines }, variantIds));
  const { order, userErrors } = data.orderCreate;
  if (userErrors.length > 0) throw new Error(`orderCreate failed: ${userErrors.map((e) => e.message).join('; ')}`);
  return { id: order.id, name: order.name };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const env = parseEnv(fs.readFileSync(path.join(__dirname, '..', '.env.local'), 'utf8'));
  assertTarget(env.SHOPIFY_SHOP, args.to);
  const token = await getAccessToken({ shop: env.SHOPIFY_SHOP, clientId: env.SHOPIFY_CLIENT_ID, clientSecret: env.SHOPIFY_CLIENT_SECRET });
  const order = await createTestOrder(createClient({ shop: env.SHOPIFY_SHOP, token }), args);
  console.log(`created ${order.name} (${order.id}) tagged ${TAG}`);
}

if (require.main === module) main().catch((err) => { console.error(err.message); process.exit(1); });

module.exports = { TAG, parseArgs, buildOrderInput, createTestOrder };
