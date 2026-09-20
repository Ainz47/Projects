import { useCart } from './useCart';

export function Header() {
  const { detail, open, isOpen } = useCart();
  return (
    <header className="site-header">
      <a className="brand" href="#/">
        Lantern Roasters <span className="brand-tag">demo</span>
      </a>
      {/* An explicit label, not a visually hidden span: engines differ on the space before an inline child. */}
      <button
        type="button"
        className="cart-button"
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        aria-label={`Cart (${detail.count === 1 ? '1 item' : `${detail.count} items`})`}
        onClick={open}
      >
        Cart
        <span className="cart-count" aria-hidden="true">
          {detail.count}
        </span>
      </button>
    </header>
  );
}
