import { normalizeProducts } from '../model/normalize';
import type { NormalizeResult } from '../model/types';
import fixture from '../../data/catalog.fixture.json';

// The ONE place that decides where products come from. To use a real export,
// import data/catalog.export.json here instead (see README).
export function loadCatalog(): NormalizeResult {
  return normalizeProducts(fixture.data.products.nodes);
}
