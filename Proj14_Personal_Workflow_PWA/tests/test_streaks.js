import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadTemplate, loadCampaign } from '../src/data/load.js';
import { weekKeyOf, isLocked, evaluateStreak, dayStatus } from '../src/streaks.js';
import { blocksFor, withBlockList } from '../src/schedule.js';
import { putBlockList, editFields, placeBlock, moveBoundary } from '../src/block-edit.js';

const T = loadTemplate();
const C = loadCampaign();

// A template with one weekday's block list replaced.
function withDay(dow, blocks) {
  return { ...T, days: withBlockList(T.days, dow, null, blocks) };
}

const snapOf = (b) => ({ id: b.id, start: b.start, end: b.end, hours: b.hours, fields: null });

// Build a day doc where the named block or check is done.
function day(date, { branch = null, blocks = [], checks = [] } = {}) {
  const at = `${date}T08:00:00.000Z`;
  return {
    _id: `day:${date}`, type: 'day', date, branch,
    blocks: Object.fromEntries(blocks.map(id => [id, { done: true, at }])),
    checks: Object.fromEntries(checks.map(id => [id, { done: true, at }])),
  };
}

const ev = (streakId, dayDocs, from, today) =>
  evaluateStreak({ template: T, campaign: C, streakId, dayDocs, from, today });

test('weekKeyOf returns the Monday of that week', () => {
  assert.equal(weekKeyOf('2026-08-10'), '2026-08-10'); // a Monday
  assert.equal(weekKeyOf('2026-08-16'), '2026-08-10'); // the Sunday after
  assert.equal(weekKeyOf('2026-08-17'), '2026-08-17'); // next Monday
});

test('a date is locked once it is older than the backfill window', () => {
  assert.equal(isLocked('2026-08-10', '2026-08-13', 3), false);
  assert.equal(isLocked('2026-08-10', '2026-08-14', 3), true);
});

test('a satisfied run increments each applicable day', () => {
  const docs = [
    day('2026-08-10', { branch: 'A', checks: ['sleep-cap'] }),
    day('2026-08-11', { checks: ['sleep-cap'] }),
    day('2026-08-12', { branch: 'A', checks: ['sleep-cap'] }),
  ];
  const r = ev('sleep-cap', docs, '2026-08-10', '2026-08-12');
  assert.equal(r.current, 3);
  assert.equal(r.provisional, false);
});

// NOTE ON DATES IN THESE TESTS: a miss only counts as a miss once the date is
// locked, i.e. more than backfillDays old relative to `today`. Every scenario
// below therefore places its misses well before `today`, otherwise they would
// correctly evaluate as `open` and the assertion would be testing nothing.

test('a miss inside the grace budget keeps the streak alive', () => {
  const docs = [
    day('2026-08-10', { branch: 'A', checks: ['sleep-cap'] }),
    day('2026-08-11', {}),                                    // explicit miss, locked
    day('2026-08-12', { branch: 'A', checks: ['sleep-cap'] }),
    day('2026-08-13', { checks: ['sleep-cap'] }),
    day('2026-08-14', { checks: ['sleep-cap'] }),
    day('2026-08-15', { checks: ['sleep-cap'] }),
    day('2026-08-16', { checks: ['sleep-cap'] }),
  ];
  const r = ev('sleep-cap', docs, '2026-08-10', '2026-08-16');
  assert.equal(r.current, 7);
  assert.equal(r.graceUsedThisWeek, 1);
  assert.equal(r.graceRemaining, 1);
});

test('the third miss in one week resets the streak', () => {
  const docs = [
    day('2026-08-10', { branch: 'A', checks: ['sleep-cap'] }),
    day('2026-08-11', {}),                 // miss 1, grace
    day('2026-08-12', { branch: 'A' }),    // miss 2, grace
    day('2026-08-13', {}),                 // miss 3, budget spent
    // 08-14 onward absent and still inside the window, so they are `open`
    // and cannot mask the reset.
  ];
  const r = ev('sleep-cap', docs, '2026-08-10', '2026-08-17');
  assert.equal(r.current, 0);
  assert.equal(r.provisional, true);
});

