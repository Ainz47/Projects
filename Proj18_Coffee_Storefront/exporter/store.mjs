// Lookups the store-dressing steps (images, collections) share. Kept apart from seed.mjs so the proven seed stays untouched.
const STORE_PRODUCTS = `query StoreProducts($cursor: String) {
  products(first: 50, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes { id handle mediaCount { count } }
  }
}`;
const PUBLICATIONS_QUERY = 'query { publications(first: 20) { nodes { id name } } }';

export const failures = (errors) => errors.map((e) => e.message).join('; ');

// Every product in the store, keyed by handle, with how many media it already holds.
export async function fetchStoreProducts(client, maxPages = 50) {
  const byHandle = new Map();
  let cursor = null;
  for (let page = 0; page < maxPages; page += 1) {
    const { products } = await client.graphql(STORE_PRODUCTS, { cursor });
    for (const n of products.nodes) byHandle.set(n.handle, { id: n.id, media: n.mediaCount?.count ?? 0 });
    if (!products.pageInfo.hasNextPage) return byHandle;
    cursor = products.pageInfo.endCursor;
  }
  throw new Error(`Stopped after ${maxPages} pages; the store has more products than expected`);
}

export async function findOnlineStore(client) {
  const channel = (await client.graphql(PUBLICATIONS_QUERY)).publications.nodes.find((p) => p.name === 'Online Store');
  if (!channel) throw new Error('The store has no Online Store sales channel to publish to (the app needs the read_publications scope)');
  return channel;
}
