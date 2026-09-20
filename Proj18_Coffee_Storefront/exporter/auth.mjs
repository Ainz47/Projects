// Client credentials grant for an app created in the Shopify Dev Dashboard.
// Unverified against a real store: confirm the request format at the first live run.
const SHOP = /^[a-z0-9][a-z0-9-]*$/;

export async function getAccessToken({ shop, clientId, clientSecret, fetchImpl = fetch }) {
  if (!shop) throw new Error('Missing SHOPIFY_SHOP (the store handle, e.g. "my-store")');
  if (!clientId) throw new Error('Missing SHOPIFY_CLIENT_ID');
  if (!clientSecret) throw new Error('Missing SHOPIFY_CLIENT_SECRET');
  if (!SHOP.test(shop)) throw new Error('Invalid shop handle: use only the part before .myshopify.com');

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
