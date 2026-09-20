import { defaultQuery, type Query } from '../src/lib/catalog';
import { listHref, parseHash, productHref, replaceHash } from '../src/ui/router';

test('parses the listing, with and without a query', () => {
  expect(parseHash('')).toEqual({ name: 'list', query: defaultQuery });
  expect(parseHash('#/')).toEqual({ name: 'list', query: defaultQuery });
  expect(parseHash('#/?q=kenya&sort=name')).toEqual({ name: 'list', query: { ...defaultQuery, q: 'kenya', sort: 'name' } });
});

test('parses a product route and decodes the handle', () => {
  expect(parseHash('#/product/kiambu-aa-kenya')).toEqual({ name: 'product', handle: 'kiambu-aa-kenya' });
  expect(parseHash('#/product/a%20b')).toEqual({ name: 'product', handle: 'a b' });
});

test('anything else is not found, including a malformed escape', () => {
  expect(parseHash('#/nope')).toEqual({ name: 'notfound' });
  expect(parseHash('#/product/')).toEqual({ name: 'notfound' });
  expect(parseHash('#/product/a/b')).toEqual({ name: 'notfound' });
  expect(parseHash('#/product/%E0%A4%A')).toEqual({ name: 'notfound' });
});

test('hrefs round trip through parseHash', () => {
  const q: Query = { ...defaultQuery, q: 'light roast', origins: ['Kenya'], sort: 'price-asc' };
  expect(listHref(defaultQuery)).toBe('#/');
  expect(parseHash(listHref(q))).toEqual({ name: 'list', query: q });
  expect(parseHash(productHref('a b'))).toEqual({ name: 'product', handle: 'a b' });
});

test('replaceHash changes the hash, adds no history entry and notifies listeners', () => {
  const before = window.history.length;
  const seen = vi.fn();
  window.addEventListener('hashchange', seen);
  replaceHash('#/?q=x');
  window.removeEventListener('hashchange', seen);
  expect(window.location.hash).toBe('#/?q=x');
  expect(window.history.length).toBe(before);
  expect(seen).toHaveBeenCalledTimes(1);
});
