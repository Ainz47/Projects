const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

function summarize(rows, nowMs) {
  const counts = { hot: 0, warm: 0, cold: 0, needs_review: 0, rejected: 0 };
  const hotLeads = [];
  for (const row of rows) {
    const at = Date.parse(row.timestamp);
    if (!Number.isFinite(at) || at < nowMs - WEEK_MS) continue;
    const tier = Object.hasOwn(counts, row.tier) ? row.tier : 'needs_review';
    counts[tier] += 1;
    if (tier === 'hot') hotLeads.push({ company: row.company, reason: row.reason });
  }
  const total = Object.values(counts).reduce((sum, n) => sum + n, 0);
  return { total, counts, hotLeads };
}

// --- exports (stripped when embedded in n8n) ---
module.exports = { summarize };
