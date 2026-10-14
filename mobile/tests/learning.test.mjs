import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { test } from 'node:test';
import {
  QueryClient,
  QueryObserver,
  focusManager,
  onlineManager,
} from '@tanstack/react-query';
import { LearningSession } from '../src/lib/learning-session.ts';
import {
  browseNotes,
  learningKeys,
  validNoteId,
} from '../src/lib/learning-model.ts';
import {
  learningQueueOptions,
  learningRefreshOptions,
  reconcileLearningRating,
} from '../src/lib/learning-cache.ts';

const tick = () => new Promise((resolve) => setImmediate(resolve));
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
};
const card = { card_id: 'topic:q', progress_revision: 0 };
const response = (input) => ({
  request_id: input.request_id,
  card_id: input.card_id,
  rating: input.rating,
  next_review_display: 'Next review in 1 day',
  progress_revision: 1,
});
function harness(overrides = {}) {
  let value = null;
  let online = true;
  let reconciliations = 0;
  const posts = [];
  const storage = {
    read: async () => value,
    write: async (raw) => {
      value = raw;
    },
    clear: async () => {
      value = null;
    },
  };
  const api = {
    rateCard: async (input) => {
      posts.push(input);
      return response(input);
    },
    getReceipt: async () => ({ receipt: null }),
    ...overrides,
  };
  const deps = {
    api,
    storage,
    online: () => online,
    uuid: randomUUID,
    onConfirmed: () => {
      reconciliations++;
    },
  };
  return {
    session: new LearningSession(1, deps),
    deps,
    storage,
    posts,
    stored: () => value,
    setOnline: (next) => {
      online = next;
    },
    reconciliations: () => reconciliations,
  };
}

test('browse search, filter and deterministic sort compose without changing the source', () => {
  const notes = [
    {
      id: 'ten',
      title: 'Topic 10',
      summary: 'Databases',
      tags: ['Postgres'],
      due_count: 0,
      created_at: '2026-01-01',
    },
    {
      id: 'two',
      title: 'Topic 2',
      summary: 'Database',
      tags: ['SQL'],
      due_count: 4,
      created_at: '2026-02-01',
    },
    {
      id: 'one',
      title: 'Topic 1',
      summary: 'Database',
      tags: ['SQL'],
      due_count: 4,
    },
  ];
  assert.deepEqual(
    browseNotes(notes, '', 'all', 'due').map((n) => n.id),
    ['one', 'two', 'ten'],
  );
  assert.deepEqual(
    browseNotes(notes, '  SQL  database ', 'due', 'newest').map((n) => n.id),
    ['two', 'one'],
  );
  assert.deepEqual(
    browseNotes(notes, 'POSTGRES', 'all', 'title').map((n) => n.id),
    ['ten'],
  );
  assert.deepEqual(browseNotes(notes, 'POSTGRES', 'due', 'title'), []);
  assert.deepEqual(
    notes.map((n) => n.id),
    ['ten', 'two', 'one'],
  );
  for (const id of ['', '../note', ['one'], 'a'.repeat(101), 'UPPER'])
    assert.equal(validNoteId(id), false);
  assert.equal(validNoteId('topic-2'), true);
});

test('rapid taps freeze one rating and advance only after confirmed persistence', async () => {
  const pending = deferred();
  const h = harness({
    rateCard: async (input) => {
      h.posts.push(input);
      return pending.promise;
    },
  });
  await h.session.restore();
  const first = h.session.begin(card, 4, 1000, 'session');
  await h.session.begin(card, 0, 1200, 'session');
  await tick();
  assert.equal(h.posts.length, 1);
  assert.equal(h.session.snapshot().confirmed.length, 0);
  assert.equal(JSON.parse(h.stored()).input.rating, 4);
  pending.resolve(response(h.posts[0]));
  await first;
  assert.equal(h.session.snapshot().confirmed.length, 1);
  assert.equal(h.stored(), null);
  assert.equal(h.reconciliations(), 1);
});

