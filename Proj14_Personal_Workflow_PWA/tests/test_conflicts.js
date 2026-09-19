import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mergeDayDocs, mergeTodoDocs, mergeTemplateDocs } from '../src/conflicts.js';

// A day doc with explicit revs so the merge result can be checked precisely.
function rev(_rev, { blocks = {}, checks = {}, branch, branchSetAt, updatedAt = '2026-08-10T00:00:00.000Z' } = {}) {
  const doc = {
    _id: 'day:2026-08-10', _rev, type: 'day', date: '2026-08-10', dow: 'mon',
    blocks, checks, updatedAt,
  };
  if (branch !== undefined) { doc.branch = branch; doc.branchSetAt = branchSetAt; }
  return doc;
}

const done = (at) => ({ done: true, at });
const undone = (at) => ({ done: false, at });

test('a single revision is returned unchanged with no losers', () => {
  const only = rev('2-aaa', { blocks: { 'mon-a-topfocus': done('2026-08-10T06:28:00.000Z') } });
  const { merged, losers } = mergeDayDocs([only]);
  assert.deepEqual(merged, only);
  assert.deepEqual(losers, []);
});

test('the later at wins for a block ticked on both devices', () => {
  const winner = rev('2-aaa', { blocks: { 'mon-a-client1': undone('2026-08-10T10:00:00.000Z') } });
  const loser  = rev('2-bbb', { blocks: { 'mon-a-client1': done('2026-08-10T11:00:00.000Z') } });
  const { merged } = mergeDayDocs([winner, loser]);
  assert.deepEqual(merged.blocks['mon-a-client1'], done('2026-08-10T11:00:00.000Z'));
});

test('an exact tie on at prefers done true', () => {
  const at = '2026-08-10T10:00:00.000Z';
  const a = rev('2-aaa', { blocks: { 'mon-a-client1': undone(at) } });
  const b = rev('2-bbb', { blocks: { 'mon-a-client1': done(at) } });
  assert.equal(mergeDayDocs([a, b]).merged.blocks['mon-a-client1'].done, true);
  // Order of the losing revisions must not change the answer.
  assert.equal(mergeDayDocs([b, a]).merged.blocks['mon-a-client1'].done, true);
});

test('blocks present in only one revision survive the merge', () => {
  const a = rev('2-aaa', { blocks: { 'mon-a-topfocus': done('2026-08-10T06:00:00.000Z') } });
  const b = rev('2-bbb', { blocks: { 'mon-a-client1':  done('2026-08-10T10:00:00.000Z') } });
  const { merged } = mergeDayDocs([a, b]);
  assert.deepEqual(Object.keys(merged.blocks).sort(), ['mon-a-client1', 'mon-a-topfocus']);
});

test('checks merge by the same rule as blocks', () => {
  const a = rev('2-aaa', { checks: { 'sleep-cap': undone('2026-08-10T06:00:00.000Z') } });
  const b = rev('2-bbb', { checks: { 'sleep-cap': done('2026-08-10T07:00:00.000Z') } });
  const { merged } = mergeDayDocs([a, b]);
  assert.equal(merged.checks['sleep-cap'].done, true);
});

test('branch resolves to the later branchSetAt', () => {
  const a = rev('2-aaa', { branch: 'A', branchSetAt: '2026-08-10T05:58:00.000Z' });
  const b = rev('2-bbb', { branch: 'B', branchSetAt: '2026-08-10T06:10:00.000Z' });
  assert.equal(mergeDayDocs([a, b]).merged.branch, 'B');
  assert.equal(mergeDayDocs([b, a]).merged.branch, 'B');
});

test('a revision that never set a branch does not clear one that did', () => {
  const withBranch = rev('2-aaa', { branch: 'B', branchSetAt: '2026-08-10T06:10:00.000Z' });
  const without    = rev('2-bbb');
  assert.equal(mergeDayDocs([without, withBranch]).merged.branch, 'B');
});

test('an unknown block id is preserved, not dropped', () => {
  const a = rev('2-aaa', { blocks: { 'retired-block-id': done('2026-08-10T09:00:00.000Z') } });
  const b = rev('2-bbb', { blocks: {} });
  assert.ok('retired-block-id' in mergeDayDocs([a, b]).merged.blocks);
});