test('grace resets on Monday: two misses one week, two the next, both survive', () => {
  const docs = [
    day('2026-08-10', { branch: 'A', checks: ['sleep-cap'] }),
    day('2026-08-11', {}),                 // week 1, miss 1
    day('2026-08-12', { branch: 'A' }),    // week 1, miss 2
    day('2026-08-13', { checks: ['sleep-cap'] }),
    day('2026-08-14', { checks: ['sleep-cap'] }),
    day('2026-08-15', { checks: ['sleep-cap'] }),
    day('2026-08-16', { checks: ['sleep-cap'] }),
    day('2026-08-17', { branch: 'A' }),    // week 2, miss 1
    day('2026-08-18', {}),                 // week 2, miss 2
    day('2026-08-19', { branch: 'A', checks: ['sleep-cap'] }),
    day('2026-08-20', { checks: ['sleep-cap'] }),
    day('2026-08-21', { checks: ['sleep-cap'] }),
    day('2026-08-22', { checks: ['sleep-cap'] }),
    day('2026-08-23', { checks: ['sleep-cap'] }),
  ];
  const r = ev('sleep-cap', docs, '2026-08-10', '2026-08-23');
  assert.equal(r.current, 14);
  assert.equal(r.graceUsedThisWeek, 2);
  assert.equal(r.graceRemaining, 0);
});

test('a day outside appliesOn is skipped: Saturday never breaks the hard-stop streak', () => {
  const docs = [
    day('2026-08-17', { checks: ['hard-stop'] }), // Mon
    day('2026-08-18', { checks: ['hard-stop'] }), // Tue
    day('2026-08-19', { checks: ['hard-stop'] }), // Wed
    day('2026-08-20', { checks: ['hard-stop'] }), // Thu
    day('2026-08-21', { checks: ['hard-stop'] }), // Fri
    day('2026-08-22', {}),                         // Sat, not applicable
    day('2026-08-23', {}),                         // Sun, not applicable
  ];
  const r = ev('hard-stop', docs, '2026-08-17', '2026-08-23');
  assert.equal(r.current, 5);
});

test('a campaign rest day is neutral: no break, no grace consumed', () => {
  const docs = [
    day('2026-08-21', { blocks: ['fri-talk'] }),
    day('2026-08-22', { blocks: ['sat-talk'] }),
    day('2026-08-23', {}),                // Day 7, prescribed rest
    day('2026-08-24', { branch: 'A', blocks: ['mon-a-talk'] }),
  ];
  const r = ev('talk', docs, '2026-08-21', '2026-08-24');
  assert.equal(r.current, 3);
  assert.equal(r.graceUsedThisWeek, 0);
});

test('an absent day inside the window is open: neutral and provisional', () => {
  const docs = [
    day('2026-08-10', { branch: 'A', checks: ['sleep-cap'] }),
    // 2026-08-11 absent entirely
    day('2026-08-12', { branch: 'A', checks: ['sleep-cap'] }),
  ];
  const r = ev('sleep-cap', docs, '2026-08-10', '2026-08-12');
  assert.equal(r.current, 2);
  assert.equal(r.provisional, true);
  assert.equal(r.graceUsedThisWeek, 0);
});

test('the same absent day becomes a miss once locked', () => {
  const docs = [
    day('2026-08-10', { branch: 'A', checks: ['sleep-cap'] }),
    // 2026-08-11 absent entirely, now four days old
    day('2026-08-12', { branch: 'A', checks: ['sleep-cap'] }),
    day('2026-08-13', { checks: ['sleep-cap'] }),
    day('2026-08-14', { checks: ['sleep-cap'] }),
    day('2026-08-15', { checks: ['sleep-cap'] }),
  ];
  const r = ev('sleep-cap', docs, '2026-08-10', '2026-08-15');
  assert.equal(r.provisional, false);
  assert.equal(r.graceUsedThisWeek, 1);
  assert.equal(r.current, 6);
});

test('future days are ignored, not counted as misses', () => {
  const docs = [day('2026-08-10', { branch: 'A', checks: ['sleep-cap'] })];
  const r = ev('sleep-cap', docs, '2026-08-10', '2026-08-10');
  assert.equal(r.current, 1);
});

