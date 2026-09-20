import fixture from '../data/catalog.fixture.json';
import { chooseCatalog } from '../src/data/source';
import { readInjectedCatalog, inShopifyTheme } from '../src/data/injected';
import { normalizeProducts } from '../src/model/normalize';

const exported = { data: { products: { nodes: [] } } } as unknown as typeof fixture;
const injected = { data: { products: { nodes: [] } } } as unknown as typeof fixture;

test('a catalog injected by the theme wins over the snapshot and the fixture, except in tests', () => {
  expect(chooseCatalog('production', exported, injected)).toBe(injected);
  expect(chooseCatalog('production', undefined, injected)).toBe(injected);
  expect(chooseCatalog('test', exported, injected)).toBe(fixture);
});

test('without an injected catalog the choice is unchanged', () => {
  expect(chooseCatalog('production', exported, undefined)).toBe(exported);
  expect(chooseCatalog('production', undefined, undefined)).toBe(fixture);
});

function withCatalogElement(text: string, run: () => void) {
  const el = document.createElement('div');
  el.id = 'catalog-data';
  el.setAttribute('data-catalog', text);
  document.body.appendChild(el);
  try {
    run();
  } finally {
    el.remove();
  }
}

test('the theme is recognised by its catalog element, and only by that', () => {
  expect(inShopifyTheme()).toBe(false);
  expect(readInjectedCatalog()).toBeUndefined();
  withCatalogElement('{"data":{"products":{"nodes":[]}}}', () => {
    expect(inShopifyTheme()).toBe(true);
    expect(readInjectedCatalog()).toEqual({ data: { products: { nodes: [] } } });
  });
});

test('a catalog element with broken JSON throws, so the page shows its error screen and not the fixture', () => {
  withCatalogElement('{not json', () => {
    expect(() => readInjectedCatalog()).toThrow();
  });
});

test('the normalizer keeps an https image url and drops anything else', () => {
  const node = (image: unknown) => ({ ...(fixture.data.products.nodes[0] as object), image });
  const image = (v: unknown) => normalizeProducts([node(v)]).products[0]!.image;
  expect(image('https://cdn.shopify.com/s/files/x.png?width=800')).toBe('https://cdn.shopify.com/s/files/x.png?width=800');
  expect(image('//jhurald05.myshopify.com/cdn/shop/files/x.png?v=1&width=800')).toBe('https://jhurald05.myshopify.com/cdn/shop/files/x.png?v=1&width=800');
  expect(image('http://insecure.test/x.png')).toBeNull();
  expect(image('javascript:alert(1)')).toBeNull();
  expect(image(null)).toBeNull();
  expect(image(undefined)).toBeNull();
});
