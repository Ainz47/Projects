import { test } from 'node:test';
import assert from 'node:assert/strict';
import { checkActiveOn, activeChecks } from '../src/checks.js';

const unbounded = { label: 'Health protocols', activeFrom: null, retiredOn: null };
const started = { label: 'Read scripture', activeFrom: '2026-08-12', retiredOn: null };
const retired = { label: 'Old habit', activeFrom: null, retiredOn: '2026-08-12' };
const windowed = { label: 'Both ends', activeFrom: '2026-08-10', retiredOn: '2026-08-12' };

test('a check with no bounds applies on any date', () => {
  assert.equal(checkActiveOn(unbounded, '2020-01-01'), true);
  assert.equal(checkActiveOn(unbounded, '2099-12-31'), true);
});

test('activeFrom is inclusive', () => {
  assert.equal(checkActiveOn(started, '2026-08-11'), false);
  assert.equal(checkActiveOn(started, '2026-08-12'), true);
  assert.equal(checkActiveOn(started, '2026-08-13'), true);
});

test('retiredOn is exclusive, so the day before retirement still counts', () => {
  assert.equal(checkActiveOn(retired, '2026-08-11'), true);
  assert.equal(checkActiveOn(retired, '2026-08-12'), false);
});

test('both bounds together describe a half open window', () => {
  assert.equal(checkActiveOn(windowed, '2026-08-09'), false);
  assert.equal(checkActiveOn(windowed, '2026-08-10'), true);
  assert.equal(checkActiveOn(windowed, '2026-08-11'), true);
  assert.equal(checkActiveOn(windowed, '2026-08-12'), false);
});

test('a check missing the fields entirely is treated as unbounded', () => {
  assert.equal(checkActiveOn({ label: 'Legacy' }, '2026-08-12'), true);
});

test('activeChecks filters the template map and keeps ids', () => {
  const template = {
    checks: {
      'health': unbounded,
      'read-scripture': started,
      'old-habit': retired,
    },
  };
  const ids = activeChecks(template, '2026-08-11').map(([id]) => id);
  assert.deepEqual(ids, ['health', 'old-habit']);

  const later = activeChecks(template, '2026-08-13').map(([id]) => id);
  assert.deepEqual(later, ['health', 'read-scripture']);
});
