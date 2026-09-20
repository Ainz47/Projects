const OVERLAP_MS = 10 * 60 * 1000;
const MAX_ORDERS = 250;

// Re-reading the last 10 minutes on every tick is safe: the sync writes Shopify's current stock, so a repeat changes nothing.
function planOrdersQuery(cursorIso, nowMs) {
  const parsed = Date.parse(cursorIso);
  const base = Number.isFinite(parsed) ? Math.min(parsed, nowMs) : nowMs;
  const since = new Date(base - OVERLAP_MS).toISOString();
  return { since, search: `updated_at:>=${since}`, first: MAX_ORDERS };
}

// --- exports (stripped when embedded in n8n) ---
module.exports = { planOrdersQuery, OVERLAP_MS, MAX_ORDERS };
