import { useEffect, useMemo, useRef } from 'react';
import { resolveCatalog } from './data/state';
import type { Query } from './lib/catalog';
import type { Product } from './model/types';
import { Header } from './ui/Header';
import { ListingPage } from './ui/ListingPage';
import { ErrorScreen, NotFound } from './ui/Notices';
import { listHref, replaceHash, useRoute } from './ui/router';

const focusMain = () => document.getElementById('main-content')?.focus();

function Store({ products, rejectedCount }: { products: Product[]; rejectedCount: number }) {
  const route = useRoute();

  // A hash route is not a page load, so the browser will not move focus or scroll for us.
  const routeKey = route.name === 'product' ? `product:${route.handle}` : route.name;
  const shownKey = useRef(routeKey);
  useEffect(() => {
    if (shownKey.current === routeKey) return;
    shownKey.current = routeKey;
    window.scrollTo(0, 0);
    focusMain();
  }, [routeKey]);

  const page =
    route.name === 'list' ? (
      <ListingPage
        products={products}
        query={route.query}
        rejectedCount={rejectedCount}
        onQueryChange={(q: Query) => replaceHash(listHref(q))}
      />
    ) : (
      <NotFound what="That page does not exist." />
    );

  return (
    <>
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
  return <Store products={catalog.products} rejectedCount={catalog.rejectedCount} />;
}
