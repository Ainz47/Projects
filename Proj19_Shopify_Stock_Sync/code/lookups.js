const quoteSearch = (s) => `"${String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
const quoteFormula = (s) => `'${String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'")}'`;

function skusSearch(skus) {
  return skus.map((s) => `sku:${quoteSearch(s)}`).join(' OR ');
}

function airtableFormula(skus) {
  return `OR(${skus.map((s) => `{SKU}=${quoteFormula(s)}`).join(',')})`;
}

// --- exports (stripped when embedded in n8n) ---
module.exports = { skusSearch, airtableFormula };