test('known offline ratings are not stored or replayed when connectivity returns', async () => {
  const h = harness();
  await h.session.restore();
  h.setOnline(false);
  await h.session.begin(card, 4, 100, 'session');
  assert.equal(h.posts.length, 0);
  assert.equal(h.stored(), null);
  h.setOnline(true);
  await h.session.check();
  await tick();
  assert.equal(h.posts.length, 0);
  await h.session.begin(card, 4, 100, 'session');
  assert.equal(h.posts.length, 1);
});

test('a lost POST response recovers a receipt without another write', async () => {
  let saved;
  const h = harness({
    rateCard: async (input) => {
      h.posts.push(input);
      saved = response(input);
      throw Error('response lost');
    },
    getReceipt: async () => ({ receipt: saved }),
  });
  await h.session.restore();
  await h.session.begin(card, 3, 200, 'session');
  assert.equal(h.posts.length, 1);
  assert.equal(h.session.snapshot().confirmed[0].result.rating, 3);
  assert.equal(h.session.snapshot().phase, 'idle');
});

test('unknown outcomes and failed status reads retain the exact payload for explicit retry', async () => {
  const h = harness({
    rateCard: async (input) => {
      h.posts.push(input);
      if (h.posts.length === 1) throw Error('timeout');
      return response(input);
    },
  });
  await h.session.restore();
  await h.session.begin(card, 0, 123, 'session');
  const original = h.stored();
  h.deps.api.getReceipt = async () => {
    throw Error('status unavailable');
  };
  await h.session.check();
  await h.session.begin(card, 5, 999, 'another-session');
  assert.equal(h.stored(), original);
  assert.equal(h.posts.length, 1);
  assert.equal(h.session.snapshot().phase, 'uncertain');
  await h.session.retry();
  assert.equal(h.posts.length, 2);
  assert.deepEqual(h.posts[0], h.posts[1]);
  assert.equal(h.session.snapshot().confirmed.length, 1);
});

test('restart restores an unresolved attempt for its account and checks without posting', async () => {
  const h = harness({
    rateCard: async (input) => {
      h.posts.push(input);
      throw Error('timeout');
    },
  });
  await h.session.restore();
  await h.session.begin(card, 4, 300, 'old-session');
  h.session.dispose();
  const other = new LearningSession(2, h.deps);
  await other.restore();
  assert.equal(other.snapshot().attempt, null);
  const input = JSON.parse(h.stored()).input;
  h.deps.api.getReceipt = async () => ({ receipt: response(input) });
  const restored = new LearningSession(1, h.deps);
  await restored.restore();
  assert.equal(h.posts.length, 1);
  assert.equal(
    restored.snapshot().confirmed[0].input.session_id,
    'old-session',
  );
  other.dispose();
  restored.dispose();
});

test('logout during a pending response cannot confirm or clear a later account attempt', async () => {
  const pending = deferred();
  const h = harness({
    rateCard: async (input) => {
      h.posts.push(input);
      return pending.promise;
    },
  });
  await h.session.restore();
  const sending = h.session.begin(card, 4, 100, 'session');
  await tick();
  h.session.dispose();
  await h.storage.clear();
  await h.storage.write('second-account-attempt');
  pending.resolve(response(h.posts[0]));
  await sending;
  assert.equal(h.reconciliations(), 0);
  assert.equal(h.stored(), 'second-account-attempt');
});

test('logout while persistence waits prevents the POST', async () => {
  const disk = deferred();
  const h = harness();
  h.storage.write = async () => disk.promise;
  await h.session.restore();
  const saving = h.session.begin(card, 4, 100, 'session');
  h.session.dispose();
  disk.resolve();
  await saving;
  assert.equal(h.posts.length, 0);
});

