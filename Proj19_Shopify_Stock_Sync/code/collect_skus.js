function collectSkus(orders) {
  const seen = new Set();
  for (const order of orders ?? []) {
    for (const line of order?.lineItems?.nodes ?? []) {
      const sku = typeof line?.sku === 'string' ? line.sku.trim() : '';
      if (sku) seen.add(sku);
    }
  }
  return [...seen].sort();
}

function skuOrderNames(orders) {
  const bySku = new Map();
  for (const order of orders ?? []) {
    const name = typeof order?.name === 'string' ? order.name : '';
    if (!name) continue;
    for (const line of order?.lineItems?.nodes ?? []) {
      const sku = typeof line?.sku === 'string' ? line.sku.trim() : '';
      if (!sku) continue;
      if (!bySku.has(sku)) bySku.set(sku, new Set());
      bySku.get(sku).add(name);
    }
  }
  const result = {};
  for (const [sku, names] of bySku) result[sku] = [...names].sort().join('; ');
  return result;
}

// --- exports (stripped when embedded in n8n) ---
module.exports = { collectSkus, skuOrderNames };
