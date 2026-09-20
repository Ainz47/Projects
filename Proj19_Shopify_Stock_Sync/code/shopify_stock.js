// Shopify's search can match neighbours (a hyphen splits words), so the answer is picked by exact SKU here.
// undefined: not found. null: no single tracked stock (untracked, ambiguous, or not a whole number).
function stockFromVariants(nodes, sku) {
  const hits = (nodes ?? []).filter((v) => v?.sku === sku);
  if (hits.length === 0) return undefined;
  if (hits.length > 1) return null;
  const variant = hits[0];
  if (variant.inventoryItem?.tracked !== true) return null;
  return Number.isInteger(variant.inventoryQuantity) ? variant.inventoryQuantity : null;
}

// --- exports (stripped when embedded in n8n) ---
module.exports = { stockFromVariants };