test('best survives a reset of current', () => {
  const docs = [
    day('2026-08-10', { branch: 'A', checks: ['sleep-cap'] }),
    day('2026-08-11', { checks: ['sleep-cap'] }),
    day('2026-08-12', { branch: 'A', checks: ['sleep-cap'] }),
    day('2026-08-13', { checks: ['sleep-cap'] }),
    day('2026-08-14', {}),   // miss 1, grace, streak reaches 5
    day('2026-08-15', {}),   // miss 2, grace, streak reaches 6
    day('2026-08-16', {}),   // miss 3, budget spent, reset
  ];
  const r = ev('sleep-cap', docs, '2026-08-10', '2026-08-20');
  assert.equal(r.current, 0);
  assert.equal(r.best, 6);
});

test('a block-sourced streak reads the branch actually chosen', () => {
  const docs = [day('2026-08-10', { branch: 'B', blocks: ['mon-b-client1'] })];
  const r = ev('client-core', docs, '2026-08-10', '2026-08-10');
  assert.equal(r.current, 1);
});

test('a day before a check started is skipped, not missed', () => {
  const template = {
    ...T,
    checks: { ...T.checks, 'health': { ...T.checks.health, activeFrom: '2026-08-12' } },
  };
  const status = dayStatus({
    template, campaign: C, streak: T.streaks.health, streakId: 'health',
    dateStr: '2026-08-05', doc: undefined, today: '2026-08-20', backfillDays: 3,
  });
  assert.equal(status, 'skipped');
});

test('a day after a check was retired is skipped, not missed', () => {
  const template = {
    ...T,
    checks: { ...T.checks, 'health': { ...T.checks.health, retiredOn: '2026-08-10' } },
  };
  const status = dayStatus({
    template, campaign: C, streak: T.streaks.health, streakId: 'health',
    dateStr: '2026-08-15', doc: undefined, today: '2026-08-20', backfillDays: 3,
  });
  assert.equal(status, 'skipped');
});

test('a streak on a retired check burns no grace and keeps its count', () => {
  const template = {
    ...T,
    checks: { ...T.checks, 'health': { ...T.checks.health, retiredOn: '2026-08-08' } },
  };
  const dayDocs = [
    { date: '2026-08-05', checks: { health: { done: true, at: 'x' } } },
    { date: '2026-08-06', checks: { health: { done: true, at: 'x' } } },
    { date: '2026-08-07', checks: { health: { done: true, at: 'x' } } },
  ];
  const result = evaluateStreak({
    template, campaign: C, streakId: 'health', dayDocs,
    from: '2026-08-05', today: '2026-08-20',
  });
  assert.equal(result.current, 3);
  assert.equal(result.graceUsedThisWeek, 0);
});

test('a streak whose check does not exist is skipped rather than throwing', () => {
  const template = { ...T, checks: {} };
  const status = dayStatus({
    template, campaign: C, streak: T.streaks.health, streakId: 'health',
    dateStr: '2026-08-15', doc: undefined, today: '2026-08-20', backfillDays: 3,
  });
  assert.equal(status, 'skipped');
});

test('a weekday no block carries the streak on is skipped, not missed', () => {
  // top-focus applies every day; drop the block that carries it on Tuesday.
  const stripped = blocksFor(T, 'tue', null).map(b => ({ ...b, streakId: null }));
  const status = dayStatus({
    template: withDay('tue', stripped), campaign: C, streak: T.streaks['top-focus'],
    streakId: 'top-focus', dateStr: '2026-08-11', doc: undefined,
    today: '2026-08-20', backfillDays: 3,
  });
  assert.equal(status, 'skipped');
});

test('removing the last block carrying a streak costs the streak nothing', () => {
  // top-focus applies every day of the week, tagged on that day's first block.
  // Friday and Sunday are done; Saturday is the day whose tagged block is
  // being removed.
  const docs = [
    day('2026-08-14', { blocks: ['fri-topfocus'] }),
    day('2026-08-16', { blocks: ['sun-topfocus'] }),
  ];
  const args = { campaign: C, streakId: 'top-focus', dayDocs: docs, from: '2026-08-14', today: '2026-08-20' };

  // Before: Saturday is locked and nothing is recorded, so it scores missed and
  // survives only by spending one of the two grace days that week.
  const before = evaluateStreak({ ...args, template: T });
  assert.equal(before.current, 3);

  const stripped = blocksFor(T, 'sat', null).map(b => ({ ...b, streakId: null }));
  const after = evaluateStreak({ ...args, template: withDay('sat', stripped) });
  // After: Saturday is skipped rather than missed. The count drops by the one
  // day that no longer applies, and no grace was spent to keep it alive.
  assert.equal(after.current, 2);
});

