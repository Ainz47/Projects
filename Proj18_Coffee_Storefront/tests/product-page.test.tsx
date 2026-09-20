import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '../src/App';
import { CART_KEY } from '../src/lib/cart';

const LOW = 'boquete-reserve-panama';
const SOLD_OUT = 'kiambu-aa-kenya';
const SINGLE = 'temperature-kettle-pro';

async function openProduct(handle: string) {
  window.location.hash = `#/product/${handle}`;
  render(<App />);
  return screen.findByRole('heading', { level: 1 });
}

test('opens on the one in-stock variant, with its price and a low-stock note', async () => {
  expect(await openProduct(LOW)).toHaveTextContent('Boquete Reserve Panama');
  expect(screen.getByRole('radio', { name: '250g' })).toBeChecked();
  expect(screen.getByRole('radio', { name: 'Whole bean' })).toBeChecked();
  expect(screen.getByRole('status')).toHaveTextContent('Only 3 left');
  expect(screen.getByText('$34.00')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Add to cart' })).toBeEnabled();
});

test('unavailable values are marked but stay selectable, and a sold-out choice disables Add', async () => {
  const user = userEvent.setup();
  await openProduct(LOW);
  const oneKilo = screen.getByRole('radio', { name: /^1kg/ });
  expect(oneKilo).toHaveAccessibleName('1kg (unavailable)');
  await user.click(oneKilo);
  expect(oneKilo).toBeChecked();
  expect(screen.getByRole('status')).toHaveTextContent('Sold out');
  expect(screen.getByRole('button', { name: 'Sold out' })).toBeDisabled();
  await user.click(screen.getByRole('radio', { name: '250g' }));
  expect(screen.getByRole('button', { name: 'Add to cart' })).toBeEnabled();
});

test('a product with nothing in stock cannot be added', async () => {
  await openProduct(SOLD_OUT);
  expect(screen.getByRole('status')).toHaveTextContent('Sold out');
  expect(screen.getByRole('button', { name: 'Sold out' })).toBeDisabled();
});

test('a single-variant product shows no option picker', async () => {
  await openProduct(SINGLE);
  expect(screen.queryByRole('radio')).not.toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('Only 2 left');
});

test('adding opens the drawer with the line, saves the cart, and Escape returns focus', async () => {
  const user = userEvent.setup();
  await openProduct(LOW);
  const add = screen.getByRole('button', { name: 'Add to cart' });
  await user.click(add);
  const dialog = await screen.findByRole('dialog', { name: 'Your cart' });
  expect(within(dialog).getByRole('link', { name: 'Boquete Reserve Panama' })).toBeInTheDocument();
  expect(within(dialog).getAllByText('$34.00')).toHaveLength(2); // line total and subtotal
  expect(JSON.parse(window.localStorage.getItem(CART_KEY)!)).toEqual([{ variantId: expect.any(String), handle: LOW, qty: 1 }]);
  expect(screen.getByRole('button', { name: 'Cart (1 item)' })).toBeInTheDocument();
  await user.keyboard('{Escape}');
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(add).toHaveFocus();
});

test('quantity stops at stock, and once the cart holds all of it Add is off', async () => {
  const user = userEvent.setup();
  await openProduct(LOW);
  const plus = screen.getByRole('button', { name: 'Increase quantity' });
  await user.click(plus);
  await user.click(plus);
  expect(screen.getByText('3', { selector: '.qty-value' })).toBeInTheDocument();
  expect(plus).toBeDisabled();
  await user.click(screen.getByRole('button', { name: 'Add to cart' }));
  await user.keyboard('{Escape}');
  const add = screen.getByRole('button', { name: 'All available units are in your cart' });
  expect(add).toBeDisabled();
  // The button that opened the drawer is now disabled, so focus falls back to the main region.
  expect(screen.getByRole('main')).toHaveFocus();
});

test('an unknown product shows the not-found view', async () => {
  expect(await openProduct('nope')).toHaveTextContent('Not found');
});
