import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadTemplate } from '../src/data/load.js';
import { effectiveTimes, resolveLabel, bedtimeCountdown, wakeTargetDate, shiftTime } from '../src/bedtime.js';

const T = loadTemplate();

// 2026-08-11 is a Tuesday. Defaults are wake 06:00, sleep 22:30.
const D = '2026-08-11';
const TOMORROW = '2026-08-12';

test('effectiveTimes falls back to the template when nothing is overridden', () => {
  const day = { sleepOverride: null, wakeOverride: null };
  assert.deepEqual(effectiveTimes(T, day), { wake: '06:00', sleep: '22:30' });
});

test('effectiveTimes tolerates a missing day document', () => {
  assert.deepEqual(effectiveTimes(T, null), { wake: '06:00', sleep: '22:30' });
});

test('each override applies independently of the other', () => {
  assert.deepEqual(
    effectiveTimes(T, { sleepOverride: '23:15', wakeOverride: null }),
    { wake: '06:00', sleep: '23:15' }
  );
  assert.deepEqual(
    effectiveTimes(T, { sleepOverride: null, wakeOverride: '07:00' }),
    { wake: '07:00', sleep: '22:30' }
  );
});

test('resolveLabel substitutes both tokens', () => {
  assert.equal(
    resolveLabel('Asleep by {sleep}, awake by {wake}', { wake: '06:00', sleep: '22:30' }),
    'Asleep by 22:30, awake by 06:00'
  );
});

test('resolveLabel leaves a label with no tokens unchanged', () => {
  assert.equal(resolveLabel('Phone-free evening', { wake: '06:00', sleep: '22:30' }),
    'Phone-free evening');
});

test('during the day it counts down to bedtime', () => {
  const r = bedtimeCountdown({ template: T, day: null, nextDay: null, dateStr: D, hhmm: '20:00' });
  assert.equal(r.phase, 'until-sleep');
  assert.equal(r.minutes, 150);
  assert.equal(r.targetDate, D);
});

test('the phase flips at exactly the bedtime minute', () => {
  const before = bedtimeCountdown({ template: T, day: null, nextDay: null, dateStr: D, hhmm: '22:29' });
  const at = bedtimeCountdown({ template: T, day: null, nextDay: null, dateStr: D, hhmm: '22:30' });
  assert.equal(before.phase, 'until-sleep');
  assert.equal(at.phase, 'until-wake');
});

test('level thresholds trip at their edges', () => {
  const lvl = (hhmm) => bedtimeCountdown({ template: T, day: null, nextDay: null, dateStr: D, hhmm }).level;
  assert.equal(lvl('21:29'), 'normal');   // 61 minutes
  assert.equal(lvl('21:30'), 'warn');     // 60 minutes
  assert.equal(lvl('22:14'), 'warn');     // 16 minutes
  assert.equal(lvl('22:15'), 'urgent');   // 15 minutes
});

test('past bedtime it counts to tomorrow morning, across midnight', () => {
  const late = bedtimeCountdown({ template: T, day: null, nextDay: null, dateStr: D, hhmm: '23:00' });
  assert.equal(late.phase, 'until-wake');
  assert.equal(late.minutes, 420);
  assert.equal(late.targetDate, TOMORROW);
  assert.equal(late.level, 'normal');
});

test('pre-dawn it counts to this morning, not to tonight', () => {
  const early = bedtimeCountdown({ template: T, day: null, nextDay: null, dateStr: D, hhmm: '00:30' });
  assert.equal(early.phase, 'until-wake');
  assert.equal(early.minutes, 330);
  assert.equal(early.targetDate, D);
});

test('the until-wake countdown honours tomorrow own wake override', () => {
  const r = bedtimeCountdown({
    template: T, day: null, nextDay: { wakeOverride: '07:00', sleepOverride: null },
    dateStr: D, hhmm: '23:00',
  });
  assert.equal(r.minutes, 480);
});

test('a bedtime override moves the phase boundary', () => {
  const day = { sleepOverride: '23:15', wakeOverride: null };
  const r = bedtimeCountdown({ template: T, day, nextDay: null, dateStr: D, hhmm: '23:00' });
  assert.equal(r.phase, 'until-sleep');
  assert.equal(r.minutes, 15);
  assert.equal(r.level, 'urgent');
});

test('wakeTargetDate is today pre-dawn and tomorrow otherwise', () => {
  assert.equal(wakeTargetDate({ template: T, day: null, dateStr: D, hhmm: '00:30' }), D);
  assert.equal(wakeTargetDate({ template: T, day: null, dateStr: D, hhmm: '14:00' }), TOMORROW);
  assert.equal(wakeTargetDate({ template: T, day: null, dateStr: D, hhmm: '23:00' }), TOMORROW);
});

test('shiftTime moves a time in both directions', () => {
  assert.equal(shiftTime('22:30', 15), '22:45');
  assert.equal(shiftTime('22:30', -45), '21:45');
});

test('shiftTime wraps around midnight rather than clamping', () => {
  assert.equal(shiftTime('23:45', 30), '00:15');
  assert.equal(shiftTime('00:15', -30), '23:45');
});
