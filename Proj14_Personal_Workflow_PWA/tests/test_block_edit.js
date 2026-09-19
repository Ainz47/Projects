import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadTemplate } from '../src/data/load.js';
import { blocksFor, listKey } from '../src/schedule.js';
import { ValidationError } from '../src/template-edit.js';
import {
  STEP_MINUTES, MIN_BLOCK_MINUTES, toHHMM, validateList, moveBoundary,
  uniqueBlockId, placeBlock, removeBlock,
  editFields, streakSignature, putBlockList, toOverride,
} from '../src/block-edit.js';

const T = loadTemplate();
const WAKE = T.wake;    // 06:00
const SLEEP = T.sleep;  // 22:30

// Tuesday is the fixture throughout: twelve blocks, no branching, and the
// campaign slot on tue-talk. Shallow-cloned because these tests build
// variants; nothing in block-edit.js mutates its input, so the shared
// `calendar` objects underneath are safe.
function tue() {
  return blocksFor(T, 'tue', null).map(b => ({ ...b }));
}

const at = (blocks, id) => blocks.find(b => b.id === id);
const span = (b) => `${b.start}-${b.end}`;

test('the step and the minimum are both fifteen minutes', () => {
  assert.equal(STEP_MINUTES, 15);
  assert.equal(MIN_BLOCK_MINUTES, 15);
});

test('toHHMM inverts toMinutes', () => {
  assert.equal(toHHMM(360), '06:00');
  assert.equal(toHHMM(1350), '22:30');
  assert.equal(toHHMM(645), '10:45');
});

test('the shipped Tuesday list is valid', () => {
  assert.equal(validateList(tue(), WAKE, SLEEP, T), true);
});

test('a gap between two blocks is rejected', () => {
  const blocks = tue();
  blocks[1] = { ...blocks[1], end: '07:15', hours: 0.75 };
  assert.throws(() => validateList(blocks, WAKE, SLEEP), (e) => e instanceof ValidationError);
});

test('a list that does not start at wake or end at sleep is rejected', () => {
  const late = tue();
  late[0] = { ...late[0], start: '06:15', hours: 0.25 };
  assert.throws(() => validateList(late, WAKE, SLEEP), /wake/);

  const short = tue();
  short[11] = { ...short[11], end: '22:00', hours: 1.0 };
  assert.throws(() => validateList(short, WAKE, SLEEP), /sleep/);
});

test('hours must equal end minus start', () => {
  const blocks = tue();
  blocks[0] = { ...blocks[0], hours: 99 };
  assert.throws(() => validateList(blocks, WAKE, SLEEP), /hours/);
});

test('a duplicate id is rejected', () => {
  const blocks = tue();
  blocks[1] = { ...blocks[1], id: 'tue-topfocus' };
  assert.throws(() => validateList(blocks, WAKE, SLEEP), /duplicate/);
});

test('zero or two campaign slots are both rejected', () => {
  const none = tue().map(b => ({ ...b, campaignSlot: false }));
  assert.throws(() => validateList(none, WAKE, SLEEP), /campaign/);

  const two = tue();
  two[0] = { ...two[0], campaignSlot: true };
  assert.throws(() => validateList(two, WAKE, SLEEP), /campaign/);
});

test('an empty list is rejected', () => {
  assert.throws(() => validateList([], WAKE, SLEEP), /at least one block/);
});

test('an undeclared taskId is only caught when a template is supplied', () => {
  const blocks = tue();
  blocks[0] = { ...blocks[0], taskId: 'no-such-task' };
  assert.equal(validateList(blocks, WAKE, SLEEP), true);
  assert.throws(() => validateList(blocks, WAKE, SLEEP, T), /no-such-task/);
});

test('an undeclared streakId and attribute are caught the same way', () => {
  const streak = tue();
  streak[0] = { ...streak[0], streakId: 'no-such-streak' };
  assert.throws(() => validateList(streak, WAKE, SLEEP, T), /no-such-streak/);

  const attr = tue();
  attr[0] = { ...attr[0], attribute: 'no-such-attribute' };
  assert.throws(() => validateList(attr, WAKE, SLEEP, T), /no-such-attribute/);
});

test('moveBoundary moves the seam and leaves every other block alone', () => {
  // Seam 2 is tue-client1 / tue-talk at 10:30.
  const before = tue();
  const after = moveBoundary(before, 2, '11:00');
  assert.equal(span(at(after, 'tue-client1')), '07:30-11:00');
  assert.equal(at(after, 'tue-client1').hours, 3.5);
  assert.equal(span(at(after, 'tue-talk')), '11:00-11:30');
  assert.equal(at(after, 'tue-talk').hours, 0.5);
  assert.equal(span(at(after, 'tue-lunch')), '11:30-12:30');
  assert.equal(validateList(after, WAKE, SLEEP, T), true);
});

