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

// --- exports (stripped when embedded in n8n) ---
module.exports = { collectSkus };
