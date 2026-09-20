import { normalizeProducts } from '../model/normalize';
import type { NormalizeResult } from '../model/types';
import fixture from '../../data/catalog.fixture.json';
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

export function loadCatalog(): NormalizeResult {
  const exported = Object.values(snapshots)[0];
  return normalizeProducts(chooseCatalog(import.meta.env.MODE, exported, readInjectedCatalog()).data.products.nodes);
}
