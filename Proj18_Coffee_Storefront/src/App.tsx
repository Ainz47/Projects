import { lazy, Suspense, useEffect, useMemo, useRef, type ReactNode } from 'react';
import { resolveCatalog } from './data/state';
import type { Query } from './lib/catalog';
import type { Product } from './model/types';
import { CartDrawer } from './ui/CartDrawer';
import { Header } from './ui/Header';
import { ListingPage } from './ui/ListingPage';
import { ErrorScreen, NotFound } from './ui/Notices';
import { ProductSkeleton } from './ui/ProductSkeleton';
import { listHref, replaceHash, useRoute } from './ui/router';
import { CartProvider, useCart } from './ui/useCart';

// The product route is its own chunk: the listing is the first thing most visitors see.
const ProductPage = lazy(() => import('./ui/ProductPage'));

const STORE = 'Lantern Roasters (demo)';
const focusMain = () => document.getElementById('main-content')?.focus();

function Store({ products, rejectedCount, notLoadedCount }: { products: Product[]; rejectedCount: number; notLoadedCount: number }) {
  const route = useRoute();
  const { isOpen } = useCart();

  // A hash route is not a page load, so the browser will not move focus or scroll for us.
  const routeKey = route.name === 'product' ? `product:${route.handle}` : route.name;
  const shownKey = useRef(routeKey);
  useEffect(() => {
    if (shownKey.current === routeKey) return;
    shownKey.current = routeKey;
    window.scrollTo(0, 0);
    focusMain();
  }, [routeKey]);

  const product = route.name === 'product' ? products.find((p) => p.handle === route.handle) : undefined;
  useEffect(() => {
    document.title = product ? `${product.title} | ${STORE}` : STORE;
  }, [product]);

  let page: ReactNode;
  if (route.name === 'list') {
    page = (
      <ListingPage
        products={products}
        query={route.query}
        rejectedCount={rejectedCount}
        notLoadedCount={notLoadedCount}
        onQueryChange={(q: Query) => replaceHash(listHref(q))}
      />
    );
  } else if (route.name === 'product') {
    page = (
      <Suspense fallback={<ProductSkeleton />}>
        <ProductPage products={products} handle={route.handle} />
      </Suspense>
    );
  } else {
    page = <NotFound what="That page does not exist." />;
  }

  return (
    <>
      <div className="shell" inert={isOpen}>
        {/* A plain "#main" link would replace the route, so the skip link focuses main instead. */}
        <a
          className="skip-link"
          href="#main-content"
          onClick={(e) => {
            e.preventDefault();
            focusMain();
          }}
        >
          Skip to content
        </a>
        <Header />
        <main id="main-content" tabIndex={-1}>
          {page}
        </main>
        <footer className="site-footer">
          <p>Lantern Roasters (demo) is a made-up store for a portfolio project. Nothing here is for sale.</p>
        </footer>
      </div>
      <CartDrawer products={products} />
    </>
  );
}

export default function App() {
  const catalog = useMemo(() => resolveCatalog(), []);
  if (!catalog.ok) {
    return (
      <main id="main-content" tabIndex={-1}>
        <ErrorScreen title="The store could not load" detail={catalog.reason} />
      </main>
    );
  }
  return (
    <CartProvider products={catalog.products}>
      <Store products={catalog.products} rejectedCount={catalog.rejectedCount} notLoadedCount={catalog.notLoadedCount} />
    </CartProvider>
  );
}
