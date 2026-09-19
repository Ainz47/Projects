const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function clean(value) {
  return String(value ?? '').replace(/\s+/g, ' ').trim();
}

// The Form Trigger sends keys named after the field labels (Name, Email, ...).
function validateLead(raw) {
  const lead = {
    name: clean(raw.Name),
    email: clean(raw.Email).toLowerCase(),
    company: clean(raw.Company),
    message: clean(raw.Message),
    budget: clean(raw.Budget),
    timeline: clean(raw.Timeline),
    submitted_at: raw.submittedAt || new Date().toISOString(),
  };
  const errors = [];
  if (!lead.name) errors.push('name missing');
  if (!EMAIL_RE.test(lead.email)) errors.push('email invalid');
  if (lead.message.length < 10) errors.push('message too short');
  return { ...lead, valid: errors.length === 0, errors };
}

// --- exports (stripped when embedded in n8n) ---
module.exports = { validateLead };
