import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { test } from 'node:test';
import { ConceptStudy } from '../src/lib/concept-study.ts';
import { createConceptClient } from '../src/lib/concept-client.ts';
import {
  conceptKeys,
  initialSection,
  isStudyChange,
} from '../src/lib/concept-model.ts';
import { LearningSession } from '../src/lib/learning-session.ts';
import {
  isStoredAttempt,
  ratingPath,
  reviewRoute,
} from '../src/lib/learning-model.ts';
import { retrySteps } from '../src/lib/retry-simulation.ts';
import { reconcileLearningRating } from '../src/lib/learning-cache.ts';
import { QueryClient, QueryObserver } from '@tanstack/react-query';

const tick = () => new Promise((resolve) => setImmediate(resolve));
const deferred = () => {
  let resolve;
  const promise = new Promise((yes) => {
    resolve = yes;
  });
  return { resolve, promise };
};
const position = () => ({
  kind: 'position',
  conceptId: 'idempotency',
  content_version: 2,
  section_id: 'retries',
  expected_revision: 1,
  request_id: randomUUID(),
});
const saved = (change) => ({
  concept_id: change.conceptId,
  revision: change.expected_revision + 1,
  reading_version: change.content_version,
  reading_section: change.section_id,
});
function harness(overrides = {}) {
  let raw = null,
    online = true;
  const writes = [],
    confirmations = [];
  const storage = {
    read: async () => raw,
    write: async (value) => {
      raw = value;
    },
    clear: async () => {
      raw = null;
    },
  };
  const deps = {
    storage,
    online: () => online,
    onConfirmed: (...args) => confirmations.push(args),
    api: {
      save: async (change) => {
        writes.push(change);
        return { progress: saved(change) };
      },
      progress: async () => ({ progress: null }),
      ...overrides,
    },
  };
  return {
    study: new ConceptStudy(1, deps),
    deps,
    writes,
    confirmations,
    storage,
    raw: () => raw,
    offline: () => {
      online = false;
    },
  };
}

test('concept API pins reveal and rating versions, and never fetches an answer with a queue', async () => {
  const calls = [];
  const api = createConceptClient(async (...args) => {
    calls.push(args);
    return {};
  });
  await api.queue('idempotency');
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], '/learning/concepts/idempotency/review');
  const card = {
    card_id: 'idempotency:race',
    content_version: 2,
    progress_revision: 7,
  };
  assert.equal(ratingPath(card), '/learning/concepts/idempotency/rate');
  assert.equal(ratingPath({ card_id: 'commands:curl' }), '/learning/rate');
  await api.reveal('idempotency', card);
  const params = new URL('https://fixture' + calls[1][0]).searchParams;
  assert.equal(params.get('card_id'), card.card_id);
  assert.equal(params.get('content_version'), '2');
  assert.equal(params.get('expected_revision'), '7');
  const change = position();
  await api.save(change);
  assert.deepEqual(calls[2][1].body, {
    content_version: 2,
    section_id: 'retries',
    expected_revision: 1,
    request_id: change.request_id,
  });
  assert.equal(calls[2][1].method, 'PUT');
  await api.save({ kind: 'enroll', conceptId: 'idempotency' });
  assert.deepEqual(calls[3][1].body, {});
});

test('saved section survives content updates; explicit remediation wins and removed sections fall back', () => {
  const concept = {
    content: {
      sections: [{ id: 'overview' }, { id: 'retries' }, { id: 'design' }],
    },
  };
  assert.equal(
    initialSection(concept, { reading_section: 'retries', reading_version: 1 }),
    'retries',
  );
  assert.equal(
    initialSection(concept, { reading_section: 'retries' }, 'design'),
    'design',
  );
  assert.equal(
    initialSection(concept, { reading_section: 'removed' }, '../bad'),
    'overview',
  );
  assert.notDeepEqual(conceptKeys.list(1), conceptKeys.list(2));
  assert.notDeepEqual(
    conceptKeys.detail(1, 'idempotency'),
    conceptKeys.detail(2, 'idempotency'),
  );
});

