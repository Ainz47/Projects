function nextCursor(prevCursorIso, orders, nowMs) {
  const times = [Date.parse(prevCursorIso), ...(orders ?? []).map((o) => Date.parse(o?.updatedAt))].filter(Number.isFinite);
  const newest = times.length > 0 ? Math.max(...times) : nowMs;
  return new Date(Math.min(newest, nowMs)).toISOString();
}

// --- exports (stripped when embedded in n8n) ---
module.exports = { nextCursor };
