import { LOW_STOCK_MAX, type NormalizeResult, type Product, type Rejected, type Variant } from './types';

type Raw = Record<string, any>;
const HANDLE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() !== '' ? v.trim() : null);

function toCents(price: unknown): number | null {
  if (typeof price !== 'string' || !/^\d+(?:\.\d{1,2})?$/.test(price)) return null;
  return Math.round(parseFloat(price) * 100);
}

// A product picture is only trusted when it is an https url; anything else falls back to the generated art.
function httpsUrl(v: unknown): string | null {
  const s = str(v);
  if (s === null) return null;
  // Shopify's image urls are protocol-relative (//store.myshopify.com/cdn/...), and the page is served over https.
  const url = s.startsWith('//') ? `https:${s}` : s;
  return /^https:\/\//i.test(url) ? url : null;
}

function meta(node: Raw, key: string): string | null {
  const nodes: Raw[] = Array.isArray(node.metafields?.nodes) ? node.metafields.nodes : [];
  const hit = nodes.find((m) => m?.namespace === 'custom' && m?.key === key);
  return str(hit?.value);
}

function toVariant(raw: Raw): Variant | string {
  const id = str(raw?.id);
  if (!id) return 'variant missing id';
  const priceCents = toCents(raw.price);
  if (priceCents === null) return `variant ${id} has an invalid price`;
  const inv = raw.inventoryQuantity;
  if (!Number.isInteger(inv) || inv < 0) return `variant ${id} has no usable inventory count`;
  const selected: Raw[] = Array.isArray(raw.selectedOptions) ? raw.selectedOptions : [];
  const options: Record<string, string> = {};
  for (const o of selected) {
    const name = str(o?.name);
    const value = str(o?.value);
    if (name && value) options[name] = value;
  }
  return {
    id,
    title: str(raw.title) ?? id,
    sku: typeof raw.sku === 'string' ? raw.sku : '',
    priceCents,
    inventory: inv,
    available: inv > 0,
    options,
  };
}

function toProduct(raw: Raw): Product | string {
  const id = str(raw.id);
  if (!id) return 'missing id';
  const title = str(raw.title);
  if (!title) return 'missing title';
  const handle = str(raw.handle);
  if (!handle || !HANDLE.test(handle)) return 'invalid handle';

  const rawVariants: Raw[] = Array.isArray(raw.variants?.nodes) ? raw.variants.nodes : [];
  if (rawVariants.length === 0) return 'no variants';
  const variants: Variant[] = [];
  for (const rv of rawVariants) {
    const v = toVariant(rv);
    if (typeof v === 'string') return v;
    variants.push(v);
  }

  const rawOptions: Raw[] = Array.isArray(raw.options) ? raw.options : [];
  const optionNames = rawOptions.map((o) => str(o?.name)).filter((n): n is string => n !== null);
  const optionValues: Record<string, string[]> = {};
  for (const o of rawOptions) {
    const name = str(o?.name);
    if (name) optionValues[name] = (Array.isArray(o.values) ? o.values : []).map(str).filter((v): v is string => v !== null);
  }

  const prices = variants.map((v) => v.priceCents);
  return {
    id,
    handle,
    title,
    vendor: str(raw.vendor) ?? '',
    type: str(raw.productType) ?? 'Other',
    tags: (Array.isArray(raw.tags) ? raw.tags : []).map(str).filter((t): t is string => t !== null),
    description: str(raw.description) ?? '',
    image: httpsUrl(raw.image),
    origin: meta(raw, 'origin'),
    roast: meta(raw, 'roast'),
    optionNames,
    optionValues,
    variants,
    minCents: Math.min(...prices),
    maxCents: Math.max(...prices),
    available: variants.some((v) => v.available),
    lowStock: variants.some((v) => v.inventory > 0 && v.inventory <= LOW_STOCK_MAX),
  };
}

export function normalizeProducts(nodes: unknown[]): NormalizeResult {
  const products: Product[] = [];
  const rejected: Rejected[] = [];
  const seen = new Set<string>();
  nodes.forEach((raw, index) => {
    if (raw === null || typeof raw !== 'object') {
      rejected.push({ index, handle: null, reason: 'not an object' });
      return;
    }
    const handle = str((raw as Raw).handle);
    const result = toProduct(raw as Raw);
    if (typeof result === 'string') {
      rejected.push({ index, handle, reason: result });
    } else if (seen.has(result.handle)) {
      rejected.push({ index, handle: result.handle, reason: 'duplicate handle' });
    } else {
      seen.add(result.handle);
      products.push(result);
    }
  });
  return { products, rejected };
}
