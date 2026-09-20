const ORDERS_QUERY = `query Orders($first: Int!, $search: String!) {
  orders(first: $first, query: $search, sortKey: UPDATED_AT, reverse: false) {
    nodes {
      id name email updatedAt tags
      lineItems(first: 50) { nodes { sku quantity } }
    }
  }
}`;

const STOCK_QUERY = `query Stock($search: String!) {
  productVariants(first: 250, query: $search) {
    nodes { sku inventoryQuantity inventoryItem { tracked } }
  }
}`;

// --- exports (stripped when embedded in n8n) ---
module.exports = { ORDERS_QUERY, STOCK_QUERY };
