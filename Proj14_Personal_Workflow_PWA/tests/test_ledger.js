import { test } from 'node:test';
import assert from 'node:assert/strict';
import { newEntry, balance, earnedOn, byAttribute, undoEntry, canAfford } from '../src/ledger.js';

const e = (kind, amount, opts = {}) => newEntry({
  kind, amount,
  attribute: opts.attribute ?? 'vitality',
  refId: opts.refId ?? 'x',
  label: opts.label ?? 'X',
  date: opts.date ?? '2026-08-10',
  ts: opts.ts ?? '2026-08-10T06:00:00.000Z',
  rand: opts.rand ?? 'aaaaaa',
});

test('id encodes timestamp and random suffix', () => {
  const entry = e('earn', 20, { ts: '2026-08-10T06:00:00.000Z', rand: 'ab12cd' });
  assert.equal(entry._id, 'ledger:2026-08-10T06:00:00.000Z:ab12cd');
  assert.equal(entry.type, 'ledger');
});

test('balance nets earns against spends and penalties', () => {
  // Distinct rand values are load-bearing: the helper defaults both ts and rand,
  // so entries left on the defaults collide on _id and balance() dedupes them.
  const entries = [e('earn', 100, { rand: 'a' }), e('spend', 30, { rand: 'b' }), e('penalty', 20, { rand: 'c' })];
  assert.equal(balance(entries), 50);
});

test('balance is order independent', () => {
  const entries = [e('earn', 100, { rand: 'a' }), e('spend', 30, { rand: 'b' }), e('penalty', 20, { rand: 'c' })];
  const reversed = [...entries].reverse();
  assert.equal(balance(entries), balance(reversed));
});

test('duplicate ids are counted once', () => {
  const one = e('earn', 20, { rand: 'same' });
  assert.equal(balance([one, { ...one }]), 20);
});

test('earnedOn only counts earns for that date', () => {
  const entries = [
    e('earn', 20, { date: '2026-08-10' }),
    e('earn', 15, { date: '2026-08-10', rand: 'b' }),
    e('earn', 99, { date: '2026-08-11', rand: 'c' }),
    e('spend', 10, { date: '2026-08-10', rand: 'd' }),
  ];
  assert.equal(earnedOn(entries, '2026-08-10'), 35);
});

test('byAttribute nets per attribute', () => {
  const entries = [
    e('earn', 20, { attribute: 'purpose' }),
    e('earn', 10, { attribute: 'vitality', rand: 'b' }),
    e('penalty', 5, { attribute: 'vitality', rand: 'c' }),
  ];
  assert.deepEqual(byAttribute(entries), { purpose: 20, vitality: 5 });
});

test('undo writes a compensating entry and restores the balance', () => {
  const earn = e('earn', 20);
  const undo = undoEntry(earn, { ts: '2026-08-10T07:00:00.000Z', rand: 'zzzzzz' });
  assert.equal(undo.kind, 'spend');
  assert.equal(undo.amount, 20);
  assert.equal(undo.undoOf, earn._id);
  assert.equal(balance([earn, undo]), 0);
});

test('undoing a spend gives the coins back', () => {
  const spend = e('spend', 100);
  const undo = undoEntry(spend, { ts: '2026-08-10T07:00:00.000Z', rand: 'zzzzzz' });
  assert.equal(undo.kind, 'earn');
  assert.equal(balance([spend, undo]), 0);
});

test('canAfford compares against the live balance', () => {
  const entries = [e('earn', 100)];
  assert.equal(canAfford(entries, 100), true);
  assert.equal(canAfford(entries, 101), false);
});
