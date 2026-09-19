import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadTemplate } from '../src/data/load.js';
import { balance } from '../src/ledger.js';
import { blocksFor, resolveBlocks } from '../src/schedule.js';
import {
  emptyDay, assertWritable, applyBlockToggle, applyCheckToggle, setBranch, spend,
  LockedDayError, InsufficientCoinsError, CheckNotActiveError,
  nudgeSleep, nudgeWake, clearSleepOverride, clearWakeOverride,
  setBlocksOverride, clearBlocksOverride,
} from '../src/actions.js';

const T = loadTemplate();
const AT = '2026-08-10T10:00:00.000Z';
const MON_A = blocksFor(T, 'mon', 'A');

test('emptyDay builds a well formed document', () => {
  const d = emptyDay('2026-08-10', 'mon');
  assert.equal(d._id, 'day:2026-08-10');
  assert.equal(d.type, 'day');
  assert.equal(d.date, '2026-08-10');
  assert.equal(d.dow, 'mon');
  assert.equal(d.branch, null);
  assert.deepEqual(d.blocks, {});
  assert.deepEqual(d.checks, {});
  assert.equal(d.blocksOverride, null);
  assert.equal(d.blocksOverrideAt, null);
});

test('assertWritable allows today and the backfill window', () => {
  assertWritable('2026-08-13', '2026-08-13', 3);
  assertWritable('2026-08-10', '2026-08-13', 3);
});

test('assertWritable rejects a locked day loudly', () => {
  assert.throws(
    () => assertWritable('2026-08-10', '2026-08-14', 3),
    (err) => err instanceof LockedDayError && err.name === 'LockedDayError'
  );
});

test('ticking a block records it and awards the task coins', () => {
  const { doc, ledgerEntries } = applyBlockToggle({
    template: T, blocks: MON_A, doc: emptyDay('2026-08-10', 'mon'), blockId: 'mon-a-client1',
    done: true, at: AT, rand: 'aaaaaa', ledger: [],
  });
  assert.deepEqual(doc.blocks['mon-a-client1'], { done: true, at: AT });
  assert.equal(doc.updatedAt, AT);
  assert.equal(ledgerEntries.length, 1);
  assert.equal(ledgerEntries[0].kind, 'earn');
  assert.equal(ledgerEntries[0].amount, 20);       // tasks['deep-block']
  assert.equal(ledgerEntries[0].attribute, 'dataeng');
  assert.equal(ledgerEntries[0].refId, 'deep-block');
});

test('a block with no taskId awards nothing', () => {
  const { ledgerEntries } = applyBlockToggle({
    template: T, blocks: MON_A, doc: emptyDay('2026-08-10', 'mon'), blockId: 'mon-a-breakfast',
    done: true, at: AT, rand: 'aaaaaa', ledger: [],
  });
  assert.deepEqual(ledgerEntries, []);
});

test('unticking a block writes a compensating entry and returns the balance to zero', () => {
  const first = applyBlockToggle({
    template: T, blocks: MON_A, doc: emptyDay('2026-08-10', 'mon'), blockId: 'mon-a-client1',
    done: true, at: AT, rand: 'aaaaaa', ledger: [],
  });
  const second = applyBlockToggle({
    template: T, blocks: MON_A, doc: first.doc, blockId: 'mon-a-client1',
    done: false, at: '2026-08-10T10:05:00.000Z', rand: 'bbbbbb', ledger: first.ledgerEntries,
  });
  assert.equal(second.doc.blocks['mon-a-client1'].done, false);
  assert.equal(second.ledgerEntries.length, 1);
  assert.equal(second.ledgerEntries[0].undoOf, first.ledgerEntries[0]._id);
  assert.equal(balance([...first.ledgerEntries, ...second.ledgerEntries]), 0);
});

test('unticking twice does not award a second refund', () => {
  const first = applyBlockToggle({
    template: T, blocks: MON_A, doc: emptyDay('2026-08-10', 'mon'), blockId: 'mon-a-client1',
    done: true, at: AT, rand: 'aaaaaa', ledger: [],
  });
  const undo = applyBlockToggle({
    template: T, blocks: MON_A, doc: first.doc, blockId: 'mon-a-client1',
    done: false, at: '2026-08-10T10:05:00.000Z', rand: 'bbbbbb', ledger: first.ledgerEntries,
  });
  const all = [...first.ledgerEntries, ...undo.ledgerEntries];
  const again = applyBlockToggle({
    template: T, blocks: MON_A, doc: undo.doc, blockId: 'mon-a-client1',
    done: false, at: '2026-08-10T10:06:00.000Z', rand: 'cccccc', ledger: all,
  });
  assert.deepEqual(again.ledgerEntries, []);
});

