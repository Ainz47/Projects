// Generates data/catalog.fixture.json in the shape of a Shopify Admin GraphQL
// `products` response. Deterministic: same input, same file. Run: npm run fixture
import { writeFileSync } from 'node:fs';

const slug = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const money = (cents) => (cents / 100).toFixed(2);

const COFFEES = [
  ['Yirgacheffe Washed', 'Ethiopia', 'Light', 1800, ['jasmine', 'lemon', 'tea-like']],
  ['Guji Natural', 'Ethiopia', 'Light', 2000, ['blueberry', 'floral', 'sweet']],
  ['Huila Reserve', 'Colombia', 'Medium', 1700, ['caramel', 'red apple', 'balanced']],
  ['Narino Honey', 'Colombia', 'Medium', 1750, ['honey', 'plum', 'smooth']],
  ['Kiambu AA', 'Kenya', 'Light', 2100, ['blackcurrant', 'grapefruit', 'juicy']],
  ['Nyeri Peaberry', 'Kenya', 'Medium', 2200, ['tomato', 'brown sugar', 'bright']],
  ['Antigua Volcanic', 'Guatemala', 'Medium', 1650, ['cocoa', 'orange', 'rounded']],
  ['Huehuetenango Highland', 'Guatemala', 'Medium', 1700, ['toffee', 'stone fruit', 'clean']],
  ['Cerrado Mineiro', 'Brazil', 'Medium', 1500, ['hazelnut', 'chocolate', 'low acid']],
  ['Sul de Minas', 'Brazil', 'Dark', 1500, ['dark chocolate', 'toasted nut', 'heavy']],
  ['Mandheling', 'Indonesia', 'Dark', 1750, ['cedar', 'molasses', 'earthy']],
  ['Flores Bajawa', 'Indonesia', 'Medium', 1800, ['spice', 'sweet tobacco', 'syrupy']],
  ['Tarrazu', 'Costa Rica', 'Light', 1900, ['peach', 'honey', 'crisp']],
  ['Boquete Reserve', 'Panama', 'Light', 3400, ['bergamot', 'jasmine', 'delicate']],
  ['Marcala', 'Honduras', 'Medium', 1600, ['panela', 'almond', 'gentle']],
  ['Nyamasheke', 'Rwanda', 'Light', 1950, ['raspberry', 'rose', 'lively']],
  ['House Espresso', 'Blend', 'Dark', 1600, ['dark cocoa', 'caramel', 'thick crema']],
  ['Decaf Sugarcane', 'Colombia', 'Medium', 1800, ['brown sugar', 'cherry', 'soft']],
];

// [title, type, base cents, option name or null, option values, tags]
const GEAR = [
  ['Ceramic Dripper 02', 'Dripper', 2800, 'Color', ['Sand', 'Matte black'], ['pour-over', 'ceramic']],
  ['Steel Cone Dripper', 'Dripper', 3400, null, [], ['pour-over', 'steel']],
  ['Gooseneck Kettle 0.9L', 'Kettle', 7900, 'Color', ['Matte black', 'Brushed steel'], ['kettle', 'gooseneck']],
  ['Temperature Kettle Pro', 'Kettle', 12900, null, [], ['kettle', 'electric']],
  ['Hand Grinder Compact', 'Grinder', 8900, null, [], ['grinder', 'manual']],
  ['Flat Burr Grinder', 'Grinder', 21900, 'Color', ['Graphite', 'Cream'], ['grinder', 'electric']],
  ['Paper Filters 100', 'Accessory', 900, null, [], ['filters', 'consumable']],
  ['Precision Scale 0.1g', 'Accessory', 5900, null, [], ['scale', 'timer']],
  ['Glass Server 600ml', 'Accessory', 2600, null, [], ['server', 'glass']],
  ['Enamel Camp Mug', 'Accessory', 1800, 'Color', ['Cream', 'Forest'], ['mug', 'enamel']],
  ['Travel Press', 'Accessory', 3600, null, [], ['press', 'travel']],
  ['Tamper and Brush Set', 'Accessory', 3200, null, [], ['espresso', 'tools']],
];

