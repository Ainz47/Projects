import { test } from 'node:test';
import assert from 'node:assert/strict';
import { shiftDate, daysBetween, eachDate } from '../src/dates.js';

test('shiftDate moves forward inside a month', () => {
  assert.equal(shiftDate('2026-08-11', 3), '2026-08-14');
});

test('shiftDate crosses a month boundary in both directions', () => {
  assert.equal(shiftDate('2026-08-31', 1), '2026-09-01');
  assert.equal(shiftDate('2026-09-01', -1), '2026-08-31');
});

test('shiftDate crosses a year boundary', () => {
  assert.equal(shiftDate('2026-12-31', 1), '2027-01-01');
  assert.equal(shiftDate('2027-01-01', -1), '2026-12-31');
});

test('shiftDate handles a leap day', () => {
  // 2028 is a leap year; 2026 is not, so this is the only way to catch a
  // naive "add 24 hours to a local Date" implementation.
  assert.equal(shiftDate('2028-02-28', 1), '2028-02-29');
  assert.equal(shiftDate('2027-02-28', 1), '2027-03-01');
});

test('shiftDate by zero returns the same date', () => {
  assert.equal(shiftDate('2026-08-11', 0), '2026-08-11');
});

test('daysBetween is signed and measures whole days', () => {
  assert.equal(daysBetween('2026-08-11', '2026-08-14'), 3);
  assert.equal(daysBetween('2026-08-14', '2026-08-11'), -3);
  assert.equal(daysBetween('2026-08-11', '2026-08-11'), 0);
});

test('eachDate is inclusive at both ends and ordered', () => {
  assert.deepEqual(eachDate('2026-08-30', '2026-09-02'),
    ['2026-08-30', '2026-08-31', '2026-09-01', '2026-09-02']);
});

test('eachDate over the Streaks screen window returns 30 days ending today', () => {
  const days = eachDate(shiftDate('2026-08-11', -29), '2026-08-11');
  assert.equal(days.length, 30);
  assert.equal(days.at(-1), '2026-08-11');
});

test('eachDate returns empty when the range is backwards', () => {
  assert.deepEqual(eachDate('2026-08-14', '2026-08-11'), []);
});
