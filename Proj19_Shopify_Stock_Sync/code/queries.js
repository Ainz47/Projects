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

const WEBHOOKS_QUERY = `query ExistingWebhooks($topics: [WebhookSubscriptionTopic!]) {
  webhookSubscriptions(first: 10, topics: $topics) {
    nodes {
      id
      endpoint { __typename ... on WebhookHttpEndpoint { callbackUrl } }
    }
  }
}`;

const WEBHOOK_CREATE_MUTATION = `mutation CreateOrdersWebhook($callbackUrl: String!) {
  webhookSubscriptionCreate(topic: ORDERS_CREATE, webhookSubscription: { uri: $callbackUrl, format: JSON }) {
    webhookSubscription { id }
    userErrors { field message }
  }
}`;

const TAG_ORDER_MUTATION = `mutation TagOrder($id: ID!, $tags: [String!]!) {
  tagsAdd(id: $id, tags: $tags) {
    node { id }
    userErrors { field message }
  }
}`;

// --- exports (stripped when embedded in n8n) ---
module.exports = { ORDERS_QUERY, STOCK_QUERY, WEBHOOKS_QUERY, WEBHOOK_CREATE_MUTATION, TAG_ORDER_MUTATION };
