export const LOW_STOCK_MAX = 5;

export interface Variant {
  id: string;
  title: string;
  sku: string;
  priceCents: number;
  inventory: number;
  available: boolean;
  options: Record<string, string>;
}

export interface Product {
  id: string;
  handle: string;
  title: string;
  vendor: string;
  type: string;
  tags: string[];
  description: string;
  origin: string | null;
  roast: string | null;
  optionNames: string[];
  optionValues: Record<string, string[]>;
  variants: Variant[];
  minCents: number;
  maxCents: number;
  available: boolean;
  lowStock: boolean;
}

export interface Rejected {
  index: number;
  handle: string | null;
  reason: string;
}

export interface NormalizeResult {
  products: Product[];
  rejected: Rejected[];
}
