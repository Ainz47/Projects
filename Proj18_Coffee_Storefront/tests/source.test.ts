import fixture from '../data/catalog.fixture.json';
import { chooseCatalog, notLoadedOf } from '../src/data/source';

const exported = { data: { products: { nodes: [] } } } as unknown as typeof fixture;

test('under test the fixture is always used, even when an export exists', () => {
  expect(chooseCatalog('test', exported)).toBe(fixture);
});

test('outside test the export is used when there is one', () => {
  expect(chooseCatalog('production', exported)).toBe(exported);
  expect(chooseCatalog('development', exported)).toBe(exported);
});

test('the fixture is the fallback when there is no export', () => {
  expect(chooseCatalog('production', undefined)).toBe(fixture);
});

const withCount = (productCount: unknown, printed: number) =>
  ({ data: { shop: { productCount }, products: { nodes: Array.from({ length: printed }, () => ({})) } } });

test('the number of products the theme did not print is the store count minus what it printed', () => {
  expect(notLoadedOf(withCount(70, 50))).toBe(20);
  expect(notLoadedOf(withCount(30, 30))).toBe(0);
});

test('a missing, odd or smaller store count means nothing is reported as missing', () => {
  expect(notLoadedOf(withCount(undefined, 30))).toBe(0);
  expect(notLoadedOf(withCount('many', 30))).toBe(0);
  expect(notLoadedOf(withCount(10, 30))).toBe(0);
  expect(notLoadedOf({ data: { products: { nodes: [] } } })).toBe(0);
});
