import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState, type ReactNode } from 'react';
import { cartDetail, cartReducer, loadLines, reconcile, saveLines } from '../lib/cart';
import type { Product, Variant } from '../model/types';

interface CartApi {
  detail: ReturnType<typeof cartDetail>;
  qtyOf: (variantId: string) => number;
  isOpen: boolean;
  storageOk: boolean;
  open: () => void;
  close: () => void;
  getOpener: () => HTMLElement | null;
  add: (handle: string, variant: Variant, qty: number) => void;
  setQty: (variantId: string, qty: number, max: number) => void;
  remove: (variantId: string) => void;
  clear: () => void;
}

const CartContext = createContext<CartApi | null>(null);

// Read in the click handler, before the page behind the drawer goes inert: a browser may blur a
// focused element the moment it becomes inert, so reading it later (in an effect) can find <body>.
const activeElementOrNull = (): HTMLElement | null => {
  const el = document.activeElement;
  return el instanceof HTMLElement && el !== document.body ? el : null;
};

export function CartProvider({ products, children }: { products: Product[]; children: ReactNode }) {
  // Saved lines are checked against today's catalog before the first render uses them.
  const [lines, dispatch] = useReducer(cartReducer, products, (ps) => reconcile(loadLines(), ps));
  const [isOpen, setOpen] = useState(false);
  const [storageOk, setStorageOk] = useState(true);
  const opener = useRef<HTMLElement | null>(null);

  useEffect(() => {
    setStorageOk(saveLines(lines));
  }, [lines]);

  const detail = useMemo(() => cartDetail(lines, products), [lines, products]);
  const qtyOf = useCallback((variantId: string) => lines.find((l) => l.variantId === variantId)?.qty ?? 0, [lines]);
  const open = useCallback(() => {
    opener.current = activeElementOrNull();
    setOpen(true);
  }, []);
  const close = useCallback(() => setOpen(false), []);
  const getOpener = useCallback(() => opener.current, []);
  const add = useCallback((handle: string, variant: Variant, qty: number) => {
    dispatch({ type: 'add', variantId: variant.id, handle, qty, max: variant.inventory });
    opener.current = activeElementOrNull();
    setOpen(true);
  }, []);
  const setQty = useCallback((variantId: string, qty: number, max: number) => dispatch({ type: 'set', variantId, qty, max }), []);
  const remove = useCallback((variantId: string) => dispatch({ type: 'remove', variantId }), []);
  const clear = useCallback(() => dispatch({ type: 'clear' }), []);

  const value = useMemo<CartApi>(
    () => ({ detail, qtyOf, isOpen, storageOk, open, close, getOpener, add, setQty, remove, clear }),
    [detail, qtyOf, isOpen, storageOk, open, close, getOpener, add, setQty, remove, clear],
  );
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartApi {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error('useCart must be used inside CartProvider');
  return ctx;
}