test('an override that drops a tagged block skips only that day', () => {
  const kept = blocksFor(T, 'tue', null)
    .filter(b => b.streakId !== 'top-focus')
    .map(snapOf);
  // Give the freed 06:00-06:30 back to the next block so the day still adds up.
  kept[0] = { ...kept[0], start: '06:00', hours: 1.5 };
  const doc = {
    ...day('2026-08-18', {}),
    blocksOverride: kept, blocksOverrideAt: '2026-08-18T06:00:00.000Z',
  };
  const status = dayStatus({
    template: T, campaign: C, streak: T.streaks['top-focus'], streakId: 'top-focus',
    dateStr: '2026-08-18', doc, today: '2026-08-25', backfillDays: 3,
  });
  assert.equal(status, 'skipped');
});

test('an override that keeps the tagged block still judges the day', () => {
  const all = blocksFor(T, 'tue', null).map(snapOf);
  const doc = {
    ...day('2026-08-18', { blocks: ['tue-topfocus'] }),
    blocksOverride: all, blocksOverrideAt: '2026-08-18T06:00:00.000Z',
  };
  assert.equal(dayStatus({
    template: T, campaign: C, streak: T.streaks['top-focus'], streakId: 'top-focus',
    dateStr: '2026-08-18', doc, today: '2026-08-25', backfillDays: 3,
  }), 'satisfied');
});

test('a day whose override has no campaign slot skips the campaign streak', () => {
  const noSlot = blocksFor(T, 'tue', null)
    .filter(b => !b.campaignSlot)
    .map(snapOf);
  noSlot[2] = { ...noSlot[2], end: '11:30', hours: 4 };
  const doc = {
    ...day('2026-08-18', {}),
    blocksOverride: noSlot, blocksOverrideAt: '2026-08-18T06:00:00.000Z',
  };
  assert.equal(dayStatus({
    template: T, campaign: C, streak: T.streaks.talk, streakId: 'talk',
    dateStr: '2026-08-18', doc, today: '2026-08-25', backfillDays: 3,
  }), 'skipped');
});

const EPOCH_AT = '2026-08-18T21:00:00.000Z';
const EPOCH_DAY = '2026-08-18';

// Three days of a satisfied top-focus run, ending before the edit.
const RUN = () => [
  day('2026-08-13', { blocks: ['thu-topfocus'] }),
  day('2026-08-14', { blocks: ['fri-topfocus'] }),
  day('2026-08-15', { blocks: ['sat-topfocus'] }),
];

test('adding a block tagged with an existing streak leaves the past alone', () => {
  const blocks = editFields(blocksFor(T, 'tue', null).map(b => ({ ...b })),
    'tue-reward', { streakId: 'top-focus' });
  const { template } = putBlockList({
    template: T, dow: 'tue', branch: null, blocks, at: EPOCH_AT, today: EPOCH_DAY,
  });
  assert.equal(template.daysStreakEpoch.tue, EPOCH_DAY);

  const before = evaluateStreak({
    template: T, campaign: C, streakId: 'top-focus',
    dayDocs: RUN(), from: '2026-08-13', today: '2026-08-20',
  });
  const after = evaluateStreak({
    template, campaign: C, streakId: 'top-focus',
    dayDocs: RUN(), from: '2026-08-13', today: '2026-08-20',
  });
  assert.equal(after.current, before.current);
  assert.equal(after.graceUsedThisWeek, before.graceUsedThisWeek);
});

