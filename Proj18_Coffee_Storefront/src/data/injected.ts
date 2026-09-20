import type fixture from '../../data/catalog.fixture.json';

const ELEMENT_ID = 'catalog-data';

// Inside a Shopify theme, the catalog-json snippet prints the store's products into the page as JSON, in the
// data-catalog attribute of an element. That element is how the app knows it is running in a theme, and where its
// products are.
export function inShopifyTheme(doc: Document = document): boolean {
  return doc.getElementById(ELEMENT_ID) !== null;
}

// Throws on broken JSON on purpose: the page then shows its error screen instead of quietly showing other data.
export function readInjectedCatalog(doc: Document = document): typeof fixture | undefined {
  const el = doc.getElementById(ELEMENT_ID);
  return el ? JSON.parse(el.getAttribute('data-catalog') ?? '') : undefined;
}
