const API_VERSION = '2026-07';
const SHOP = /^[a-z0-9][a-z0-9-]*$/;

function parseEnv(text) {
  const env = {};
  for (const line of String(text).split(/\r?\n/)) {
    if (!line.includes('=') || line.trim().startsWith('#')) continue;
    const i = line.indexOf('=');
    env[line.slice(0, i).trim()] = line.slice(i + 1).trim();
  }
  return env;
}

// Error text is fixed wording, never the value that was read.
function assertTarget(shop, to) {
  if (!to) throw new Error('Pass --to <store>: every Shopify write must name its store.');
  if (shop !== to) throw new Error('--to does not match SHOPIFY_SHOP in .env.local; nothing was written.');
}

async function getAccessToken({ shop, clientId, clientSecret, fetchImpl = fetch }) {
  if (!shop || !SHOP.test(shop)) throw new Error('SHOPIFY_SHOP is missing or not a store handle');
  if (!clientId) throw new Error('Missing SHOPIFY_CLIENT_ID');
  if (!clientSecret) throw new Error('Missing SHOPIFY_CLIENT_SECRET');
  const res = await fetchImpl(`https://${shop}.myshopify.com/admin/oauth/access_token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ grant_type: 'client_credentials', client_id: clientId, client_secret: clientSecret }),
  });
  if (!res.ok) throw new Error(`Token request failed with HTTP ${res.status}`);
  const body = await res.json();
  if (typeof body?.access_token !== 'string') throw new Error('Token response had no access_token');
  return body.access_token;
}

function createClient({ shop, token, fetchImpl = fetch }) {
  const url = `https://${shop}.myshopify.com/admin/api/${API_VERSION}/graphql.json`;
  async function graphql(query, variables = {}) {
    const res = await fetchImpl(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Shopify-Access-Token': token },
      body: JSON.stringify({ query, variables }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const body = await res.json();
    if (Array.isArray(body.errors) && body.errors.length > 0) {
      throw new Error(`GraphQL error: ${body.errors.map((e) => e.message).join('; ')}`);
    }
    return body.data;
  }
  return { graphql };
}

module.exports = { API_VERSION, parseEnv, assertTarget, getAccessToken, createClient };
