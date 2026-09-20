// Gives each seeded product one image. The image is rendered by the caller (`render`), sent to Shopify's staged upload
// target by the caller (`upload`), then attached to the product. Products that already have media are skipped, so a
// second run changes nothing, and every product is found in the store before the first write.
import { failures, fetchStoreProducts } from './store.mjs';

const STAGED_UPLOAD = `mutation StagedUpload($input: [StagedUploadInput!]!) {
  stagedUploadsCreate(input: $input) {
    stagedTargets { url resourceUrl parameters { name value } }
    userErrors { field message }
  }
}`;
const PRODUCT_UPDATE = `mutation ProductUpdate($product: ProductUpdateInput!, $media: [CreateMediaInput!]) {
  productUpdate(product: $product, media: $media) {
    product { id }
    userErrors { field message }
  }
}`;

export async function runSeedImages({ client, nodes, render, upload, log = (_line) => {} }) {
  const inStore = await fetchStoreProducts(client);
  const missing = nodes.filter((n) => !inStore.has(n.handle)).map((n) => n.handle);
  if (missing.length > 0) throw new Error(`Not in the store: ${missing.join(', ')}. Run npm run seed:shopify first.`);

  let added = 0;
  let skipped = 0;
  for (const node of nodes) {
    const product = inStore.get(node.handle);
    if (product.media > 0) {
      skipped += 1;
      log(`${node.handle}: already has an image`);
      continue;
    }
    const filename = `${node.handle}.png`;
    const body = await render(node);
    const staged = await client.graphql(STAGED_UPLOAD, {
      input: [{ resource: 'PRODUCT_IMAGE', filename, mimeType: 'image/png', httpMethod: 'POST' }],
    });
    if (staged.stagedUploadsCreate.userErrors.length > 0) throw new Error(`${node.handle}: ${failures(staged.stagedUploadsCreate.userErrors)}`);
    const target = staged.stagedUploadsCreate.stagedTargets[0];
    await upload(target, body, filename);
    const { productUpdate } = await client.graphql(PRODUCT_UPDATE, {
      product: { id: product.id },
      media: [{ originalSource: target.resourceUrl, mediaContentType: 'IMAGE', alt: node.title }],
    });
    if (productUpdate.userErrors.length > 0) throw new Error(`${node.handle}: ${failures(productUpdate.userErrors)}`);
    added += 1;
    log(`${node.handle}: image attached`);
  }
  return { added, skipped };
}
