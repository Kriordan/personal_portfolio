import assert from 'node:assert/strict';
import { test } from 'node:test';
import { randomUUID } from 'node:crypto';
import { ExtractionSession } from '../src/lib/job-extraction-session.ts';
import {
  extractionMatches,
  extractionErrorForDraft,
  reviewedDetailsError,
  reviewSelectionError,
  reviewFieldSelected,
  suggestedFieldSelected,
  validExtractionRequest,
} from '../src/lib/job-extraction-model.ts';
const url = 'https://job-boards.greenhouse.io/acme/jobs/123';
test('review choices survive Back but cannot replace a subsequent manual edit', () => {
  const choice = { selected: true, compared: 'My title' };
  assert.equal(reviewFieldSelected(choice, 'My title'), true);
  assert.equal(reviewFieldSelected(choice, 'My revised title'), false);
  assert.equal(reviewFieldSelected({ selected: false, compared: '' }, ''), false);
  assert.equal(reviewFieldSelected(null, ''), true);
});
test('review can skip new bullets but cannot clear an existing summary by deselecting all', () => {
  assert.equal(reviewSelectionError({ title: 'Manual title' }, [], false), null);
  assert.match(reviewSelectionError({}, [], true), /Keep current details/);
  assert.equal(reviewSelectionError({}, undefined, true), null);
  assert.equal(reviewSelectionError({}, [{ index: 4, text: 'Keep this selected detail.' }], true), null);
});
test('review validates only selected values using the API Unicode limits', () => {
  assert.equal(reviewSelectionError({ title: '𠮷'.repeat(200) }, [{ index: 0, text: '𠮷'.repeat(300) }], false), null);
  assert.match(reviewSelectionError({ company_name: '𠮷'.repeat(201) }, undefined, false), /1–200/);
  assert.match(reviewSelectionError({}, [{ index: 3, text: ' ' }], false), /Edit it or deselect/);
  assert.match(reviewSelectionError({}, [{ index: 3, text: '𠮷'.repeat(301) }], false), /1–300/);
});
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

test('a rejected form clears its feedback without a restart or another request', async () => {
  const h = harness({ api: { start: async () => {
    throw Object.assign(new Error('Unsupported listing.'), { status: 400 });
  } } });
  await h.session.restore();
  await h.session.begin({ listing_url: url, job_id: 7, expected_revision: 0 });
  assert.equal(extractionErrorForDraft(h.session.snapshot(), url, 7), 'Unsupported listing.');
  assert.equal(extractionErrorForDraft(h.session.snapshot(), '', null), null);
  assert.equal(extractionErrorForDraft(h.session.snapshot(), url, 8), null);
  assert.equal(extractionErrorForDraft(h.session.snapshot(), url + '4', 7), null);
  h.session.resetFormFeedback();
  assert.equal(h.session.snapshot().error, null);
  assert.equal(h.stored, null);
  assert.deepEqual(h.calls, []);
});

test('form reset clears offline feedback but preserves unresolved recovery', async () => {
  const h = harness({ api: { start: async () => { throw new Error('Lost response'); } } });
  await h.session.restore();
  h.setOnline(false);
  await h.session.begin({ listing_url: url });
  assert.match(extractionErrorForDraft(h.session.snapshot(), url, null), /Reconnect/);
  h.session.resetFormFeedback();
  assert.equal(h.session.snapshot().error, null);
  h.setOnline(true);
  await h.session.begin({ listing_url: url });
  const pending = h.session.snapshot();
  const stored = h.stored;
  h.session.resetFormFeedback();
  assert.equal(h.session.snapshot(), pending);
  assert.equal(h.stored, stored);
  assert.match(extractionErrorForDraft(h.session.snapshot(), '', null), /No saved result/);
});