test('stale rating recovery returns to its original kind of review', () => {
  assert.deepEqual(
    reviewRoute({ card_id: 'idempotency:race', content_version: 2 }),
    {
      pathname: '/learning/concepts/[id]/review',
      params: { id: 'idempotency' },
    },
  );
  assert.deepEqual(reviewRoute({ card_id: 'commands:curl' }), {
    pathname: '/learning/review',
  });
  assert.deepEqual(
    reviewRoute({ card_id: '../bad:race', content_version: 2 }),
    { pathname: '/learning/review' },
  );
});

test('opening a cached lesson waits for a fresh bookmark before choosing its initial section', async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const key = conceptKeys.detail(1, 'idempotency');
  const concept = {
    content: { sections: [{ id: 'overview' }, { id: 'design' }] },
  };
  client.setQueryData(key, {
    concept,
    progress: { reading_section: 'overview' },
  });
  const pending = deferred();
  const observer = new QueryObserver(client, {
    queryKey: key,
    queryFn: () => pending.promise,
  });
  const stop = observer.subscribe(() => {});
  assert.equal(observer.getCurrentResult().isFetchedAfterMount, false);
  assert.equal(observer.getCurrentResult().isFetching, true);
  pending.resolve({ concept, progress: { reading_section: 'design' } });
  await tick();
  const fresh = observer.getCurrentResult();
  assert.equal(fresh.isFetchedAfterMount, true);
  assert.equal(
    initialSection(fresh.data.concept, fresh.data.progress),
    'design',
  );
  stop();
  client.clear();
});

test('a lost bookmark response is confirmed by reading, with no automatic resubmission', async () => {
  const change = position();
  let posted = 0;
  const h = harness({
    save: async () => {
      posted++;
      throw new Error('lost');
    },
    progress: async () => ({ progress: saved(change) }),
  });
  await h.study.restore();
  await h.study.begin(change);
  assert.equal(posted, 1);
  assert.equal(h.study.snapshot().phase, 'idle');
  assert.equal(h.study.snapshot().saved.reading_section, 'retries');
  assert.equal(h.raw(), null);
});

test('an unresolved bookmark survives restart, and explicit retry reuses the entire original request', async () => {
  const change = position();
  const h = harness({
    save: async () => {
      throw new Error('connection lost');
    },
    progress: async () => ({
      progress: { concept_id: 'idempotency', revision: 1 },
    }),
  });
  await h.study.restore();
  await h.study.begin(change);
  assert.equal(h.study.snapshot().phase, 'uncertain');
  h.study.dispose();
  const restarted = new ConceptStudy(1, h.deps);
  await restarted.restore();
  assert.deepEqual(restarted.snapshot().pending, change);
  const posts = [];
  h.deps.api.save = async (body) => {
    posts.push(body);
    return { progress: saved(body) };
  };
  await restarted.retry();
  assert.deepEqual(posts, [change]);
  assert.equal(restarted.snapshot().phase, 'idle');
});

test('a web bookmark supersedes an uncertain phone save and cannot be overwritten by recovery', async () => {
  const h = harness({
    save: async () => {
      throw new Error('lost');
    },
    progress: async () => ({
      progress: {
        ...saved(position()),
        revision: 3,
        reading_section: 'design',
      },
    }),
  });
  await h.study.restore();
  await h.study.begin(position());
  assert.equal(h.study.snapshot().phase, 'conflict');
  h.deps.api.save = () => {
    throw new Error('must not post');
  };
  await h.study.retry();
  await h.study.check();
  assert.equal(await h.study.dismissConflict(), true);
  assert.equal(h.raw(), null);
});

test('repeated taps submit only once; offline and storage failure cannot write', async () => {
  const pending = deferred();
  let calls = 0;
  const h = harness({
    save: async () => {
      calls++;
      return pending.promise;
    },
  });
  await h.study.restore();
  const change = position();
  const first = h.study.begin(change);
  await tick();
  await h.study.begin(position());
  await h.study.retry();
  assert.equal(calls, 1);
  pending.resolve({ progress: saved(change) });
  await first;
  h.offline();
  await h.study.begin(position());
  assert.equal(calls, 1);
  const broken = harness();
  await broken.study.restore();
  broken.storage.write = async () => {
    throw new Error('disk full');
  };
  await broken.study.begin(position());
  assert.deepEqual(broken.writes, []);
});

