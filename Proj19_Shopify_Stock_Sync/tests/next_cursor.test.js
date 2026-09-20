const test = require('node:test');
const assert = require('node:assert/strict');
const { nextCursor } = require('../code/next_cursor.js');

const NOW = Date.parse('2026-09-20T14:00:00Z');
const at = (iso) => ({ updatedAt: iso });

test('moves to the newest order update seen', () => {
  const c = nextCursor('2026-09-20T13:00:00.000Z', [at('2026-09-20T13:20:00Z'), at('2026-09-20T13:40:00Z')], NOW);
  assert.equal(c, '2026-09-20T13:40:00.000Z');
});

test('never moves backwards, even when the orders are older than the cursor', () => {
  assert.equal(nextCursor('2026-09-20T13:30:00.000Z', [at('2026-09-20T13:00:00Z')], NOW), '2026-09-20T13:30:00.000Z');
});

test('with no orders the cursor stays where it was', () => {
  assert.equal(nextCursor('2026-09-20T13:30:00.000Z', [], NOW), '2026-09-20T13:30:00.000Z');
});

test('with no cursor and no orders it starts at now', () => {
  assert.equal(nextCursor(null, [], NOW), '2026-09-20T14:00:00.000Z');
  assert.equal(nextCursor(undefined, undefined, NOW), '2026-09-20T14:00:00.000Z');
});

test('never goes past now, even for a future timestamp', () => {
  assert.equal(nextCursor(null, [at('2026-09-20T18:00:00Z')], NOW), '2026-09-20T14:00:00.000Z');
  assert.equal(nextCursor('2026-09-20T18:00:00.000Z', [], NOW), '2026-09-20T14:00:00.000Z');
});

test('ignores orders with no readable update time', () => {
  assert.equal(nextCursor('2026-09-20T13:30:00.000Z', [{}, at('nope'), null], NOW), '2026-09-20T13:30:00.000Z');
});
