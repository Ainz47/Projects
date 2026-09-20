import { nodesToRecords } from './map.mjs';
import { P, V, PRODUCTS, VARIANTS, productsTableSpec, variantsTableSpec } from './schema.mjs';

async function ensureTable(client, tables, spec, log) {
  const found = tables.find((t) => t.name === spec.name);
  if (found) {
    log(`${spec.name}: table already exists`);
    return { table: found, existed: true };
  }
  const table = await client.createTable(spec);
  log(`${spec.name}: table created`);
  return { table, existed: false };
}

async function refuseIfNotEmpty(client, name) {
  const rows = await client.listAll(name);
  if (rows.length > 0) {
    throw new Error(
      `${name} already has ${rows.length} record${rows.length === 1 ? '' : 's'}. Seeding would duplicate them; clear the table or pass --allow-existing.`,
    );
  }
}

// Builds the Products and Variants tables in a base and loads a catalog into them.
export async function runSeed({ client, nodes, allowExisting = false, log = (_line) => {} }) {
  const tables = await client.listTables();
  const products = await ensureTable(client, tables, productsTableSpec(), log);
  const variants = await ensureTable(client, tables, variantsTableSpec(products.table.id), log);
  if (!allowExisting) {
    if (products.existed) await refuseIfNotEmpty(client, PRODUCTS);
    if (variants.existed) await refuseIfNotEmpty(client, VARIANTS);
  }

  const built = nodesToRecords(nodes);
  const createdProducts = await client.createRecords(PRODUCTS, built.products.map((p) => p.fields));
  log(`${PRODUCTS}: ${createdProducts.length} records loaded`);

  // Link by handle, not by position in the response: Airtable's reply order is not something to rely on.
  const idByHandle = new Map(createdProducts.map((r) => [r.fields[P.handle], r.id]));
  if (idByHandle.size !== built.products.length) {
    throw new Error('Two products share a handle, so variants cannot be linked to the right one');
  }
  const variantFields = built.variants.map((v) => {
    const handle = built.products[v.productIndex].fields[P.handle];
    const productId = idByHandle.get(handle);
    if (!productId) throw new Error(`Airtable did not return a record for product ${handle}`);
    return { ...v.fields, [V.product]: [productId] };
  });
  await client.createRecords(VARIANTS, variantFields);
  log(`${VARIANTS}: ${variantFields.length} records loaded`);

  return { products: createdProducts.length, variants: variantFields.length };
}
