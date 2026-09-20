import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '../src/App';
import { loadCatalog } from '../src/data/source';
import { applyQuery, defaultQuery, type Query } from '../src/lib/catalog';

const { products } = loadCatalog();
const count = (n: number) => (n === 1 ? '1 product' : `${n} products`);

function renderAt(hash = '') {
  window.location.hash = hash;
  return render(<App />);
}

test('lists every product and announces the count', () => {
  renderAt();
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Lantern Roasters');
  expect(screen.getByRole('status')).toHaveTextContent(count(products.length));
  expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(products.length);
});

test('typing in search narrows the list, keeps the text and writes the URL', async () => {
  const user = userEvent.setup();
  renderAt();
  const box = screen.getByRole('searchbox', { name: /search products/i });
  await user.type(box, 'kenya');
  const expected = applyQuery(products, { ...defaultQuery, q: 'kenya' });
  expect(expected.length).toBeGreaterThan(0);
  expect(box).toHaveValue('kenya');
  expect(screen.getByRole('status')).toHaveTextContent(count(expected.length));
  expect(window.location.hash).toBe('#/?q=kenya');
});

test('filter checkboxes update the list and the URL', async () => {
  const user = userEvent.setup();
  renderAt();
  await user.click(screen.getByRole('checkbox', { name: 'Kenya' }));
  const expected = applyQuery(products, { ...defaultQuery, origins: ['Kenya'] });
  expect(screen.getByRole('status')).toHaveTextContent(count(expected.length));
  expect(window.location.hash).toBe('#/?origin=Kenya');
  await user.click(screen.getByRole('checkbox', { name: 'In stock only' }));
  expect(window.location.hash).toBe('#/?origin=Kenya&stock=1');
});

test('a shared URL restores the search text, sort and filters', () => {
  const q: Query = { ...defaultQuery, q: 'light', sort: 'price-asc', inStockOnly: true };
  renderAt('#/?q=light&sort=price-asc&stock=1');
  expect(screen.getByRole('searchbox', { name: /search products/i })).toHaveValue('light');
  expect(screen.getByRole('combobox', { name: /sort by/i })).toHaveValue('price-asc');
  expect(screen.getByRole('checkbox', { name: 'In stock only' })).toBeChecked();
  expect(screen.getAllByRole('heading', { level: 2 })[0]).toHaveTextContent(applyQuery(products, q)[0]!.title);
});

test('no matches shows the empty state, and clearing brings everything back', async () => {
  const user = userEvent.setup();
  renderAt();
  const box = screen.getByRole('searchbox', { name: /search products/i });
  await user.type(box, 'zzzz');
  const region = screen.getByRole('region', { name: 'Products' });
  expect(within(region).getByText('Nothing matches')).toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('0 products');
  await user.click(within(region).getByRole('button', { name: /clear all filters/i }));
  expect(screen.getByRole('status')).toHaveTextContent(count(products.length));
  expect(box).toHaveValue('');
});

test('cards flag sold-out and low-stock products', () => {
  renderAt();
  expect(screen.getAllByText('Sold out')).toHaveLength(products.filter((p) => !p.available).length);
  expect(screen.getAllByText('Low stock')).toHaveLength(products.filter((p) => p.available && p.lowStock).length);
});

test('the price field takes digits only and ignores anything else', async () => {
  const user = userEvent.setup();
  renderAt();
  const min = screen.getByRole('textbox', { name: /min price/i });
  await user.type(min, '25');
  expect(window.location.hash).toBe('#/?min=25');
  await user.type(min, 'x');
  expect(min).toHaveValue('25');
  expect(window.location.hash).toBe('#/?min=25');
});

test('an unknown route shows the not-found view with a way back', () => {
  renderAt('#/nope');
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Not found');
  expect(screen.getByRole('link', { name: /back to all products/i })).toHaveAttribute('href', '#/');
});

test('moving to another page moves focus to the main region', async () => {
  renderAt();
  window.location.hash = '#/nope';
  await waitFor(() => expect(screen.getByRole('main')).toHaveFocus());
});
