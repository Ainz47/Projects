import { currencyCodeOf } from '../src/data/source';
import { formatMoney, setCurrency } from '../src/lib/money';

afterEach(() => setCurrency('USD'));

test('prices are in dollars until a store currency is set', () => {
  expect(formatMoney(1650)).toBe('$16.50');
});

test('a store currency changes the symbol, not the number', () => {
  setCurrency('PHP');
  expect(formatMoney(1650)).toBe('₱16.50');
});

test('a missing, malformed or unknown currency code changes nothing', () => {
  for (const bad of [undefined, '', 'php', 'PH', 'PESO', 'ZZZ1']) {
    setCurrency(bad);
    expect(formatMoney(1650)).toBe('$16.50');
  }
});

test('the currency is read from the catalog when the theme provided one', () => {
  expect(currencyCodeOf({ data: { shop: { currencyCode: 'PHP' }, products: { nodes: [] } } })).toBe('PHP');
  expect(currencyCodeOf({ data: { products: { nodes: [] } } })).toBeUndefined();
});
