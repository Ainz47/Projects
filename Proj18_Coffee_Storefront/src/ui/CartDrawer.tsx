import { useEffect, useMemo, useRef, type KeyboardEvent } from 'react';
import { artDataUri } from '../art';
import { shippingProgress, type DetailedLine } from '../lib/cart';
import { formatMoney } from '../lib/money';
import type { Product } from '../model/types';
import { productHref } from './router';
import { useCart } from './useCart';

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

function ShippingBar({ subtotalCents }: { subtotalCents: number }) {
  const { remainingCents, ratio } = shippingProgress(subtotalCents);
  return (
    <div className="shipping">
      <p>{remainingCents === 0 ? 'You have free shipping.' : `${formatMoney(remainingCents)} away from free shipping.`}</p>
      <progress max={100} value={Math.round(ratio * 100)} aria-label="Progress toward free shipping" />
    </div>
  );
}

function CartLineItem({ line, product }: { line: DetailedLine; product: Product | undefined }) {
  const { setQty, remove, close } = useCart();
  const src = useMemo(() => (product ? artDataUri(product) : ''), [product]);
  // Shopify names the only variant of an option-less product "Default Title"; do not show that to shoppers.
  const variantLabel = line.variantTitle === 'Default Title' ? '' : line.variantTitle;
  const name = [line.productTitle, variantLabel].filter(Boolean).join(', ');
  return (
    <li className="cart-line">
      {product && <img src={src} alt="" width={64} height={64} />}
      <div className="cart-line-main">
        <a href={productHref(line.handle)} onClick={close}>
          {line.productTitle}
        </a>
        {variantLabel && <p className="cart-line-variant">{variantLabel}</p>}
        <div className="qty" role="group" aria-label={`Quantity of ${name}`}>
          <button type="button" aria-label={`Decrease quantity of ${name}`} onClick={() => setQty(line.variantId, line.qty - 1, line.max)}>
            &minus;
          </button>
          <span className="qty-value">{line.qty}</span>
          <button type="button" aria-label={`Increase quantity of ${name}`} disabled={line.qty >= line.max} onClick={() => setQty(line.variantId, line.qty + 1, line.max)}>
            +
          </button>
        </div>
        <button type="button" className="link-button" aria-label={`Remove ${name}`} onClick={() => remove(line.variantId)}>
          Remove
        </button>
      </div>
      <p className="cart-line-total">{formatMoney(line.lineCents)}</p>
    </li>
  );
}

function DrawerPanel({ products }: { products: Product[] }) {
  const { detail, close, clear, storageOk, getOpener } = useCart();
  const panelRef = useRef<HTMLDivElement>(null);
  const byHandle = useMemo(() => new Map(products.map((p) => [p.handle, p])), [products]);

  // Focus goes in on open and back to whatever opened the drawer on close. If that button is now
  // disabled (the cart holds all the stock), gone, or was never focused (Safari does not focus a
  // clicked button), land on the main region rather than the top of the page.
  useEffect(() => {
    panelRef.current?.querySelector<HTMLElement>('[data-autofocus]')?.focus();
    return () => {
      const opener = getOpener();
      opener?.focus();
      if (!opener || document.activeElement !== opener) document.getElementById('main-content')?.focus();
    };
  }, [getOpener]);

  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [close]);

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, []);

  function trapTab(e: KeyboardEvent) {
    if (e.key !== 'Tab') return;
    const items = [...(panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])];
    const first = items[0];
    const last = items[items.length - 1];
    if (!first || !last) return;
    const active = document.activeElement;
    if (!panelRef.current?.contains(active)) {
      e.preventDefault();
      first.focus();
    } else if (e.shiftKey && active === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && active === last) {
      e.preventDefault();
      first.focus();
    }
  }

  return (
    <div className="drawer-root">
      <div className="drawer-backdrop" aria-hidden="true" onClick={close} />
      <div className="drawer" role="dialog" aria-modal="true" aria-labelledby="cart-title" ref={panelRef} onKeyDown={trapTab}>
        <div className="drawer-head">
          <h2 id="cart-title">Your cart</h2>
          <button type="button" className="icon-button" data-autofocus aria-label="Close cart" onClick={close}>
            &times;
          </button>
        </div>

        {detail.lines.length === 0 ? (
          <div className="drawer-empty">
            <p>Your cart is empty.</p>
            <button type="button" className="button" onClick={close}>
              Keep browsing
            </button>
          </div>
        ) : (
          <>
            <ShippingBar subtotalCents={detail.subtotalCents} />
            <ul className="cart-lines" role="list">
              {detail.lines.map((line) => (
                <CartLineItem key={line.variantId} line={line} product={byHandle.get(line.handle)} />
              ))}
            </ul>
            <div className="drawer-foot">
              <p className="subtotal" aria-live="polite">
                <span>Subtotal</span> <strong>{formatMoney(detail.subtotalCents)}</strong>
              </p>
              {!storageOk && <p className="hint">Your cart could not be saved on this device, so it will be empty after a reload.</p>}
              <button type="button" className="button button-primary" disabled>
                Checkout (demo, not available)
              </button>
              <p className="hint">This is a demo store. There is no checkout and nothing is sold.</p>
              <button type="button" className="link-button" onClick={clear}>
                Clear cart
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function CartDrawer({ products }: { products: Product[] }) {
  const { isOpen } = useCart();
  return isOpen ? <DrawerPanel products={products} /> : null;
}
