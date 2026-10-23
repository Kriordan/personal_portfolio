import assert from 'node:assert/strict';
import { test } from 'node:test';
import { randomUUID } from 'node:crypto';
import { ExtractionSession } from '../src/lib/job-extraction-session.ts';
import {
  extractionMatches,
  reviewedDetailsError,
  useSuggestedField,
  validExtractionRequest,
} from '../src/lib/job-extraction-model.ts';
const url = 'https://job-boards.greenhouse.io/acme/jobs/123';
test('a definitive rejected read is not restored as an unknown paid operation', async () => {
  for (const status of [400, 404, 410]) {
    const h = harness({
      api: {
        start: async () => {
          throw Object.assign(new Error('Check the listing URL.'), { status });
        },
      },
    });
    await h.session.restore();
    await h.session.begin({ listing_url: url });
    assert.equal(h.session.snapshot().request, null);
    assert.equal(h.session.snapshot().uncertain, false);
    assert.match(h.session.snapshot().error, /Check the listing URL/);
    assert.equal(h.stored, null);
    const reopened = new ExtractionSession(1, h.deps);
    await reopened.restore();
    assert.equal(reopened.snapshot().ready, true);
    assert.equal(reopened.snapshot().uncertain, false);
    assert.equal(reopened.snapshot().request, null);
  }
});

test('missing receipt preserves its UUID for deliberate retry and exposes a polling stop', async () => {
  const h = harness();
  await h.session.restore();
  await h.session.begin({ listing_url: url });
  const request = h.session.snapshot().request;
  h.receipts.clear();
  const restored = new ExtractionSession(1, h.deps);
  await restored.restore();
  assert.equal(restored.snapshot().missing, true);
  assert.equal(restored.snapshot().uncertain, true);
  assert.match(restored.snapshot().error, /No saved result/);
  const count = h.calls.length;
  await restored.begin({ listing_url: url });
  assert.equal(h.calls.length, count);
  await restored.retrySame(() => true);
  assert.equal(restored.snapshot().request.request_id, request.request_id);
  assert.equal(restored.snapshot().missing, false);
  assert.equal(restored.snapshot().uncertain, false);
  assert.equal(restored.snapshot().result.status, 'complete');
  assert.deepEqual(h.calls.slice(count), ['read', 'summary']);
});

test('unconfirmed failures keep the frozen request across restart; no paid automatic retry', async () => {
  const h = harness({
    api: {
      start: async () => { throw new Error('Connection lost'); },
    },
  });
  await h.session.restore();
  await h.session.begin({ listing_url: url });
  const request = h.session.snapshot().request;
  assert.ok(request);
  assert.equal(h.session.snapshot().uncertain, true);
  const reopened = new ExtractionSession(1, h.deps);
  await reopened.restore();
  assert.equal(reopened.snapshot().request.request_id, request.request_id);
  assert.equal(reopened.snapshot().missing, true);
  assert.deepEqual(h.calls, ['get', 'get']);
});

test('failed durable cleanup preserves the rejected UUID for recovery', async () => {
  const h = harness({
    api: {
      start: async () => {
        throw Object.assign(new Error('Rejected'), { status: 400 });
      },
    },
    storage: { clear: async () => { throw new Error('Storage unavailable'); } },
  });
  await h.session.restore();
  await h.session.begin({ listing_url: url });
  const request = h.session.snapshot().request;
  assert.ok(request);
  const reopened = new ExtractionSession(1, h.deps);
  await reopened.restore();
  assert.equal(reopened.snapshot().request.request_id, request.request_id);
  assert.equal(reopened.snapshot().uncertain, true);
  assert.deepEqual(h.calls, ['get']);
});

