import { spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const catalog = (nodes: unknown[]) => JSON.stringify({ data: { products: { nodes } } });
const node = (over: Record<string, unknown> = {}) => ({
  id: 'gid-1',
  title: 'A',
  handle: 'a',
  variants: { nodes: [{ id: 'v-1', sku: 'S', price: '1.00' }] },
  ...over,
});

function run(a: unknown[], b: unknown[]) {
  const dir = mkdtempSync(join(tmpdir(), 'compare-'));
  writeFileSync(join(dir, 'a.json'), catalog(a));
  writeFileSync(join(dir, 'b.json'), catalog(b));
  const r = spawnSync(process.execPath, ['tools/compare_catalog.mjs', join(dir, 'a.json'), join(dir, 'b.json')], {
    cwd: process.cwd(),
    encoding: 'utf8',
  });
  return { code: r.status, out: `${r.stdout}${r.stderr}` };
}

test('says two catalogs are identical when only the ids differ', () => {
  const r = run([node()], [node({ id: 'rec1', variants: { nodes: [{ id: 'rec2', sku: 'S', price: '1.00' }] } })]);
  expect(r.code).toBe(0);
  expect(r.out).toMatch(/identical apart from ids \(1 products\)/);
});

test('names the product and the field when a price changed', () => {
  const r = run([node()], [node({ variants: { nodes: [{ id: 'v-1', sku: 'S', price: '2.00' }] } })]);
  expect(r.code).toBe(1);
  expect(r.out).toMatch(/a: differs in variants/);
});

test('reports a product missing from one side and a product only on the other', () => {
  const r = run([node(), node({ handle: 'b' })], [node(), node({ handle: 'c' })]);
  expect(r.code).toBe(1);
  expect(r.out).toMatch(/b: missing from/);
  expect(r.out).toMatch(/c: only in/);
});

test('prints usage and exits 2 without two file arguments', () => {
  const r = spawnSync(process.execPath, ['tools/compare_catalog.mjs'], { cwd: process.cwd(), encoding: 'utf8' });
  expect(r.status).toBe(2);
  expect(r.stderr).toMatch(/usage/);
});
