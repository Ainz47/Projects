import { loadCatalog } from '../src/data/source';
import { artDataUri, artFor, kindFor } from '../src/art';
import { hashString } from '../src/art/palette';

const { products } = loadCatalog();
const sample = { handle: 'kiambu-aa-kenya', type: 'Coffee', origin: 'Kenya', roast: 'Light' };

function parse(svg: string) {
  return new DOMParser().parseFromString(svg, 'image/svg+xml');
}

test('the kind follows the product type, with a generic fallback', () => {
  expect(kindFor({ type: 'Coffee' })).toBe('bag');
  expect(kindFor({ type: 'Dripper' })).toBe('dripper');
  expect(kindFor({ type: 'Kettle' })).toBe('kettle');
  expect(kindFor({ type: 'Grinder' })).toBe('grinder');
  expect(kindFor({ type: 'Accessory' })).toBe('generic');
});

test('every fixture product gets well-formed SVG', () => {
  for (const p of products) {
    const doc = parse(artFor(p));
    expect(doc.getElementsByTagName('parsererror'), p.handle).toHaveLength(0);
    expect(doc.documentElement.nodeName, p.handle).toBe('svg');
    expect(doc.documentElement.getAttribute('viewBox'), p.handle).toBe('0 0 400 400');
  }
});

test('the same product always draws the same picture, different products differ', () => {
  expect(artFor(sample)).toBe(artFor({ ...sample }));
  expect(artFor(sample)).not.toBe(artFor({ ...sample, handle: 'other-handle', origin: 'Brazil' }));
  expect(artFor(sample)).not.toBe(artFor({ ...sample, roast: 'Dark' }));
  expect(hashString('a')).toBe(hashString('a'));
  expect(hashString('a')).not.toBe(hashString('b'));
});

test('the art holds no external references or script', () => {
  for (const p of products) {
    const svg = artFor(p).replace('xmlns="http://www.w3.org/2000/svg"', '');
    expect(svg, p.handle).not.toMatch(/https?:|href|<image|<script|<foreignObject|\son\w+=|url\((?!#)/i);
  }
});

test('text from the data is escaped, so odd origins cannot break the markup', () => {
  const svg = artFor({ ...sample, origin: `Cote d'Or & <Co> "x"` });
  const doc = parse(svg);
  expect(doc.getElementsByTagName('parsererror')).toHaveLength(0);
  expect(svg).not.toContain('<Co>');
});

test('artDataUri is a plain SVG data URI that decodes back to the art', () => {
  const uri = artDataUri(sample);
  expect(uri.startsWith('data:image/svg+xml,')).toBe(true);
  expect(decodeURIComponent(uri.slice('data:image/svg+xml,'.length))).toBe(artFor(sample));
});
