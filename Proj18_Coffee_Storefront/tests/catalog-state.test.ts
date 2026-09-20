import { resolveCatalog } from '../src/data/state';
import type { NormalizeResult, Product } from '../src/model/types';

const oneProduct = { handle: 'a' } as Product;

test('a loaded catalog reports how many nodes were rejected', () => {
  const result: NormalizeResult = { products: [oneProduct], rejected: [{ index: 3, handle: 'b', reason: 'no variants' }] };
  expect(resolveCatalog(() => result)).toEqual({ ok: true, products: [oneProduct], rejectedCount: 1 });
});

test('a loader that throws becomes an error state with the message', () => {
  const state = resolveCatalog(() => { throw new Error('bad json'); });
  expect(state).toEqual({ ok: false, reason: 'The catalog could not be loaded: bad json' });
});

test('zero valid products is an error state that says why', () => {
  const rejected = Array.from({ length: 5 }, (_, i) => ({ index: i, handle: `p${i}`, reason: 'no variants' }));
  const state = resolveCatalog(() => ({ products: [], rejected }));
  expect(state.ok).toBe(false);
  if (!state.ok) {
    expect(state.reason).toContain('5 rejected');
    expect(state.reason).toContain('p0: no variants');
    expect(state.reason).not.toContain('p3');
  }
});

test('an empty catalog is an error state', () => {
  expect(resolveCatalog(() => ({ products: [], rejected: [] }))).toEqual({ ok: false, reason: 'The catalog is empty.' });
});
