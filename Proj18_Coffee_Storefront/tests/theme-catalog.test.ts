import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { Liquid } from 'liquidjs';
import { normalizeProducts } from '../src/model/normalize';

const nodes = JSON.parse(readFileSync(resolve(process.cwd(), 'data/catalog.fixture.json'), 'utf8')).data.products.nodes as any[];
const snippet = readFileSync(resolve(process.cwd(), 'theme/snippets/catalog-json.liquid'), 'utf8');

// What Shopify's Liquid hands a template for a product: cents for prices, HTML descriptions, options as name lists.
const shopifyProduct = (n: any, i: number, image = true) => ({
  id: 1000 + i,
  title: n.title,
  handle: n.handle,
  vendor: n.vendor,
  type: n.productType,
  tags: n.tags,
  description: `<p>${n.description}</p>`,
  featured_image: image ? { src: `${n.handle}.png` } : null,
  options: n.options.map((o: any) => o.name),
  options_with_values: n.options.map((o: any) => ({ name: o.name, values: o.values })),
  variants: n.variants.nodes.map((v: any, j: number) => ({
    id: 90000 + i * 100 + j,
    title: v.title,
    sku: v.sku,
    price: Math.round(parseFloat(v.price) * 100),
    inventory_quantity: v.inventoryQuantity,
    options: n.options.map((o: any) => v.selectedOptions.find((s: any) => s.name === o.name).value),
  })),
  metafields: { custom: Object.fromEntries((n.metafields?.nodes ?? []).map((m: any) => [m.key, { value: m.value }])) },
});

// Only Shopify's own filters are stubbed; everything else in the snippet is standard Liquid.
const engine = new Liquid();
engine.registerFilter('image_url', (img: any) => (img ? `//cdn.test/${img.src}` : ''));

async function render(products: unknown[]) {
  const html = await engine.parseAndRender(snippet, { collections: { all: { products } } });
  // The browser's own parser decodes the attribute, exactly as it will on the storefront.
  document.body.innerHTML = html;
  const el = document.getElementById('catalog-data');
  expect(el).not.toBeNull();
  return { html, json: JSON.parse(el!.getAttribute('data-catalog')!) };
}

const stripIds = (products: ReturnType<typeof normalizeProducts>['products']) =>
  products.map(({ id, image, variants, ...p }) => ({ ...p, variants: variants.map(({ id: variantId, ...v }) => v) }));

test('the snippet turns Shopify products into a catalog that normalizes to the same products as the fixture', async () => {
  const { json } = await render(nodes.map((n, i) => shopifyProduct(n, i)));
  const fromTheme = normalizeProducts(json.data.products.nodes);
  expect(fromTheme.rejected).toEqual([]);
  expect(fromTheme.products).toHaveLength(30);
  expect(stripIds(fromTheme.products)).toEqual(stripIds(normalizeProducts(nodes).products));
});

test('prices survive as exact cents, including amounts with cents and single-digit cents', async () => {
  const one = shopifyProduct(nodes[0], 0);
  one.variants[0].price = 1845;
  one.variants[1].price = 6005;
  const { json } = await render([one]);
  const prices = json.data.products.nodes[0].variants.nodes.map((v: any) => v.price);
  expect(prices.slice(0, 2)).toEqual(['18.45', '60.05']);
});

test('each product carries its Shopify image url, or null when it has none', async () => {
  const { json } = await render([shopifyProduct(nodes[0], 0), shopifyProduct(nodes[1], 1, false)]);
  expect(json.data.products.nodes[0].image).toBe(`//cdn.test/${nodes[0].handle}.png`);
  expect(json.data.products.nodes[1].image).toBeNull();
});

test('ids come out as strings, so the normalizer accepts them and the checkout can read the variant id', async () => {
  const { json } = await render([shopifyProduct(nodes[0], 0)]);
  const node = json.data.products.nodes[0];
  expect(node.id).toBe('1000');
  expect(node.variants.nodes[0].id).toBe('90000');
});

test('a product with no metafields still renders, and its origin and roast are simply absent', async () => {
  const bare = { ...shopifyProduct(nodes[0], 0), metafields: {} };
  const { json } = await render([bare]);
  const result = normalizeProducts(json.data.products.nodes);
  expect(result.rejected).toEqual([]);
  expect(result.products[0]!.origin).toBeNull();
  expect(result.products[0]!.roast).toBeNull();
});

test('text that could break out of the element cannot, and comes back unchanged', async () => {
  const nasty = { ...shopifyProduct(nodes[0], 0), title: 'A "quoted" </script><b>title', description: '<p>Line one\nline "two" & more</p>' };
  const { html, json } = await render([nasty]);
  expect(html).not.toContain('</script');
  expect(document.querySelectorAll('script, b')).toHaveLength(0);
  expect(json.data.products.nodes[0].title).toBe('A "quoted" </script><b>title');
  expect(json.data.products.nodes[0].description).toBe('Line one\nline "two" & more');
});

test('an empty store renders an empty, valid catalog', async () => {
  const { json } = await render([]);
  expect(json.data.products.nodes).toEqual([]);
});
