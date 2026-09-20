import type { NormalizeResult, Product } from '../model/types';
import { loadCatalog } from './source';

export type CatalogState =
  | { ok: true; products: Product[]; rejectedCount: number }
  | { ok: false; reason: string };

export function resolveCatalog(load: () => NormalizeResult = loadCatalog): CatalogState {
  let result: NormalizeResult;
  try {
    result = load();
  } catch (err) {
    return { ok: false, reason: `The catalog could not be loaded: ${err instanceof Error ? err.message : String(err)}` };
  }
  if (result.products.length === 0) {
    if (result.rejected.length === 0) return { ok: false, reason: 'The catalog is empty.' };
    const why = result.rejected
      .slice(0, 3)
      .map((r) => `${r.handle ?? `item ${r.index}`}: ${r.reason}`)
      .join('; ');
    return { ok: false, reason: `No valid products (${result.rejected.length} rejected). ${why}` };
  }
  return { ok: true, products: result.products, rejectedCount: result.rejected.length };
}
