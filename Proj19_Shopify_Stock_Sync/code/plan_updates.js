const isWholeStock = (n) => Number.isInteger(n) && n >= 0;

function planUpdates(skus, shopifyStock, airtableRows) {
  const bySku = new Map();
  const duplicated = new Set();
  for (const row of airtableRows ?? []) {
    if (bySku.has(row.sku)) duplicated.add(row.sku);
    else bySku.set(row.sku, row);
  }
  const result = { updates: [], skipped: [], rejected: [], unchanged: 0 };
  for (const sku of skus ?? []) {
    if (duplicated.has(sku)) {
      result.rejected.push({ sku, reason: 'duplicate SKU in Airtable' });
      continue;
    }
    const row = bySku.get(sku);
    if (!row) {
      result.skipped.push({ sku, reason: 'no Airtable row' });
      continue;
    }
    const stock = shopifyStock?.[sku];
    if (stock === undefined) {
      result.rejected.push({ sku, reason: 'SKU not found in Shopify' });
    } else if (stock === null) {
      result.rejected.push({ sku, reason: 'Shopify has no single tracked stock for this SKU' });
    } else if (!isWholeStock(stock)) {
      result.rejected.push({ sku, reason: 'Shopify stock is not a whole number of 0 or more' });
    } else if (row.stock === stock) {
      result.unchanged += 1;
    } else {
      result.updates.push({ recordId: row.id, sku, oldStock: row.stock ?? null, newStock: stock });
    }
  }
  return result;
}

function chunkUpdates(updates, size) {
  const chunks = [];
  for (let i = 0; i < (updates ?? []).length; i += size) chunks.push(updates.slice(i, i + size));
  return chunks;
}

// --- exports (stripped when embedded in n8n) ---
module.exports = { planUpdates, chunkUpdates };
