import { getAccessToken } from '../exporter/auth.mjs';
import { API_VERSION, PAGE_SIZE, createClient, fetchAllProducts } from '../exporter/client.mjs';

type Reply = { status?: number; body?: unknown };
const respond = (r: Reply) => ({ ok: (r.status ?? 200) < 400, status: r.status ?? 200, json: async () => r.body });

function fakeFetch(replies: Reply[]) {
  const calls: { url: string; init: any }[] = [];
  const impl = async (url: string, init: any) => {
    calls.push({ url, init });
    const next = replies.shift();
    if (!next) throw new Error('unexpected extra request');
    return respond(next);
  };
  return { impl, calls };
}

const cost = (requested: number, available: number, restoreRate = 50) => ({
  cost: { requestedQueryCost: requested, actualQueryCost: requested, throttleStatus: { maximumAvailable: 1000, currentlyAvailable: available, restoreRate } },
});

const page = (nodes: unknown[], hasNextPage: boolean, endCursor: string | null, extensions = cost(100, 900)) => ({
  body: { data: { products: { pageInfo: { hasNextPage, endCursor }, nodes } }, extensions },
});

const noSleep = async () => {};

test('paginates with the cursor until hasNextPage is false', async () => {
  const f = fakeFetch([page([{ id: 1 }], true, 'c1'), page([{ id: 2 }], true, 'c2'), page([{ id: 3 }], false, null)]);
  const client = createClient({ shop: 'demo', token: 't', fetchImpl: f.impl, sleep: noSleep });
  expect(await fetchAllProducts(client)).toEqual([{ id: 1 }, { id: 2 }, { id: 3 }]);
  expect(f.calls.map((c) => JSON.parse(c.init.body).variables.cursor)).toEqual([null, 'c1', 'c2']);
});

test('calls the pinned API version with the token header', async () => {
  const f = fakeFetch([page([], false, null)]);
  await fetchAllProducts(createClient({ shop: 'demo', token: 'secret-token', fetchImpl: f.impl, sleep: noSleep }));
  expect(API_VERSION).toBe('2026-07');
  expect(f.calls[0]!.url).toBe('https://demo.myshopify.com/admin/api/2026-07/graphql.json');
  expect(f.calls[0]!.init.headers['X-Shopify-Access-Token']).toBe('secret-token');
  expect(JSON.parse(f.calls[0]!.init.body).query).toContain(`first: ${PAGE_SIZE}`);
});

test('waits for the bucket to refill when the next query would not fit', async () => {
  const sleeps: number[] = [];
  // Last query cost 400 and left only 100 available; restore rate is 50/s, so wait (400-100)/50 = 6 s.
  const f = fakeFetch([page([{ id: 1 }], true, 'c1', cost(400, 100)), page([{ id: 2 }], false, null)]);
  const client = createClient({ shop: 'demo', token: 't', fetchImpl: f.impl, sleep: async (ms: number) => void sleeps.push(ms) });
  await fetchAllProducts(client);
  expect(sleeps).toEqual([6000]);
});

test('retries a THROTTLED error, then succeeds', async () => {
  const sleeps: number[] = [];
  const throttled = { body: { errors: [{ message: 'Throttled', extensions: { code: 'THROTTLED' } }] } };
  const f = fakeFetch([throttled, page([{ id: 1 }], false, null)]);
  const client = createClient({ shop: 'demo', token: 't', fetchImpl: f.impl, sleep: async (ms: number) => void sleeps.push(ms) });
  expect(await fetchAllProducts(client)).toEqual([{ id: 1 }]);
  expect(sleeps).toHaveLength(1);
});

test('gives up after maxRetries and says how many attempts were made', async () => {
  const throttled = { body: { errors: [{ message: 'Throttled', extensions: { code: 'THROTTLED' } }] } };
  const f = fakeFetch([throttled, throttled, throttled]);
  const client = createClient({ shop: 'demo', token: 't', fetchImpl: f.impl, sleep: noSleep, maxRetries: 2 });
  await expect(fetchAllProducts(client)).rejects.toThrow(/throttled.*3 attempts/i);
});

test('retries HTTP 429 and surfaces a clear error for MAX_COST_EXCEEDED', async () => {
  const f = fakeFetch([{ status: 429 }, { body: { errors: [{ message: 'x', extensions: { code: 'MAX_COST_EXCEEDED' } }] } }]);
  const client = createClient({ shop: 'demo', token: 't', fetchImpl: f.impl, sleep: noSleep });
  await expect(fetchAllProducts(client)).rejects.toThrow(/PAGE_SIZE/);
});

test('other GraphQL errors and HTTP failures throw with the message', async () => {
  const bad = fakeFetch([{ body: { errors: [{ message: 'Access denied for products field' }] } }]);
  await expect(fetchAllProducts(createClient({ shop: 'demo', token: 't', fetchImpl: bad.impl, sleep: noSleep }))).rejects.toThrow(/Access denied/);
  const denied = fakeFetch([{ status: 401 }]);
  await expect(fetchAllProducts(createClient({ shop: 'demo', token: 't', fetchImpl: denied.impl, sleep: noSleep }))).rejects.toThrow(/HTTP 401/);
});

test('getAccessToken posts a client credentials grant and returns the token', async () => {
  const f = fakeFetch([{ body: { access_token: 'shpat_abc', scope: 'read_products', expires_in: 86399 } }]);
  const token = await getAccessToken({ shop: 'demo', clientId: 'id', clientSecret: 'sec', fetchImpl: f.impl });
  expect(token).toBe('shpat_abc');
  expect(f.calls[0]!.url).toBe('https://demo.myshopify.com/admin/oauth/access_token');
  const body = String(f.calls[0]!.init.body);
  expect(body).toContain('grant_type=client_credentials');
});

test('getAccessToken refuses to run without credentials or with a bad shop, and never echoes the secret', async () => {
  const f = fakeFetch([]);
  await expect(getAccessToken({ shop: '', clientId: 'id', clientSecret: 'sec', fetchImpl: f.impl })).rejects.toThrow(/SHOPIFY_SHOP/);
  await expect(getAccessToken({ shop: 'demo', clientId: '', clientSecret: 'sec', fetchImpl: f.impl })).rejects.toThrow(/SHOPIFY_CLIENT_ID/);
  await expect(getAccessToken({ shop: 'evil.com/x', clientId: 'id', clientSecret: 'sec', fetchImpl: f.impl })).rejects.toThrow(/shop/i);
  const failing = fakeFetch([{ status: 403 }]);
  const err = await getAccessToken({ shop: 'demo', clientId: 'id', clientSecret: 'TOP-SECRET', fetchImpl: failing.impl }).catch((e) => e);
  expect(String(err.message)).not.toContain('TOP-SECRET');
  expect(f.calls).toHaveLength(0);
});
