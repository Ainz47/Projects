// Creates the store's collections and fills its front page collection. The collections are rule-based (product type
// and tags), so they stay right when products change. Existing collections are left alone, so a second run changes
// nothing, and everything the run depends on is checked before the first write.
import { failures, fetchStoreProducts, findOnlineStore } from './store.mjs';

const rule = (column, condition) => ({ column, relation: 'EQUALS', condition });
export const COLLECTIONS = [
  { handle: 'coffee', title: 'Coffee', ruleSet: { appliedDisjunctively: false, rules: [rule('TYPE', 'Coffee')] } },
  {
    handle: 'brewing-gear',
    title: 'Brewing gear',
    ruleSet: { appliedDisjunctively: true, rules: ['Dripper', 'Kettle', 'Grinder', 'Accessory'].map((t) => rule('TYPE', t)) },
  },
  { handle: 'light-roast', title: 'Light roast', ruleSet: { appliedDisjunctively: false, rules: [rule('TAG', 'light-roast')] } },
  { handle: 'medium-roast', title: 'Medium roast', ruleSet: { appliedDisjunctively: false, rules: [rule('TAG', 'medium-roast')] } },
  { handle: 'dark-roast', title: 'Dark roast', ruleSet: { appliedDisjunctively: false, rules: [rule('TAG', 'dark-roast')] } },
];

// What the theme's home page section shows: a mix of the range, coffee first.
export const FRONT_PAGE = 'frontpage';
export const FEATURED = [
  'yirgacheffe-washed-ethiopia',
  'huila-reserve-colombia',
  'kiambu-aa-kenya',
  'antigua-volcanic-guatemala',
  'house-espresso',
  'ceramic-dripper-02',
  'gooseneck-kettle-0-9l',
  'hand-grinder-compact',
];

const EXISTING = 'query { collections(first: 250) { nodes { id handle } } }';
const FRONT = `query Front($handle: String!) {
  collectionByIdentifier(identifier: { handle: $handle }) { id products(first: 250) { nodes { id } } }
}`;
const CREATE = `mutation CollectionCreate($input: CollectionInput!) {
  collectionCreate(input: $input) { collection { id } userErrors { field message } }
}`;
const ADD = `mutation CollectionAdd($id: ID!, $productIds: [ID!]!) {
  collectionAddProducts(id: $id, productIds: $productIds) { userErrors { field message } }
}`;
const PUBLISH = `mutation Publish($id: ID!, $input: [PublicationInput!]!) {
  publishablePublish(id: $id, input: $input) { userErrors { field message } }
}`;

export async function runSeedCollections({ client, nodes, log = (_line) => {} }) {
  const channel = await findOnlineStore(client);
  const front = (await client.graphql(FRONT, { handle: FRONT_PAGE })).collectionByIdentifier;
  if (!front) throw new Error(`The store has no "${FRONT_PAGE}" collection to fill (Shopify creates it with the store)`);
  const inStore = await fetchStoreProducts(client);
  const notThere = FEATURED.filter((h) => !inStore.has(h));
  if (notThere.length > 0) throw new Error(`Featured products not in the store: ${notThere.join(', ')}. Run npm run seed:shopify first.`);
  const existing = new Set((await client.graphql(EXISTING)).collections.nodes.map((c) => c.handle));

  let created = 0;
  for (const c of COLLECTIONS) {
    if (existing.has(c.handle)) {
      log(`${c.handle}: already exists`);
      continue;
    }
    const { collectionCreate } = await client.graphql(CREATE, { input: { title: c.title, handle: c.handle, ruleSet: c.ruleSet } });
    if (collectionCreate.userErrors.length > 0) throw new Error(`${c.handle}: ${failures(collectionCreate.userErrors)}`);
    const { publishablePublish } = await client.graphql(PUBLISH, {
      id: collectionCreate.collection.id,
      input: [{ publicationId: channel.id }],
    });
    if (publishablePublish.userErrors.length > 0) throw new Error(`${c.handle}: created but not published: ${failures(publishablePublish.userErrors)}`);
    created += 1;
    log(`${c.handle}: created and published`);
  }

  const onFront = new Set(front.products.nodes.map((p) => p.id));
  const toAdd = FEATURED.map((h) => inStore.get(h).id).filter((id) => !onFront.has(id));
  if (toAdd.length > 0) {
    const { collectionAddProducts } = await client.graphql(ADD, { id: front.id, productIds: toAdd });
    if (collectionAddProducts.userErrors.length > 0) throw new Error(`${FRONT_PAGE}: ${failures(collectionAddProducts.userErrors)}`);
  }
  log(`${FRONT_PAGE}: ${toAdd.length} featured products added`);
  return { created, existing: COLLECTIONS.length - created, featuredAdded: toAdd.length };
}
