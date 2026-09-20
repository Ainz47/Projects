import { BATCH_SIZE, RATE_LIMIT_WAIT_MS, createClient } from '../airtable/client.mjs';
import { readConfig } from '../airtable/config.mjs';

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
  return { impl: impl as unknown as typeof fetch, calls };
}

const BASE = 'appTESTBASE000001';
const TOKEN = 'pat-SECRET-123';
const noSleep = async () => {};
const make = (f: ReturnType<typeof fakeFetch>, extra: Record<string, unknown> = {}) =>
  createClient({ baseId: BASE, token: TOKEN, fetchImpl: f.impl, sleep: noSleep, gapMs: 0, ...extra });

test('lists a table page by page, following the offset', async () => {
  const f = fakeFetch([
    { body: { records: [{ id: 'rec1', fields: {} }], offset: 'off1' } },
    { body: { records: [{ id: 'rec2', fields: {} }] } },
  ]);
  const records = await make(f).listAll('Products');
  expect(records.map((r: any) => r.id)).toEqual(['rec1', 'rec2']);
  expect(f.calls.map((c) => c.url)).toEqual([
    `https://api.airtable.com/v0/${BASE}/Products?pageSize=100`,
    `https://api.airtable.com/v0/${BASE}/Products?pageSize=100&offset=off1`,
  ]);
});

test('sends the token as a bearer header and nowhere else', async () => {
  const f = fakeFetch([{ body: { records: [] } }]);
  await make(f).listAll('Products');
  expect(f.calls[0]!.init.headers.Authorization).toBe(`Bearer ${TOKEN}`);
  expect(f.calls[0]!.url).not.toContain(TOKEN);
  expect(f.calls[0]!.init.body).toBeUndefined();
});

test('encodes table names that contain spaces', async () => {
  const f = fakeFetch([{ body: { records: [] } }]);
  await make(f).listAll('Table 1');
  expect(f.calls[0]!.url).toContain('/Table%201?');
});

test('stops with a clear message if a table has more pages than expected', async () => {
  const f = fakeFetch([{ body: { records: [], offset: 'a' } }, { body: { records: [], offset: 'b' } }]);
  await expect(make(f).listAll('Products', 2)).rejects.toThrow(/Stopped after 2 pages of Products/);
});

test('creates records in batches and returns them all', async () => {
  const total = BATCH_SIZE * 2 + 5;
  const sizes: number[] = [];
  const f = fakeFetch([]);
  f.impl = (async (url: string, init: any) => {
    f.calls.push({ url, init });
    const sent = JSON.parse(init.body).records as { fields: { n: number } }[];
    sizes.push(sent.length);
    return respond({ body: { records: sent.map((r) => ({ id: `rec${r.fields.n}`, fields: r.fields })) } });
  }) as unknown as typeof fetch;
  const created = await make(f).createRecords('Products', Array.from({ length: total }, (_, n) => ({ n })));
  expect(BATCH_SIZE).toBe(10);
  expect(sizes).toEqual([10, 10, 5]);
  expect(created).toHaveLength(total);
  expect(f.calls[0]!.init.method).toBe('POST');
  expect(JSON.parse(f.calls[0]!.init.body).records[0]).toEqual({ fields: { n: 0 } });
});

test('updates records with PATCH in batches, sending only the fields given', async () => {
  const sizes: number[] = [];
  const f = fakeFetch([]);
  f.impl = (async (url: string, init: any) => {
    f.calls.push({ url, init });
    const sent = JSON.parse(init.body).records as unknown[];
    sizes.push(sent.length);
    return respond({ body: { records: sent } });
  }) as unknown as typeof fetch;
  const updates = Array.from({ length: BATCH_SIZE + 3 }, (_, n) => ({ id: `rec${n}`, fields: { Stock: n } }));
  const done = await make(f).updateRecords('Variants', updates);
  expect(sizes).toEqual([10, 3]);
  expect(done).toHaveLength(13);
  expect(f.calls[0]!.init.method).toBe('PATCH');
  expect(f.calls[0]!.url).toBe(`https://api.airtable.com/v0/${BASE}/Variants`);
  expect(JSON.parse(f.calls[0]!.init.body).records[0]).toEqual({ id: 'rec0', fields: { Stock: 0 } });
});