test('the merged doc keeps the winning rev and lists every loser', () => {
  const a = rev('2-aaa');
  const b = rev('2-bbb');
  const c = rev('2-ccc');
  const { merged, losers } = mergeDayDocs([a, b, c]);
  assert.equal(merged._rev, '2-aaa');
  assert.deepEqual(losers, [
    { _id: 'day:2026-08-10', _rev: '2-bbb' },
    { _id: 'day:2026-08-10', _rev: '2-ccc' },
  ]);
});

test('updatedAt becomes the latest across all revisions', () => {
  const a = rev('2-aaa', { updatedAt: '2026-08-10T06:00:00.000Z' });
  const b = rev('2-bbb', { updatedAt: '2026-08-10T11:30:00.000Z' });
  assert.equal(mergeDayDocs([a, b]).merged.updatedAt, '2026-08-10T11:30:00.000Z');
});

test('the input revisions are not mutated', () => {
  const a = rev('2-aaa', { blocks: { 'mon-a-client1': undone('2026-08-10T10:00:00.000Z') } });
  const b = rev('2-bbb', { blocks: { 'mon-a-client1': done('2026-08-10T11:00:00.000Z') } });
  mergeDayDocs([a, b]);
  assert.equal(a.blocks['mon-a-client1'].done, false);
});

test('an empty revision list throws rather than returning something meaningless', () => {
  assert.throws(() => mergeDayDocs([]), /at least one revision/);
});

test('a nudge on the losing revision survives the merge', () => {
  const base = {
    _id: 'day:2026-08-11', _rev: '2-a', type: 'day', date: '2026-08-11', dow: 'tue',
    branch: null, branchSetAt: null, blocks: {}, checks: {},
    sleepOverride: null, sleepOverrideAt: null,
    wakeOverride: null, wakeOverrideAt: null, updatedAt: null,
  };
  const winner = { ...base };
  const loser = {
    ...base, _rev: '2-b',
    sleepOverride: '23:15', sleepOverrideAt: '2026-08-11T22:00:00.000Z',
    updatedAt: '2026-08-11T22:00:00.000Z',
  };

  const { merged } = mergeDayDocs([winner, loser]);
  assert.equal(merged.sleepOverride, '23:15');
  assert.equal(merged.sleepOverrideAt, '2026-08-11T22:00:00.000Z');
});

test('a wake nudge and a sleep nudge on different revisions both survive', () => {
  const base = {
    _id: 'day:2026-08-11', _rev: '2-a', type: 'day', date: '2026-08-11', dow: 'tue',
    branch: null, branchSetAt: null, blocks: {}, checks: {},
    sleepOverride: null, sleepOverrideAt: null,
    wakeOverride: null, wakeOverrideAt: null, updatedAt: null,
  };
  const a = {
    ...base,
    sleepOverride: '23:15', sleepOverrideAt: '2026-08-11T22:00:00.000Z',
    updatedAt: '2026-08-11T22:00:00.000Z',
  };
  const b = {
    ...base, _rev: '2-b',
    wakeOverride: '07:00', wakeOverrideAt: '2026-08-11T22:05:00.000Z',
    updatedAt: '2026-08-11T22:05:00.000Z',
  };

  const { merged } = mergeDayDocs([a, b]);
  assert.equal(merged.sleepOverride, '23:15');
  assert.equal(merged.wakeOverride, '07:00');
});

test('the later of two competing nudges wins', () => {
  const base = {
    _id: 'day:2026-08-11', _rev: '2-a', type: 'day', date: '2026-08-11', dow: 'tue',
    branch: null, branchSetAt: null, blocks: {}, checks: {},
    sleepOverride: null, sleepOverrideAt: null,
    wakeOverride: null, wakeOverrideAt: null, updatedAt: null,
  };
  const early = { ...base, sleepOverride: '23:00', sleepOverrideAt: '2026-08-11T22:00:00.000Z' };
  const late = { ...base, _rev: '2-b', sleepOverride: '23:45', sleepOverrideAt: '2026-08-11T22:30:00.000Z' };

  assert.equal(mergeDayDocs([early, late]).merged.sleepOverride, '23:45');
  assert.equal(mergeDayDocs([late, early]).merged.sleepOverride, '23:45');
});

function todoRev(_rev, { text = 'buy milk', done = false, updatedAt } = {}) {
  return {
    _id: 'todo:2026-08-12T09:00:00.000Z:a1b2c3', _rev, type: 'todo',
    text, note: '', due: null, pinned: false, done, doneAt: null,
    createdAt: '2026-08-12T09:00:00.000Z', updatedAt,
  };
}

