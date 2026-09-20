function assertNoGraphqlErrors(body, label) {
  const errors = body && Array.isArray(body.errors) ? body.errors : [];
  if (errors.length > 0) throw new Error(`${label}: ${errors.map((e) => e.message).join('; ')}`);
  if (!body || typeof body.data !== 'object' || body.data === null) throw new Error(`${label}: the response had no data`);
}

// --- exports (stripped when embedded in n8n) ---
module.exports = { assertNoGraphqlErrors };
