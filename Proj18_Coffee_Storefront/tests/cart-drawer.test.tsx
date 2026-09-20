import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '../src/App';
import { loadCatalog } from '../src/data/source';
import { CART_KEY, type CartLine } from '../src/lib/cart';

const { products } = loadCatalog();
const boquete = products.find((p) => p.handle === 'boquete-reserve-panama')!;
const inStock = boquete.variants.find((v) => v.available)!; // 250g / Whole bean, 3 left, $34.00

const seed = (lines: CartLine[]) => window.localStorage.setItem(CART_KEY, JSON.stringify(lines));
const seedOne = (qty: number) => seed([{ variantId: inStock.id, handle: boquete.handle, qty }]);

async function openDrawer() {
  const user = userEvent.setup();
  window.location.hash = '#/';
  render(<App />);
  await user.click(screen.getByRole('button', { name: /^cart/i }));
  return { user, dialog: await screen.findByRole('dialog', { name: 'Your cart' }) };
}

afterEach(() => vi.restoreAllMocks());

test('restores a saved cart, drops variants that are gone and clamps to stock', () => {
  seed([
    { variantId: inStock.id, handle: boquete.handle, qty: 9 },
    { variantId: 'gid://shopify/ProductVariant/gone', handle: boquete.handle, qty: 1 },
  ]);
  window.location.hash = '#/';
  render(<App />);
  expect(screen.getByRole('button', { name: 'Cart (3 items)' })).toBeInTheDocument();
  expect(JSON.parse(window.localStorage.getItem(CART_KEY)!)).toEqual([{ variantId: inStock.id, handle: boquete.handle, qty: 3 }]);
});

test('steppers stop at stock, Remove works and an empty cart says so', async () => {
  seedOne(2);
  const { user, dialog } = await openDrawer();
  const plus = within(dialog).getByRole('button', { name: /increase quantity of boquete/i });
  await user.click(plus);
  expect(within(dialog).getByText('3', { selector: '.qty-value' })).toBeInTheDocument();
  expect(plus).toBeDisabled();
  await user.click(within(dialog).getByRole('button', { name: /remove boquete/i }));
  expect(within(dialog).getByText('Your cart is empty.')).toBeInTheDocument();
  await user.click(within(dialog).getByRole('button', { name: 'Keep browsing' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('the free-shipping bar follows the subtotal', async () => {
  seedOne(1); // $34.00 of $60.00
  const { user, dialog } = await openDrawer();
  expect(within(dialog).getByText('$26.00 away from free shipping.')).toBeInTheDocument();
  expect(within(dialog).getByRole('progressbar', { name: /free shipping/i })).toHaveAttribute('value', '57');
  await user.click(within(dialog).getByRole('button', { name: /increase quantity of boquete/i }));
  expect(within(dialog).getByText('You have free shipping.')).toBeInTheDocument();
  expect(within(dialog).getByRole('progressbar', { name: /free shipping/i })).toHaveAttribute('value', '100');
});

test('checkout is a disabled demo button', async () => {
  seedOne(1);
  const { dialog } = await openDrawer();
  expect(within(dialog).getByRole('button', { name: /checkout/i })).toBeDisabled();
  expect(within(dialog).getByText(/this is a demo store/i)).toBeInTheDocument();
});

test('Tab wraps around inside the drawer in both directions', async () => {
  seedOne(1);
  const { user, dialog } = await openDrawer();
  expect(within(dialog).getByRole('button', { name: 'Close cart' })).toHaveFocus();
  await user.tab({ shift: true });
  expect(within(dialog).getByRole('button', { name: 'Clear cart' })).toHaveFocus();
  await user.tab();
  expect(within(dialog).getByRole('button', { name: 'Close cart' })).toHaveFocus();
});

test('closing the drawer puts focus back on the cart button', async () => {
  seedOne(1);
  const { user, dialog } = await openDrawer();
  await user.click(within(dialog).getByRole('button', { name: 'Close cart' }));
  expect(screen.getByRole('button', { name: /^cart/i })).toHaveFocus();
});

test('a product link in the drawer closes it and opens the product', async () => {
  seedOne(1);
  const { user, dialog } = await openDrawer();
  await user.click(within(dialog).getByRole('link', { name: 'Boquete Reserve Panama' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(await screen.findByRole('heading', { level: 1, name: /boquete reserve/i })).toBeInTheDocument();
});

test('the store still works when site data is blocked, and says the cart will not be kept', async () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
  const user = userEvent.setup();
  window.location.hash = `#/product/${boquete.handle}`;
  render(<App />);
  await user.click(await screen.findByRole('button', { name: 'Add to cart' }));
  const dialog = await screen.findByRole('dialog', { name: 'Your cart' });
  expect(within(dialog).getByRole('link', { name: 'Boquete Reserve Panama' })).toBeInTheDocument();
  expect(within(dialog).getByText(/could not be saved on this device/i)).toBeInTheDocument();
});
