import { useMemo, useSyncExternalStore } from 'react';
import { parseQuery, serializeQuery, type Query } from '../lib/catalog';

export type Route =
  | { name: 'list'; query: Query }
  | { name: 'product'; handle: string }
  | { name: 'notfound' };

export function parseHash(hash: string): Route {
  const raw = hash.startsWith('#') ? hash.slice(1) : hash;
  const cut = raw.indexOf('?');
  const path = cut === -1 ? raw : raw.slice(0, cut);
  const search = cut === -1 ? '' : raw.slice(cut + 1);
  if (path === '' || path === '/') return { name: 'list', query: parseQuery(search) };
  const match = /^\/product\/([^/]+)$/.exec(path);
  if (match) {
    try {
      return { name: 'product', handle: decodeURIComponent(match[1]!) };
    } catch {
      return { name: 'notfound' };
    }
  }
  return { name: 'notfound' };
}

export const listHref = (q: Query): string => {
  const s = serializeQuery(q);
  return s ? `#/?${s}` : '#/';
};

export const productHref = (handle: string): string => `#/product/${encodeURIComponent(handle)}`;

function subscribe(onChange: () => void): () => void {
  window.addEventListener('hashchange', onChange);
  return () => window.removeEventListener('hashchange', onChange);
}

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash, () => '');
  return useMemo(() => parseHash(hash), [hash]);
}

// Filters and search change on every click or keystroke, so they replace the history entry instead of
// stacking hundreds of back-button stops. replaceState fires no hashchange, so send one ourselves.
export function replaceHash(href: string): void {
  try {
    window.history.replaceState(null, '', href);
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  } catch {
    window.location.replace(href);
  }
}