test('moveBoundary does not mutate its input', () => {
  const before = tue();
  moveBoundary(before, 2, '11:00');
  assert.equal(span(at(before, 'tue-client1')), '07:30-10:30');
});

test('moveBoundary clamps rather than driving a block below the minimum', () => {
  const blocks = tue();
  // tue-talk runs 10:30-11:30 and ends at the 11:30 seam. Pushing seam 2
  // to 11:45 would leave it negative; the clamp stops at 11:15.
  const forward = moveBoundary(blocks, 2, '11:45');
  assert.equal(span(at(forward, 'tue-talk')), '11:15-11:30');
  // Pulling back past tue-client1's own start is clamped to start + 15.
  const back = moveBoundary(blocks, 2, '06:00');
  assert.equal(span(at(back, 'tue-client1')), '07:30-07:45');
  assert.equal(validateList(forward, WAKE, SLEEP, T), true);
  assert.equal(validateList(back, WAKE, SLEEP, T), true);
});

test('a boundary index outside the interior seams is rejected', () => {
  assert.throws(() => moveBoundary(tue(), -1, '07:00'), (e) => e instanceof ValidationError);
  // 12 blocks means seams 0..10; 11 would be the pinned sleep edge.
  assert.throws(() => moveBoundary(tue(), 11, '22:00'), /boundary/);
});

test('a boundary off the fifteen minute grid is rejected', () => {
  assert.throws(() => moveBoundary(tue(), 2, '10:37'), /15/);
});

const DENTIST = {
  label: 'Dentist', detail: 'Molar, upper left.', attribute: 'lifeskills',
  taskId: null, streakId: null, campaignSlot: false,
  calendar: { event: true, remindMinutes: 30 },
};

const place = (blocks, start, end, over = {}) =>
  placeBlock(blocks, { start, end, fields: DENTIST, id: 'tue-dentist', ...over });

test('uniqueBlockId suffixes from two upward', () => {
  assert.equal(uniqueBlockId(['a', 'b'], 'c'), 'c');
  assert.equal(uniqueBlockId(['a', 'b'], 'a'), 'a-2');
  assert.equal(uniqueBlockId(['a', 'a-2'], 'a'), 'a-3');
  assert.equal(uniqueBlockId(new Set(['a']), 'a'), 'a-2');
});

test('placing a block inside two neighbours borrows from both', () => {
  // talk 10:30-11:30, lunch 11:30-12:30. Place 11:00-12:00.
  const after = place(tue(), '11:00', '12:00');
  assert.equal(span(at(after, 'tue-talk')), '10:30-11:00');
  assert.equal(span(at(after, 'tue-dentist')), '11:00-12:00');
  assert.equal(span(at(after, 'tue-lunch')), '12:00-12:30');
  assert.equal(at(after, 'tue-dentist').hours, 1);
  assert.equal(validateList(after, WAKE, SLEEP, T), true);
});

test('placing a block exactly over one replaces it', () => {
  const after = place(tue(), '11:30', '12:30');
  assert.equal(at(after, 'tue-lunch'), undefined);
  assert.equal(span(at(after, 'tue-dentist')), '11:30-12:30');
  assert.equal(span(at(after, 'tue-talk')), '10:30-11:30');
  assert.equal(span(at(after, 'tue-coursework')), '12:30-14:00');
  assert.equal(after.length, 12);
  assert.equal(validateList(after, WAKE, SLEEP, T), true);
});

test('placing a block over one and into both neighbours swallows and borrows', () => {
  const after = place(tue(), '11:00', '13:00');
  assert.equal(at(after, 'tue-lunch'), undefined);
  assert.equal(span(at(after, 'tue-talk')), '10:30-11:00');
  assert.equal(span(at(after, 'tue-dentist')), '11:00-13:00');
  assert.equal(span(at(after, 'tue-coursework')), '13:00-14:00');
  assert.equal(validateList(after, WAKE, SLEEP, T), true);
});

