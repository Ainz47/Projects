const HOT_MIN = 8;
const WARM_MIN = 5;

function tierFromScore(score) {
  if (score >= HOT_MIN) return 'hot';
  if (score >= WARM_MIN) return 'warm';
  return 'cold';
}

function needsReview(reason) {
  return { score: null, tier: 'needs_review', reason, suggested_reply: '' };
}

// Models wrap JSON in prose or code fences, so take the outermost {...}.
function parseQualification(text) {
  const match = String(text ?? '').match(/\{[\s\S]*\}/);
  if (!match) return needsReview('model returned no JSON');
  let data;
  try {
    data = JSON.parse(match[0]);
  } catch {
    return needsReview('model returned malformed JSON');
  }
  const raw = data.score === null || data.score === undefined ? NaN : Number(data.score);
  if (!Number.isFinite(raw)) return needsReview('model returned no usable score');
  const score = Math.min(10, Math.max(1, Math.round(raw)));
  return {
    score,
    tier: tierFromScore(score),
    reason: String(data.reason ?? '').trim(),
    suggested_reply: String(data.suggested_reply ?? '').trim(),
  };
}

// --- exports (stripped when embedded in n8n) ---
module.exports = { parseQualification, tierFromScore };
