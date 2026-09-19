import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadTemplate } from '../src/data/load.js';
import { toMinutes, blocksFor, allBlockLists, sumHours, clientHours, listKey, withBlockList, resolveBlocks } from '../src/schedule.js';

const T = loadTemplate();

test('toMinutes converts HH:MM', () => {
  assert.equal(toMinutes('06:00'), 360);
  assert.equal(toMinutes('22:30'), 1350);
});

test('every day and branch sums to the waking budget', () => {
  for (const { dow, branch, blocks } of allBlockLists(T)) {
    assert.equal(
      sumHours(blocks), T.wakingBudgetHours,
      `${dow}${branch ? '/' + branch : ''} sums to ${sumHours(blocks)}`
    );
  }
});

test('blocks are contiguous from wake to sleep with no gaps or overlaps', () => {
  for (const { dow, branch, blocks } of allBlockLists(T)) {
    const label = `${dow}${branch ? '/' + branch : ''}`;
    assert.equal(blocks[0].start, T.wake, `${label} does not start at wake`);
    assert.equal(blocks.at(-1).end, T.sleep, `${label} does not end at sleep`);
    for (let i = 1; i < blocks.length; i++) {
      assert.equal(
        blocks[i].start, blocks[i - 1].end,
        `${label}: gap or overlap before ${blocks[i].id}`
      );
    }
  }
});

test('each block hours equals end minus start', () => {
  for (const { dow, blocks } of allBlockLists(T)) {
    for (const b of blocks) {
      const span = (toMinutes(b.end) - toMinutes(b.start)) / 60;
      assert.equal(b.hours, span, `${dow}: ${b.id} hours ${b.hours} != span ${span}`);
    }
  }
});

test('exactly one campaign slot per day and branch', () => {
  for (const { dow, branch, blocks } of allBlockLists(T)) {
    const n = blocks.filter(b => b.campaignSlot).length;
    assert.equal(n, 1, `${dow}${branch ? '/' + branch : ''} has ${n} campaign slots`);
  }
});

test('every streakId and taskId referenced by a block is declared', () => {
  for (const { blocks } of allBlockLists(T)) {
    for (const b of blocks) {
      if (b.streakId) assert.ok(T.streaks[b.streakId], `unknown streakId ${b.streakId}`);
      if (b.taskId) assert.ok(T.tasks[b.taskId], `unknown taskId ${b.taskId}`);
      assert.ok(T.attributes[b.attribute], `unknown attribute ${b.attribute}`);
    }
  }
});

test('block ids are globally unique', () => {
  const seen = new Set();
  for (const { blocks } of allBlockLists(T)) {
    for (const b of blocks) {
      assert.ok(!seen.has(b.id), `duplicate block id ${b.id}`);
      seen.add(b.id);
    }
  }
});

test('client hours are 17.0 core, 33.0 with surge when both MW run branch B', () => {
  const h = clientHours(T, { monBranch: 'B', wedBranch: 'B' });
  assert.equal(h.core, 17.0);
  assert.equal(h.total, 33.0);
});

test('blocksFor returns the branch asked for', () => {
  assert.equal(blocksFor(T, 'mon', 'A')[7].id, 'mon-a-class');
  assert.ok(blocksFor(T, 'mon', 'B').every(b => b.id.startsWith('mon-b-')));
  assert.equal(blocksFor(T, 'tue', null).length, 12);
});

test('every check declares a taskId that is either null or a real task', () => {
  for (const [id, check] of Object.entries(T.checks)) {
    assert.ok('taskId' in check, `check ${id} has no taskId field`);
    if (check.taskId !== null) {
      assert.ok(T.tasks[check.taskId], `check ${id} names unknown task ${check.taskId}`);
    }
    assert.ok(T.attributes[check.attribute], `check ${id} names unknown attribute ${check.attribute}`);
  }
});

test('listKey matches the identity allBlockLists produces', () => {
  assert.equal(listKey('tue', null), 'tue');
  assert.equal(listKey('mon', 'A'), 'mon/A');
  for (const { dow, branch } of allBlockLists(T)) {
    assert.equal(typeof listKey(dow, branch), 'string');
  }
  const keys = allBlockLists(T).map(({ dow, branch }) => listKey(dow, branch));
  assert.equal(new Set(keys).size, keys.length);
  assert.equal(keys.length, 9);
});

test('withBlockList replaces one list and leaves every other alone', () => {
  const replacement = [{ ...blocksFor(T, 'tue', null)[0], id: 'tue-only', end: T.sleep, hours: 16.5 }];
  const days = withBlockList(T.days, 'tue', null, replacement);
  assert.equal(days.tue.blocks.length, 1);
  assert.equal(days.tue.blocks[0].id, 'tue-only');
  assert.equal(days.wed.branches.A.length, T.days.wed.branches.A.length);
  // The input is untouched.
  assert.equal(T.days.tue.blocks.length, 12);
});

test('withBlockList writes into a branch without disturbing its twin', () => {
  const replacement = [{ ...blocksFor(T, 'mon', 'A')[0], id: 'mon-a-only', end: T.sleep, hours: 16.5 }];
  const days = withBlockList(T.days, 'mon', 'A', replacement);
  assert.equal(days.mon.branches.A.length, 1);
  assert.equal(days.mon.branches.B.length, T.days.mon.branches.B.length);
});

