import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadCampaign } from '../src/data/load.js';
import { dowOf } from '../src/clock.js';
import { dayFor, daysRemaining, isRestDay } from '../src/campaign.js';

const C = loadCampaign();

test('the campaign is exactly 28 days, numbered 1 to 28 in date order', () => {
  assert.equal(C.days.length, 28);
  C.days.forEach((d, i) => assert.equal(d.n, i + 1));
  for (let i = 1; i < C.days.length; i++) {
    assert.ok(C.days[i].date > C.days[i - 1].date, `day ${i + 1} is out of order`);
  }
});

test('Day 1 is Mon 17 Aug and Day 28 is Sun 13 Sep', () => {
  assert.equal(C.days[0].date, '2026-08-17');
  assert.equal(dowOf(C.days[0].date), 'mon');
  assert.equal(C.days[27].date, '2026-09-13');
  assert.equal(dowOf(C.days[27].date), 'sun');
  assert.equal(C.days[27].kind, 'perform');
});

test('every rest day falls on a Sunday', () => {
  const rests = C.days.filter(d => d.kind === 'rest');
  assert.equal(rests.length, 3);
  for (const d of rests) assert.equal(dowOf(d.date), 'sun', `${d.date} is not a Sunday`);
});

test('full runs land on Sep 4, 7 and 9', () => {
  const runs = C.days.filter(d => d.kind === 'fullrun').map(d => d.date);
  assert.deepEqual(runs, ['2026-09-04', '2026-09-07', '2026-09-09']);
});

test('dayFor finds a date and returns null outside the campaign', () => {
  assert.equal(dayFor(C, '2026-08-17').n, 1);
  assert.equal(dayFor(C, '2026-09-13').n, 28);
  assert.equal(dayFor(C, '2026-08-10'), null);
  assert.equal(dayFor(C, '2026-09-14'), null);
});

test('daysRemaining counts down to the performance and floors at zero', () => {
  assert.equal(daysRemaining(C, '2026-09-13'), 0);
  assert.equal(daysRemaining(C, '2026-09-12'), 1);
  assert.equal(daysRemaining(C, '2026-08-10'), 34);
  assert.equal(daysRemaining(C, '2026-09-20'), 0);
});

test('isRestDay is true only on prescribed rest days', () => {
  assert.equal(isRestDay(C, '2026-08-23'), true);
  assert.equal(isRestDay(C, '2026-08-24'), false);
  assert.equal(isRestDay(C, '2026-08-10'), false);
});