test('the todo revision with the later updatedAt wins whole', () => {
  const a = todoRev('2-aaa', { text: 'buy milk', updatedAt: '2026-08-12T10:00:00.000Z' });
  const b = todoRev('2-bbb', { text: 'buy oat milk', updatedAt: '2026-08-12T11:00:00.000Z' });
  assert.equal(mergeTodoDocs([a, b]).merged.text, 'buy oat milk');
  // Order of the revisions must not change the answer.
  assert.equal(mergeTodoDocs([b, a]).merged.text, 'buy oat milk');
});

test('a todo merge lists every revision that lost', () => {
  const a = todoRev('2-aaa', { updatedAt: '2026-08-12T12:00:00.000Z' });
  const b = todoRev('2-bbb', { updatedAt: '2026-08-12T10:00:00.000Z' });
  const { losers } = mergeTodoDocs([a, b]);
  assert.deepEqual(losers, [{ _id: a._id, _rev: '2-bbb' }]);
});

test('an exact tie on updatedAt keeps the CouchDB winner', () => {
  const at = '2026-08-12T10:00:00.000Z';
  const a = todoRev('2-aaa', { text: 'first', updatedAt: at });
  const b = todoRev('2-bbb', { text: 'second', updatedAt: at });
  assert.equal(mergeTodoDocs([a, b]).merged.text, 'first');
});

test('the winning todo keeps the CouchDB winning rev, not its own', () => {
  const a = todoRev('2-aaa', { updatedAt: '2026-08-12T10:00:00.000Z' });
  const b = todoRev('2-bbb', { text: 'newer', updatedAt: '2026-08-12T11:00:00.000Z' });
  const { merged } = mergeTodoDocs([a, b]);
  assert.equal(merged.text, 'newer');
  assert.equal(merged._rev, '2-aaa');
});

test('a single todo revision is returned unchanged with no losers', () => {
  const only = todoRev('2-aaa', { updatedAt: '2026-08-12T10:00:00.000Z' });
  const { merged, losers } = mergeTodoDocs([only]);
  assert.deepEqual(merged, only);
  assert.deepEqual(losers, []);
});

test('an empty todo revision list throws', () => {
  assert.throws(() => mergeTodoDocs([]), /at least one revision/);
});

// A template revision carrying only the maps the merge rebuilds, plus one
// scalar to prove the winner supplies everything else.
function tmpl(_rev, { checks = {}, tasks = {}, streaks = {}, backfillDays = 3 } = {}) {
  return {
    _id: 'schedule:v1', _rev, type: 'schedule', version: 1,
    backfillDays, checks, tasks, streaks,
  };
}

const stamped = (updatedAt, extra = {}) => ({ updatedAt, ...extra });

test('mergeTemplateDocs returns a single revision unchanged', () => {
  const only = tmpl('4-aaa', { checks: { health: stamped('2026-08-12T09:00:00.000Z') } });
  const { merged, losers } = mergeTemplateDocs([only]);
  assert.deepEqual(merged, only);
  assert.deepEqual(losers, []);
});

test('two devices adding different checks both survive', () => {
  const phone = tmpl('5-aaa', {
    checks: { health: stamped('2026-08-01T00:00:00.000Z'),
              'read-scripture': stamped('2026-08-12T09:00:00.000Z', { label: 'Read scripture' }) },
  });
  const desktop = tmpl('5-bbb', {
    checks: { health: stamped('2026-08-01T00:00:00.000Z'),
              'stretch': stamped('2026-08-12T10:00:00.000Z', { label: 'Stretch' }) },
  });
  const { merged, losers } = mergeTemplateDocs([phone, desktop]);
  assert.deepEqual(Object.keys(merged.checks).sort(), ['health', 'read-scripture', 'stretch']);
  assert.equal(merged.checks['read-scripture'].label, 'Read scripture');
  assert.equal(merged.checks['stretch'].label, 'Stretch');
  assert.deepEqual(losers, [{ _id: 'schedule:v1', _rev: '5-bbb' }]);
});

test('the newest updatedAt wins when the same check was edited twice', () => {
  const a = tmpl('5-aaa', { checks: { health: stamped('2026-08-12T09:00:00.000Z', { label: 'Old' }) } });
  const b = tmpl('5-bbb', { checks: { health: stamped('2026-08-12T21:00:00.000Z', { label: 'New' }) } });
  const { merged } = mergeTemplateDocs([a, b]);
  assert.equal(merged.checks.health.label, 'New');
});

