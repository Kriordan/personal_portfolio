import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { test } from 'node:test';
import {
  QueryClient,
  QueryObserver,
  focusManager,
  onlineManager,
} from '@tanstack/react-query';
import {
  browseJobs,
  jobwizardKeys,
  routeJobId,
  safeJobUrl,
  storedOperation,
} from '../src/lib/jobwizard-model.ts';
import { JobSession } from '../src/lib/jobwizard-session.ts';
import { jobRefreshOptions, reconcileJob } from '../src/lib/jobwizard-cache.ts';
const tick = () => new Promise((resolve) => setImmediate(resolve));
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
};
const job = (id, extra = {}) => ({
  id,
  title: 'Engineer',
  company_name: 'Acme',
  listing_url: 'https://jobs.example.com/1',
  user_id: 1,
  saved_at: null,
  archived_at: null,
  revision: 0,
  ...extra,
});
const input = {
  title: 'Engineer',
  company_name: 'Acme',
  listing_url: 'https://jobs.example.com/1',
};
const result = (op) => ({
  request_id: op.input.request_id,
  job: job(op.jobId ?? 5),
});
function harness(overrides = {}) {
  let stored = null,
    online = true,
    confirmed = 0;
  const posts = [];
  const storage = {
    read: async () => stored,
    write: async (value) => {
      stored = value;
    },
    clear: async () => {
      stored = null;
    },
    ...overrides.storage,
  };
  const api = {
    submit: async (op) => {
      posts.push(op);
      return result(op);
    },
    getReceipt: async () => ({ receipt: null }),
    getCapture: async () => ({ capture: { requested: null } }),
    ...overrides.api,
  };
  const session = new JobSession(1, {
    storage,
    api,
    online: () => online,
    uuid: randomUUID,
    onConfirmed: () => {
      confirmed++;
    },
  });
  return {
    session,
    storage,
    api,
    posts,
    get stored() {
      return stored;
    },
    get confirmed() {
      return confirmed;
    },
    setOnline: (value) => {
      online = value;
    },
  };
}
test('job browse composes all terms, archive state and deterministic sorts without truncating', () => {
  const jobs = [
    job(4),
    job(2, { title: 'Designer', archived_at: '2026-01-01' }),
    job(3, { saved_at: '2026-10-21' }),
    job(1, { saved_at: '2026-10-20', company_name: 'Beta' }),
  ];
  assert.deepEqual(
    browseJobs(jobs, '  ACME jobs.example  ', 'active', 'newest').map(
      (j) => j.id,
    ),
    [3, 4],
  );
  assert.deepEqual(
    browseJobs(jobs, '', 'all', 'oldest').map((j) => j.id),
    [1, 3, 2, 4],
  );
  assert.deepEqual(
    browseJobs(jobs, '', 'archived', 'title').map((j) => j.id),
    [2],
  );
  assert.equal(
    browseJobs(
      Array.from({ length: 400 }, (_, i) => job(i + 1)),
      '',
      'all',
      'title',
    ).length,
    400,
  );
  assert.deepEqual(
    jobs.map((j) => j.id),
    [4, 2, 3, 1],
  );
});
test('invalid routes terminate and unsafe listing URLs cannot launch', () => {
  for (const id of [
    undefined,
    ['1'],
    '0',
    '-1',
    '1.2',
    'NaN',
    '01',
    '2147483648',
  ])
    assert.equal(routeJobId(id), 0);
  assert.equal(routeJobId('12'), 12);
  for (const url of [
    'javascript:alert(1)',
    'file:///secret',
    'https://a:b@example.com',
    'https://exam\nple.com',
    'https://example.com\\@host',
  ])
    assert.equal(safeJobUrl(url), false);
  assert.equal(safeJobUrl('https://example.com/job?listing=123'), true);
});
test('synchronous lock prevents rapid duplicate submissions and confirms once', async () => {
  const gate = deferred(),
    h = harness({
      api: {
        submit: (op) => {
          h.posts.push(op);
          return gate.promise;
        },
      },
    });
  await h.session.restore();
  const first = h.session.begin({ kind: 'save', jobId: null, input });
  await h.session.begin({ kind: 'save', jobId: null, input });
  await tick();
  assert.equal(h.posts.length, 1);
  gate.resolve(result(h.posts[0]));
  await first;
  assert.equal(h.confirmed, 1);
  assert.equal(h.stored, null);
});
test('lost response stays unresolved; retry freezes request and recovery only reads', async () => {
  const h = harness({
    api: {
      submit: async (op) => {
        h.posts.push(op);
        throw new Error('timeout');
      },
    },
  });
  await h.session.restore();
  await h.session.begin({ kind: 'save', jobId: null, input });
  const attempt = h.session.snapshot().attempt;
  assert.equal(h.session.snapshot().phase, 'uncertain');
  assert.ok(h.stored);
  await h.session.check();
  assert.equal(h.posts.length, 1);
  await h.session.retry();
  assert.deepEqual(h.posts, [attempt, attempt]);
  h.api.getReceipt = async () => ({ receipt: result(attempt) });
  await h.session.check();
  assert.equal(h.session.snapshot().phase, 'idle');
  assert.equal(h.confirmed, 1);
});
test('offline and recovery-storage failure never send writes', async () => {
  const h = harness();
  await h.session.restore();
  h.setOnline(false);
  await h.session.begin({ kind: 'save', jobId: null, input });
  h.setOnline(true);
  await h.session.check();
  assert.equal(h.posts.length, 0);
  const failed = harness({
    storage: {
      write: async () => {
        throw new Error('full');
      },
    },
  });
  await failed.session.restore();
  await failed.session.begin({ kind: 'save', jobId: null, input });
  assert.equal(failed.posts.length, 0);
  assert.equal(failed.session.snapshot().attempt, null);
});
test('conflicts do not replay automatically and require explicit rejection clearing', async () => {
  const h = harness({
    api: {
      submit: async () => {
        throw { status: 409 };
      },
    },
  });
  await h.session.restore();
  await h.session.begin({
    kind: 'save',
    jobId: 2,
    input: { ...input, expected_revision: 0 },
  });
  assert.equal(h.session.snapshot().phase, 'rejected');
  await h.session.check();
  await h.session.retry();
  assert.ok(h.session.snapshot().attempt);
  await h.session.clearRejection();
  assert.equal(h.session.snapshot().attempt, null);
});
test('logout suppresses late completions and other accounts never restore an old attempt', async () => {
  const gate = deferred(),
    h = harness({
      api: {
        submit: (op) => {
          h.posts.push(op);
          return gate.promise;
        },
      },
    });
  await h.session.restore();
  const pending = h.session.begin({ kind: 'save', jobId: null, input });
  await tick();
  h.session.dispose();
  gate.resolve(result(h.posts[0]));
  await pending;
  assert.equal(h.confirmed, 0);
  const other = new JobSession(2, {
    storage: h.storage,
    api: h.api,
    uuid: randomUUID,
    online: () => true,
    onConfirmed: () => assert.fail('foreign completion'),
  });
  await other.restore();
  assert.equal(other.snapshot().attempt, null);
});
test('capture timeout recovers the same attempt and failed captures still resolve', async () => {
  const h = harness({
    api: {
      submit: async (op) => {
        h.posts.push(op);
        throw new Error('timeout');
      },
    },
  });
  await h.session.restore();
  await h.session.begin({
    kind: 'capture',
    jobId: 2,
    input: { expected_revision: 1 },
  });
  const attempt = h.session.snapshot().attempt;
  h.api.getCapture = async () => ({
    capture: {
      requested: { id: attempt.input.request_id, status: 'running' },
      busy: true,
    },
  });
  await h.session.check();
  assert.equal(h.session.snapshot().phase, 'uncertain');
  h.api.getCapture = async () => ({
    capture: { requested: { id: attempt.input.request_id, status: 'failed' } },
  });
  await h.session.check();
  assert.equal(h.confirmed, 1);
  assert.equal(h.posts.length, 1);
});
test('stored recovery refuses malformed IDs and cross-job receipts', async () => {
  assert.equal(
    storedOperation({
      kind: 'save',
      jobId: 0,
      input: { request_id: randomUUID() },
    }),
    false,
  );
  const h = harness({
    api: { submit: async (op) => ({ ...result(op), job: job(999) }) },
  });
  await h.session.restore();
  await h.session.begin({
    kind: 'save',
    jobId: 2,
    input: { ...input, expected_revision: 0 },
  });
  assert.equal(h.confirmed, 0);
  assert.equal(h.session.snapshot().phase, 'uncertain');
});
test('foreground and reconnect refetch fresh jobs; cache reconciliation remains account scoped', async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 30_000 } },
  });
  client.mount();
  let calls = 0;
  const observer = new QueryObserver(client, {
    ...jobRefreshOptions,
    queryKey: jobwizardKeys.jobs(1),
    queryFn: async () => {
      calls++;
      return { jobs: [job(2)] };
    },
  });
  const unsubscribe = observer.subscribe(() => {});
  await tick();
  const initial = calls;
  focusManager.setFocused(false);
  focusManager.setFocused(true);
  await tick();
  assert.ok(calls > initial);
  const before = calls;
  onlineManager.setOnline(false);
  onlineManager.setOnline(true);
  await tick();
  assert.ok(calls > before);
  client.setQueryData(jobwizardKeys.jobs(2), {
    jobs: [job(99, { user_id: 2 })],
  });
  await reconcileJob(
    client,
    1,
    { job: job(5), request_id: randomUUID() },
    () => true,
  );
  assert.equal(client.getQueryData(jobwizardKeys.jobs(2)).jobs[0].id, 99);
  await reconcileJob(
    client,
    1,
    { job: job(90), request_id: randomUUID() },
    () => false,
  );
  assert.equal(client.getQueryData(jobwizardKeys.job(1, 90)), undefined);
  unsubscribe();
  client.unmount();
  client.clear();
});
