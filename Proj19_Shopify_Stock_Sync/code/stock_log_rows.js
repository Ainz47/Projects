function stockLogRows(updates, orderNamesBySku, source, nowIso) {
  return (updates ?? []).map((u) => ({
    timestamp: nowIso,
    sku: u.sku,
    old_stock: u.oldStock,
    new_stock: u.newStock,
    source,
    order_name: orderNamesBySku?.[u.sku] ?? '',
  }));
}

// --- exports (stripped when embedded in n8n) ---
module.exports = { stockLogRows };