test('retry does not summarize after leaving the draft or backgrounding', async () => {
  for (const background of [false, true]) {
    const h = harness();
    await h.session.restore();
    await h.session.begin({ listing_url: url });
    h.receipts.clear();
    const reopened = new ExtractionSession(1, h.deps);
    await reopened.restore();
    if (background) h.setForeground(false);
    const count = h.calls.length;
    await reopened.retrySame(() => background);
    assert.deepEqual(h.calls.slice(count), ['read']);
    assert.equal(reopened.snapshot().result.status, 'ready');
  }
});
test('reviewed bullets stay bound to their URL and revision after conflict recovery', () => {
  assert.equal(reviewedDetailsError({ url }, url), null);
  assert.equal(reviewedDetailsError({ url, revision: 1 }, url, 1), null);
  assert.match(
    reviewedDetailsError({ url, revision: 1 }, url, 2),
    /older job version/,
  );
  assert.match(reviewedDetailsError({ url }, `${url}4`), /URL changed/);
});
test('late manual entry stays protected until replacement is explicitly selected', () => {
  assert.equal(useSuggestedField(null, ''), true);
  assert.equal(useSuggestedField(null, 'My saved title'), false);
  assert.equal(useSuggestedField(true, 'My saved title'), true);
  assert.equal(useSuggestedField(false, ''), false);
});
const deferred = () => {
  let resolve;
  const promise = new Promise((r) => {
    resolve = r;
  });
  return { promise, resolve };
};
function harness(overrides = {}) {
  let stored = null,
    online = true,
    foreground = true;
  const calls = [],
    receipts = new Map();
  const api = {
    start: async (request) => {
      calls.push('read');
      const extraction = {
        id: request.request_id,
        source_url: request.listing_url,
        job_id: request.job_id ?? null,
        status: 'ready',
        stage: 'read',
        can_summarize: true,
        fields: {},
        result: null,
        error_message: null,
      };
      receipts.set(request.request_id, extraction);
      return { extraction };
    },
    summarize: async (id) => {
      calls.push('summary');
      const extraction = {
        ...receipts.get(id),
        status: 'complete',
        stage: 'summary',
        can_summarize: false,
      };
      receipts.set(id, extraction);
      return { extraction };
    },
    get: async (id) => {
      calls.push('get');
      if (!receipts.has(id)) throw { status: 404 };
      return { extraction: receipts.get(id) };
    },
    ...overrides.api,
  };
  const storage = {
    read: async () => stored,
    write: async (v) => {
      stored = v;
    },
    clear: async () => {
      stored = null;
    },
    ...overrides.storage,
  };
  const deps = {
    api,
    storage,
    uuid: randomUUID,
    online: () => online,
    foreground: () => foreground,
  };
  return {
    deps,
    storage,
    api,
    receipts,
    calls,
    session: new ExtractionSession(1, deps),
    setOnline: (v) => {
      online = v;
    },
    setForeground: (v) => {
      foreground = v;
    },
    get stored() {
      return stored;
    },
  };
}
test('deliberate action chains two stages, recovery only reads', async () => {
  const h = harness();
  await h.session.restore();
  await h.session.begin({ listing_url: url }, () => true);
  assert.deepEqual(h.calls, ['read', 'summary']);
  assert.equal(h.session.snapshot().result.status, 'complete');
  assert.deepEqual(Object.keys(JSON.parse(h.stored)), ['userId', 'request']);
  const restored = new ExtractionSession(1, h.deps);
  await restored.restore();
  assert.deepEqual(h.calls, ['read', 'summary', 'get']);
  assert.equal(restored.snapshot().result.status, 'complete');
});
test('background between stages and changed URL require explicit continue', async () => {
  for (const background of [true, false]) {
    const h = harness();
    await h.session.restore();
    if (background) h.setForeground(false);
    await h.session.begin({ listing_url: url }, () => background);
    assert.deepEqual(h.calls, ['read']);
    h.setForeground(true);
    await h.session.check();
    assert.deepEqual(h.calls, ['read', 'get']);
    await h.session.continue();
    assert.deepEqual(h.calls, ['read', 'get', 'summary']);
  }
});
test('double taps and uncertain outcome cannot initiate another paid attempt', async () => {
  const wait = deferred(),
    h = harness({ api: { start: () => wait.promise } });
  await h.session.restore();
  const first = h.session.begin({ listing_url: url });
  await h.session.begin({ listing_url: url });
  await new Promise((r) => setImmediate(r));
  const request = h.session.snapshot().request;
  wait.resolve({
    extraction: {
      id: request.request_id,
      job_id: null,
      source_url: url,
      status: 'running',
      stage: 'read',
    },
  });
  await first;
  const id = h.session.snapshot().request.request_id;
  await h.session.begin({ listing_url: url });
  assert.equal(h.session.snapshot().request.request_id, id);
});
test('lost summary response recovers receipt without repeating summary', async () => {
  const h = harness();
  const original = h.api.summarize;
  h.api.summarize = async (id) => {
    await original(id);
    throw new Error('response lost');
  };
  await h.session.restore();
  await h.session.begin({ listing_url: url }, () => true);
  assert.deepEqual(h.calls, ['read', 'summary', 'get']);
  assert.equal(h.session.snapshot().result.status, 'complete');
});
test('logout suppresses late result and the next paid stage', async () => {
  const wait = deferred(),
    h = harness({ api: { start: () => wait.promise } });
  await h.session.restore();
  const pending = h.session.begin({ listing_url: url }, () => true);
  await new Promise((r) => setImmediate(r));
  const request = h.session.snapshot().request;
  h.session.dispose();
  wait.resolve({
    extraction: {
      id: request.request_id,
      source_url: url,
      job_id: null,
      status: 'ready',
      stage: 'read',
      can_summarize: true,
    },
  });
  await pending;
  assert.equal(h.session.snapshot().result, null);
  assert.deepEqual(h.calls, []);
  const other = new ExtractionSession(2, h.deps);
  await other.restore();
  assert.equal(other.snapshot().request, null);
});
test('offline or failed storage never sends paid work', async () => {
  const h = harness();
  await h.session.restore();
  h.setOnline(false);
  await h.session.begin({ listing_url: url });
  assert.deepEqual(h.calls, []);
  const failed = harness({
    storage: {
      write: async () => {
        throw new Error();
      },
    },
  });
  await failed.session.restore();
  await failed.session.begin({ listing_url: url });
  assert.deepEqual(failed.calls, []);
  assert.match(failed.session.snapshot().error, /Nothing was sent/);
});
test('expired status removes stale suggestions; URL and revision scope is exact', async () => {
  const h = harness();
  await h.session.restore();
  await h.session.begin({ listing_url: url });
  h.api.get = async () => {
    throw { status: 410 };
  };
  await h.session.check();
  assert.equal(h.session.snapshot().result, null);
  assert.match(h.session.snapshot().error, /expired/);
  const value = { source_url: url, job_id: 5, source_revision: 2 };
  assert.equal(extractionMatches(value, url, 5, 2), true);
  assert.equal(extractionMatches(value, url, 5, 3), false);
  assert.equal(extractionMatches(value, url + '4', 5, 2), false);
  assert.equal(
    validExtractionRequest({ request_id: randomUUID(), listing_url: url }),
    true,
  );
  assert.equal(
    validExtractionRequest({
      request_id: randomUUID(),
      listing_url: url,
      job_id: 5,
    }),
    false,
  );
});
