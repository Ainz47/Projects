import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadTemplate } from '../src/data/load.js';
import {
  slugify, uniqueCheckId, addCheck, updateCheck, retireCheck, defaultRetireDate,
  migrateDedicatedTasks, addTask, uniqueTaskId, ValidationError,
} from '../src/template-edit.js';
import { allBlockLists } from '../src/schedule.js';

const T = loadTemplate();
const AT = '2026-08-12T09:00:00.000Z';
const TODAY = '2026-08-12';

function add(over = {}) {
  return addCheck({
    template: T, label: 'Read scripture', attribute: 'purpose', coins: 15,
    activeFrom: TODAY, streakDays: null, today: TODAY, at: AT, ...over,
  });
}

test('slugify lowercases and hyphenates', () => {
  assert.equal(slugify('Read scripture'), 'read-scripture');
  assert.equal(slugify('  Phone-free EVENING  '), 'phone-free-evening');
  assert.equal(slugify('10,000 steps!'), '10-000-steps');
});

test('uniqueCheckId suffixes on collision', () => {
  assert.equal(uniqueCheckId(T, 'Read scripture'), 'read-scripture');
  assert.equal(uniqueCheckId(T, 'Health protocols'), 'health-protocols');
  const withOne = { ...T, checks: { ...T.checks, 'read-scripture': {} } };
  assert.equal(uniqueCheckId(withOne, 'Read scripture'), 'read-scripture-2');
  const withTwo = { ...withOne, checks: { ...withOne.checks, 'read-scripture-2': {} } };
  assert.equal(uniqueCheckId(withTwo, 'Read scripture'), 'read-scripture-3');
});

test('a label that slugs to nothing still gets an id', () => {
  assert.equal(uniqueCheckId(T, '!!!'), 'check');
});

test('addCheck writes the check with its window and stamp', () => {
  const { template, checkId } = add();
  assert.equal(checkId, 'read-scripture');
  assert.deepEqual(template.checks['read-scripture'], {
    label: 'Read scripture',
    attribute: 'purpose',
    taskId: 'check-read-scripture',
    activeFrom: '2026-08-12',
    retiredOn: null,
    updatedAt: AT,
  });
});

test('addCheck creates a dedicated task nothing else points at', () => {
  const { template } = add();
  assert.deepEqual(template.tasks['check-read-scripture'], {
    label: 'Read scripture',
    attribute: 'purpose',
    coins: 15,
    updatedAt: AT,
  });
  // The fifteen original tasks are untouched.
  for (const id of Object.keys(T.tasks)) {
    assert.deepEqual(template.tasks[id], T.tasks[id]);
  }
});

test('zero coins creates no task at all', () => {
  const { template } = add({ coins: 0 });
  assert.equal(template.checks['read-scripture'].taskId, null);
  assert.equal(template.tasks['check-read-scripture'], undefined);
});

test('addCheck does not mutate the template it was given', () => {
  const before = JSON.stringify(T);
  add();
  assert.equal(JSON.stringify(T), before);
});

test('no streak is written unless days are given', () => {
  const { template } = add();
  assert.equal(template.streaks['read-scripture'], undefined);
});

test('streakDays writes a check-sourced streak with the same id', () => {
  const { template } = add({ streakDays: ['mon', 'tue', 'wed', 'thu', 'fri'] });
  assert.deepEqual(template.streaks['read-scripture'], {
    label: 'Read scripture',
    attribute: 'purpose',
    source: 'check',
    appliesOn: ['mon', 'tue', 'wed', 'thu', 'fri'],
  });
});

test('an empty label is rejected', () => {
  assert.throws(() => add({ label: '   ' }),
    (err) => err instanceof ValidationError && /label/i.test(err.message));
});

test('a label over 60 characters is rejected', () => {
  assert.throws(() => add({ label: 'x'.repeat(61) }),
    (err) => err instanceof ValidationError);
});

test('an unknown attribute is rejected', () => {
  assert.throws(() => add({ attribute: 'wisdom' }),
    (err) => err instanceof ValidationError && /attribute/i.test(err.message));
});

test('coins must be a whole number from 0 to 999', () => {
  assert.throws(() => add({ coins: -1 }), (err) => err instanceof ValidationError);
  assert.throws(() => add({ coins: 1000 }), (err) => err instanceof ValidationError);
  assert.throws(() => add({ coins: 7.5 }), (err) => err instanceof ValidationError);
});