test('ticking a check awards through the checks taskId mapping', () => {
  const { doc, ledgerEntries } = applyCheckToggle({
    template: T, doc: emptyDay('2026-08-10', 'mon'), checkId: 'sleep-cap',
    done: true, at: AT, rand: 'aaaaaa', ledger: [],
  });
  assert.equal(doc.checks['sleep-cap'].done, true);
  assert.equal(ledgerEntries[0].amount, 15);       // tasks['the-cap']
  assert.equal(ledgerEntries[0].refId, 'the-cap');
});

test('a check with a null taskId awards nothing', () => {
  const { ledgerEntries } = applyCheckToggle({
    template: T, doc: emptyDay('2026-08-10', 'mon'), checkId: 'health',
    done: true, at: AT, rand: 'aaaaaa', ledger: [],
  });
  assert.deepEqual(ledgerEntries, []);
});

test('an unknown block id is rejected rather than silently written', () => {
  assert.throws(() => applyBlockToggle({
    template: T, blocks: MON_A, doc: emptyDay('2026-08-10', 'mon'), blockId: 'no-such-block',
    done: true, at: AT, rand: 'aaaaaa', ledger: [],
  }), /unknown block/);
});

test('setBranch records the branch and the moment it was set', () => {
  const { doc } = setBranch({ doc: emptyDay('2026-08-10', 'mon'), branch: 'B', at: AT });
  assert.equal(doc.branch, 'B');
  assert.equal(doc.branchSetAt, AT);
});

test('setBranch rejects anything other than A or B', () => {
  assert.throws(() => setBranch({ doc: emptyDay('2026-08-10', 'mon'), branch: 'C', at: AT }), /branch/);
});

test('spending writes a spend entry when affordable', () => {
  const earned = applyBlockToggle({
    template: T, blocks: MON_A, doc: emptyDay('2026-08-10', 'mon'), blockId: 'mon-a-client1',
    done: true, at: AT, rand: 'aaaaaa', ledger: [],
  }).ledgerEntries;
  const many = [...Array(6)].map((_, i) => ({ ...earned[0], _id: `ledger:x:${i}` }));
  const { ledgerEntries } = spend({
    template: T, ledger: many, shopId: 'gaming', date: '2026-08-10', at: AT, rand: 'zzzzzz',
  });
  assert.equal(ledgerEntries[0].kind, 'spend');
  assert.equal(ledgerEntries[0].amount, 100);
  assert.equal(ledgerEntries[0].refId, 'gaming');
});

test('spending beyond the balance is rejected, not allowed to go negative', () => {
  assert.throws(
    () => spend({ template: T, ledger: [], shopId: 'gaming', date: '2026-08-10', at: AT, rand: 'z' }),
    (err) => err instanceof InsufficientCoinsError && err.name === 'InsufficientCoinsError'
  );
});

test('mutations never mutate the document passed in', () => {
  const before = emptyDay('2026-08-10', 'mon');
  applyBlockToggle({
    template: T, blocks: MON_A, doc: before, blockId: 'mon-a-client1',
    done: true, at: AT, rand: 'aaaaaa', ledger: [],
  });
  assert.deepEqual(before.blocks, {});
});

test('nudgeSleep writes the shifted time and a timestamp', () => {
  const doc = emptyDay('2026-08-11', 'tue');
  const { doc: out } = nudgeSleep({
    doc, deltaMinutes: 45, template: T, at: '2026-08-11T22:00:00.000Z',
  });
  assert.equal(out.sleepOverride, '23:15');
  assert.equal(out.sleepOverrideAt, '2026-08-11T22:00:00.000Z');
  assert.equal(out.updatedAt, '2026-08-11T22:00:00.000Z');
});

test('a second nudge compounds on the first', () => {
  const doc = emptyDay('2026-08-11', 'tue');
  const once = nudgeSleep({ doc, deltaMinutes: 15, template: T, at: '2026-08-11T22:00:00.000Z' }).doc;
  const twice = nudgeSleep({ doc: once, deltaMinutes: 15, template: T, at: '2026-08-11T22:01:00.000Z' }).doc;
  assert.equal(twice.sleepOverride, '23:00');
});

test('nudgeWake leaves the sleep override alone', () => {
  const doc = emptyDay('2026-08-11', 'tue');
  const { doc: out } = nudgeWake({
    doc, deltaMinutes: 60, template: T, at: '2026-08-11T22:00:00.000Z',
  });
  assert.equal(out.wakeOverride, '07:00');
  assert.equal(out.sleepOverride, null);
});

