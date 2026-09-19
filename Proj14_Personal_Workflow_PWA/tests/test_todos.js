import { test } from 'node:test';
import assert from 'node:assert/strict';
import { newTodo, isOverdue, sortOpen, sortArchive, toggleDone, togglePin, edit, remove } from '../src/todos.js';

const TS = '2026-08-12T09:14:22.031Z';

test('newTodo builds a chronologically sortable id from ts and rand', () => {
  const t = newTodo({ text: 'buy milk', ts: TS, rand: 'a1b2c3' });
  assert.equal(t._id, `todo:${TS}:a1b2c3`);
  assert.equal(t.type, 'todo');
});

test('newTodo defaults every optional field', () => {
  const t = newTodo({ text: 'buy milk', ts: TS, rand: 'a1b2c3' });
  assert.equal(t.note, '');
  assert.equal(t.due, null);
  assert.equal(t.pinned, false);
  assert.equal(t.done, false);
  assert.equal(t.doneAt, null);
  assert.equal(t.createdAt, TS);
  assert.equal(t.updatedAt, TS);
});

test('newTodo keeps a note and a due date when given', () => {
  const t = newTodo({
    text: 'email the client', note: 'about the invoice',
    due: '2026-08-20', ts: TS, rand: 'a1b2c3',
  });
  assert.equal(t.note, 'about the invoice');
  assert.equal(t.due, '2026-08-20');
});

test('newTodo trims the text', () => {
  const t = newTodo({ text: '  buy milk  ', ts: TS, rand: 'a1b2c3' });
  assert.equal(t.text, 'buy milk');
});

test('newTodo rejects empty text', () => {
  assert.throws(() => newTodo({ text: '   ', ts: TS, rand: 'a1b2c3' }), /text is required/);
});

test('ids sort chronologically as plain strings', () => {
  const older = newTodo({ text: 'a', ts: '2026-08-12T09:00:00.000Z', rand: 'zzzzzz' });
  const newer = newTodo({ text: 'b', ts: '2026-08-12T10:00:00.000Z', rand: 'aaaaaa' });
  assert.ok(older._id < newer._id);
});

test('isOverdue is false when due is today', () => {
  assert.equal(isOverdue({ due: '2026-08-12' }, '2026-08-12'), false);
});

test('isOverdue is true the day after due', () => {
  assert.equal(isOverdue({ due: '2026-08-11' }, '2026-08-12'), true);
});

test('isOverdue is false for a future due date', () => {
  assert.equal(isOverdue({ due: '2026-08-13' }, '2026-08-12'), false);
});

test('an undated todo is never overdue', () => {
  assert.equal(isOverdue({ due: null }, '2026-08-12'), false);
});

// Explicit documents rather than newTodo calls, so each test states exactly the
// fields it depends on and nothing else.
function todo(id, extra = {}) {
  return {
    _id: `todo:${id}`, type: 'todo', text: id, note: '', due: null,
    pinned: false, done: false, doneAt: null,
    createdAt: id, updatedAt: id,
  };
}

const ids = (list) => list.map(t => t._id.replace('todo:', ''));

test('sortOpen drops done items', () => {
  const list = [todo('a'), { ...todo('b'), done: true }];
  assert.deepEqual(ids(sortOpen(list)), ['a']);
});

test('pinned items come first', () => {
  const list = [todo('a'), { ...todo('b'), pinned: true }];
  assert.deepEqual(ids(sortOpen(list)), ['b', 'a']);
});

test('a pinned item beats an overdue one', () => {
  const list = [
    { ...todo('overdue'), due: '2000-01-01' },
    { ...todo('pinned'), pinned: true },
  ];
  assert.deepEqual(ids(sortOpen(list)), ['pinned', 'overdue']);
});

test('dated items come before undated ones, soonest first', () => {
  const list = [
    todo('undated'),
    { ...todo('later'), due: '2026-09-01' },
    { ...todo('sooner'), due: '2026-08-13' },
  ];
  assert.deepEqual(ids(sortOpen(list)), ['sooner', 'later', 'undated']);
});

test('undated items are newest first', () => {
  const list = [todo('2026-08-10'), todo('2026-08-12'), todo('2026-08-11')];
  assert.deepEqual(ids(sortOpen(list)), ['2026-08-12', '2026-08-11', '2026-08-10']);
});

test('the pinned group sorts by the same rules inside itself', () => {
  const list = [
    { ...todo('pinned-undated'), pinned: true },
    { ...todo('pinned-dated'), pinned: true, due: '2026-08-13' },
  ];
  assert.deepEqual(ids(sortOpen(list)), ['pinned-dated', 'pinned-undated']);
});

test('sortOpen does not mutate its argument', () => {
  const list = [todo('a'), { ...todo('b'), pinned: true }];
  sortOpen(list);
  assert.deepEqual(ids(list), ['a', 'b']);
});

test('sortArchive keeps only done items, most recently completed first', () => {
  const list = [
    { ...todo('early'), done: true, doneAt: '2026-08-10T08:00:00.000Z' },
    todo('still-open'),
    { ...todo('late'), done: true, doneAt: '2026-08-12T08:00:00.000Z' },
  ];
  assert.deepEqual(ids(sortArchive(list)), ['late', 'early']);
});

const AT = '2026-08-12T21:00:00.000Z';

test('toggleDone sets done and stamps doneAt', () => {
  const t = toggleDone(todo('a'), { done: true, at: AT });
  assert.equal(t.done, true);
  assert.equal(t.doneAt, AT);
  assert.equal(t.updatedAt, AT);
});

test('unticking clears doneAt rather than leaving a stale one', () => {
  const done = toggleDone(todo('a'), { done: true, at: AT });
  const undone = toggleDone(done, { done: false, at: '2026-08-12T22:00:00.000Z' });
  assert.equal(undone.done, false);
  assert.equal(undone.doneAt, null);
});

test('togglePin sets pinned and stamps updatedAt', () => {
  const t = togglePin(todo('a'), { pinned: true, at: AT });
  assert.equal(t.pinned, true);
  assert.equal(t.updatedAt, AT);
});

test('edit replaces text, note and due', () => {
  const t = edit(todo('a'), { text: 'new text', note: 'new note', due: '2026-09-01', at: AT });
  assert.equal(t.text, 'new text');
  assert.equal(t.note, 'new note');
  assert.equal(t.due, '2026-09-01');
  assert.equal(t.updatedAt, AT);
});

test('edit trims text and rejects an empty result', () => {
  assert.equal(edit(todo('a'), { text: '  spaced  ', note: '', due: null, at: AT }).text, 'spaced');
  assert.throws(() => edit(todo('a'), { text: '  ', note: '', due: null, at: AT }), /text is required/);
});

test('edit can clear a due date', () => {
  const dated = { ...todo('a'), due: '2026-09-01' };
  assert.equal(edit(dated, { text: 'a', note: '', due: null, at: AT }).due, null);
});

test('remove marks the document deleted', () => {
  const t = remove(todo('a'), { at: AT });
  assert.equal(t._deleted, true);
  assert.equal(t.updatedAt, AT);
});

test('mutations never mutate their argument', () => {
  const original = todo('a');
  toggleDone(original, { done: true, at: AT });
  togglePin(original, { pinned: true, at: AT });
  edit(original, { text: 'changed', note: '', due: null, at: AT });
  remove(original, { at: AT });
  assert.equal(original.done, false);
  assert.equal(original.pinned, false);
  assert.equal(original.text, 'a');
  assert.equal(original._deleted, undefined);
});
