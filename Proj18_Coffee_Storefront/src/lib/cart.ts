import type { Product } from '../model/types';

export const CART_KEY = 'lantern-cart-v1';
export const FREE_SHIPPING_CENTS = 6000;

export interface CartLine { variantId: string; handle: string; qty: number }

export type CartAction =
  | { type: 'add'; variantId: string; handle: string; qty: number; max: number }
  | { type: 'set'; variantId: string; qty: number; max: number }
  | { type: 'remove'; variantId: string }
  | { type: 'clear' }
  | { type: 'replace'; lines: CartLine[] };

export function cartReducer(lines: CartLine[], a: CartAction): CartLine[] {
  switch (a.type) {
    case 'add': {
      if (a.max <= 0 || a.qty <= 0) return lines;
      const existing = lines.find((l) => l.variantId === a.variantId);
      if (!existing) return [...lines, { variantId: a.variantId, handle: a.handle, qty: Math.min(a.qty, a.max) }];
      return lines.map((l) => (l.variantId === a.variantId ? { ...l, qty: Math.min(l.qty + a.qty, a.max) } : l));
    }
    case 'set':
      if (a.qty <= 0) return lines.filter((l) => l.variantId !== a.variantId);
      return lines.map((l) => (l.variantId === a.variantId ? { ...l, qty: Math.min(a.qty, a.max) } : l));
    case 'remove':
      return lines.filter((l) => l.variantId !== a.variantId);
    case 'clear':
      return [];
    case 'replace':
      return a.lines;
  }
}

export function reconcile(lines: CartLine[], products: Product[]): CartLine[] {
  const out: CartLine[] = [];
  for (const line of lines) {
    const variant = products.find((p) => p.handle === line.handle)?.variants.find((v) => v.id === line.variantId);
    if (!variant || !variant.available) continue;
    out.push({ ...line, qty: Math.min(line.qty, variant.inventory) });
  }
  return out;
}

export interface DetailedLine {
  variantId: string; handle: string; productTitle: string; variantTitle: string;
  unitCents: number; qty: number; max: number; lineCents: number;
}

export function cartDetail(lines: CartLine[], products: Product[]) {
  const detailed: DetailedLine[] = [];
  for (const line of lines) {
    const product = products.find((p) => p.handle === line.handle);
    const variant = product?.variants.find((v) => v.id === line.variantId);
    if (!product || !variant) continue;
    detailed.push({
      variantId: line.variantId, handle: line.handle, productTitle: product.title, variantTitle: variant.title,
      unitCents: variant.priceCents, qty: line.qty, max: variant.inventory, lineCents: variant.priceCents * line.qty,
    });
  }
  return {
    lines: detailed,
    count: detailed.reduce((n, l) => n + l.qty, 0),
    subtotalCents: detailed.reduce((n, l) => n + l.lineCents, 0),
  };
}

export function shippingProgress(subtotalCents: number) {
  return {
    remainingCents: Math.max(0, FREE_SHIPPING_CENTS - subtotalCents),
    ratio: Math.min(1, subtotalCents / FREE_SHIPPING_CENTS),
  };
}

const isLine = (x: unknown): x is CartLine => {
  const l = x as CartLine;
  return !!l && typeof l.variantId === 'string' && typeof l.handle === 'string' && Number.isInteger(l.qty) && l.qty > 0;
};

// The getter runs inside the try: reading window.localStorage throws when site data is blocked.
export function loadLines(getStorage: () => Pick<Storage, 'getItem'> = () => window.localStorage): CartLine[] {
  try {
    const parsed = JSON.parse(getStorage().getItem(CART_KEY) ?? '[]');
    return Array.isArray(parsed) && parsed.every(isLine) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveLines(lines: CartLine[], getStorage: () => Pick<Storage, 'setItem'> = () => window.localStorage): boolean {
  try {
    getStorage().setItem(CART_KEY, JSON.stringify(lines));
    return true;
  } catch {
    return false;
  }
}