test('placing a block inside one block splits it, and the remainder gets a new id', () => {
  // tue-surge runs 14:00-16:30. A 15:00-15:30 block sits strictly inside it.
  const after = place(tue(), '15:00', '15:30');
  assert.equal(span(at(after, 'tue-surge')), '14:00-15:00');
  assert.equal(span(at(after, 'tue-dentist')), '15:00-15:30');
  assert.equal(span(at(after, 'tue-surge-2')), '15:30-16:30');
  // The remainder is the same block in every respect but its id.
  assert.equal(at(after, 'tue-surge-2').label, 'Client Work (SURGE)');
  assert.equal(at(after, 'tue-surge-2').taskId, 'surge-taken');
  assert.equal(after.length, 14);
  assert.equal(validateList(after, WAKE, SLEEP, T), true);
});

test('the split remainder avoids ids used elsewhere in the template', () => {
  const after = place(tue(), '15:00', '15:30', { takenIds: ['tue-surge-2', 'tue-surge-3'] });
  assert.ok(at(after, 'tue-surge-4'));
});

test('placing a block at the start of the day keeps the list pinned to wake', () => {
  const after = place(tue(), '06:00', '06:15');
  assert.equal(after[0].id, 'tue-dentist');
  assert.equal(span(at(after, 'tue-topfocus')), '06:15-06:30');
  assert.equal(validateList(after, WAKE, SLEEP, T), true);
});

test('placing a block at the end of the day keeps the list pinned to sleep', () => {
  const after = place(tue(), '22:00', '22:30');
  assert.equal(after.at(-1).id, 'tue-dentist');
  assert.equal(span(at(after, 'tue-evening')), '21:00-22:00');
  assert.equal(validateList(after, WAKE, SLEEP, T), true);
});

test('placing a block that swallows the campaign slot leaves the list invalid', () => {
  // Deliberate. The pure function returns the list as computed; the calling
  // flow is what refuses to save until a slot is reassigned.
  const after = place(tue(), '10:30', '11:30');
  assert.equal(at(after, 'tue-talk'), undefined);
  assert.throws(() => validateList(after, WAKE, SLEEP, T), /campaign/);
});

test('placeBlock rejects an interval that is backwards, too short or off grid', () => {
  assert.throws(() => place(tue(), '12:00', '12:00'), /after/);
  assert.throws(() => place(tue(), '12:00', '11:00'), /after/);
  assert.throws(() => place(tue(), '12:00', '12:07'), /15/);
  assert.throws(() => place(tue(), '12:07', '13:00'), /15/);
});

test('placeBlock rejects an interval outside the day', () => {
  assert.throws(() => place(tue(), '05:00', '06:00'), /outside/);
  assert.throws(() => place(tue(), '22:15', '23:00'), /outside/);
});

test('placeBlock rejects an id already in use', () => {
  assert.throws(() => place(tue(), '11:00', '12:00', { id: 'tue-lunch' }), /already/);
});

test('placeBlock does not mutate its input', () => {
  const before = tue();
  place(before, '11:00', '12:00');
  assert.equal(before.length, 12);
  assert.equal(span(at(before, 'tue-lunch')), '11:30-12:30');
});

test('removing a block with prev extends the block before it', () => {
  const after = removeBlock(tue(), 'tue-lunch', 'prev');
  assert.equal(at(after, 'tue-lunch'), undefined);
  assert.equal(span(at(after, 'tue-talk')), '10:30-12:30');
  assert.equal(at(after, 'tue-talk').hours, 2);
  assert.equal(span(at(after, 'tue-coursework')), '12:30-14:00');
  assert.equal(after.length, 11);
  assert.equal(validateList(after, WAKE, SLEEP, T), true);
});

test('removing a block with next pulls the block after it back', () => {
  const after = removeBlock(tue(), 'tue-lunch', 'next');
  assert.equal(span(at(after, 'tue-talk')), '10:30-11:30');
  assert.equal(span(at(after, 'tue-coursework')), '11:30-14:00');
  assert.equal(validateList(after, WAKE, SLEEP, T), true);
});

test('removing a block with divide sets the seam between its neighbours', () => {
  const after = removeBlock(tue(), 'tue-lunch', 'divide', '12:00');
  assert.equal(span(at(after, 'tue-talk')), '10:30-12:00');
  assert.equal(span(at(after, 'tue-coursework')), '12:00-14:00');
  assert.equal(validateList(after, WAKE, SLEEP, T), true);
});

test('removing the first block extends the second back to wake whatever the mode', () => {
  for (const mode of ['prev', 'next', 'divide']) {
    const after = removeBlock(tue(), 'tue-topfocus', mode, '06:15');
    assert.equal(after[0].id, 'tue-breakfast');
    assert.equal(span(after[0]), '06:00-07:30');
    assert.equal(validateList(after, WAKE, SLEEP, T), true);
  }
});

