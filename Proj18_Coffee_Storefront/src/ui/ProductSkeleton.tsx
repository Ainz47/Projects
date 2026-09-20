// Suspense fallback for the lazy-loaded product page. Static placeholder blocks, not a spinner or
// a shimmer: this app's motion rules are one-shot only (see motion.css), nothing loops, so the
// shape alone (not movement) is what tells the shopper a product is on its way.
export function ProductSkeleton() {
  return (
    <div className="product-skeleton">
      <p className="sr-only" role="status">
        Loading product…
      </p>
      <div className="product-layout" aria-hidden="true">
        <div className="skeleton skeleton-art" />
        <div className="product-info">
          <div className="skeleton skeleton-line skeleton-line-title" />
          <div className="skeleton skeleton-line skeleton-line-meta" />
          <div className="skeleton skeleton-line skeleton-line-price" />
          <div className="skeleton skeleton-line" />
          <div className="skeleton skeleton-line skeleton-line-short" />
        </div>
      </div>
    </div>
  );
}
