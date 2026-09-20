import fixture from '../data/catalog.fixture.json';
import { chooseCatalog } from '../src/data/source';

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
