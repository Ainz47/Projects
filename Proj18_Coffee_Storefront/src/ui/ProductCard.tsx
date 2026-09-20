import { useMemo } from 'react';
import { imageFor } from '../art';
import { priceLabel } from '../lib/money';
import type { Product } from '../model/types';
import { productHref } from './router';

export function ProductCard({ product }: { product: Product }) {
  const src = useMemo(() => imageFor(product), [product]);
  const meta = product.origin && product.roast ? `${product.origin} · ${product.roast} roast` : product.type;
  return (
    <li className="card" data-unavailable={!product.available || undefined}>
      <img className="card-art" src={src} alt="" width={400} height={400} loading="lazy" decoding="async" />
      <div className="card-body">
        <h2 className="card-title">
          <a href={productHref(product.handle)}>{product.title}</a>
        </h2>
        <p className="card-meta">{meta}</p>
        <p className="card-price">{priceLabel(product)}</p>
        {!product.available ? (
          <p className="badge badge-out">Sold out</p>
        ) : product.lowStock ? (
          <p className="badge badge-low">Low stock</p>
        ) : null}
      </div>
    </li>
  );
}
