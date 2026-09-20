import { P, V, PRODUCTS, VARIANTS } from './schema.mjs';

// Everything wrong with a batch of records, reported at once so one export run shows the whole list.
export class AirtableDataError extends Error {
  constructor(problems) {
    const shown = problems.slice(0, 20).map((p) => `- ${p}`).join('\n');
    const more = problems.length > 20 ? `\n- and ${problems.length - 20} more` : '';
    super(`Airtable data is not usable (${problems.length} problem${problems.length === 1 ? '' : 's'}):\n${shown}${more}`);
    this.name = 'AirtableDataError';
    this.problems = problems;
  }
}

// Airtable leaves empty cells out of a record entirely, so a missing key means empty.
const clean = (v) => (typeof v === 'string' && v.trim() !== '' ? v.trim() : null);
const isWhole = (n) => Number.isInteger(n) && n >= 0;
const isMoney = (n) => typeof n === 'number' && Number.isFinite(n) && n >= 0;
const inOrder = (a, b) => a.position - b.position || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);

// Airtable records -> Shopify-shaped product nodes, the shape the fixture and the Shopify exporter produce.
export function recordsToNodes({ products, variants }) {
  const problems = [];
  const bad = (table, id, why) => problems.push(`${table} ${id}: ${why}`);

  const parents = new Map();
  for (const rec of products) {
    const f = rec.fields ?? {};
    if (!clean(f[P.title])) bad(PRODUCTS, rec.id, `${P.title} is empty`);
    if (!clean(f[P.handle])) bad(PRODUCTS, rec.id, `${P.handle} is empty`);
    if (!clean(f[P.option1Name])) bad(PRODUCTS, rec.id, `${P.option1Name} is empty`);
    if (!isWhole(f[P.position])) bad(PRODUCTS, rec.id, `${P.position} must be a whole number of 0 or more`);
    parents.set(rec.id, { id: rec.id, f, position: f[P.position], variants: [] });
  }

  for (const rec of variants) {
    const f = rec.fields ?? {};
    const links = Array.isArray(f[V.product]) ? f[V.product] : [];
    if (links.length !== 1) {
      bad(VARIANTS, rec.id, `${V.product} must link to exactly one product, found ${links.length}`);
      continue;
    }
    const parent = parents.get(links[0]);
    if (!parent) {
      bad(VARIANTS, rec.id, `${V.product} links to ${links[0]}, which is not a row in ${PRODUCTS}`);
      continue;
    }
    if (!isMoney(f[V.price])) bad(VARIANTS, rec.id, `${V.price} must be a number of 0 or more`);
    if (!isWhole(f[V.stock])) bad(VARIANTS, rec.id, `${V.stock} must be a whole number of 0 or more`);
    if (!isWhole(f[V.position])) bad(VARIANTS, rec.id, `${V.position} must be a whole number of 0 or more`);
    parent.variants.push({ id: rec.id, f, position: f[V.position] });
  }

  const optionColumns = [V.option1, V.option2];
  const nodes = [];
  for (const parent of [...parents.values()].sort(inOrder)) {
    const { id, f } = parent;
    if (parent.variants.length === 0) bad(PRODUCTS, id, 'has no variants');
    const names = [clean(f[P.option1Name]), clean(f[P.option2Name])];

    const built = parent.variants.sort(inOrder).map((v) => {
      const selectedOptions = [];
      names.forEach((name, i) => {
        const value = clean(v.f[optionColumns[i]]);
        if (name && !value) {
          bad(VARIANTS, v.id, `${optionColumns[i]} is empty, but the product names its option "${name}"`);
        } else if (!name && value) {
          bad(VARIANTS, v.id, `${optionColumns[i]} has a value, but the product has no ${i === 0 ? P.option1Name : P.option2Name}`);
        } else if (name) {
          selectedOptions.push({ name, value });
        }
      });
      return {
        id: v.id,
        title: selectedOptions.map((o) => o.value).join(' / '),
        sku: clean(v.f[V.sku]) ?? '',
        price: isMoney(v.f[V.price]) ? v.f[V.price].toFixed(2) : '',
        inventoryQuantity: v.f[V.stock],
        selectedOptions,
      };
    });

    const options = names.flatMap((name) => {
      if (!name) return [];
      const values = [];
      for (const v of built) {
        const hit = v.selectedOptions.find((o) => o.name === name);
        if (hit && !values.includes(hit.value)) values.push(hit.value);
      }
      return [{ name, values }];
    });

    const metafields = [
      ['origin', P.origin],
      ['roast', P.roast],
    ]
      .map(([key, column]) => [key, clean(f[column])])
      .filter(([, value]) => value !== null)
      .map(([key, value]) => ({ namespace: 'custom', key, value }));

    nodes.push({
      id,
      title: clean(f[P.title]) ?? '',
      handle: clean(f[P.handle]) ?? '',
      vendor: clean(f[P.vendor]) ?? '',
      productType: clean(f[P.type]) ?? '',
      tags: (clean(f[P.tags]) ?? '').split(',').map((t) => t.trim()).filter(Boolean),
      description: clean(f[P.description]) ?? '',
      options,
      variants: { nodes: built },
      metafields: { nodes: metafields },
    });
  }

  if (problems.length > 0) throw new AirtableDataError(problems);
  return nodes;
}

const compact = (fields) => Object.fromEntries(Object.entries(fields).filter(([, v]) => v !== undefined && v !== ''));

// Shopify-shaped product nodes -> Airtable rows, for the seed. The inverse of recordsToNodes. Each variant carries
// productIndex (into the products list); the seed swaps it for the created product's record id.
export function nodesToRecords(nodes) {
  const products = [];
  const variants = [];
  nodes.forEach((node, i) => {
    const options = node.options ?? [];
    if (options.length < 1 || options.length > 2) {
      throw new Error(`${node.handle}: the Airtable layout holds one or two options, found ${options.length}`);
    }
    const tags = node.tags ?? [];
    const comma = tags.find((t) => t.includes(','));
    if (comma !== undefined) {
      throw new Error(`${node.handle}: tag "${comma}" contains a comma, which the Tags column uses as its separator`);
    }
    const meta = (key) => (node.metafields?.nodes ?? []).find((m) => m.namespace === 'custom' && m.key === key)?.value;

    products.push({
      fields: compact({
        [P.title]: node.title,
        [P.handle]: node.handle,
        [P.description]: node.description,
        [P.vendor]: node.vendor,
        [P.type]: node.productType,
        [P.tags]: tags.join(', '),
        [P.origin]: meta('origin'),
        [P.roast]: meta('roast'),
        [P.option1Name]: options[0].name,
        [P.option2Name]: options[1]?.name,
        [P.position]: i + 1,
      }),
    });

    (node.variants?.nodes ?? []).forEach((v, j) => {
      const value = (name) => (v.selectedOptions ?? []).find((o) => o.name === name)?.value;
      variants.push({
        productIndex: i,
        fields: compact({
          [V.sku]: v.sku,
          [V.option1]: value(options[0].name),
          [V.option2]: options[1] ? value(options[1].name) : undefined,
          [V.price]: Number(v.price),
          [V.stock]: v.inventoryQuantity,
          [V.position]: j + 1,
        }),
      });
    });
  });
  return { products, variants };
}
