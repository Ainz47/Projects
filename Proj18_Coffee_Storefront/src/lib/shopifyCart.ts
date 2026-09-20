// Inside a Shopify theme the drawer's Checkout button hands the cart to Shopify: it fills Shopify's own cart with the
// same variants and quantities, then opens Shopify's checkout. The cart the shopper edits stays the app's own.
export interface HandOffLine {
  variantId: string;
  qty: number;
}

interface Deps {
  fetchImpl?: typeof fetch;
  navigate?: (url: string) => void;
}

// Shopify variant ids are numbers; the app keeps them as text, sometimes as a global id (gid://shopify/ProductVariant/1).
export function numericVariantId(id: string): number | null {
  const tail = id.split('/').pop() ?? '';
  return /^\d+$/.test(tail) ? Number(tail) : null;
}

const post = (fetchImpl: typeof fetch, url: string, body?: unknown) =>
  fetchImpl(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });

export async function handOffToShopify(
  lines: HandOffLine[],
  { fetchImpl = fetch, navigate = (url) => window.location.assign(url) }: Deps = {},
): Promise<void> {
  if (lines.length === 0) throw new Error('Your cart is empty.');
  const items = lines.map((l) => ({ id: numericVariantId(l.variantId), quantity: l.qty }));
  if (items.some((i) => i.id === null)) throw new Error('This cart holds an item that is not a Shopify variant, so it cannot be checked out.');

  await post(fetchImpl, '/cart/clear.js');
  const res = await post(fetchImpl, '/cart/add.js', { items });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { description?: string };
    throw new Error(body.description || 'Shopify could not add these items to its cart. Try again in a moment.');
  }
  navigate('/checkout');
}
