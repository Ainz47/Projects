import type { Product } from '../model/types';

const fmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

export const formatMoney = (cents: number): string => fmt.format(cents / 100);

export const priceLabel = (p: Product): string =>
  p.minCents === p.maxCents ? formatMoney(p.minCents) : `From ${formatMoney(p.minCents)}`;