test('tasks and streaks merge the same way as checks', () => {
  const a = tmpl('5-aaa', {
    tasks: { 'check-a': stamped('2026-08-12T09:00:00.000Z', { coins: 10 }) },
    streaks: { 'a': { label: 'A', source: 'check', appliesOn: ['mon'] } },
  });
  const b = tmpl('5-bbb', {
    tasks: { 'check-b': stamped('2026-08-12T10:00:00.000Z', { coins: 20 }) },
    streaks: { 'b': { label: 'B', source: 'check', appliesOn: ['tue'] } },
  });
  const { merged } = mergeTemplateDocs([a, b]);
  assert.deepEqual(Object.keys(merged.tasks).sort(), ['check-a', 'check-b']);
  assert.deepEqual(Object.keys(merged.streaks).sort(), ['a', 'b']);
});

test('an entry with no stamp never outranks one that has it', () => {
  const a = tmpl('5-aaa', { checks: { health: { label: 'Unstamped' } } });
  const b = tmpl('5-bbb', { checks: { health: stamped('2026-08-12T09:00:00.000Z', { label: 'Stamped' }) } });
  assert.equal(mergeTemplateDocs([a, b]).merged.checks.health.label, 'Stamped');
  assert.equal(mergeTemplateDocs([b, a]).merged.checks.health.label, 'Stamped');
});

test('every field the merge does not rebuild comes from the winner', () => {
  const winner = tmpl('5-aaa', { backfillDays: 3 });
  const loser = tmpl('5-bbb', { backfillDays: 99 });
  const { merged } = mergeTemplateDocs([winner, loser]);
  assert.equal(merged.backfillDays, 3);
  assert.equal(merged._rev, '5-aaa');
});

test('the merged result is not aliased to any input revision', () => {
  const a = tmpl('5-aaa', { checks: { health: stamped('2026-08-12T09:00:00.000Z') } });
  const { merged } = mergeTemplateDocs([a, tmpl('5-bbb')]);
  merged.checks.health.label = 'mutated';
  assert.equal(a.checks.health.label, undefined);
});

import { loadTemplate } from '../src/data/load.js';
import { blocksFor, listKey } from '../src/schedule.js';

const TPL = loadTemplate();

function dayRev(_rev, extra = {}) {
  return {
    _id: 'day:2026-08-18', _rev, type: 'day', date: '2026-08-18', dow: 'tue',
    branch: null, branchSetAt: null, blocks: {}, checks: {},
    blocksOverride: null, blocksOverrideAt: null, updatedAt: null, ...extra,
  };
}

const snapshot = (blocks) =>
  blocks.map(b => ({ id: b.id, start: b.start, end: b.end, hours: b.hours, fields: null }));

// A template revision carrying real days, so the list merge has something to
// pick between.
function tmplDays(_rev, { dow = 'tue', branch = null, blocks, updatedAt = null, epoch = null } = {}) {
  const key = listKey(dow, branch);
  const base = { ...TPL, _id: 'schedule:v1', _rev };
  return {
    ...base,
    days: blocks ? { ...TPL.days, [dow]: { ...TPL.days[dow], blocks } } : TPL.days,
    daysUpdatedAt: { [key]: updatedAt },
    daysStreakEpoch: { [key]: epoch },
  };
}

test('an override on one device survives a tick on the other', () => {
  const snap = snapshot(blocksFor(TPL, 'tue', null));
  const phone = dayRev('3-aaa', {
    blocksOverride: snap, blocksOverrideAt: '2026-08-18T09:00:00.000Z',
    updatedAt: '2026-08-18T09:00:00.000Z',
  });
  const desktop = dayRev('3-bbb', {
    blocks: { 'tue-lunch': { done: true, at: '2026-08-18T12:30:00.000Z' } },
    updatedAt: '2026-08-18T12:30:00.000Z',
  });
  const { merged } = mergeDayDocs([desktop, phone]);
  assert.equal(merged.blocksOverride.length, 12);
  assert.equal(merged.blocksOverrideAt, '2026-08-18T09:00:00.000Z');
  assert.deepEqual(merged.blocks['tue-lunch'], { done: true, at: '2026-08-18T12:30:00.000Z' });
});