// A day document carrying a structural snapshot. `fields: null` on every entry
// means resolve everything non-structural from the template block with this id.
function override(entries) {
  return {
    _id: 'day:2026-08-18', type: 'day', date: '2026-08-18', dow: 'tue',
    branch: null, blocks: {}, checks: {},
    blocksOverride: entries, blocksOverrideAt: '2026-08-18T14:02:56.117Z',
  };
}

const snap = (b, over = {}) => ({ id: b.id, start: b.start, end: b.end, hours: b.hours, fields: null, ...over });

test('resolveBlocks returns the template list when there is no override', () => {
  assert.deepEqual(resolveBlocks(T, 'tue', null, null), blocksFor(T, 'tue', null));
  assert.deepEqual(resolveBlocks(T, 'tue', null, undefined), blocksFor(T, 'tue', null));
  assert.deepEqual(resolveBlocks(T, 'tue', null, { blocksOverride: null }), blocksFor(T, 'tue', null));
  assert.deepEqual(resolveBlocks(T, 'mon', 'A', null), blocksFor(T, 'mon', 'A'));
});

test('a retime-only override moves the times and leaves the fields live', () => {
  const base = blocksFor(T, 'tue', null);
  const entries = base.map(b => snap(b));
  entries[2] = { ...entries[2], end: '11:00', hours: 3.5 };
  entries[3] = { ...entries[3], start: '11:00', hours: 0.5 };

  const resolved = resolveBlocks(T, 'tue', null, override(entries));
  assert.equal(resolved.length, 12);
  assert.equal(resolved[2].end, '11:00');
  assert.equal(resolved[2].hours, 3.5);
  // Everything non-structural still comes from the template block.
  assert.equal(resolved[2].label, 'Client Work (CORE)');
  assert.equal(resolved[2].taskId, 'deep-block');
  assert.equal(resolved[2].streakId, 'client-core');
  assert.equal(resolved[3].campaignSlot, true);
});

test('a relabelled template block reaches a date that was overridden earlier', () => {
  const entries = blocksFor(T, 'tue', null).map(b => snap(b));
  const renamed = {
    ...T,
    days: withBlockList(T.days, 'tue', null,
      blocksFor(T, 'tue', null).map(b => (b.id === 'tue-lunch' ? { ...b, label: 'Lunch' } : b))),
  };
  const resolved = resolveBlocks(renamed, 'tue', null, override(entries));
  assert.equal(resolved.find(b => b.id === 'tue-lunch').label, 'Lunch');
});

test('a one-off block carries its fields inline', () => {
  const base = blocksFor(T, 'tue', null);
  const entries = base.map(b => snap(b));
  entries.splice(4, 0, {
    id: '2026-08-18-dentist', start: '11:30', end: '12:00', hours: 0.5,
    fields: {
      label: 'Dentist', detail: 'Molar.', attribute: 'lifeskills', kind: 'fixed',
      taskId: null, campaignSlot: false, streakId: null,
      calendar: { event: true, remindMinutes: 30 },
    },
  });
  entries[5] = { ...entries[5], start: '12:00', hours: 0.5 };

  const resolved = resolveBlocks(T, 'tue', null, override(entries));
  const one = resolved.find(b => b.id === '2026-08-18-dentist');
  assert.equal(one.label, 'Dentist');
  assert.equal(one.attribute, 'lifeskills');
  assert.equal(one.start, '11:30');
  assert.equal(one.hours, 0.5);
  assert.equal(one.tombstone, undefined);
});

test('a snapshotted id the template no longer has becomes a tombstone', () => {
  const entries = blocksFor(T, 'tue', null).map(b => snap(b));
  const shrunk = {
    ...T,
    days: withBlockList(T.days, 'tue', null,
      blocksFor(T, 'tue', null).filter(b => b.id !== 'tue-lunch')),
  };
  const resolved = resolveBlocks(shrunk, 'tue', null, override(entries));
  const dead = resolved.find(b => b.id === 'tue-lunch');
  assert.equal(dead.tombstone, true);
  assert.equal(dead.attribute, null);
  assert.equal(dead.taskId, null);
  assert.equal(dead.streakId, null);
  assert.equal(dead.campaignSlot, false);
  assert.equal(dead.calendar.event, false);
  // It keeps its interval, so the day is still a partition.
  assert.equal(dead.start, '11:30');
  assert.equal(dead.end, '12:30');
});

test('an override taken on one branch still resolves after the branch flips', () => {
  const entries = blocksFor(T, 'mon', 'A').map(b => snap(b));
  const doc = { ...override(entries), dow: 'mon', branch: 'B' };
  const resolved = resolveBlocks(T, 'mon', 'B', doc);
  assert.equal(resolved.length, blocksFor(T, 'mon', 'A').length);
  assert.ok(resolved.every(b => !b.tombstone));
  assert.equal(resolved[0].label, blocksFor(T, 'mon', 'A')[0].label);
});
