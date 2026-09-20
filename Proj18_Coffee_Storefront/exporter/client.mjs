export const API_VERSION = '2026-07';
export const PAGE_SIZE = 10;

export const PRODUCTS_QUERY = `query Products($cursor: String) {
  products(first: ${PAGE_SIZE}, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id title handle vendor productType tags description
      options { name values }
      variants(first: 50) { nodes { id title sku price inventoryQuantity selectedOptions { name value } } }
      metafields(first: 5, namespace: "custom") { nodes { namespace key value } }
    }
  }
}`;

const defaultSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export function createClient({ shop, token, fetchImpl = fetch, sleep = defaultSleep, maxRetries = 3 }) {
  const url = `https://${shop}.myshopify.com/admin/api/${API_VERSION}/graphql.json`;
  let lastCost = 0;
  let available = Infinity;
  let restoreRate = 50;

  async function graphql(query, variables = {}) {
    for (let attempt = 0; ; attempt += 1) {
      // Cost-aware throttling: wait for the bucket to refill if the last query's cost would not fit.
      if (lastCost > available) {
        await sleep(Math.ceil((lastCost - available) / restoreRate) * 1000);
        available = lastCost;
      }
      const res = await fetchImpl(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Shopify-Access-Token': token },
        body: JSON.stringify({ query, variables }),
      });
      if (res.status === 429 || res.status >= 500) {
        if (attempt >= maxRetries) throw new Error(`HTTP ${res.status} after ${attempt + 1} attempts`);
        await sleep(1000 * 2 ** attempt);
        continue;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const body = await res.json();
      const cost = body.extensions?.cost;
      if (cost) {
        lastCost = cost.requestedQueryCost ?? lastCost;
        available = cost.throttleStatus?.currentlyAvailable ?? available;
        restoreRate = cost.throttleStatus?.restoreRate || restoreRate;
      }
      const errors = body.errors ?? [];
      if (errors.some((e) => e.extensions?.code === 'MAX_COST_EXCEEDED')) {
        throw new Error('The query cost is above the API limit; lower PAGE_SIZE in exporter/client.mjs');
      }
      if (errors.some((e) => e.extensions?.code === 'THROTTLED')) {
        if (attempt >= maxRetries) throw new Error(`Throttled by Shopify after ${attempt + 1} attempts`);
        await sleep(1000 * 2 ** attempt);
        continue;
      }
      if (errors.length > 0) throw new Error(`GraphQL error: ${errors.map((e) => e.message).join('; ')}`);
      return body.data;
    }
  }
  return { graphql };
}

export async function fetchAllProducts(client, maxPages = 200) {
  const nodes = [];
  let cursor = null;
  for (let page = 0; page < maxPages; page += 1) {
    const data = await client.graphql(PRODUCTS_QUERY, { cursor });
    nodes.push(...data.products.nodes);
    if (!data.products.pageInfo.hasNextPage) return nodes;
    cursor = data.products.pageInfo.endCursor;
  }
  throw new Error(`Stopped after ${maxPages} pages; the catalog is larger than expected`);
}
