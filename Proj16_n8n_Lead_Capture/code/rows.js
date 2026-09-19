const SHEET_COLUMNS = [
  'timestamp', 'name', 'email', 'company', 'message', 'budget', 'timeline',
  'status', 'tier', 'score', 'reason', 'suggested_reply',
];

function acceptedRow(lead, q) {
  return {
    timestamp: lead.submitted_at,
    name: lead.name,
    email: lead.email,
    company: lead.company,
    message: lead.message,
    budget: lead.budget,
    timeline: lead.timeline,
    status: 'accepted',
    tier: q.tier,
    score: q.score ?? '',
    reason: q.reason,
    suggested_reply: q.suggested_reply,
  };
}

function rejectedRow(lead) {
  const q = { tier: 'rejected', score: '', reason: lead.errors.join('; '), suggested_reply: '' };
  return { ...acceptedRow(lead, q), status: 'rejected' };
}

// --- exports (stripped when embedded in n8n) ---
module.exports = { SHEET_COLUMNS, acceptedRow, rejectedRow };
