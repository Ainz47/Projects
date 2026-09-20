import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { gzipSync } from 'node:zlib';

// Gzip bytes. Set from the first build plus about 15 percent (first build: 81,389 entry, 82,619
// total). Raise one only after looking at what grew, and say why in the commit.
const ENTRY_BUDGET = 94_000; // the JavaScript the first page load needs
const TOTAL_BUDGET = 96_000; // all JavaScript, including the lazy product route

// Hosts that appear only as inert strings inside the bundle (SVG namespaces, React's error-message
// link), never as a request. Add one only after checking where it comes from.
const INERT_HOSTS = new Set(['www.w3.org', 'react.dev']);

// Resolved from the project root: under jsdom the global URL is not the one node's fs accepts.
const out = resolve(process.cwd(), '../docs/coffee-store');
const html = readFileSync(resolve(out, 'index.html'), 'utf8');
const assetDir = resolve(out, 'assets');
const assets = readdirSync(assetDir).map((name) => ({ name, bytes: readFileSync(resolve(assetDir, name)) }));
const js = assets.filter((a) => a.name.endsWith('.js'));
const css = assets.filter((a) => a.name.endsWith('.css'));
const gz = (b: Buffer) => gzipSync(b).length;

test('the built page exists and uses the Pages base path', () => {
  expect(existsSync(resolve(out, 'index.html'))).toBe(true);
  expect(html).toContain('<div id="root"></div>');
  expect(html).toContain('<title>Lantern Roasters (demo)</title>');
});

test('everything the page loads sits under the Pages base path', () => {
  const refs = [...html.matchAll(/(?:src|href)="([^"]+)"/g)].map((m) => m[1]!);
  expect(refs.length).toBeGreaterThan(0);
  for (const ref of refs) expect(ref.startsWith('/Projects/coffee-store/'), ref).toBe(true);
});

test('the product route is its own lazy chunk', () => {
  expect(js.length).toBeGreaterThanOrEqual(2);
});

test('the first-load JavaScript stays under budget', () => {
  const entryName = /assets\/([^"]+\.js)"/.exec(html)![1]!;
  const entry = js.find((a) => a.name === entryName)!;
  expect(gz(entry.bytes)).toBeLessThanOrEqual(ENTRY_BUDGET);
});

test('all the JavaScript together stays under budget', () => {
  expect(js.reduce((n, a) => n + gz(a.bytes), 0)).toBeLessThanOrEqual(TOTAL_BUDGET);
});

test('nothing in the page points at another origin', () => {
  const blobs = [html, ...js.map((a) => a.bytes.toString('utf8')), ...css.map((a) => a.bytes.toString('utf8'))];
  const hosts = new Set(blobs.flatMap((b) => [...b.matchAll(/https?:\/\/([a-z0-9.-]+)/gi)].map((m) => m[1]!.toLowerCase())));
  for (const host of hosts) expect(INERT_HOSTS.has(host), host).toBe(true);
});