test('clearing stamps the timestamp so the clear outranks a stale nudge', () => {
  const doc = nudgeSleep({
    doc: emptyDay('2026-08-11', 'tue'), deltaMinutes: 45, template: T,
    at: '2026-08-11T22:00:00.000Z',
  }).doc;
  const { doc: out } = clearSleepOverride({ doc, at: '2026-08-11T22:30:00.000Z' });
  assert.equal(out.sleepOverride, null);
  assert.equal(out.sleepOverrideAt, '2026-08-11T22:30:00.000Z');
});

test('applyCheckToggle rejects a check that had not started yet', () => {
  const template = {
    ...T,
    checks: { ...T.checks, 'read-scripture': {
      label: 'Read scripture', attribute: 'purpose', taskId: null,
      activeFrom: '2026-08-12', retiredOn: null,
    } },
  };
  assert.throws(
    () => applyCheckToggle({
      template, doc: emptyDay('2026-08-10', 'mon'), checkId: 'read-scripture',
      done: true, at: AT, rand: 'aaaaaa', ledger: [],
    }),
    (err) => err instanceof CheckNotActiveError
      && err.name === 'CheckNotActiveError'
      && err.checkId === 'read-scripture'
      && err.date === '2026-08-10'
  );
});

test('applyCheckToggle rejects a check retired before this day', () => {
  const template = {
    ...T,
    checks: { ...T.checks, 'health': { ...T.checks.health, retiredOn: '2026-08-10' } },
  };
  assert.throws(
    () => applyCheckToggle({
      template, doc: emptyDay('2026-08-10', 'mon'), checkId: 'health',
      done: true, at: AT, rand: 'aaaaaa', ledger: [],
    }),
    (err) => err instanceof CheckNotActiveError
  );
});

test('applyCheckToggle still allows a check inside its window', () => {
  const template = {
    ...T,
    checks: { ...T.checks, 'health': {
      ...T.checks.health, activeFrom: '2026-08-01', retiredOn: '2026-09-01',
    } },
  };
  const { doc } = applyCheckToggle({
    template, doc: emptyDay('2026-08-10', 'mon'), checkId: 'health',
    done: true, at: AT, rand: 'aaaaaa', ledger: [],
  });
  assert.deepEqual(doc.checks.health, { done: true, at: AT });
});

test('ticking a one-off override block earns coins', () => {
  // The case the old template-scanning findBlock threw `unknown block` on.
  const base = blocksFor(T, 'tue', null);
  const entries = base.map(b => ({ id: b.id, start: b.start, end: b.end, hours: b.hours, fields: null }));
  entries.splice(4, 0, {
    id: '2026-08-18-writeup', start: '11:30', end: '12:00', hours: 0.5,
    fields: {
      label: 'Write the report', detail: '', attribute: 'dataeng', kind: 'fixed',
      taskId: 'the-report', campaignSlot: false, streakId: null,
      calendar: { event: false, remindMinutes: 10 },
    },
  });
  entries[5] = { ...entries[5], start: '12:00', hours: 0.5 };

  const doc = {
    ...emptyDay('2026-08-18', 'tue'),
    blocksOverride: entries, blocksOverrideAt: AT,
  };
  const blocks = resolveBlocks(T, 'tue', null, doc);

  const { doc: after, ledgerEntries } = applyBlockToggle({
    template: T, blocks, doc, blockId: '2026-08-18-writeup',
    done: true, at: AT, rand: 'bbbbbb', ledger: [],
  });
  assert.deepEqual(after.blocks['2026-08-18-writeup'], { done: true, at: AT });
  assert.equal(ledgerEntries.length, 1);
  assert.equal(ledgerEntries[0].refId, 'the-report');
  assert.equal(ledgerEntries[0].amount, T.tasks['the-report'].coins);
});

test('setBlocksOverride records the snapshot and the moment it was taken', () => {
  const snap = blocksFor(T, 'tue', null)
    .map(b => ({ id: b.id, start: b.start, end: b.end, hours: b.hours, fields: null }));
  const { doc } = setBlocksOverride({
    doc: emptyDay('2026-08-18', 'tue'), blocksOverride: snap, at: AT,
  });
  assert.equal(doc.blocksOverride.length, 12);
  assert.equal(doc.blocksOverrideAt, AT);
  assert.equal(doc.updatedAt, AT);
});

test('clearBlocksOverride nulls the list but keeps a stamp so the clear can win', () => {
  const snap = blocksFor(T, 'tue', null)
    .map(b => ({ id: b.id, start: b.start, end: b.end, hours: b.hours, fields: null }));
  const set = setBlocksOverride({ doc: emptyDay('2026-08-18', 'tue'), blocksOverride: snap, at: AT }).doc;
  const later = '2026-08-18T20:00:00.000Z';
  const { doc } = clearBlocksOverride({ doc: set, at: later });
  assert.equal(doc.blocksOverride, null);
  assert.equal(doc.blocksOverrideAt, later);
});
