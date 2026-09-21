// Shopify has no upsert for webhook subscriptions: list first, create only if none targets this URL.
function needsWebhookRegistration(subscriptions, callbackUrl) {
  return !(subscriptions ?? []).some((s) => s?.callbackUrl === callbackUrl);
}

// --- exports (stripped when embedded in n8n) ---
module.exports = { needsWebhookRegistration };