test('moving the campaign slot still skips the talk streak for the edit day', () => {
  const blocks = editFields(blocksFor(T, 'tue', null).map(b => ({ ...b })),
    'tue-reward', { campaignSlot: true });
  const { template } = putBlockList({
    template: T, dow: 'tue', branch: null, blocks, at: EPOCH_AT, today: EPOCH_DAY,
  });
  assert.equal(template.daysStreakEpoch.tue, EPOCH_DAY);

  // The epoch guard is per-weekday, not per-streak: any edit to Tuesday's
  // blocks bumps the epoch for every streak that reads Tuesday, even one
  // the edit didn't touch. So the talk streak also gets skipped (not
  // judged) for the edit day, rather than corrupted by it.
  const docs = [day('2026-08-11', { blocks: ['tue-talk'] })];
  const before = evaluateStreak({
    template: T, campaign: C, streakId: 'talk',
    dayDocs: docs, from: '2026-08-11', today: '2026-08-11',
  });
  const after = evaluateStreak({
    template, campaign: C, streakId: 'talk',
    dayDocs: docs, from: '2026-08-11', today: '2026-08-11',
  });
  assert.equal(before.current, 1);
  assert.equal(after.current, 0);
});

test('a day on or after the epoch is judged normally', () => {
  const blocks = editFields(blocksFor(T, 'tue', null).map(b => ({ ...b })),
    'tue-reward', { streakId: 'top-focus' });
  const { template } = putBlockList({
    template: T, dow: 'tue', branch: null, blocks, at: EPOCH_AT, today: EPOCH_DAY,
  });
  // The Tuesday the edit was made: both tagged blocks are now required.
  assert.equal(dayStatus({
    template, campaign: C, streak: T.streaks['top-focus'], streakId: 'top-focus',
    dateStr: EPOCH_DAY, doc: day(EPOCH_DAY, { blocks: ['tue-topfocus'] }),
    today: '2026-08-25', backfillDays: 3,
  }), 'missed');
  assert.equal(dayStatus({
    template, campaign: C, streak: T.streaks['top-focus'], streakId: 'top-focus',
    dateStr: EPOCH_DAY, doc: day(EPOCH_DAY, { blocks: ['tue-topfocus', 'tue-reward'] }),
    today: '2026-08-25', backfillDays: 3,
  }), 'satisfied');
});

test('the epoch on one weekday does not skip another', () => {
  const blocks = editFields(blocksFor(T, 'tue', null).map(b => ({ ...b })),
    'tue-reward', { streakId: 'top-focus' });
  const { template } = putBlockList({
    template: T, dow: 'tue', branch: null, blocks, at: EPOCH_AT, today: EPOCH_DAY,
  });
  // 2026-08-13 is a Thursday, well before the epoch, and untouched by it.
  assert.equal(dayStatus({
    template, campaign: C, streak: T.streaks['top-focus'], streakId: 'top-focus',
    dateStr: '2026-08-13', doc: day('2026-08-13', {}),
    today: '2026-08-25', backfillDays: 3,
  }), 'missed');
});

test('a pure retime sets no epoch and skips nothing', () => {
  const blocks = moveBoundary(blocksFor(T, 'tue', null).map(b => ({ ...b })), 2, '11:00');
  const { template } = putBlockList({
    template: T, dow: 'tue', branch: null, blocks, at: EPOCH_AT, today: EPOCH_DAY,
  });
  assert.equal(template.daysStreakEpoch.tue ?? null, null);
  assert.equal(dayStatus({
    template, campaign: C, streak: T.streaks['top-focus'], streakId: 'top-focus',
    dateStr: '2026-08-11', doc: day('2026-08-11', {}),
    today: '2026-08-25', backfillDays: 3,
  }), 'missed');
});

test('a check-sourced streak ignores the block epoch entirely', () => {
  const blocks = editFields(blocksFor(T, 'tue', null).map(b => ({ ...b })),
    'tue-reward', { streakId: 'top-focus' });
  const { template } = putBlockList({
    template: T, dow: 'tue', branch: null, blocks, at: EPOCH_AT, today: EPOCH_DAY,
  });
  assert.equal(dayStatus({
    template, campaign: C, streak: T.streaks['sleep-cap'], streakId: 'sleep-cap',
    dateStr: '2026-08-11', doc: day('2026-08-11', { checks: ['sleep-cap'] }),
    today: '2026-08-25', backfillDays: 3,
  }), 'satisfied');
});
