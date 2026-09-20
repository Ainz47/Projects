import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const theme = (p: string) => resolve(process.cwd(), 'theme', p);
const read = (p: string) => readFileSync(theme(p), 'utf8');

test('the layout has the two things Shopify requires of every theme, and loads the built stylesheet', () => {
  const layout = read('layout/theme.liquid');
  expect(layout).toMatch(/\{\{\s*content_for_header\s*\}\}/);
  expect(layout).toMatch(/\{\{\s*content_for_layout\s*\}\}/);
  expect(layout).toMatch(/'coffee-storefront\.css'\s*\|\s*asset_url/);
});

test('the app snippet mounts the root element, injects the catalog, and loads the built script as a module', () => {
  const app = read('snippets/storefront-app.liquid');
  expect(app).toMatch(/id="root"/);
  expect(app).toMatch(/render 'catalog-json'/);
  expect(app).toMatch(/type="module"[^>]*'coffee-storefront\.js'\s*\|\s*asset_url|'coffee-storefront\.js'\s*\|\s*asset_url[^>]*type="module"/);
});

test('every template renders the app, so no Shopify route shows an empty page', () => {
  const templates = readdirSync(theme('templates')).filter((f) => f.endsWith('.liquid'));
  expect(templates.sort()).toEqual(['404.liquid', 'cart.liquid', 'collection.liquid', 'index.liquid', 'list-collections.liquid', 'page.liquid', 'password.liquid', 'product.liquid', 'search.liquid']);
  for (const t of templates) expect(read(`templates/${t}`), t).toMatch(/render 'storefront-app'/);
});

test('the product and collection templates open the matching route of the app', () => {
  expect(read('templates/product.liquid')).toMatch(/\/product\/.*product\.handle/);
  expect(read('templates/index.liquid')).not.toMatch(/product\.handle/);
});

test('the theme has the config and locale files Shopify expects, and the schema names the theme', () => {
  expect(existsSync(theme('config/settings_schema.json'))).toBe(true);
  expect(existsSync(theme('locales/en.default.json'))).toBe(true);
  const schema = JSON.parse(read('config/settings_schema.json'));
  expect(schema[0]).toMatchObject({ name: 'theme_info' });
  expect(JSON.parse(read('locales/en.default.json'))).toEqual({});
});

test('the catalog snippet keeps the two limits in view: Liquid loops stop at 50 items, and the JSON is escaped into an attribute', () => {
  const snippet = read('snippets/catalog-json.liquid');
  expect(snippet).toMatch(/limit:\s*50/);
  expect(snippet).toMatch(/data-catalog="\{\{\s*catalog\s*\|\s*escape\s*\}\}"/);
});

test('the built assets are ignored by git, so the theme folder holds source only', () => {
  expect(readFileSync(resolve(process.cwd(), '.gitignore'), 'utf8')).toMatch(/theme\/assets/);
});

test('the server-rendered title uses the app\'s own store name, so link previews and search results do not show the admin default', () => {
  const store = /const STORE = '([^']+)'/.exec(readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8'))?.[1];
  expect(store).toBeTruthy();
  const title = /<title>([\s\S]*?)<\/title>/.exec(read('layout/theme.liquid'))?.[1] ?? '';
  expect(title).toContain(store!);
  expect(title).not.toMatch(/page_title/);
  // a product page reads "<product> | <store>", as the app sets it once it runs
  expect(title).toMatch(/product\.title/);
});

test('a collection page opens the listing filtered to that collection, and /collections/all opens the plain listing', () => {
  const t = read('templates/collection.liquid');
  expect(t).toMatch(/\/\?collection=.*collection\.handle/);
  expect(t).toMatch(/collection\.handle\s*!=\s*'all'/);
});