test('activeFrom cannot reach back past the backfill window', () => {
  // backfillDays is 3, so 2026-08-09 is the earliest allowed on 2026-08-12.
  assert.doesNotThrow(() => add({ activeFrom: '2026-08-09' }));
  assert.throws(() => add({ activeFrom: '2026-08-08' }),
    (err) => err instanceof ValidationError && /backfill/i.test(err.message));
});

test('an unknown streak day is rejected', () => {
  assert.throws(() => add({ streakDays: ['mon', 'funday'] }),
    (err) => err instanceof ValidationError);
});

const LATER = '2026-08-12T21:00:00.000Z';

test('updateCheck rewrites the check and its dedicated task together', () => {
  const { template: t1 } = add();
  const { template } = updateCheck({
    template: t1, checkId: 'read-scripture',
    label: 'Read the word', attribute: 'lifeskills', coins: 25, at: LATER,
  });
  assert.equal(template.checks['read-scripture'].label, 'Read the word');
  assert.equal(template.checks['read-scripture'].attribute, 'lifeskills');
  assert.equal(template.checks['read-scripture'].updatedAt, LATER);
  assert.deepEqual(template.tasks['check-read-scripture'], {
    label: 'Read the word', attribute: 'lifeskills', coins: 25, updatedAt: LATER,
  });
});

test('updateCheck leaves the window alone', () => {
  const { template: t1 } = add();
  const { template } = updateCheck({
    template: t1, checkId: 'read-scripture',
    label: 'Read the word', attribute: 'purpose', coins: 25, at: LATER,
  });
  assert.equal(template.checks['read-scripture'].activeFrom, '2026-08-12');
  assert.equal(template.checks['read-scripture'].retiredOn, null);
});

test('repricing a check never touches a task a block points at', () => {
  const { template } = updateCheck({
    template: T, checkId: 'sleep-cap',
    label: T.checks['sleep-cap'].label, attribute: 'vitality', coins: 99, at: LATER,
  });
  // sleep-cap owns the-cap outright, so that one moves.
  assert.equal(template.tasks['the-cap'].coins, 99);
  // And nothing else does.
  for (const id of Object.keys(T.tasks)) {
    if (id === 'the-cap') continue;
    assert.deepEqual(template.tasks[id], T.tasks[id]);
  }
});

test('giving coins to a check that had none creates its task then', () => {
  assert.equal(T.checks['phone-free'].taskId, null);
  const { template } = updateCheck({
    template: T, checkId: 'phone-free',
    label: 'Phone-free evening', attribute: 'lifeskills', coins: 10, at: LATER,
  });
  assert.equal(template.checks['phone-free'].taskId, 'check-phone-free');
  assert.deepEqual(template.tasks['check-phone-free'], {
    label: 'Phone-free evening', attribute: 'lifeskills', coins: 10, updatedAt: LATER,
  });
});

test('setting coins to zero unpoints the check but keeps the task', () => {
  const { template: t1 } = add();
  const { template } = updateCheck({
    template: t1, checkId: 'read-scripture',
    label: 'Read scripture', attribute: 'purpose', coins: 0, at: LATER,
  });
  assert.equal(template.checks['read-scripture'].taskId, null);
  assert.ok(template.tasks['check-read-scripture'], 'the task must survive for past refunds');
});

test('updateCheck rejects an unknown check', () => {
  assert.throws(() => updateCheck({
    template: T, checkId: 'nope', label: 'x', attribute: 'vitality', coins: 1, at: LATER,
  }), (err) => /unknown check/.test(err.message));
});

test('updateCheck validates the same way addCheck does', () => {
  assert.throws(() => updateCheck({
    template: T, checkId: 'health', label: '', attribute: 'vitality', coins: 1, at: LATER,
  }), (err) => err instanceof ValidationError);
  assert.throws(() => updateCheck({
    template: T, checkId: 'health', label: 'Health', attribute: 'wisdom', coins: 1, at: LATER,
  }), (err) => err instanceof ValidationError);
});

test('defaultRetireDate is tomorrow, so today stays as it was lived', () => {
  assert.equal(defaultRetireDate('2026-08-12'), '2026-08-13');
  assert.equal(defaultRetireDate('2026-08-31'), '2026-09-01');
});

