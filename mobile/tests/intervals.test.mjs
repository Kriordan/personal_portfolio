import assert from 'node:assert/strict';
import test from 'node:test';
import { defaultIntervalLibrary, duplicateBlock, expandWorkout, formatDuration, intervalAt, moveBlock, readIntervalLibrary, validateWorkout } from '../src/lib/interval-model.ts';
import { createIntervalStore } from '../src/lib/interval-store.ts';
import { createIntervalSession } from '../src/lib/interval-session.ts';

const example = () => defaultIntervalLibrary().workouts[0];
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const tick = () => new Promise((resolve) => setImmediate(resolve));

test('run/walk preset is 18 intervals and exactly 34 minutes with eight complete rounds', () => {
  const timeline = expandWorkout(example());
  assert.equal(timeline.length, 18);
  assert.equal(timeline.at(-1).end, 2040);
  for (let round = 1; round <= 8; round++) {
    const jog = timeline[round * 2 - 1], walk = timeline[round * 2];
    assert.deepEqual([jog.name, jog.seconds, jog.round, jog.rounds, jog.start], ['Jog', 120, round, 8, 300 + (round - 1) * 180]);
    assert.deepEqual([walk.name, walk.seconds, walk.round, walk.rounds, walk.start], ['Walk', 60, round, 8, jog.end]);
  }
  assert.equal(timeline[17].start, 1740);
  assert.equal(intervalAt(timeline, 299.99), 0);
  assert.equal(intervalAt(timeline, 300), 1);
  assert.equal(intervalAt(timeline, 2040), -1);
  assert.equal(formatDuration(60.001), '1:01');
});

test('rejects unsafe expansion, nested groups, duplicate IDs, invalid labels and durations', () => {
  for (const seconds of [0, -1, 1.5, NaN, Infinity, 14_401, '60']) {
    const workout = example(); workout.blocks[0].seconds = seconds;
    assert.ok(validateWorkout(workout));
    assert.throws(() => expandWorkout(workout));
  }
  for (const repeats of [0, -1, 1.5, Number.MAX_SAFE_INTEGER, '8']) {
    const workout = example(); workout.blocks[1].repeats = repeats;
    assert.ok(validateWorkout(workout));
  }
  const nested = example(); nested.blocks[1].intervals.push(nested.blocks[1]);
  assert.ok(validateWorkout(nested));
  const duplicate = example(); duplicate.blocks[0].id = 'jog';
  assert.ok(validateWorkout(duplicate));
  const empty = example(); empty.blocks[1].intervals = [];
  assert.ok(validateWorkout(empty));
  const blank = example(); blank.blocks[0].name = '   ';
  assert.ok(validateWorkout(blank));
  const long = example(); long.blocks[0].name = 'x'.repeat(81);
  assert.ok(validateWorkout(long));
  const max = { id: 'max', name: 'Maximum', blocks: [{ kind: 'repeat', id: 'g', repeats: 500, intervals: [{ kind: 'interval', id: 'a', name: 'Step', seconds: 1 }] }] };
  assert.equal(expandWorkout(max).length, 500);
  max.blocks[0].intervals.push({ kind: 'interval', id: 'b', name: 'Step', seconds: 1 });
  assert.ok(validateWorkout(max));
});

test('block duplication gives independent identifiers and moves preserve group contents', () => {
  const workout = example(); let sequence = 0;
  const copy = duplicateBlock(workout.blocks[1], () => `copy${++sequence}`);
  assert.equal(new Set([copy.id, ...copy.intervals.map((item) => item.id)]).size, 3);
  copy.intervals[0].name = 'Changed';
  assert.equal(workout.blocks[1].intervals[0].name, 'Jog');
  const moved = moveBlock(workout.blocks, 1, -1);
  assert.equal(moved[0], workout.blocks[1]);
  assert.equal(moveBlock(moved, 0, -1), moved);
});

test('only missing storage seeds the example; deleting all and corruption survive reload', () => {
  assert.equal(readIntervalLibrary(null).workouts.length, 1);
  assert.equal(readIntervalLibrary(JSON.stringify({ version: 1, volume: 0.5, workouts: [] })).workouts.length, 0);
  for (const raw of ['bad json', 'null', '{"version":2,"workouts":[],"volume":1}', '{"version":1,"workouts":[],"volume":0}'])
    assert.throws(() => readIntervalLibrary(raw));
});

