import { useMemo, useState } from 'react';
import { imageFor } from '../art';
import { formatMoney } from '../lib/money';
import { defaultSelection, isValueAvailable, pickVariant, type Selection } from '../lib/variants';
import { LOW_STOCK_MAX, type Product, type Variant } from '../model/types';
import { NotFound } from './Notices';
import { useCart } from './useCart';

function stockNote(v: Variant | undefined): string {
  if (!v) return 'This combination is not available.';
  if (!v.available) return 'Sold out';
  if (v.inventory <= LOW_STOCK_MAX) return `Only ${v.inventory} left`;
  return 'In stock';
}

function ProductView({ product }: { product: Product }) {
  const cart = useCart();
  const [selection, setSelection] = useState<Selection>(() => defaultSelection(product));
  const [wanted, setWanted] = useState(1);
  const art = useMemo(() => imageFor(product), [product]);

  const variant = pickVariant(product, selection);
  const room = variant && variant.available ? Math.max(0, variant.inventory - cart.qtyOf(variant.id)) : 0;
  // Derived while rendering, so a smaller stock after changing options can never leave a stale number.
  const qty = Math.max(1, Math.min(wanted, room));
  const addLabel = !variant ? 'Unavailable' : !variant.available ? 'Sold out' : room === 0 ? 'All available units are in your cart' : 'Add to cart';
  const meta = [product.vendor, product.origin, product.roast && `${product.roast} roast`].filter(Boolean).join(' · ');

  return (
    <article className="product">
      <p className="crumb">
        <a href="#/">All products</a>
      </p>
      <div className="product-layout">
        <img className="product-art" src={art} alt={`${product.title}, product illustration`} width={400} height={400} />
        <div className="product-info">
          <h1>{product.title}</h1>
          <p className="product-meta">{meta}</p>
          <p className="product-price">{formatMoney(variant?.priceCents ?? product.minCents)}</p>
          <p className="stock" role="status" data-state={!variant || !variant.available ? 'out' : variant.inventory <= LOW_STOCK_MAX ? 'low' : 'ok'}>
            {stockNote(variant)}
          </p>
          <p className="product-desc">{product.description}</p>

          {product.optionNames
            .filter((name) => (product.optionValues[name]?.length ?? 0) > 1)
            .map((name) => (
              <fieldset className="options" key={name}>
                <legend>{name}</legend>
                <div className="chips">
                  {product.optionValues[name]!.map((value) => {
                    const unavailable = !isValueAvailable(product, selection, name, value);
                    return (
                      <label key={value} className="chip" data-unavailable={unavailable || undefined}>
                        <input
                          type="radio"
                          name={`${product.handle}-${name}`}
                          value={value}
                          checked={selection[name] === value}
                          aria-label={unavailable ? `${value} (unavailable)` : undefined}
                          onChange={() => setSelection({ ...selection, [name]: value })}
                        />
                        <span>{value}</span>
                      </label>
                    );
                  })}
                </div>
              </fieldset>
            ))}

          <div className="buy">
            <div className="qty" role="group" aria-label="Quantity">
              <button type="button" aria-label="Decrease quantity" disabled={qty <= 1 || room === 0} onClick={() => setWanted(qty - 1)}>
                &minus;
              </button>
              <span className="qty-value" aria-live="polite">
                {qty}
              </span>
              <button type="button" aria-label="Increase quantity" disabled={qty >= room} onClick={() => setWanted(qty + 1)}>
                +
              </button>
            </div>
            <button
              type="button"
              className="button button-primary"
              disabled={!variant || room === 0}
              onClick={() => {
                if (!variant) return;
                cart.add(product.handle, variant, qty);
                setWanted(1);
              }}
            >
              {addLabel}
            </button>
          </div>
        </div>
      </div>
    </article>
  );
}

export default function ProductPage({ products, handle }: { products: Product[]; handle: string }) {
  const product = products.find((p) => p.handle === handle);
  if (!product) return <NotFound what="That product could not be found." />;
  // Keyed by handle so choices and quantity start fresh on every product.
  return <ProductView key={product.handle} product={product} />;
}