test('removing the last block extends its predecessor to sleep whatever the mode', () => {
  for (const mode of ['prev', 'next', 'divide']) {
    const after = removeBlock(tue(), 'tue-evening', mode, '21:30');
    assert.equal(after.at(-1).id, 'tue-reward');
    assert.equal(span(after.at(-1)), '19:30-22:30');
    assert.equal(validateList(after, WAKE, SLEEP, T), true);
  }
});

test('divide needs an on-grid seam inside both neighbours', () => {
  assert.throws(() => removeBlock(tue(), 'tue-lunch', 'divide', '12:07'), /15/);
  // tue-talk starts 10:30, so the seam cannot land before 10:45.
  assert.throws(() => removeBlock(tue(), 'tue-lunch', 'divide', '10:30'), /between/);
  // tue-coursework ends 14:00, so it cannot land after 13:45.
  assert.throws(() => removeBlock(tue(), 'tue-lunch', 'divide', '14:00'), /between/);
});

test('divide with no seam given is rejected', () => {
  assert.throws(() => removeBlock(tue(), 'tue-lunch', 'divide'), (e) => e instanceof ValidationError);
});

test('an unknown mode is rejected', () => {
  assert.throws(() => removeBlock(tue(), 'tue-lunch', 'sideways'), /mode/);
});

test('removing the only block is rejected', () => {
  const one = [{ ...tue()[0], start: WAKE, end: SLEEP, hours: 16.5, campaignSlot: true }];
  assert.throws(() => removeBlock(one, one[0].id, 'prev'), /last remaining/);
});

test('removing an unknown block is rejected', () => {
  assert.throws(() => removeBlock(tue(), 'tue-nope', 'prev'), /unknown block/);
});

test('removing the campaign slot leaves the list invalid rather than guessing', () => {
  const after = removeBlock(tue(), 'tue-talk', 'prev');
  assert.equal(after.filter(b => b.campaignSlot).length, 0);
  assert.throws(() => validateList(after, WAKE, SLEEP, T), /campaign/);
});

test('removeBlock does not mutate its input', () => {
  const before = tue();
  removeBlock(before, 'tue-lunch', 'prev');
  assert.equal(before.length, 12);
  assert.equal(span(at(before, 'tue-talk')), '10:30-11:30');
});

const AT = '2026-08-13T21:04:11.208Z';
const TODAY = '2026-08-13';

test('editFields patches only the fields named', () => {
  const after = editFields(tue(), 'tue-lunch', { label: 'Lunch', detail: 'Leftovers.' });
  assert.equal(at(after, 'tue-lunch').label, 'Lunch');
  assert.equal(at(after, 'tue-lunch').detail, 'Leftovers.');
  assert.equal(span(at(after, 'tue-lunch')), '11:30-12:30');
  assert.equal(at(after, 'tue-lunch').attribute, 'lifeskills');
  assert.equal(validateList(after, WAKE, SLEEP, T), true);
});

test('setting campaignSlot clears it everywhere else', () => {
  const after = editFields(tue(), 'tue-lunch', { campaignSlot: true });
  assert.equal(at(after, 'tue-lunch').campaignSlot, true);
  assert.equal(at(after, 'tue-talk').campaignSlot, false);
  assert.equal(after.filter(b => b.campaignSlot).length, 1);
  assert.equal(validateList(after, WAKE, SLEEP, T), true);
});

test('clearing campaignSlot is refused, because a day needs exactly one', () => {
  assert.throws(() => editFields(tue(), 'tue-talk', { campaignSlot: false }), /campaign/);
});

test('editFields rejects a structural key', () => {
  for (const key of ['start', 'end', 'hours', 'id']) {
    assert.throws(() => editFields(tue(), 'tue-lunch', { [key]: 'x' }), /cannot be edited/);
  }
});

test('editFields rejects an unknown block and an unknown field', () => {
  assert.throws(() => editFields(tue(), 'tue-nope', { label: 'x' }), /unknown block/);
  assert.throws(() => editFields(tue(), 'tue-lunch', { colour: 'red' }), /cannot be edited/);
});

test('editFields does not mutate its input', () => {
  const before = tue();
  editFields(before, 'tue-lunch', { label: 'Lunch' });
  assert.equal(at(before, 'tue-lunch').label, 'Lunch and chores');
});