test('logout fences late completion and another account never recovers this account’s request', async () => {
  const pending = deferred();
  const h = harness({ save: async () => pending.promise });
  await h.study.restore();
  const change = position();
  const sending = h.study.begin(change);
  await tick();
  h.study.dispose();
  const other = new ConceptStudy(2, h.deps);
  await other.restore();
  pending.resolve({ progress: saved(change) });
  await sending;
  assert.equal(other.snapshot().pending, null);
  assert.deepEqual(h.confirmations, []);
});

test('malformed pending records fail closed instead of inventing progress', async () => {
  for (const value of [
    null,
    { ...position(), expected_revision: 0 },
    { ...position(), content_version: true },
    { ...position(), request_id: 'bad' },
  ])
    assert.equal(isStudyChange(value), false);
  const h = harness();
  await h.storage.write(JSON.stringify({ userId: 1, change: {} }));
  await h.study.restore();
  await h.study.begin(position());
  assert.equal(h.study.snapshot().ready, false);
  assert.deepEqual(h.writes, []);
});

test('curriculum ratings preserve version through disk recovery and reject a different-version receipt', async () => {
  const card = {
    card_id: 'idempotency:race',
    content_version: 2,
    progress_revision: 4,
  };
  let raw = null,
    calls = 0;
  const storage = {
    read: async () => raw,
    write: async (v) => {
      raw = v;
    },
    clear: async () => {
      raw = null;
    },
  };
  const deps = {
    storage,
    online: () => true,
    uuid: randomUUID,
    onConfirmed: () => {},
    api: {
      rateCard: async (input) => {
        calls++;
        return {
          ...input,
          content_version: 1,
          next_review_display: 'Tomorrow',
        };
      },
      getReceipt: async () => ({ receipt: null }),
    },
  };
  const session = new LearningSession(1, deps);
  await session.restore();
  await session.begin(card, 4, 100, 'fixture');
  assert.equal(session.snapshot().phase, 'uncertain');
  assert.equal(JSON.parse(raw).input.content_version, 2);
  assert.equal(
    isStoredAttempt({ ...JSON.parse(raw).input, content_version: 0 }),
    false,
  );
  session.dispose();
  const restarted = new LearningSession(1, deps);
  await restarted.restore();
  assert.equal(calls, 1);
  deps.api.rateCard = async (input) => {
    calls++;
    return { ...input, next_review_display: 'Tomorrow' };
  };
  await restarted.retry();
  assert.equal(calls, 2);
  assert.equal(restarted.snapshot().confirmed[0].input.content_version, 2);
});

test('rating reconciliation refreshes concept counts without replacing a revealed review queue', async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  let lists = 0,
    queues = 0;
  const list = new QueryObserver(client, {
    queryKey: conceptKeys.list(1),
    queryFn: async () => ++lists,
  });
  const queue = new QueryObserver(client, {
    queryKey: conceptKeys.review(1, 'idempotency'),
    queryFn: async () => ++queues,
  });
  const a = list.subscribe(() => {}),
    b = queue.subscribe(() => {});
  await tick();
  await reconcileLearningRating(client, () => true);
  await tick();
  assert.equal(lists, 2);
  assert.equal(queues, 1);
  a();
  b();
  client.clear();
});

test('retry simulation distinguishes rollback, same-key recovery and duplicate new-key effects', () => {
  assert.deepEqual(
    retrySteps('after', true).map((s) => s.orders),
    [0, 1, 1, 1, 1],
  );
  assert.deepEqual(
    retrySteps('before', true).map((s) => s.orders),
    [0, 0, 0, 0, 1],
  );
  assert.equal(retrySteps('after', false).at(-1).orders, 2);
  assert.equal(retrySteps('before', false).at(-1).orders, 1);
  assert.match(retrySteps('success', true)[2].text, /no retry is needed/);
});