test('waits 30 seconds after a 429, then succeeds', async () => {
  const sleeps: number[] = [];
  const f = fakeFetch([{ status: 429 }, { body: { records: [] } }]);
  await make(f, { sleep: async (ms: number) => void sleeps.push(ms) }).listAll('Products');
  expect(RATE_LIMIT_WAIT_MS).toBe(30000);
  expect(sleeps).toEqual([30000]);
});

test('retries a 503 with a short backoff', async () => {
  const sleeps: number[] = [];
  const f = fakeFetch([{ status: 503 }, { body: { records: [] } }]);
  await make(f, { sleep: async (ms: number) => void sleeps.push(ms) }).listAll('Products');
  expect(sleeps).toEqual([1000]);
});

test('gives up after maxRetries and says how many attempts were made', async () => {
  const f = fakeFetch([{ status: 429 }, { status: 429 }, { status: 429 }]);
  await expect(make(f, { maxRetries: 2 }).listAll('Products')).rejects.toThrow(/gave up after 3 attempts/);
});

test('explains 401, 403 and 404 in plain language and never echoes the token', async () => {
  const cases: [number, RegExp][] = [
    [401, /rejected the token \(HTTP 401\)/],
    [403, /cannot reach the base or lacks a scope \(HTTP 403\)/],
    [404, /could not find that base or table \(HTTP 404\)/],
  ];
  for (const [status, pattern] of cases) {
    const err = (await make(fakeFetch([{ status }])).listAll('Products').catch((e: unknown) => e)) as Error;
    expect(err.message).toMatch(pattern);
    expect(err.message).not.toContain(TOKEN);
  }
});

test('includes the message Airtable gives on a 422', async () => {
  const f = fakeFetch([{ status: 422, body: { error: { type: 'INVALID_REQUEST_UNKNOWN', message: 'Unknown field name: "Foo"' } } }]);
  await expect(make(f).createRecords('Products', [{ Foo: 1 }])).rejects.toThrow(/HTTP 422.*Unknown field name/);
});

test('leaves a gap between requests to stay under five a second', async () => {
  const sleeps: number[] = [];
  const f = fakeFetch([{ body: { records: [] } }, { body: { records: [] } }]);
  const client = make(f, { gapMs: 220, sleep: async (ms: number) => void sleeps.push(ms) });
  await client.listAll('Products');
  await client.listAll('Variants');
  expect(sleeps).toEqual([220]);
});

test('lists and creates tables through the metadata endpoints', async () => {
  const spec = { name: 'Products', fields: [{ name: 'Title', type: 'singleLineText' }] };
  const f = fakeFetch([{ body: { tables: [{ id: 'tbl1', name: 'Table 1' }] } }, { body: { id: 'tblNew', name: 'Products' } }]);
  const client = make(f);
  expect(await client.listTables()).toEqual([{ id: 'tbl1', name: 'Table 1' }]);
  expect(await client.createTable(spec)).toEqual({ id: 'tblNew', name: 'Products' });
  expect(f.calls[0]!.url).toBe(`https://api.airtable.com/v0/meta/bases/${BASE}/tables`);
  expect(f.calls[1]!.init.method).toBe('POST');
  expect(JSON.parse(f.calls[1]!.init.body)).toEqual(spec);
});

test('readConfig returns the token and base id, trimmed', () => {
  expect(readConfig({ AIRTABLE_TOKEN: ` ${TOKEN} `, AIRTABLE_BASE_ID: ` ${BASE} ` })).toEqual({ token: TOKEN, baseId: BASE });
});

test('readConfig refuses a missing token or a malformed base id without echoing values', () => {
  expect(() => readConfig({ AIRTABLE_BASE_ID: BASE })).toThrow(/AIRTABLE_TOKEN/);
  let err: Error | undefined;
  try {
    readConfig({ AIRTABLE_TOKEN: TOKEN, AIRTABLE_BASE_ID: 'nope' });
  } catch (e) {
    err = e as Error;
  }
  expect(err?.message).toMatch(/AIRTABLE_BASE_ID/);
  expect(err?.message).not.toContain(TOKEN);
});
