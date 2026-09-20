import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const root = process.cwd();
const html = readFileSync(join(root, 'index.html'), 'utf8');

test('index.html links a favicon', () => {
  expect(html).toMatch(/<link[^>]+rel="icon"[^>]+href="[^"]*favicon\.svg"/);
});

test('the favicon file exists and is a real SVG', () => {
  const path = join(root, 'public', 'favicon.svg');
  expect(existsSync(path)).toBe(true);
  expect(readFileSync(path, 'utf8').trim().startsWith('<svg')).toBe(true);
});

test('index.html carries social preview meta (title, description, type)', () => {
  expect(html).toMatch(/<meta property="og:title" content="[^"]+"/);
  expect(html).toMatch(/<meta property="og:description" content="[^"]+"/);
  expect(html).toMatch(/<meta property="og:type" content="website"/);
  expect(html).toMatch(/<meta name="twitter:card" content="summary"/);
});
