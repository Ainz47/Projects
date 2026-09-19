const test = require('node:test');
const assert = require('node:assert/strict');
const { SHEET_COLUMNS, acceptedRow, rejectedRow } = require('../code/rows.js');

const lead = {
  name: 'Dana Reyes', email: 'dana@example.com', company: 'Reyes Dental',
  message: 'We need our booking form wired to a CRM.', budget: '$500-$2,000',
  timeline: 'This month', submitted_at: '2026-09-19T10:00:00.000Z', valid: true, errors: [],
};

test('accepted row has exactly the sheet columns, in order', () => {
  const row = acceptedRow(lead, { score: 9, tier: 'hot', reason: 'Fits.', suggested_reply: 'Hi Dana.' });
  assert.deepEqual(Object.keys(row), SHEET_COLUMNS);
  assert.equal(row.timestamp, lead.submitted_at);
  assert.equal(row.status, 'accepted');
  assert.equal(row.tier, 'hot');
  assert.equal(row.score, 9);
});

test('a needs_review qualification writes an empty score cell', () => {
  const row = acceptedRow(lead, { score: null, tier: 'needs_review', reason: 'model returned no JSON', suggested_reply: '' });
  assert.equal(row.score, '');
  assert.equal(row.tier, 'needs_review');
});

test('rejected row carries the validation errors as the reason', () => {
  const row = rejectedRow({ ...lead, valid: false, errors: ['email invalid', 'message too short'] });
  assert.deepEqual(Object.keys(row), SHEET_COLUMNS);
  assert.equal(row.status, 'rejected');
  assert.equal(row.tier, 'rejected');
  assert.equal(row.score, '');
  assert.equal(row.reason, 'email invalid; message too short');
});
