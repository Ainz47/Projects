function draftEmail(lead) {
  const firstName = String(lead?.name ?? '').trim().split(/\s+/)[0] || 'there';
  const company = String(lead?.company ?? '').trim();
  const subject = company ? `Re: your project (${company})` : 'Re: your project';
  const reply = String(lead?.suggested_reply ?? '');
  return {
    to: lead?.email ?? '',
    subject,
    text: `Hi ${firstName},\n\n${reply}\n\nJhurald`,
  };
}

// --- exports (stripped when embedded in n8n) ---
module.exports = { draftEmail };
