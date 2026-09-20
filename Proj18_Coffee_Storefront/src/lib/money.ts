import type { Product } from '../model/types';

let fmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

// Inside a Shopify theme the store's own currency replaces the default, so the page shows the amount checkout will
// charge. A missing or unknown code changes nothing.
export function setCurrency(code: string | undefined): void {
  if (!code || !/^[A-Z]{3}$/.test(code)) return;
  try {
    fmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: code });
  } catch {
    // an unknown code keeps the current format
  }
}

export const formatMoney = (cents: number): string => fmt.format(cents / 100);

export const priceLabel = (p: Product): string =>
  p.minCents === p.maxCents ? formatMoney(p.minCents) : `From ${formatMoney(p.minCents)}`;
