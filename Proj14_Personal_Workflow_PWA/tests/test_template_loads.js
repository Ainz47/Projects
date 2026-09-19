import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadTemplate } from '../src/data/load.js';

test('template parses and has all seven days', () => {
  const t = loadTemplate();
  assert.equal(t._id, 'schedule:v1');
  assert.deepEqual(
    Object.keys(t.days).sort(),
    ['fri', 'mon', 'sat', 'sun', 'thu', 'tue', 'wed']
  );
});

test('no day list is empty', () => {
  const t = loadTemplate();
  for (const [dow, day] of Object.entries(t.days)) {
    const lists = day.branching ? Object.values(day.branches) : [day.blocks];
    for (const blocks of lists) {
      assert.ok(blocks.length > 0, `${dow} has an empty block list`);
    }
  }
});

test('check labels carry no hardcoded wake or sleep time', () => {
  const T = loadTemplate();
  assert.equal(T.checks['sleep-cap'].label, 'Asleep by {sleep}, awake by {wake}');
});
