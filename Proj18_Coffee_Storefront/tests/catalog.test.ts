import { applyQuery, defaultQuery, facets, parseQuery, serializeQuery, type Query } from '../src/lib/catalog';
import type { Product } from '../src/model/types';

const p = (over: Partial<Product>): Product => ({
  id: 'x', handle: 'x', title: 'X', vendor: 'V', type: 'Coffee', tags: [], description: '', image: null,
  origin: null, roast: null, collections: [], optionNames: [], optionValues: {}, variants: [],
  minCents: 1000, maxCents: 1000, available: true, lowStock: false, ...over,
});

const items = [
  p({ handle: 'a', title: 'Ethiopia Light', origin: 'Ethiopia', roast: 'Light', tags: ['fruity'], minCents: 1800, maxCents: 6500 }),
  p({ handle: 'b', title: 'Brazil Dark', origin: 'Brazil', roast: 'Dark', minCents: 1500, maxCents: 5400, available: false }),
  p({ handle: 'c', title: 'Ceramic Dripper', type: 'Dripper', minCents: 2800, maxCents: 2800 }),
  p({ handle: 'd', title: 'Kenya Light', origin: 'Kenya', roast: 'Light', minCents: 2100, maxCents: 7500 }),
];
const q = (over: Partial<Query>): Query => ({ ...defaultQuery, ...over });
const handles = (list: Product[]) => list.map((x) => x.handle);

test('featured keeps the original order but pushes sold-out products last', () => {
  expect(handles(applyQuery(items, defaultQuery))).toEqual(['a', 'c', 'd', 'b']);
});

test('search needs every word to match title, tags, vendor, type, origin or roast', () => {
  expect(handles(applyQuery(items, q({ q: 'light' })))).toEqual(['a', 'd']);
  expect(handles(applyQuery(items, q({ q: 'FRUITY ethiopia' })))).toEqual(['a']);
  expect(applyQuery(items, q({ q: 'zzz' }))).toEqual([]);
});

test('filters combine: type, origin, roast, in stock, price', () => {
  expect(handles(applyQuery(items, q({ types: ['Dripper'] })))).toEqual(['c']);
  expect(handles(applyQuery(items, q({ origins: ['Kenya', 'Brazil'] })))).toEqual(['d', 'b']);
  expect(handles(applyQuery(items, q({ roasts: ['Light'], inStockOnly: true })))).toEqual(['a', 'd']);
  expect(handles(applyQuery(items, q({ inStockOnly: true })))).not.toContain('b');
  // A price bound keeps a product when any of its variants can fall inside it (sold-out b stays, last).
  expect(handles(applyQuery(items, q({ minCents: 2500 })))).toEqual(['a', 'c', 'd', 'b']);
  expect(handles(applyQuery(items, q({ maxCents: 1600 })))).toEqual(['b']);
});

test('sorts by price and name', () => {
  expect(handles(applyQuery(items, q({ sort: 'price-asc' })))).toEqual(['b', 'a', 'd', 'c']);
  expect(handles(applyQuery(items, q({ sort: 'price-desc' })))).toEqual(['c', 'd', 'a', 'b']);
  expect(handles(applyQuery(items, q({ sort: 'name' })))).toEqual(['b', 'c', 'a', 'd']);
});

test('facets list the distinct values and the price bounds', () => {
  const f = facets(items);
  expect(f.types).toEqual(['Coffee', 'Dripper']);
  expect(f.origins).toEqual(['Brazil', 'Ethiopia', 'Kenya']);
  expect(f.roasts).toEqual(['Light', 'Dark']);
  expect([f.minCents, f.maxCents]).toEqual([1500, 7500]);
});

test('a query survives a round trip through the URL', () => {
  const original = q({ q: 'kenya light', types: ['Coffee'], origins: ['Kenya'], roasts: ['Light'], inStockOnly: true, minCents: 2000, maxCents: 8000, sort: 'price-desc' });
  expect(parseQuery(serializeQuery(original))).toEqual(original);
  expect(serializeQuery(defaultQuery)).toBe('');
});

test('parseQuery ignores junk instead of throwing', () => {
  expect(parseQuery('sort=bogus&min=abc&max=-5&stock=maybe')).toEqual(defaultQuery);
  expect(parseQuery('?q=hello')).toEqual({ ...defaultQuery, q: 'hello' });
});

test('a collection keeps only its members, and combines with the other filters', () => {
  const inPicks = [{ handle: 'picks', title: 'Staff picks' }];
  const list = [p({ handle: 'a', collections: inPicks }), p({ handle: 'b' }), p({ handle: 'c', collections: inPicks, type: 'Dripper' })];
  expect(handles(applyQuery(list, q({ collection: 'picks' })))).toEqual(['a', 'c']);
  expect(handles(applyQuery(list, q({ collection: 'picks', types: ['Dripper'] })))).toEqual(['c']);
  expect(applyQuery(list, q({ collection: 'nope' }))).toEqual([]);
  expect(handles(applyQuery(list, q({ collection: '' })))).toEqual(['a', 'b', 'c']);
});

test('the collection travels in the URL and comes back unchanged', () => {
  const query = q({ collection: 'light-roast', roasts: ['Light'] });
  expect(serializeQuery(query)).toBe('roast=Light&collection=light-roast');
  expect(parseQuery(serializeQuery(query))).toEqual(query);
  expect(parseQuery('')).toEqual(defaultQuery);
});
