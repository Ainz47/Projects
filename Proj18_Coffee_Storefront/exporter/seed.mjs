// Loads a catalog into a Shopify store through the Admin GraphQL API. Products are upserted by handle, so a second
// run updates them instead of duplicating them. What the seed needs from the store (a location for stock, the Online
// Store channel to publish to) is looked up before the first write, so a missing permission fails before anything exists.
const LOCATION_QUERY = 'query { locations(first: 1) { nodes { id } } }';
const PUBLICATIONS_QUERY = 'query { publications(first: 20) { nodes { id name } } }';
const PRODUCT_SET = `mutation ProductSet($input: ProductSetInput!, $identifier: ProductSetIdentifiers) {
  productSet(synchronous: true, input: $input, identifier: $identifier) {
    product { id handle }
    userErrors { field message }
  }
}`;
const PUBLISH = `mutation Publish($id: ID!, $input: [PublicationInput!]!) {
  publishablePublish(id: $id, input: $input) {
    userErrors { field message }
  }
}`;
const METAFIELD_TYPE = 'single_line_text_field';

// The store the seed writes to must be named on the command line as well as in the settings, so a wrong settings file
// can never aim it at a store nobody meant.
export function assertTargetShop(configuredShop, confirmedShop) {
  if (!confirmedShop) throw new Error(`Pass --to ${configuredShop} to confirm that is the store to write to`);
  if (confirmedShop !== configuredShop) {
    throw new Error(`--to says ${confirmedShop} but the settings point at ${configuredShop}; nothing was written`);
  }
}

function toInput(node, locationId) {
  return {
    title: node.title,
    handle: node.handle,
    vendor: node.vendor,
    productType: node.productType,
    status: 'ACTIVE',
    tags: node.tags,
    descriptionHtml: node.description,
    productOptions: node.options.map((option, i) => ({
      name: option.name,
      position: i + 1,
      values: option.values.map((name) => ({ name })),
    })),
    variants: node.variants.nodes.map((v) => ({
      optionValues: v.selectedOptions.map((s) => ({ optionName: s.name, name: s.value })),
      sku: v.sku,
      price: v.price,
      inventoryQuantities: [{ locationId, name: 'available', quantity: v.inventoryQuantity }],
    })),
    metafields: (node.metafields?.nodes ?? []).map((m) => ({ ...m, type: METAFIELD_TYPE })),
  };
}

const failures = (errors) => errors.map((e) => e.message).join('; ');

export async function runSeed({ client, nodes, log = (_line) => {} }) {
  const location = (await client.graphql(LOCATION_QUERY)).locations.nodes[0];
  if (!location) throw new Error('The store has no location to hold stock (the app needs the read_locations scope, or add a location in Settings)');
  const channel = (await client.graphql(PUBLICATIONS_QUERY)).publications.nodes.find((p) => p.name === 'Online Store');
  if (!channel) throw new Error('The store has no Online Store sales channel to publish to (the app needs the read_publications scope)');

  let variants = 0;
  for (const node of nodes) {
    const { productSet } = await client.graphql(PRODUCT_SET, {
      input: toInput(node, location.id),
      identifier: { handle: node.handle },
    });
    if (productSet.userErrors.length > 0) throw new Error(`${node.handle}: ${failures(productSet.userErrors)}`);
    const { publishablePublish } = await client.graphql(PUBLISH, {
      id: productSet.product.id,
      input: [{ publicationId: channel.id }],
    });
    if (publishablePublish.userErrors.length > 0) {
      throw new Error(`${node.handle}: created but not published: ${failures(publishablePublish.userErrors)}`);
    }
    variants += node.variants.nodes.length;
    log(`${node.handle}: loaded and published`);
  }
  return { products: nodes.length, variants };
}
