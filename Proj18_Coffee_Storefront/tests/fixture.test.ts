import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { normalizeProducts } from '../src/model/normalize';
import { loadCatalog } from '../src/data/source';

const raw = readFileSync(resolve(process.cwd(), 'data/catalog.fixture.json'), 'utf8');
const nodes = JSON.parse(raw).data.products.nodes as unknown[];

test('every fixture node normalizes with zero rejects', () => {
  const { products, rejected } = normalizeProducts(nodes);
  expect(rejected).toEqual([]);
  expect(products.length).toBeGreaterThanOrEqual(28);
  expect(products.length).toBeLessThanOrEqual(40);
});

test('the fixture exercises the states the UI must handle', () => {
  const { products } = normalizeProducts(nodes);
  expect(products.some((p) => !p.available)).toBe(true);
  expect(products.some((p) => p.lowStock)).toBe(true);
  expect(products.some((p) => p.variants.length === 1)).toBe(true);
  expect(products.some((p) => p.available && p.variants.some((v) => !v.available))).toBe(true);
  expect(new Set(products.map((p) => p.type)).size).toBeGreaterThanOrEqual(4);
  expect(new Set(products.map((p) => p.origin).filter(Boolean)).size).toBeGreaterThanOrEqual(6);
});

test('the fixture holds no email, phone number or url (the publish gate scans for them)', () => {
  expect(raw).not.toMatch(/@/);
  expect(raw).not.toMatch(/\d{3}[-. ]\d{3}[-. ]\d{4}/);
  expect(raw).not.toMatch(/https?:\/\//);
});

test('loadCatalog returns the normalized fixture', () => {
  const { products, rejected } = loadCatalog();
  expect(rejected).toEqual([]);
  expect(products.length).toBeGreaterThan(0);
});