test('stale progress is explicit and cannot silently replay or submit a different rating', async () => {
  const h = harness({
    rateCard: async (input) => {
      h.posts.push(input);
      throw Object.assign(Error('stale'), { status: 409 });
    },
  });
  await h.session.restore();
  await h.session.begin(card, 4, 100, 'session');
  assert.equal(h.session.snapshot().phase, 'conflict');
  await h.session.retry();
  await h.session.begin(card, 3, 200, 'session');
  assert.equal(h.posts.length, 1);
  assert.equal(await h.session.dismissConflict(), true);
  assert.equal(h.stored(), null);
});

test('a receipt for another attempt never advances the session', async () => {
  const h = harness({
    rateCard: async (input) => ({
      ...response(input),
      request_id: randomUUID(),
    }),
  });
  await h.session.restore();
  await h.session.begin(card, 4, 100, 'session');
  assert.equal(h.session.snapshot().phase, 'uncertain');
  assert.equal(h.session.snapshot().confirmed.length, 0);
});

test('failed local persistence sends nothing; a confirmed receipt with failed cleanup stays recoverable', async () => {
  const h = harness();
  await h.session.restore();
  h.storage.write = async () => {
    throw Error('disk full');
  };
  await h.session.begin(card, 4, 100, 'session');
  assert.equal(h.posts.length, 0);
  const second = harness();
  await second.session.restore();
  second.storage.clear = async () => {
    throw Error('keychain unavailable');
  };
  await second.session.begin(card, 4, 100, 'session');
  assert.equal(second.session.snapshot().phase, 'uncertain');
  assert.equal(second.posts.length, 1);
});

test('every confirmed rating invalidates counts and details without replacing an active review snapshot', async () => {
  const client = new QueryClient();
  client.setQueryData(learningKeys.notes(), { total_due: 20 });
  client.setQueryData(learningKeys.note('topic'), { note: { due_count: 20 } });
  const queue = { cards: [card], total_due: 21 };
  client.setQueryData(learningKeys.review(1), queue);
  await reconcileLearningRating(client, () => true);
  assert.equal(client.getQueryState(learningKeys.notes()).isInvalidated, true);
  assert.equal(
    client.getQueryState(learningKeys.note('topic')).isInvalidated,
    true,
  );
  assert.equal(
    client.getQueryState(learningKeys.review(1)).isInvalidated,
    false,
  );
  assert.deepEqual(client.getQueryData(learningKeys.review(1)), queue);
  client.clear();
  await reconcileLearningRating(client, () => false);
  assert.equal(client.getQueryCache().getAll().length, 0);
});

test('foreground and reconnect refresh fresh counts while preserving the active queue', async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 30000 } },
  });
  client.mount();
  focusManager.setFocused(true);
  onlineManager.setOnline(true);
  let noteReads = 0;
  let queueReads = 0;
  const notes = new QueryObserver(client, {
    ...learningRefreshOptions,
    queryKey: learningKeys.notes(),
    queryFn: async () => ++noteReads,
  });
  const queue = new QueryObserver(client, {
    ...learningQueueOptions,
    queryKey: learningKeys.review(1),
    queryFn: async () => ++queueReads,
  });
  const stopNotes = notes.subscribe(() => {});
  const stopQueue = queue.subscribe(() => {});
  try {
    await tick();
    focusManager.setFocused(false);
    focusManager.setFocused(true);
    await tick();
    onlineManager.setOnline(false);
    onlineManager.setOnline(true);
    await tick();
    assert.equal(noteReads, 3);
    assert.equal(queueReads, 1);
    // A rating temporarily disables the observer; enabling it must not reset the session.
    queue.setOptions({ ...queue.options, enabled: false });
    queue.setOptions({ ...queue.options, enabled: true });
    await tick();
    assert.equal(queueReads, 1);
  } finally {
    stopNotes();
    stopQueue();
    client.unmount();
    client.clear();
    focusManager.setFocused(undefined);
    onlineManager.setOnline(true);
  }
});