const WEIGHTS = ['250g', '1kg'];
const GRINDS = ['Whole bean', 'Espresso', 'Filter'];

// Deterministic stock: mostly healthy, with a few forced edge cases.
function stock(i, j) {
  return (i * 7 + j * 5) % 13 === 0 ? 0 : 4 + ((i * 3 + j * 11) % 30);
}

const nodes = [];
let n = 0;

COFFEES.forEach(([title, origin, roast, base, notes], i) => {
  n += 1;
  const variants = [];
  let j = 0;
  for (const w of WEIGHTS) {
    for (const g of GRINDS) {
      j += 1;
      const cents = w === '1kg' ? Math.round((base * 3.6) / 100) * 100 : base;
      let inv = stock(i, j);
      if (title === 'Kiambu AA') inv = 0; // fully sold out
      if (title === 'Boquete Reserve') inv = w === '250g' && g === 'Whole bean' ? 3 : 0; // one low-stock variant
      if (title === 'Sul de Minas' && g === 'Espresso') inv = 0; // one grind sold out
      variants.push({
        id: `gid://shopify/ProductVariant/${n}${j}`,
        title: `${w} / ${g}`,
        sku: `${slug(title).toUpperCase().slice(0, 8)}-${w}-${g.slice(0, 2).toUpperCase()}`,
        price: money(cents),
        inventoryQuantity: inv,
        selectedOptions: [{ name: 'Weight', value: w }, { name: 'Grind', value: g }],
      });
    }
  }
  nodes.push({
    id: `gid://shopify/Product/${n}`,
    title: `${title} ${origin === 'Blend' ? 'Blend' : origin}`.replace(/ Blend Blend/, ' Blend'),
    handle: slug(`${title} ${origin === 'Blend' ? '' : origin}`),
    vendor: 'Lantern Roasters',
    productType: 'Coffee',
    tags: ['coffee', `${roast.toLowerCase()}-roast`, ...notes.map(slug)],
    description: `Tasting notes of ${notes.join(', ')}. Roasted in small batches for a ${roast.toLowerCase()} profile.`,
    options: [
      { name: 'Weight', values: WEIGHTS },
      { name: 'Grind', values: GRINDS },
    ],
    variants: { nodes: variants },
    metafields: {
      nodes: [
        { namespace: 'custom', key: 'origin', value: origin },
        { namespace: 'custom', key: 'roast', value: roast },
      ],
    },
  });
});

GEAR.forEach(([title, type, base, optName, optValues, tags], k) => {
  n += 1;
  const values = optName ? optValues : ['Default Title'];
  const name = optName ?? 'Title';
  const variants = values.map((value, j) => {
    let inv = stock(k + 20, j + 1);
    if (title === 'Temperature Kettle Pro') inv = 2; // low stock, single variant
    return {
      id: `gid://shopify/ProductVariant/${n}${j + 1}`,
      title: value,
      sku: `${slug(title).toUpperCase().slice(0, 8)}-${j + 1}`,
      price: money(base),
      inventoryQuantity: inv,
      selectedOptions: [{ name, value }],
    };
  });
  nodes.push({
    id: `gid://shopify/Product/${n}`,
    title,
    handle: slug(title),
    vendor: 'Northbound Gear',
    productType: type,
    tags,
    description: `${title}, chosen for everyday brewing at home.`,
    options: [{ name, values }],
    variants: { nodes: variants },
    metafields: { nodes: [] },
  });
});

const out = { data: { products: { nodes } } };
writeFileSync(new URL('../data/catalog.fixture.json', import.meta.url), JSON.stringify(out, null, 2) + '\n');
console.log(`wrote ${nodes.length} products`);