test('the newest blocksOverrideAt wins', () => {
  const early = dayRev('4-aaa', {
    blocksOverride: snapshot(blocksFor(TPL, 'tue', null)),
    blocksOverrideAt: '2026-08-18T09:00:00.000Z',
  });
  const late = dayRev('4-bbb', {
    blocksOverride: snapshot(blocksFor(TPL, 'tue', null)).slice(0, 3),
    blocksOverrideAt: '2026-08-18T18:00:00.000Z',
  });
  assert.equal(mergeDayDocs([early, late]).merged.blocksOverride.length, 3);
  assert.equal(mergeDayDocs([late, early]).merged.blocksOverride.length, 3);
});

test('clearing an override can win, because the clear is stamped', () => {
  const set = dayRev('4-aaa', {
    blocksOverride: snapshot(blocksFor(TPL, 'tue', null)),
    blocksOverrideAt: '2026-08-18T09:00:00.000Z',
  });
  const cleared = dayRev('4-bbb', {
    blocksOverride: null, blocksOverrideAt: '2026-08-18T18:00:00.000Z',
  });
  assert.equal(mergeDayDocs([set, cleared]).merged.blocksOverride, null);
});

test('a day revision with no override stamp never outranks one that has it', () => {
  const stamped = dayRev('4-aaa', {
    blocksOverride: snapshot(blocksFor(TPL, 'tue', null)),
    blocksOverrideAt: '2026-08-18T09:00:00.000Z',
  });
  const never = dayRev('4-bbb');
  assert.equal(mergeDayDocs([never, stamped]).merged.blocksOverride.length, 12);
});

test('two edits to the same weekday resolve to the newer, list and all', () => {
  const short = blocksFor(TPL, 'tue', null).map((b, i) =>
    (i === 2 ? { ...b, end: '10:00', hours: 2.5 } : i === 3 ? { ...b, start: '10:00', hours: 1.5 } : b));
  const long = blocksFor(TPL, 'tue', null).map((b, i) =>
    (i === 2 ? { ...b, end: '11:00', hours: 3.5 } : i === 3 ? { ...b, start: '11:00', hours: 0.5 } : b));

  const a = tmplDays('5-aaa', { blocks: short, updatedAt: '2026-08-18T09:00:00.000Z' });
  const b = tmplDays('5-bbb', { blocks: long, updatedAt: '2026-08-18T18:00:00.000Z' });

  const { merged } = mergeTemplateDocs([a, b]);
  assert.equal(merged.days.tue.blocks[2].end, '11:00');
  assert.equal(merged.days.tue.blocks[3].start, '11:00');
  assert.equal(merged.daysUpdatedAt.tue, '2026-08-18T18:00:00.000Z');
  // Whole lists, so no block from the losing revision leaks in.
  assert.equal(merged.days.tue.blocks[2].hours, 3.5);
});

test('the streak epoch travels with the list that won', () => {
  const a = tmplDays('5-aaa', {
    blocks: blocksFor(TPL, 'tue', null),
    updatedAt: '2026-08-18T09:00:00.000Z', epoch: '2026-08-18',
  });
  const b = tmplDays('5-bbb', {
    blocks: blocksFor(TPL, 'tue', null),
    updatedAt: '2026-08-18T18:00:00.000Z', epoch: null,
  });
  // b is newer and set no epoch, so the merged template must not inherit a's.
  assert.equal(mergeTemplateDocs([a, b]).merged.daysStreakEpoch.tue, null);
  assert.equal(mergeTemplateDocs([b, a]).merged.daysStreakEpoch.tue, null);
});

test('edits to different weekdays on two devices both survive', () => {
  const tue = blocksFor(TPL, 'tue', null).map((b, i) =>
    (i === 2 ? { ...b, end: '11:00', hours: 3.5 } : i === 3 ? { ...b, start: '11:00', hours: 0.5 } : b));
  const thu = blocksFor(TPL, 'thu', null).map((b, i) => (i === 0 ? { ...b, label: 'Prayer' } : b));

  const a = { ...tmplDays('5-aaa', { blocks: tue, updatedAt: '2026-08-18T09:00:00.000Z' }) };
  const b = {
    ...TPL, _id: 'schedule:v1', _rev: '5-bbb',
    days: { ...TPL.days, thu: { ...TPL.days.thu, blocks: thu } },
    daysUpdatedAt: { thu: '2026-08-18T10:00:00.000Z' },
    daysStreakEpoch: { thu: null },
  };

  const { merged } = mergeTemplateDocs([a, b]);
  assert.equal(merged.days.tue.blocks[2].end, '11:00');
  assert.equal(merged.days.thu.blocks[0].label, 'Prayer');
});
