import { normalizeProducts } from '../model/normalize';
import type { NormalizeResult } from '../model/types';
import fixture from '../../data/catalog.fixture.json';
import { setCurrency } from '../lib/money';
import { readInjectedCatalog } from './injected';

// A snapshot written by `npm run export:airtable` (or by the Shopify exporter) when one exists. The glob is
// optional on purpose: on a fresh clone it finds nothing and the fixture is used.
const snapshots = import.meta.glob('../../data/catalog.export.json', { eager: true, import: 'default' }) as Record<
  string,
  typeof fixture
>;

// The ONE place that decides where products come from: the catalog a Shopify theme printed into the page, else the
// exported snapshot, else the fixture. Tests always read the fixture, so their expectations do not move when the
// shop's data does.
export function chooseCatalog(mode: string, exported: typeof fixture | undefined, injected?: typeof fixture): typeof fixture {
  if (mode === 'test') return fixture;
  return injected ?? exported ?? fixture;
}

// The store's currency code, when the theme's snippet provided one (the fixture and the exporters do not).
export const currencyCodeOf = (catalog: unknown): string | undefined =>
  (catalog as { data?: { shop?: { currencyCode?: unknown } } }).data?.shop?.currencyCode as string | undefined;

// How many of the store's products the theme's snippet did not print (its Liquid loop stops at 50). Anything odd in the
// count means "nothing known to be missing", never a made-up number.
export function notLoadedOf(catalog: unknown): number {
  const c = catalog as { data?: { shop?: { productCount?: unknown }; products?: { nodes?: unknown[] } } };
  const total = c.data?.shop?.productCount;
  const printed = c.data?.products?.nodes?.length ?? 0;
  return typeof total === 'number' && Number.isInteger(total) && total > printed ? total - printed : 0;
}

export function loadCatalog(): NormalizeResult & { notLoaded: number } {
  const exported = Object.values(snapshots)[0];
  const catalog = chooseCatalog(import.meta.env.MODE, exported, readInjectedCatalog());
  setCurrency(currencyCodeOf(catalog));
  return { ...normalizeProducts(catalog.data.products.nodes), notLoaded: notLoadedOf(catalog) };
}
