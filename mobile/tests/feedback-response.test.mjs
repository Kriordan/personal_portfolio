import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  FeedbackResponseDrafts,
  responseDraftIndex,
} from '../src/lib/feedback-response-drafts.ts';
import { clearStoredWorkDrafts } from '../src/lib/practice-work-drafts.ts';
import {
  copyResponse,
  responseRoute,
  responsePath,
  responseNoteLength,
  validResponseEdit,
  feedbackReturnRoute,
} from '../src/lib/feedback-response-model.ts';
import { createPracticeClient } from '../src/lib/practice-client.ts';
import { PracticeOperation } from '../src/lib/practice-operation.ts';
import { LearningSession } from '../src/lib/learning-session.ts';
import {
  isStoredAttempt,
  ratingPath,
  ratingBody,
  reviewRoute,
} from '../src/lib/learning-model.ts';
import { isPracticeChange, practiceKeys } from '../src/lib/practice-model.ts';

const sid = '76f7750a-6a22-4594-b6c1-a807fc9aab41';
const rid = 'abf91dc0-d95e-4a00-bb7f-a9f77a433871';
const source = { sessionId: sid, submission_sequence: 7, findingId: 'f2' };
const edit = {
  kind: 'annotate',
  submission_sequence: 7,
  findingId: 'f2',
  base_revision: 0,
  decision: 'agree',
  note: 'Test simultaneous requests.',
};
const change = {
  ...edit,
  ...source,
  conceptId: 'idempotency',
  request_id: rid,
};
const result = {
  session_id: sid,
  submission_sequence: 7,
  finding_id: 'f2',
  revision: 1,
  changed: true,
};
const card = {
  card_id: 'idempotency:race',
  progress_revision: 0,
  content_version: 3,
};
const tick = () => new Promise((resolve) => setImmediate(resolve));
const fail = () => {
  throw new Error('offline');
};
const receipt = (input) => ({
  request_id: input.request_id,
  card_id: input.card_id,
  content_version: input.content_version,
  rating: input.rating,
  next_review_display: 'Tomorrow',
  progress_revision: 1,
});
function storage() {
  let value = null;
  return {
    read: async () => value,
    write: async (v) => {
      value = v;
    },
    clear: async () => {
      value = null;
    },
  };
}
function operation(api = {}, overrides = {}) {
  const writes = [];
  const deps = {
    storage: storage(),
    api: {
      change: async (c) => {
        writes.push(c);
        return result;
      },
      receipt: async () => ({ receipt: null }),
      ...api,
    },
    online: () => true,
    onConfirmed: async () => {},
    ...overrides,
  };
  return { controller: new PracticeOperation(1, deps), deps, writes };
}
function drafts() {
  const data = new Map();
  let tail = Promise.resolve();
  const serial = (run) => {
    const next = tail.then(run, run);
    tail = next.catch(() => {});
    return next;
  };
  const store = {
    get: async (k) => data.get(k) ?? null,
    set: async (k, v) => {
      data.set(k, v);
    },
    remove: async (k) => {
      data.delete(k);
    },
  };
  return {
    controller: new FeedbackResponseDrafts(1, store, serial),
    store,
    serial,
    data,
  };
}
test('response, reveal and rating adapters use exact existing contracts with no private or local fields', async () => {
  const calls = [];
  const api = createPracticeClient(async (...args) => {
    calls.push(args);
    return {};
  });
  await api.change(change);
  assert.equal(calls[0][0], `${responsePath(source)}/response`);
  assert.deepEqual(calls[0][1].body, {
    expected_revision: 0,
    request_id: rid,
    decision: 'agree',
    note: edit.note,
  });
  await api.focusedReview(source);
  await api.revealFocused(source, card, rid);
  assert.equal(calls[1][0], `${responsePath(source)}/review`);
  const url = new URL(calls[2][0], 'https://fixture.test');
  assert.deepEqual(Object.fromEntries(url.searchParams), {
    card_id: card.card_id,
    content_version: '3',
    expected_revision: '0',
    request_id: rid,
  });
  const input = {
    ...card,
    request_id: rid,
    expected_revision: 0,
    rating: 4,
    response_ms: 12,
    session_id: rid,
    feedback_source: source,
  };
  assert.equal(ratingPath(input), `${responsePath(source)}/review`);
  assert.deepEqual(ratingBody(input), {
    request_id: rid,
    expected_revision: 0,
    card_id: card.card_id,
    content_version: 3,
    rating: 4,
  });
  assert.notDeepEqual(
    practiceKeys.focused(1, source),
    practiceKeys.focused(2, source),
  );
  assert.notDeepEqual(
    practiceKeys.focused(1, source),
    practiceKeys.focused(1, { ...source, findingId: 'f3' }),
  );
});
test('response validation counts Unicode like Python and keeps unfinished drafts without allowing invalid sends', () => {
  assert.equal(validResponseEdit({ ...edit, note: '💡'.repeat(2000) }), true);
  assert.equal(responseNoteLength('💡\r\nx'), 3);
  assert.equal(copyResponse({ ...edit, note: 'a\r\nb\r' }).note, 'a\nb\n');
  for (const note of ['x'.repeat(2001), '\0', '\ud800']) {
    assert.equal(validResponseEdit({ ...edit, note }), false);
    assert.equal(validResponseEdit({ ...edit, note }, true), true);
  }
  for (const patch of [
    { findingId: '../other' },
    { submission_sequence: 0 },
    { base_revision: -1 },
    { decision: 'maybe' },
    { note: null },
  ])
    assert.equal(isPracticeChange({ ...change, ...patch }), false);
});
test('annotation duplicate taps freeze intent before sending, and validate the receipt boundary', async () => {
  let resolve;
  const waiting = new Promise((r) => {
    resolve = r;
  });
  const h = operation({
    change: async (c) => {
      h.writes.push(c);
      await waiting;
      return result;
    },
  });
  await h.controller.restore();
  const mutable = { ...change };
  const saving = h.controller.begin(mutable);
  mutable.note = 'later';
  await h.controller.begin({ ...change, note: 'second tap' });
  await tick();
  assert.equal(h.writes.length, 1);
  assert.equal(JSON.parse(await h.deps.storage.read()).change.note, edit.note);
  resolve();
  await saving;
  assert.equal(h.controller.snapshot().saved.result.revision, 1);
  for (const patch of [
    { finding_id: 'f3' },
    { submission_sequence: 8 },
    { revision: 2 },
    { changed: false },
    { session_id: rid },
  ]) {
    const bad = operation({ change: async () => ({ ...result, ...patch }) });
    await bad.controller.restore();
    await bad.controller.begin(change);
    assert.equal(bad.controller.snapshot().phase, 'uncertain');
    assert.ok(await bad.deps.storage.read());
  }
});
test('lost annotation survives restart; automatic recovery reads only and matches metadata-only receipt', async () => {
  let readable = false,
    calls = 0;
  const h = operation({
    change: async () => {
      calls++;
      fail();
    },
    receipt: async () =>
      readable
        ? { receipt: { operation: 'annotate', response: result } }
        : fail(),
  });
  await h.controller.restore();
  await h.controller.begin(change);
  h.controller.dispose();
  const restarted = new PracticeOperation(1, h.deps);
  await restarted.restore();
  assert.equal(calls, 1);
  assert.equal(restarted.snapshot().pending.note, edit.note);
  readable = true;
  await restarted.check();
  assert.equal(calls, 1);
  assert.equal(restarted.snapshot().pending, null);
  assert.equal(await h.deps.storage.read(), null);
});
test('stale response is retained without automatic overwrite; explicit same-ID retry handles uncertainty', async () => {
  const rejected = operation({
    change: async () => {
      throw { status: 409, body: { code: 'stale_annotation' } };
    },
  });
  await rejected.controller.restore();
  await rejected.controller.begin(change);
  assert.equal(rejected.controller.snapshot().phase, 'rejected');
  await rejected.controller.retry();
  assert.equal(rejected.controller.snapshot().pending.note, edit.note);
  assert.equal(await rejected.controller.dismissRejected(), true);
  let succeed = false;
  const h = operation({
    change: async (c) => {
      h.writes.push(c);
      return succeed ? result : fail();
    },
  });
  await h.controller.restore();
  await h.controller.begin(change);
  await h.controller.check();
  assert.equal(h.writes.length, 1);
  succeed = true;
  await h.controller.retry();
  assert.deepEqual(h.writes, [change, change]);
});
test('storage failure, offline mode and account disposal never send or confirm another account’s response', async () => {
  for (const overrides of [
    { storage: { ...storage(), write: async () => fail() } },
    { online: () => false },
  ]) {
    const h = operation({}, overrides);
    await h.controller.restore();
    await h.controller.begin(change);
    assert.equal(h.writes.length, 0);
  }
  const h = operation();
  await h.deps.storage.write(JSON.stringify({ userId: 1, change }));
  let confirmed = 0;
  const other = new PracticeOperation(2, {
    ...h.deps,
    onConfirmed: async () => {
      confirmed++;
    },
  });
  await other.restore();
  assert.equal(other.snapshot().pending, null);
  assert.equal(confirmed, 0);
});
test('response drafts persist original revisions per finding/snapshot and rebase only explicitly', async () => {
  const h = drafts();
  await h.controller.load(sid);
  h.controller.edit(sid, edit);
  h.controller.edit(sid, {
    ...edit,
    findingId: 'f3',
    note: 'Different finding',
  });
  h.controller.edit(sid, {
    ...edit,
    submission_sequence: 8,
    note: 'Different snapshot',
  });
  await tick();
  const restored = new FeedbackResponseDrafts(1, h.store, h.serial);
  await restored.load(sid);
  assert.equal(restored.snapshot(sid).edits.length, 3);
  assert.equal(restored.snapshot(sid).edits[0].base_revision, 0);
  restored.rebase(sid, { ...edit, base_revision: 2, note: 'web text' });
  await tick();
  const rebased = restored
    .snapshot(sid)
    .edits.find((e) => e.submission_sequence === 7 && e.findingId === 'f2');
  assert.equal(rebased.base_revision, 2);
  assert.equal(rebased.note, edit.note);
  await restored.clearIfMatches(sid, edit); // old request cannot clear a newer draft
  assert.equal(restored.snapshot(sid).edits.length, 3);
  await restored.clearIfMatches(sid, rebased);
  assert.equal(restored.snapshot(sid).edits.length, 2);
});
test('response draft storage failures remain visible and sign-out cleanup cannot be undone by late writes', async () => {
  const h = drafts();
  await h.controller.load(sid);
  const set = h.store.set;
  h.store.set = async () => fail();
  h.controller.edit(sid, edit);
  await tick();
  assert.ok(h.controller.snapshot(sid).error);
  assert.equal(h.controller.snapshot(sid).edits[0].note, edit.note);
  h.store.set = set;
  h.controller.retrySave(sid);
  await tick();
  assert.equal(h.controller.snapshot(sid).error, null);
  h.controller.edit(sid, { ...edit, note: 'newer' });
  h.controller.dispose();
  await h.serial(() => clearStoredWorkDrafts(h.store, responseDraftIndex));
  await tick();
  assert.equal(h.data.size, 0);
});
test('another account cannot read response drafts, and saving clears the old account namespace', async () => {
  const h = drafts();
  await h.controller.load(sid);
  h.controller.edit(sid, edit);
  await tick();
  h.controller.dispose();
  const other = new FeedbackResponseDrafts(2, h.store, h.serial);
  await other.load(sid);
  assert.deepEqual(other.snapshot(sid).edits, []);
  other.edit(sid, { ...edit, note: 'account two' });
  await tick();
  assert.equal(h.data.has(`${responseDraftIndex}.1.${sid}`), false);
});
test('focused rating recovery retains its route, snapshot and finding across restart and explicit retry', async () => {
  const stored = storage();
  let succeed = false,
    readable = false;
  const posts = [];
  const deps = {
    storage: stored,
    online: () => true,
    uuid: () => rid,
    onConfirmed: () => {},
    api: {
      rateCard: async (input) => {
        posts.push(input);
        return succeed ? receipt(input) : fail();
      },
      getReceipt: async () =>
        readable ? { receipt: receipt(posts[0]) } : { receipt: null },
    },
  };
  const first = new LearningSession(1, deps);
  await first.restore();
  const mutable = { ...source };
  await first.begin(card, 4, 200, rid, mutable);
  mutable.findingId = 'changed later';
  first.dispose();
  const restarted = new LearningSession(1, deps);
  await restarted.restore();
  assert.equal(posts.length, 1);
  assert.deepEqual(
    reviewRoute(restarted.snapshot().attempt),
    responseRoute(source, true),
  );
  assert.equal(
    ratingPath(restarted.snapshot().attempt),
    `${responsePath(source)}/review`,
  );
  await restarted.check();
  assert.equal(posts.length, 1);
  succeed = true;
  await restarted.retry();
  assert.deepEqual(posts[0], posts[1]);
  assert.equal(restarted.snapshot().confirmed.length, 1);
  readable = true;
  await restarted.check();
  assert.equal(posts.length, 2);
});
test('committed focused rating recovers by receipt without another rating, including from a different screen', async () => {
  const stored = storage();
  let readable = false;
  const posts = [];
  const deps = {
    storage: stored,
    online: () => true,
    uuid: () => rid,
    onConfirmed: () => {},
    api: {
      rateCard: async (input) => {
        posts.push(input);
        fail();
      },
      getReceipt: async () =>
        readable ? { receipt: receipt(posts[0]) } : fail(),
    },
  };
  const first = new LearningSession(1, deps);
  await first.restore();
  await first.begin(card, 0, 0, rid, source);
  first.dispose();
  readable = true;
  const home = new LearningSession(1, deps);
  await home.restore();
  assert.equal(home.snapshot().attempt, null);
  assert.equal(home.snapshot().confirmed.length, 1);
  assert.deepEqual(home.snapshot().confirmed[0].input.feedback_source, source);
  assert.equal(posts.length, 1);
});
test('corrupt feedback recovery never falls back to ordinary review, and old ratings keep original routes', async () => {
  const input = {
    request_id: rid,
    card_id: card.card_id,
    rating: 4,
    expected_revision: 0,
    content_version: 3,
    response_ms: 0,
    session_id: rid,
    feedback_source: source,
  };
  assert.equal(isStoredAttempt(input), true);
  for (const bad of [
    null,
    {},
    { ...source, submission_sequence: 0 },
    { ...source, findingId: '../other' },
  ]) {
    const corrupt = { ...input, feedback_source: bad };
    assert.equal(isStoredAttempt(corrupt), false);
    const stored = storage();
    await stored.write(JSON.stringify({ userId: 1, input: corrupt }));
    const controller = new LearningSession(1, {
      storage: stored,
      api: { rateCard: fail, getReceipt: fail },
      online: () => true,
      uuid: () => rid,
      onConfirmed: fail,
    });
    await controller.restore();
    assert.equal(controller.snapshot().ready, false);
  }
  const { feedback_source, ...ordinary } = input;
  assert.equal(ratingPath(ordinary), '/learning/concepts/idempotency/rate');
  assert.deepEqual(ratingBody(ordinary), ordinary);
  const { content_version, ...legacy } = ordinary;
  assert.equal(ratingPath(legacy), '/learning/rate');
  assert.deepEqual(feedbackReturnRoute('idempotency', source).params, {
    id: 'idempotency',
    practice_session: sid,
    work: 'feedback',
    snapshot: '7',
    finding: 'f2',
  });
});
