const test = require('node:test');
const assert = require('node:assert/strict');
const { parseQualification, tierFromScore } = require('../code/parse_llm.js');

test('tier boundaries: 8+ hot, 5-7 warm, below 5 cold', () => {
  assert.equal(tierFromScore(10), 'hot');
  assert.equal(tierFromScore(8), 'hot');
  assert.equal(tierFromScore(7), 'warm');
  assert.equal(tierFromScore(5), 'warm');
  assert.equal(tierFromScore(4), 'cold');
  assert.equal(tierFromScore(1), 'cold');
});

test('parses clean JSON and computes the tier from the score', () => {
  const q = parseQualification('{"score": 9, "reason": "Budget and timeline fit.", "suggested_reply": "Thanks, can we talk Tuesday?"}');
  assert.deepEqual(q, { score: 9, tier: 'hot', reason: 'Budget and timeline fit.', suggested_reply: 'Thanks, can we talk Tuesday?' });
});

test('ignores a tier the model wrote and trusts the score', () => {
  const q = parseQualification('{"score": 3, "tier": "hot", "reason": "r", "suggested_reply": "s"}');
  assert.equal(q.tier, 'cold');
});

test('extracts JSON wrapped in a code fence and prose', () => {
  const q = parseQualification('Sure!\n```json\n{"score": 6, "reason": "Vague.", "suggested_reply": "Tell me more."}\n```');
  assert.equal(q.tier, 'warm');
  assert.equal(q.score, 6);
});

test('accepts a numeric string score and rounds', () => {
  assert.equal(parseQualification('{"score": "7.6"}').score, 8);
});

test('clamps scores into 1..10', () => {
  assert.equal(parseQualification('{"score": 15}').score, 10);
  assert.equal(parseQualification('{"score": 0}').score, 1);
});

test('falls back to needs_review on no JSON, bad JSON, or no usable score', () => {
  for (const input of ['I cannot help with that.', '{"score": 8,', '{"reason": "x"}', '{"score": null}', '{"score": "high"}', undefined, '']) {
    const q = parseQualification(input);
    assert.equal(q.tier, 'needs_review', String(input));
    assert.equal(q.score, null);
    assert.ok(q.reason.length > 0);
  }
});
