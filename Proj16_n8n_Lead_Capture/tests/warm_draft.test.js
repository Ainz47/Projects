const test = require('node:test');
const assert = require('node:assert/strict');
const { draftEmail } = require('../code/warm_draft.js');

const lead = (over) => ({
  name: 'Tom Becker', email: 'tom@example.com', company: 'Becker Design',
  suggested_reply: 'Happy to help with onboarding automation, when works for a quick call?',
  ...over,
});

test('subject includes the company when one was given', () => {
  assert.equal(draftEmail(lead()).subject, 'Re: your project (Becker Design)');
});

test('subject omits the parens when no company was given', () => {
  assert.equal(draftEmail(lead({ company: '' })).subject, 'Re: your project');
});

test('the greeting uses only the first word of the name', () => {
  assert.match(draftEmail(lead({ name: 'Maria Santos' })).text, /^Hi Maria,/);
});

test('an empty name falls back to a generic greeting, not a crash', () => {
  assert.match(draftEmail(lead({ name: '' })).text, /^Hi there,/);
});

test('the body carries the suggested reply and a fixed sign-off', () => {
  const text = draftEmail(lead()).text;
  assert.match(text, /Happy to help with onboarding automation, when works for a quick call\?/);
  assert.match(text, /Jhurald$/);
});

test('to is the lead email, unchanged', () => {
  assert.equal(draftEmail(lead({ email: 'someone@example.com' })).to, 'someone@example.com');
});

test('tolerates a missing suggested_reply rather than printing "undefined"', () => {
  assert.doesNotMatch(draftEmail(lead({ suggested_reply: undefined })).text, /undefined/);
});