test('streakSignature ignores everything a retime or a relabel touches', () => {
  const base = streakSignature(tue());
  assert.equal(streakSignature(moveBoundary(tue(), 2, '11:00')), base);
  assert.equal(streakSignature(editFields(tue(), 'tue-lunch', { label: 'Lunch' })), base);
  assert.equal(streakSignature(editFields(tue(), 'tue-lunch', { detail: 'x' })), base);
  assert.equal(streakSignature(editFields(tue(), 'tue-lunch', { attribute: 'vitality' })), base);
  assert.equal(streakSignature(editFields(tue(), 'tue-lunch', { taskId: 'showed-up' })), base);
  assert.equal(streakSignature(editFields(tue(), 'tue-lunch', {
    calendar: { event: true, remindMinutes: 30 },
  })), base);
});

test('streakSignature changes when a streak id appears or disappears', () => {
  const base = streakSignature(tue());
  assert.notEqual(streakSignature(editFields(tue(), 'tue-lunch', { streakId: 'workout' })), base);
  assert.notEqual(streakSignature(removeBlock(tue(), 'tue-topfocus', 'next')), base);
  // top-focus is on one Tuesday block only, so removing it drops the id.
  assert.notEqual(streakSignature(removeBlock(tue(), 'tue-client1', 'prev')), base);
});

test('streakSignature changes when the campaign slot moves', () => {
  const base = streakSignature(tue());
  assert.notEqual(streakSignature(editFields(tue(), 'tue-lunch', { campaignSlot: true })), base);
});

test('putBlockList stamps daysUpdatedAt for that list only', () => {
  const blocks = moveBoundary(tue(), 2, '11:00');
  const { template } = putBlockList({ template: T, dow: 'tue', branch: null, blocks, at: AT, today: TODAY });
  assert.equal(template.daysUpdatedAt.tue, AT);
  assert.equal(template.daysUpdatedAt['mon/A'] ?? null, null);
  assert.equal(template.days.tue.blocks[2].end, '11:00');
  // The input template is untouched.
  assert.equal(T.days.tue.blocks[2].end, '10:30');
});

test('a pure retime does not move the streak epoch', () => {
  const blocks = moveBoundary(tue(), 2, '11:00');
  const { template } = putBlockList({ template: T, dow: 'tue', branch: null, blocks, at: AT, today: TODAY });
  assert.equal(template.daysStreakEpoch.tue ?? null, null);
});

test('a structural streak change moves the epoch to today', () => {
  const blocks = editFields(tue(), 'tue-lunch', { streakId: 'workout' });
  const { template } = putBlockList({ template: T, dow: 'tue', branch: null, blocks, at: AT, today: TODAY });
  assert.equal(template.daysStreakEpoch.tue, TODAY);
  assert.equal(template.daysUpdatedAt.tue, AT);
});

test('putBlockList refuses to write an invalid list', () => {
  const blocks = removeBlock(tue(), 'tue-talk', 'prev'); // drops the campaign slot
  assert.throws(
    () => putBlockList({ template: T, dow: 'tue', branch: null, blocks, at: AT, today: TODAY }),
    /campaign/,
  );
});

test('putBlockList writes into a branch', () => {
  const monA = blocksFor(T, 'mon', 'A').map(b => ({ ...b }));
  const blocks = moveBoundary(monA, 0, '06:45');
  const { template } = putBlockList({ template: T, dow: 'mon', branch: 'A', blocks, at: AT, today: TODAY });
  assert.equal(template.days.mon.branches.A[0].end, '06:45');
  assert.equal(template.daysUpdatedAt[listKey('mon', 'A')], AT);
  assert.deepEqual(template.days.mon.branches.B, T.days.mon.branches.B);
});

test('toOverride snapshots structure and leaves template fields to resolve live', () => {
  const snap = toOverride(T, moveBoundary(tue(), 2, '11:00'));
  assert.equal(snap.length, 12);
  assert.deepEqual(snap[2], { id: 'tue-client1', start: '07:30', end: '11:00', hours: 3.5, fields: null });
  assert.ok(snap.every(e => e.fields === null));
  assert.ok(snap.every(e => !('label' in e)));
});

test('toOverride carries the fields of a block the template does not have', () => {
  const placed = placeBlock(tue(), { start: '11:00', end: '12:00', fields: DENTIST, id: '2026-08-18-dentist' });
  const snap = toOverride(T, placed);
  const entry = snap.find(e => e.id === '2026-08-18-dentist');
  assert.equal(entry.fields.label, 'Dentist');
  assert.equal(entry.fields.attribute, 'lifeskills');
  assert.equal(entry.fields.start, undefined);
  assert.equal(snap.find(e => e.id === 'tue-talk').fields, null);
});
