import { useMemo, useState } from 'react';
import { imageFor } from '../art';
import { applyQuery, defaultQuery, facets, serializeQuery, type Query, type SortKey } from '../lib/catalog';
import type { Product } from '../model/types';
import { FilterPanel } from './FilterPanel';
import { ProductCard } from './ProductCard';
import { listHref } from './router';
import { SearchBox } from './SearchBox';

const SORT_LABELS: Record<SortKey, string> = {
  featured: 'Featured',
  'price-asc': 'Price, low to high',
  'price-desc': 'Price, high to low',
  name: 'Name',
};

const countLabel = (n: number): string => (n === 1 ? '1 product' : `${n} products`);

// A handful of real, in-stock products across different types, for a hero preview that shows what
// is actually in the catalog instead of a decorative stock image.
function heroPreview(products: Product[]): Product[] {
  const seen = new Set<string>();
  const picks: Product[] = [];
  for (const p of products) {
    if (!p.available || seen.has(p.type)) continue;
    seen.add(p.type);
    picks.push(p);
    if (picks.length === 4) break;
  }
  return picks;
}

interface Props {
  products: Product[];
  query: Query;
  rejectedCount: number;
  notLoadedCount: number;
  onQueryChange: (q: Query) => void;
}

export function ListingPage({ products, query, rejectedCount, notLoadedCount, onQueryChange }: Props) {
  const f = useMemo(() => facets(products), [products]);
  const shown = useMemo(() => applyQuery(products, query), [products, query]);
  const preview = useMemo(() => heroPreview(products), [products]);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const changed = serializeQuery(query) !== '';
  // A collection's name comes from any product in it; an unknown handle shows as typed.
  const collectionTitle =
    query.collection === '' ? '' : products.flatMap((p) => p.collections).find((c) => c.handle === query.collection)?.title ?? query.collection;
  const activeCount =
    query.types.length + query.origins.length + query.roasts.length + (query.collection !== '' ? 1 : 0) +
    (query.inStockOnly ? 1 : 0) + (query.minCents !== null ? 1 : 0) + (query.maxCents !== null ? 1 : 0);

  return (
    <div className="listing">
      <div className="hero">
        <div className="hero-copy">
          <h1>Lantern Roasters (demo)</h1>
          <p className="lede">Specialty coffee and brewing gear. A demo storefront with made-up products and no checkout.</p>
          <a className="button button-primary hero-cta" href={listHref({ ...defaultQuery, roasts: ['Light'] })}>
            Browse light roasts
          </a>
        </div>
        {preview.length > 0 && (
          <div className="hero-art" aria-hidden="true">
            {preview.map((p) => (
              <img key={p.id} src={imageFor(p)} width={96} height={96} alt="" loading="lazy" />
            ))}
          </div>
        )}
      </div>

      <div className="toolbar">
        <SearchBox value={query.q} onChange={(q) => onQueryChange({ ...query, q })} />
        <div className="sort">
          <label htmlFor="sort-select">Sort by</label>
          <select id="sort-select" value={query.sort} onChange={(e) => onQueryChange({ ...query, sort: e.target.value as SortKey })}>
            {(Object.keys(SORT_LABELS) as SortKey[]).map((key) => (
              <option key={key} value={key}>
                {SORT_LABELS[key]}
              </option>
            ))}
          </select>
        </div>
        <button type="button" className="button filters-toggle" aria-expanded={filtersOpen} aria-controls="filters" onClick={() => setFiltersOpen((o) => !o)}>
          Filters{activeCount > 0 ? ` (${activeCount})` : ''}
        </button>
      </div>

      <div className="listing-body">
        <aside id="filters" className="filters" data-open={filtersOpen} aria-label="Filters">
          <FilterPanel query={query} facets={f} onChange={onQueryChange} />
          {changed && (
            <button type="button" className="link-button" onClick={() => onQueryChange(defaultQuery)}>
              Clear all
            </button>
          )}
        </aside>

        <section aria-label="Products">
          {collectionTitle !== '' && (
            <p className="collection-line">
              <span className="collection-name">{collectionTitle}</span>
              <button type="button" className="link-button" onClick={() => onQueryChange({ ...query, collection: '' })}>
                Show all products
              </button>
            </p>
          )}
          <p className="result-count" role="status">
            {countLabel(shown.length)}
          </p>
          {shown.length === 0 ? (
            <div className="empty">
              <h2>Nothing matches</h2>
              <p>Try a different word, or clear the filters.</p>
              <button type="button" className="button" onClick={() => onQueryChange(defaultQuery)}>
                Clear all filters
              </button>
            </div>
          ) : (
            <ul className="grid" role="list">
              {shown.map((p) => (
                <ProductCard key={p.id} product={p} />
              ))}
            </ul>
          )}
        </section>
      </div>

      {notLoadedCount > 0 && (
        <p className="fineprint">
          {notLoadedCount === 1 ? '1 more product is' : `${notLoadedCount} more products are`} in the store but were not loaded: the theme prints the first 50.
        </p>
      )}
      {rejectedCount > 0 && (
        <p className="fineprint">{rejectedCount === 1 ? '1 product' : `${rejectedCount} products`} could not be loaded.</p>
      )}
    </div>
  );
}