test('a late rejection cannot attach its feedback to a new blank or different draft', async () => {
  const wait = deferred();
  const h = harness({ api: { start: async () => {
    await wait.promise;
    throw Object.assign(new Error('Unsupported listing.'), { status: 400 });
  } } });
  await h.session.restore();
  const sending = h.session.begin({ listing_url: url });
  await new Promise((resolve) => setImmediate(resolve));
  const frozen = h.stored;
  h.session.resetFormFeedback();
  assert.equal(h.stored, frozen);
  wait.resolve();
  await sending;
  assert.equal(extractionErrorForDraft(h.session.snapshot(), '', null), null);
  assert.equal(extractionErrorForDraft(h.session.snapshot(), url + '4', null), null);
  assert.equal(extractionErrorForDraft(h.session.snapshot(), url, null), 'Unsupported listing.');
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

test('rate-limited and unavailable reads do not become phantom work after restart', async () => {
  for (const [status, code] of [[429, 'rate_limit'], [409, 'job_conflict'], [503, 'unavailable']]) {
    const h = harness({ api: { start: async () => {
      throw Object.assign(new Error('Try again later.'), { status, body: { code } });
    } } });
    await h.session.restore();
    await h.session.begin({ listing_url: url });
    assert.equal(h.stored, null);
    const reopened = new ExtractionSession(1, h.deps);
    await reopened.restore();
    assert.equal(reopened.snapshot().uncertain, false);
    assert.equal(reopened.snapshot().request, null);
    assert.deepEqual(h.calls, []);
  }
});

test('an unclassified 503 keeps the original request and recovers committed work', async () => {
  const h = harness();
  const start = h.api.start;
  h.api.start = async (request) => {
    await start(request);
    throw Object.assign(new Error('Gateway unavailable after commit'), { status: 503 });
  };
  await h.session.restore();
  await h.session.begin({ listing_url: url });
  assert.equal(h.session.snapshot().result?.status, 'ready');
  assert.deepEqual(h.calls, ['read', 'get']);
  assert.ok(h.stored);
});

test('late rejection from a signed-out account cannot erase the next account recovery record', async () => {
  const waiting = deferred();
  const h = harness({ api: { start: async () => {
    await waiting.promise;
    throw Object.assign(new Error('Rejected old request'), { status: 400 });
  } } });
  await h.session.restore();
  const pending = h.session.begin({ listing_url: url });
  await new Promise((resolve) => setImmediate(resolve));
  h.session.dispose();
  const nextAccount = JSON.stringify({ userId: 2, request: { request_id: randomUUID(), listing_url: url } });
  await h.storage.write(nextAccount);
  waiting.resolve();
  await pending;
  assert.equal(h.stored, nextAccount);
});

test('expired status or summary clears stale actions and permits a fresh read', async () => {
  for (const stage of ['get', 'summarize']) {
    const h = harness();
    await h.session.restore();
    await h.session.begin({ listing_url: url });
    const previous = h.session.snapshot().request.request_id;
    h.api[stage] = async () => { throw Object.assign(new Error('Suggestions expired.'), { status: 410 }); };
    await (stage === 'get' ? h.session.check() : h.session.continue());
    assert.equal(h.session.snapshot().result, null);
    assert.equal(h.session.snapshot().request, null);
    assert.equal(h.stored, null);
    assert.equal(h.session.snapshot().uncertain, false);
    await h.session.begin({ listing_url: url });
    assert.notEqual(h.session.snapshot().request.request_id, previous);
    assert.equal(h.session.snapshot().result.status, 'ready');
  }
});

test('a rejected summary retains its existing source for deliberate continuation', async () => {
  const h = harness({ api: { summarize: async () => {
    throw Object.assign(new Error('Try again later.'), { status: 429, body: { code: 'rate_limit' } });
  } } });
  await h.session.restore();
  await h.session.begin({ listing_url: url });
  const saved = h.stored;
  await h.session.continue();
  assert.equal(h.stored, saved);
  assert.equal(h.session.snapshot().result.status, 'ready');
  assert.equal(h.session.snapshot().uncertain, false);
  assert.deepEqual(h.calls, ['read']);
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
  assert.equal(suggestedFieldSelected(null, ''), true);
  assert.equal(suggestedFieldSelected(null, 'My saved title'), false);
  assert.equal(suggestedFieldSelected(true, 'My saved title'), true);
  assert.equal(suggestedFieldSelected(false, ''), false);
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
