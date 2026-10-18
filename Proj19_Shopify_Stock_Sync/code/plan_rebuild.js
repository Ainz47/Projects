// Whether the public storefront needs a rebuild is decided from what was actually published (the
// catalog snapshot refresh-catalog commits), not from "did this tick change Airtable". If Airtable was
// written and the dispatch after it failed, the retry tick finds Airtable already matching Shopify and
// would never dispatch again; comparing against the snapshot still sees the page is behind. It also
// covers a Make dispatch that ran out of retries and a refresh-catalog run that failed on GitHub.
const MAX_FAILED_REBUILDS = 3;

function publishedStock(snapshot) {
  const stock = {};
  for (const product of snapshot?.data?.products?.nodes ?? []) {
    for (const variant of product?.variants?.nodes ?? []) {
      if (variant?.sku) stock[variant.sku] = variant.inventoryQuantity;
    }
  }
  return stock;
}

// synced: { sku: stock } Airtable holds after this tick. runs: refresh-catalog runs, newest first.
function planRebuild(synced, published, runs) {
  const stale = Object.keys(synced ?? {}).filter((sku) => published?.[sku] !== synced[sku]).sort();
  if (stale.length === 0) return { dispatch: false, stale };
  if ((runs ?? []).some((r) => r?.status !== 'completed')) {
    return { dispatch: false, stale, reason: 'a rebuild is already queued or running' };
  }
  let failedInARow = 0;
  for (const run of runs ?? []) {
    if (run.conclusion === 'success') break;
    failedInARow += 1;
  }
  if (failedInARow >= MAX_FAILED_REBUILDS) {
    throw new Error(`refresh-catalog failed ${MAX_FAILED_REBUILDS} times in a row; not dispatching again until it is fixed (stale: ${stale.join(', ')})`);
  }
  return { dispatch: true, stale };
}

// --- exports (stripped when embedded in n8n) ---
module.exports = { publishedStock, planRebuild };
