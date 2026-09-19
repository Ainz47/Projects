const test = require('node:test');
const assert = require('node:assert/strict');
const { validateLead } = require('../code/validate.js');

const good = {
  Name: '  Dana Reyes ',
  Email: 'Dana@Example.com',
  Company: 'Reyes Dental',
  Message: 'We need our booking form wired to a CRM.',
  Budget: '$500-$2,000',
  Timeline: 'This month',
  submittedAt: '2026-09-19T10:00:00.000Z',
};

test('accepts a complete lead and normalizes it', () => {
  const lead = validateLead(good);
  assert.equal(lead.valid, true);
  assert.deepEqual(lead.errors, []);
  assert.equal(lead.name, 'Dana Reyes');
  assert.equal(lead.email, 'dana@example.com');
  assert.equal(lead.submitted_at, '2026-09-19T10:00:00.000Z');
});

test('rejects a malformed email', () => {
  const lead = validateLead({ ...good, Email: 'not-an-email' });
  assert.equal(lead.valid, false);
  assert.deepEqual(lead.errors, ['email invalid']);
});

test('rejects a message under 10 characters', () => {
  const lead = validateLead({ ...good, Message: 'asdf' });
  assert.deepEqual(lead.errors, ['message too short']);
});

test('reports every problem at once', () => {
  const lead = validateLead({ Email: 'x', Message: 'hi' });
  assert.equal(lead.valid, false);
  assert.deepEqual(lead.errors, ['name missing', 'email invalid', 'message too short']);
});

test('collapses whitespace and newlines in the message', () => {
  const lead = validateLead({ ...good, Message: 'Line one\n\n  line   two is here' });
  assert.equal(lead.message, 'Line one line two is here');
});

test('fills submitted_at when the trigger did not send one', () => {
  const { submittedAt, ...rest } = good;
  assert.match(validateLead(rest).submitted_at, /^\d{4}-\d{2}-\d{2}T/);
});
