export const API = 'https://api.airtable.com';
export const PAGE_SIZE = 100; // the most Airtable returns per list request
export const BATCH_SIZE = 10; // records per create request; the first live seed run confirms this is accepted
export const RATE_LIMIT_WAIT_MS = 30000; // Airtable asks for a 30 second wait after a 429

const defaultSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Messages are built from the status alone, so nothing that reaches a log can contain the credential.
const FAILURES = {
  401: 'Airtable rejected the token (HTTP 401). Check AIRTABLE_TOKEN.',
  403: 'Airtable says this token cannot reach the base or lacks a scope (HTTP 403). Check its base access and scopes.',
  404: 'Airtable could not find that base or table (HTTP 404). Check AIRTABLE_BASE_ID and the table name.',
};

export function createClient({ baseId, token, fetchImpl = fetch, sleep = defaultSleep, maxRetries = 3, gapMs = 220 }) {
  let first = true;

  async function request(method, path, body) {
    for (let attempt = 0; ; attempt += 1) {
      // Airtable allows 5 requests a second per base. A small gap stays under that, so the 30 second penalty is rare.
      if (!first && gapMs > 0) await sleep(gapMs);
      first = false;
      const res = await fetchImpl(`${API}${path}`, {
        method,
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (res.status === 429 || res.status === 503) {
        if (attempt >= maxRetries) throw new Error(`Airtable kept answering HTTP ${res.status}; gave up after ${attempt + 1} attempts`);
        await sleep(res.status === 429 ? RATE_LIMIT_WAIT_MS : 1000 * 2 ** attempt);
        continue;
      }
      if (FAILURES[res.status]) throw new Error(FAILURES[res.status]);
      if (!res.ok) {
        const detail = await res.json().then((b) => b?.error?.message, () => undefined);
        throw new Error(`Airtable request failed (HTTP ${res.status})${detail ? `: ${detail}` : ''}`);
      }
      return res.json();
    }
  }

  // Airtable promises no order on a list, so callers sort by their own Position column.
  async function listAll(table, maxPages = 50) {
    const records = [];
    let offset;
    for (let page = 0; page < maxPages; page += 1) {
      const query = new URLSearchParams({ pageSize: String(PAGE_SIZE) });
      if (offset) query.set('offset', offset);
      const body = await request('GET', `/v0/${baseId}/${encodeURIComponent(table)}?${query}`);
      records.push(...body.records);
      if (!body.offset) return records;
      offset = body.offset;
    }
    throw new Error(`Stopped after ${maxPages} pages of ${table}; the table is larger than expected`);
  }

  async function createRecords(table, fieldsList) {
    const created = [];
    for (let i = 0; i < fieldsList.length; i += BATCH_SIZE) {
      const chunk = fieldsList.slice(i, i + BATCH_SIZE);
      const body = await request('POST', `/v0/${baseId}/${encodeURIComponent(table)}`, {
        records: chunk.map((fields) => ({ fields })),
      });
      created.push(...body.records);
    }
    return created;
  }

  // updates: [{ id, fields }]. PATCH changes only the fields given and leaves every other cell alone.
  async function updateRecords(table, updates) {
    const updated = [];
    for (let i = 0; i < updates.length; i += BATCH_SIZE) {
      const body = await request('PATCH', `/v0/${baseId}/${encodeURIComponent(table)}`, {
        records: updates.slice(i, i + BATCH_SIZE),
      });
      updated.push(...body.records);
    }
    return updated;
  }

  const listTables = async () => (await request('GET', `/v0/meta/bases/${baseId}/tables`)).tables;
  const createTable = (spec) => request('POST', `/v0/meta/bases/${baseId}/tables`, spec);

  return { listAll, createRecords, updateRecords, listTables, createTable };
}
