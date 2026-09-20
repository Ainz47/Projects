const test = require('node:test');
const assert = require('node:assert/strict');
const { skusSearch, airtableFormula } = require('../code/lookups.js');

test('a Shopify search ORs one quoted sku term per SKU', () => {
  assert.equal(skusSearch(['A-1', 'B-2']), 'sku:"A-1" OR sku:"B-2"');
});

test('an Airtable formula ORs one equality per SKU', () => {
  assert.equal(airtableFormula(['A-1', 'B-2']), "OR({SKU}='A-1',{SKU}='B-2')");
});

test('a hostile SKU cannot break out of the Shopify search quotes', () => {
  assert.equal(skusSearch(['a" OR sku:"b']), 'sku:"a\\" OR sku:\\"b"');
});

test('a hostile SKU cannot break out of the Airtable formula quotes', () => {
  assert.equal(airtableFormula(["x'),{SKU}!=('"]), "OR({SKU}='x\\'),{SKU}!=(\\'')");
  assert.equal(airtableFormula(['a\\']), "OR({SKU}='a\\\\')");
});

test('no SKUs gives empty strings the workflow never sends', () => {
  assert.equal(skusSearch([]), '');
  assert.equal(airtableFormula([]), 'OR()');
});