test('retireCheck sets the date and nothing else', () => {
  const { template } = retireCheck({
    template: T, checkId: 'health', retiredOn: '2026-08-13', at: LATER,
  });
  assert.equal(template.checks['health'].retiredOn, '2026-08-13');
  assert.equal(template.checks['health'].updatedAt, LATER);
  assert.equal(template.checks['health'].label, T.checks['health'].label);
  assert.equal(template.checks['health'].taskId, T.checks['health'].taskId);
});

test('retiring never removes a task or a check', () => {
  const { template } = retireCheck({
    template: T, checkId: 'sleep-cap', retiredOn: '2026-08-13', at: LATER,
  });
  assert.ok(template.checks['sleep-cap']);
  assert.deepEqual(Object.keys(template.tasks).sort(), Object.keys(T.tasks).sort());
});

test('retireCheck can be undone by clearing the date', () => {
  const { template: t1 } = retireCheck({
    template: T, checkId: 'health', retiredOn: '2026-08-13', at: LATER,
  });
  const { template } = retireCheck({
    template: t1, checkId: 'health', retiredOn: null, at: LATER,
  });
  assert.equal(template.checks['health'].retiredOn, null);
});

test('migrateDedicatedTasks splits the one task a check shares with blocks', () => {
  const { template, changed } = migrateDedicatedTasks(T, LATER);
  assert.equal(changed, true);
  assert.equal(template.checks['hard-stop'].taskId, 'check-hard-stop');
  assert.deepEqual(template.tasks['check-hard-stop'], {
    label: T.tasks['hard-stop'].label,
    attribute: T.tasks['hard-stop'].attribute,
    coins: T.tasks['hard-stop'].coins,
    updatedAt: LATER,
  });
});

test('the blocks keep pointing at the original task', () => {
  const { template } = migrateDedicatedTasks(T, LATER);
  assert.deepEqual(template.tasks['hard-stop'], T.tasks['hard-stop']);
  let count = 0;
  for (const { blocks } of allBlockLists(template)) {
    for (const b of blocks) if (b.taskId === 'hard-stop') count += 1;
  }
  assert.equal(count, 6);
});

test('a check that owns its task outright is left alone', () => {
  const { template } = migrateDedicatedTasks(T, LATER);
  // the-cap is used by no block, so sleep-cap keeps it.
  assert.equal(template.checks['sleep-cap'].taskId, 'the-cap');
  assert.equal(template.tasks['check-sleep-cap'], undefined);
});

test('a check with no task is left alone', () => {
  const { template } = migrateDedicatedTasks(T, LATER);
  assert.equal(template.checks['health'].taskId, null);
  assert.equal(template.checks['phone-free'].taskId, null);
});

test('migrateDedicatedTasks is idempotent', () => {
  const { template: once } = migrateDedicatedTasks(T, LATER);
  const { template: twice, changed } = migrateDedicatedTasks(once, LATER);
  assert.equal(changed, false);
  assert.deepEqual(twice, once);
});

test('uniqueTaskId prefixes with task- and suffixes on collision', () => {
  assert.equal(uniqueTaskId(T, 'Morning pages'), 'task-morning-pages');
  const withOne = { ...T, tasks: { ...T.tasks, 'task-morning-pages': {} } };
  assert.equal(uniqueTaskId(withOne, 'Morning pages'), 'task-morning-pages-2');
});

test('addTask writes a shareable task with its stamp', () => {
  const { template, taskId } = addTask({
    template: T, label: 'Morning pages', attribute: 'purpose', coins: 10, at: AT,
  });
  assert.equal(taskId, 'task-morning-pages');
  assert.deepEqual(template.tasks['task-morning-pages'], {
    label: 'Morning pages', attribute: 'purpose', coins: 10, updatedAt: AT,
  });
  for (const id of Object.keys(T.tasks)) {
    assert.deepEqual(template.tasks[id], T.tasks[id]);
  }
});

test('addTask validates its label, attribute and coins', () => {
  assert.throws(() => addTask({ template: T, label: '', attribute: 'purpose', coins: 10, at: AT }),
    (err) => err instanceof ValidationError);
  assert.throws(() => addTask({ template: T, label: 'X', attribute: 'nope', coins: 10, at: AT }), /attribute/);
  assert.throws(() => addTask({ template: T, label: 'X', attribute: 'purpose', coins: -1, at: AT }), /coins/);
});