test('serialized saves do not lose concurrent changes and a disk failure keeps the last good library', async () => {
  let raw = null, fail = false;
  const storage = { readLibrary: async () => raw, writeLibrary: async (next) => { if (fail) throw Error('disk full'); raw = next; } };
  const store = createIntervalStore(storage);
  await store.read();
  await Promise.all([
    store.change((library) => ({ ...library, volume: 0.3 })),
    store.change((library) => ({ ...library, workouts: [] })),
  ]);
  assert.deepEqual(await store.read(), { version: 1, volume: 0.3, workouts: [] });
  fail = true;
  await assert.rejects(store.change((library) => ({ ...library, volume: 0.9 })));
  assert.equal((await store.read()).volume, 0.3);
  fail = false;
  assert.equal((await createIntervalStore(storage).read()).workouts.length, 0);
});

function fakePort() {
  let audio = { state: 'idle', position: 0, duration: 2040, reason: null };
  let listener = () => {};
  let prepares = 0, plays = 0;
  const port = {
    async prepare() { prepares++; audio = { ...audio, state: 'ready' }; return audio; },
    async play() { plays++; audio = { ...audio, state: 'running' }; return audio; },
    async pause() { audio = { ...audio, state: 'paused' }; return audio; },
    async skip() { audio = { ...audio, position: audio.position + 60 }; return audio; },
    async stop() { audio = { ...audio, state: 'idle', position: 0 }; return audio; },
    async setVolume() {}, async snapshot() { return audio; }, async preview() {},
    async readLibrary() { return null; }, async writeLibrary() {},
    addListener(_, callback) { listener = callback; return { remove() {} }; },
  };
  return { port, counts: () => ({ prepares, plays }), emit: (change) => { audio = { ...audio, ...change }; listener(audio); } };
}

test('double start is ignored; pause freezes position; skip and resume use native snapshots', async () => {
  const fake = fakePort(); const session = createIntervalSession(fake.port); const workout = example();
  await Promise.all([session.start(workout, 1), session.start(workout, 1)]);
  assert.deepEqual(fake.counts(), { prepares: 1, plays: 1 });
  workout.blocks[0].name = 'Edited saved workout';
  assert.equal(session.getSnapshot().workout.blocks[0].name, 'Warm-up');
  fake.emit({ position: 123 });
  await session.pause(); assert.equal(session.getSnapshot().audio.position, 123);
  await session.skip(); assert.equal(session.getSnapshot().audio.position, 183);
  assert.equal(session.getSnapshot().audio.state, 'paused');
  await session.resume(); assert.equal(session.getSnapshot().audio.state, 'running');
  fake.emit({ state: 'completed', position: 2040 });
  assert.equal(session.getSnapshot().audio.state, 'completed');
});

test('logout/cancel during preparation cannot start late audio or revive a cancelled session', async () => {
  const fake = fakePort(); const gate = deferred();
  fake.port.prepare = () => gate.promise;
  const session = createIntervalSession(fake.port);
  const starting = session.start(example(), 1);
  await tick();
  await session.stop();
  gate.resolve({ state: 'ready', position: 0, duration: 2040, reason: null });
  await starting;
  assert.equal(fake.counts().plays, 0);
  fake.emit({ state: 'running' });
  assert.equal(session.getSnapshot().workout, null);
});

test('preparation failure can retry and late pause results do not overwrite a newer run', async () => {
  const fake = fakePort(); const prepare = fake.port.prepare;
  fake.port.prepare = async () => { throw Error('no voice'); };
  const session = createIntervalSession(fake.port);
  await session.start(example(), 1);
  assert.equal(session.getSnapshot().audio.state, 'error');
  fake.port.prepare = prepare;
  await session.start(example(), 1);
  const gate = deferred(); fake.port.pause = () => gate.promise;
  const pausing = session.pause();
  await session.stop();
  await session.start(example(), 1);
  gate.resolve({ state: 'paused', position: 123, duration: 2040, reason: null });
  await pausing;
  assert.equal(session.getSnapshot().audio.state, 'running');
  assert.equal(session.getSnapshot().audio.position, 0);
});

test('a sound preview ending after a completed run does not block the next workout', async () => {
  const fake = fakePort(); const session = createIntervalSession(fake.port);
  await session.start(example(), 1);
  fake.emit({ state: 'completed', position: 2040 });
  fake.emit({ state: 'idle', position: 0 });
  await session.start(example(), 1);
  assert.equal(session.getSnapshot().audio.state, 'running');
  assert.equal(fake.counts().plays, 2);
});
