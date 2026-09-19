import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadTemplate } from '../src/data/load.js';
import { dowOf, currentBlock } from '../src/clock.js';
import { blocksFor } from '../src/schedule.js';

const T = loadTemplate();

test('dowOf maps dates to weekday keys', () => {
  assert.equal(dowOf('2026-08-10'), 'mon');
  assert.equal(dowOf('2026-09-13'), 'sun');
  assert.equal(dowOf('2026-08-17'), 'mon');
});

test('14:30 Monday resolves differently on each branch', () => {
  assert.equal(currentBlock(T, 'mon', 'A', '14:30').block.id, 'mon-a-class');
  assert.equal(currentBlock(T, 'mon', 'B', '14:30').block.id, 'mon-b-surge');
});

test('a block is entered at its start and left at its end', () => {
  assert.equal(currentBlock(T, 'tue', null, '07:30').block.id, 'tue-client1');
  assert.equal(currentBlock(T, 'tue', null, '10:29').block.id, 'tue-client1');
  assert.equal(currentBlock(T, 'tue', null, '10:30').block.id, 'tue-talk');
});

test('minutesLeft counts down to the block end', () => {
  const r = currentBlock(T, 'tue', null, '10:00');
  assert.equal(r.minutesLeft, 30);
});

test('next points at the following block, and is null in the last one', () => {
  assert.equal(currentBlock(T, 'tue', null, '07:30').next.id, 'tue-talk');
  assert.equal(currentBlock(T, 'tue', null, '22:00').next, null);
});

test('before wake and after sleep are off-hours, not undefined', () => {
  const early = currentBlock(T, 'tue', null, '03:00');
  assert.equal(early.status, 'off-hours');
  assert.equal(early.block, null);
  assert.equal(early.next.id, 'tue-topfocus');

  const late = currentBlock(T, 'tue', null, '23:30');
  assert.equal(late.status, 'off-hours');
  assert.equal(late.block, null);
  assert.equal(late.next, null);
});

test('currentBlock counts down the override block on an overridden day', () => {
  const base = blocksFor(T, 'tue', null);
  const entries = base.map(b => ({ id: b.id, start: b.start, end: b.end, hours: b.hours, fields: null }));
  // Stretch tue-client1 to 11:00 and shorten tue-talk to match.
  entries[2] = { ...entries[2], end: '11:00', hours: 3.5 };
  entries[3] = { ...entries[3], start: '11:00', hours: 0.5 };
  const doc = { blocksOverride: entries, blocksOverrideAt: '2026-08-18T00:00:00.000Z' };

  assert.equal(currentBlock(T, 'tue', null, '10:45').block.id, 'tue-talk');
  assert.equal(currentBlock(T, 'tue', null, '10:45', doc).block.id, 'tue-client1');
  assert.equal(currentBlock(T, 'tue', null, '10:45', doc).minutesLeft, 15);
});
