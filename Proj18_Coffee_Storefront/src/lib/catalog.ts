import type { Product } from '../model/types';

export type SortKey = 'featured' | 'price-asc' | 'price-desc' | 'name';

export interface Query {
  q: string;
  types: string[];
  origins: string[];
  roasts: string[];
  collection: string;
  inStockOnly: boolean;
  minCents: number | null;
  maxCents: number | null;
  sort: SortKey;
}

export const defaultQuery: Query = {
  q: '', types: [], origins: [], roasts: [], collection: '', inStockOnly: false, minCents: null, maxCents: null, sort: 'featured',
};

const SORTS: SortKey[] = ['featured', 'price-asc', 'price-desc', 'name'];
const ROAST_ORDER = ['Light', 'Medium', 'Dark'];

const haystack = (p: Product): string =>
  [p.title, p.vendor, p.type, p.origin ?? '', p.roast ?? '', ...p.tags].join(' ').toLowerCase();

export function applyQuery(products: Product[], q: Query): Product[] {
  const tokens = q.q.toLowerCase().split(/\s+/).filter(Boolean);
  const kept = products.filter(
    (p) =>
      tokens.every((t) => haystack(p).includes(t)) &&
      (q.types.length === 0 || q.types.includes(p.type)) &&
      (q.origins.length === 0 || (p.origin !== null && q.origins.includes(p.origin))) &&
      (q.roasts.length === 0 || (p.roast !== null && q.roasts.includes(p.roast))) &&
      (q.collection === '' || p.collections.some((c) => c.handle === q.collection)) &&
      (!q.inStockOnly || p.available) &&
      (q.minCents === null || p.maxCents >= q.minCents) &&
      (q.maxCents === null || p.minCents <= q.maxCents),
  );
  switch (q.sort) {
    case 'price-asc':
      return [...kept].sort((a, b) => a.minCents - b.minCents);
    case 'price-desc':
      return [...kept].sort((a, b) => b.minCents - a.minCents);
    case 'name':
      return [...kept].sort((a, b) => a.title.localeCompare(b.title));
    default:
      // Featured: original order, sold-out products last (stable partition).
      return [...kept.filter((p) => p.available), ...kept.filter((p) => !p.available)];
  }
}

const uniqueSorted = (values: (string | null)[]): string[] =>
  [...new Set(values.filter((v): v is string => v !== null))].sort((a, b) => a.localeCompare(b));

export function facets(products: Product[]) {
  return {
    types: uniqueSorted(products.map((p) => p.type)),
    origins: uniqueSorted(products.map((p) => p.origin)),
    roasts: uniqueSorted(products.map((p) => p.roast)).sort((a, b) => ROAST_ORDER.indexOf(a) - ROAST_ORDER.indexOf(b)),
    minCents: Math.min(...products.map((p) => p.minCents)),
    maxCents: Math.max(...products.map((p) => p.maxCents)),
  };
}

const toCents = (dollars: string | null): number | null => {
  if (dollars === null || !/^\d+$/.test(dollars)) return null;
  return Number(dollars) * 100;
};

export function parseQuery(search: string): Query {
  const params = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
  const sort = params.get('sort');
  return {
    q: params.get('q') ?? '',
    types: params.getAll('type'),
    origins: params.getAll('origin'),
    roasts: params.getAll('roast'),
    collection: params.get('collection') ?? '',
    inStockOnly: params.get('stock') === '1',
    minCents: toCents(params.get('min')),
    maxCents: toCents(params.get('max')),
    sort: SORTS.includes(sort as SortKey) ? (sort as SortKey) : 'featured',
  };
}

export function serializeQuery(q: Query): string {
  const params = new URLSearchParams();
  if (q.q) params.set('q', q.q);
  q.types.forEach((v) => params.append('type', v));
  q.origins.forEach((v) => params.append('origin', v));
  q.roasts.forEach((v) => params.append('roast', v));
  if (q.collection) params.set('collection', q.collection);
  if (q.inStockOnly) params.set('stock', '1');
  if (q.minCents !== null) params.set('min', String(q.minCents / 100));
  if (q.maxCents !== null) params.set('max', String(q.maxCents / 100));
  if (q.sort !== 'featured') params.set('sort', q.sort);
  return params.toString();
}
