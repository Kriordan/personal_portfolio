import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { test } from 'node:test';
import { PracticeOperation } from '../src/lib/practice-operation.ts';
import {
  PracticeDrafts,
  clearStoredDrafts,
  draftIndex,
  draftOutdated,
} from '../src/lib/practice-drafts.ts';
import { createPracticeClient } from '../src/lib/practice-client.ts';
import {
  isPracticeChange,
  messageBytes,
  practiceKeys,
  replyNotice,
  sendChange,
} from '../src/lib/practice-model.ts';

const sid = '76f7750a-6a22-4594-b6c1-a807fc9aab41';
const deferred = () => {
  let resolve;
  const promise = new Promise((yes) => {
    resolve = yes;
  });
  return { promise, resolve };
};
const tick = () => new Promise((resolve) => setImmediate(resolve));
const detail = () => ({
  session: { id: sid, concept_id: 'idempotency' },
  messages: [{ sequence: 7 }],
  artifacts: [
    { artifact_id: 'api', revision: 2 },
    { artifact_id: 'schema', revision: 0 },
  ],
  session_brief: { revision: 3 },
});
const send = () =>
  sendChange(detail(), 'What does a retry guarantee?', randomUUID());
const failure = (status, code) =>
  Object.assign(new Error('Fixture failure'), { status, body: { code } });
function harness(api = {}, storageOverrides = {}) {
  let raw = null,
    online = true;
  const writes = [],
    confirmed = [];
  const storage = {
    read: async () => raw,
    write: async (value) => {
      raw = value;
    },
    clear: async () => {
      raw = null;
    },
    ...storageOverrides,
  };
  const deps = {
    storage,
    online: () => online,
    api: {
      change: async (c) => {
        writes.push(c);
        return { session_id: sid, sequence: 8 };
      },
      receipt: async () => ({ receipt: null }),
      ...api,
    },
    onConfirmed: async (...args) => {
      confirmed.push(args);
    },
  };
  return {
    controller: new PracticeOperation(1, deps),
    deps,
    writes,
    confirmed,
    storage,
    raw: () => raw,
    offline: () => {
      online = false;
    },
    online: () => {
      online = true;
    },
  };
}
test('real practice adapter pins send and retry, reads exact artifact revisions, and carries stable IDs', async () => {
  const calls = [];
  const api = createPracticeClient(async (...args) => {
    calls.push(args);
    return {};
  });
  const change = send();
  await api.change(change);
  assert.equal(calls[0][0], `/learning/practice/sessions/${sid}/turns`);
  assert.deepEqual(calls[0][1], {
    method: 'POST',
    body: {
      request_id: change.request_id,
      body: change.body,
      expected_sequence: 7,
      artifact_revisions: { api: 2, schema: 0 },
      brief_revision: 3,
    },
    timeoutMs: 20_000,
    requestId: change.request_id,
  });
  await api.change({
    kind: 'reply',
    sessionId: sid,
    conceptId: 'idempotency',
    request_id: change.request_id,
    expected_sequence: 8,
    context: 'recent',
  });
  assert.deepEqual(calls[1][1].body, {
    request_id: change.request_id,
    expected_sequence: 8,
    context: 'recent',
  });
  await api.change({
    kind: 'start',
    conceptId: 'idempotency',
    exerciseId: 'idempotent-order-api',
    request_id: change.request_id,
  });
  assert.equal(calls[2][1].body.exercise_id, 'idempotent-order-api');
  await api.revision(sid, 'api', 1);
  assert.ok(calls[3][0].endsWith('/artifacts/api/revisions/1'));
  await api.receipt(change.request_id);
  assert.equal(calls[4][1].method, undefined);
});
test('send freezes the displayed transcript, brief and artifact revisions, including empty artifacts', () => {
  const d = detail();
  const c = sendChange(d, 'Explain', randomUUID());
  d.artifacts[0].revision = 9;
  d.messages.push({ sequence: 8 });
  assert.equal(c.artifact_revisions.api, 2);
  assert.equal(c.artifact_revisions.schema, 0);
  assert.equal(c.expected_sequence, 7);
  assert.equal(isPracticeChange(c), true);
  assert.equal(isPracticeChange({ ...c, body: '💡'.repeat(2049) }), false);
  assert.equal(messageBytes('💡'), 4);
  assert.notDeepEqual(practiceKeys.detail(1, sid), practiceKeys.detail(2, sid));
});
test('lost send response recovers from receipt exactly once without another POST', async () => {
  const c = send();
  let posts = 0;
  const h = harness({
    change: async () => {
      posts++;
      throw new Error('Lost response');
    },
    receipt: async () => ({
      receipt: {
        operation: 'send',
        response: { session_id: sid, sequence: 8 },
      },
    }),
  });
  await h.controller.restore();
  await h.controller.begin(c);
  await h.controller.check();
  assert.equal(posts, 1);
  assert.equal(h.confirmed.length, 1);
  assert.equal(h.raw(), null);
  assert.equal(h.controller.snapshot().pending, null);
});
test('missing receipt is not a failed send: restart only reads and explicit retry preserves original payload and ID', async () => {
  const calls = [];
  const gate = deferred();
  const h = harness({
    change: async (c) => {
      calls.push(c);
      if (calls.length === 1) {
        await gate.promise;
        throw new Error('lost');
      }
      return { session_id: sid, sequence: 8 };
    },
  });
  await h.controller.restore();
  const c = send();
  const pending = h.controller.begin(c);
  await tick();
  c.body = 'mutated caller';
  await h.controller.begin(send());
  gate.resolve();
  await pending;
  assert.equal(calls.length, 1);
  assert.equal(h.controller.snapshot().phase, 'uncertain');
  h.controller.dispose();
  const restored = new PracticeOperation(1, h.deps);
  await restored.restore();
  await restored.check();
  assert.equal(calls.length, 1);
  assert.equal(
    restored.snapshot().pending.body,
    'What does a retry guarantee?',
  );
  await restored.retry();
  assert.deepEqual(calls[1], calls[0]);
  assert.equal(restored.snapshot().pending, null);
});
test('start, retry, recent continuation, pause and resume all use receipt recovery without automatic paid retries', async () => {
  for (const kind of ['start', 'reply', 'pause', 'resume']) {
    const c = {
      kind,
      conceptId: 'idempotency',
      exerciseId: 'idempotent-order-api',
      sessionId: sid,
      expected_sequence: 7,
      context: 'recent',
      request_id: randomUUID(),
    };
    let posts = 0;
    const h = harness({
      change: async () => {
        posts++;
        throw new Error('lost');
      },
      receipt: async () => ({
        receipt: {
          operation: kind,
          response: { session_id: sid },
        },
      }),
    });
    await h.controller.restore();
    await h.controller.begin(c);
    assert.equal(posts, 1);
    assert.equal(h.raw(), null);
  }
});
test('another device changing work rejects send and retains its text for deliberate reconciliation', async () => {
  for (const code of [
    'stale_artifact',
    'stale_brief',
    'stale_transcript',
    'reply_pending',
  ]) {
    const h = harness({
      change: async () => {
        throw failure(409, code);
      },
    });
    await h.controller.restore();
    const c = send();
    await h.controller.begin(c);
    assert.equal(h.controller.snapshot().phase, 'rejected');
    assert.equal(h.controller.snapshot().pending.body, c.body);
    await h.controller.check();
    await h.controller.retry();
    assert.equal(h.confirmed.length, 0);
    assert.equal(await h.controller.dismissRejected(), true);
    assert.equal(h.controller.snapshot().pending, null);
  }
});
test('storage failure refuses network writes; cleanup failure keeps the original request recoverable', async () => {
  const h = harness(
    {},
    {
      write: async () => {
        throw new Error('locked');
      },
    },
  );
  await h.controller.restore();
  await h.controller.begin(send());
  assert.equal(h.writes.length, 0);
  assert.equal(h.controller.snapshot().phase, 'rejected');
  const c = send();
  let failClear = true;
  const h2 = harness(
    {
      receipt: async () => ({
        receipt: {
          operation: 'send',
          response: { session_id: sid, sequence: 8 },
        },
      }),
    },
    {
      clear: async () => {
        if (failClear) throw new Error('locked');
      },
    },
  );
  await h2.controller.restore();
  await h2.controller.begin(c);
  assert.ok(h2.controller.snapshot().pending);
  failClear = false;
  await h2.controller.check();
  assert.equal(h2.controller.snapshot().pending, null);
  assert.equal(h2.writes.length, 1);
});
test('offline refusal, wrong receipt and unreadable journal fail closed', async () => {
  const h = harness();
  await h.controller.restore();
  h.offline();
  await h.controller.begin(send());
  assert.equal(h.writes.length, 0);
  const bad = harness({
    change: async () => {
      throw new Error('lost');
    },
    receipt: async () => ({
      receipt: { operation: 'pause', response: { session_id: sid } },
    }),
  });
  await bad.controller.restore();
  await bad.controller.begin(send());
  assert.equal(bad.controller.snapshot().phase, 'uncertain');
  const corrupt = harness(
    {},
    { read: async () => '{"userId":1,"change":null}' },
  );
  await corrupt.controller.restore();
  await corrupt.controller.begin(send());
  assert.equal(corrupt.controller.snapshot().ready, false);
  assert.equal(corrupt.writes.length, 0);
});
test('logout fences late responses; another account never recovers the previous account journal', async () => {
  const gate = deferred();
  const h = harness({ change: () => gate.promise });
  await h.controller.restore();
  const sending = h.controller.begin(send());
  await tick();
  h.controller.dispose();
  const next = new PracticeOperation(2, h.deps);
  await next.restore();
  assert.equal(next.snapshot().pending, null);
  gate.resolve({ session_id: sid, sequence: 8 });
  await sending;
  assert.equal(h.confirmed.length, 0);
  assert.equal(next.snapshot().saved, null);
});
test('budget exhaustion and context boundaries explain the limit without treating 24 turns as a stop', () => {
  assert.match(replyNotice({ unavailable: 'budget' }), /spending allowance/);
  assert.match(
    replyNotice({ can_continue_recent: true }),
    /explicitly continue/,
  );
  assert.match(
    replyNotice({ unavailable: 'essential_too_large' }),
    /Nothing has been omitted/,
  );
  assert.match(replyNotice({ status: 'running' }), /leave and return/);
});

function draftHarness(overrides = {}) {
  const values = new Map();
  let tail = Promise.resolve();
  const serial = (run) => {
    const next = tail.then(run, run);
    tail = next.catch(() => {});
    return next;
  };
  const storage = {
    get: async (key) => values.get(key) ?? null,
    set: async (key, value) => {
      values.set(key, value);
    },
    remove: async (key) => {
      values.delete(key);
    },
    ...overrides,
  };
  return {
    values,
    storage,
    serial,
    drafts: new PracticeDrafts(1, storage, serial),
  };
}
test('draft text and its original context survive restart, and clearing a draft removes its index entry', async () => {
  const h = draftHarness();
  await h.drafts.load(sid);
  h.drafts.edit(sid, 'My design', detail());
  await tick();
  assert.equal(h.drafts.snapshot(sid).saving, false);
  h.drafts.dispose();
  const restored = new PracticeDrafts(1, h.storage, h.serial);
  await restored.load(sid);
  assert.equal(restored.snapshot(sid).draft.body, 'My design');
  const changed = detail();
  changed.messages.push({ sequence: 8 });
  changed.artifacts[0].revision++;
  assert.equal(draftOutdated(restored.snapshot(sid).draft, changed), true);
  restored.edit(sid, 'My revised draft', changed);
  await tick();
  assert.equal(
    draftOutdated(restored.snapshot(sid).draft, changed),
    true,
    'typing must not silently rebase',
  );
  restored.rebase(sid, changed);
  await tick();
  assert.equal(draftOutdated(restored.snapshot(sid).draft, changed), false);
  restored.edit(sid, '', changed);
  await tick();
  assert.deepEqual(JSON.parse(h.values.get(draftIndex)).ids, []);
});
test('drafts remain isolated by session and account, and sign-out removes every tracked draft', async () => {
  const h = draftHarness(),
    second = randomUUID();
  await h.drafts.load(sid);
  await h.drafts.load(second);
  h.drafts.edit(sid, 'First', detail());
  h.drafts.edit(second, 'Second', {
    ...detail(),
    session: { ...detail().session, id: second },
  });
  await tick();
  const other = new PracticeDrafts(2, h.storage, h.serial);
  await other.load(sid);
  assert.equal(other.snapshot(sid).draft, null);
  h.drafts.dispose();
  other.dispose();
  await h.serial(() => clearStoredDrafts(h.storage));
  assert.equal(h.values.size, 0);
});
test('logout waits behind an in-flight draft write, and disposed controllers cannot resurrect it', async () => {
  const gate = deferred(),
    values = new Map();
  const h = draftHarness({
    set: async (key, value) => {
      await gate.promise;
      values.set(key, value);
    },
    get: async (key) => values.get(key) ?? null,
    remove: async (key) => {
      values.delete(key);
    },
  });
  await h.drafts.load(sid);
  h.drafts.edit(sid, 'Private draft', detail());
  await tick();
  h.drafts.dispose();
  const cleanup = h.serial(() => clearStoredDrafts(h.storage));
  gate.resolve();
  await cleanup;
  await tick();
  assert.equal(values.size, 0);
  h.drafts.edit(sid, 'Late callback', detail());
  await tick();
  assert.equal(values.size, 0);
});
test('rapid edits coalesce to the latest text instead of a delayed older draft overwriting it', async () => {
  const gate = deferred(),
    values = new Map();
  let writes = 0;
  const h = draftHarness({
    set: async (key, value) => {
      if (key !== draftIndex && writes++ === 0) await gate.promise;
      values.set(key, value);
    },
    get: async (key) => values.get(key) ?? null,
  });
  await h.drafts.load(sid);
  h.drafts.edit(sid, 'Old', detail());
  await tick();
  h.drafts.edit(sid, 'Newest', detail());
  gate.resolve();
  await tick();
  const restored = new PracticeDrafts(1, h.storage, h.serial);
  await restored.load(sid);
  assert.equal(restored.snapshot(sid).draft.body, 'Newest');
});
test('device-storage failure retains typing and exposes an explicit retry; no false saved status', async () => {
  let broken = true;
  const h = draftHarness({
    set: async () => {
      if (broken) throw new Error('Keychain locked');
    },
  });
  await h.drafts.load(sid);
  h.drafts.edit(sid, 'Retain this', detail());
  await tick();
  assert.equal(h.drafts.snapshot(sid).draft.body, 'Retain this');
  assert.ok(h.drafts.snapshot(sid).error);
  broken = false;
  h.drafts.retrySave(sid);
  await tick();
  assert.equal(h.drafts.snapshot(sid).error, null);
});
test('large Unicode and whitespace drafts remain editable after restart but cannot bypass send limits', async () => {
  const h = draftHarness();
  await h.drafts.load(sid);
  for (const body of [' ', '💡'.repeat(3000)]) {
    h.drafts.edit(sid, body, detail());
    await tick();
    const restored = new PracticeDrafts(1, h.storage, h.serial);
    await restored.load(sid);
    assert.equal(restored.snapshot(sid).draft.body, body);
    assert.equal(isPracticeChange(restored.snapshot(sid).draft), false);
  }
});
test('confirmation clears only the sent draft, and a failed cleanup remains safely retryable', async () => {
  const values = new Map();
  let failDelete = true;
  const h = draftHarness({
    get: async (key) => values.get(key) ?? null,
    set: async (k, v) => values.set(k, v),
    remove: async (k) => {
      if (failDelete) throw new Error('Locked');
      values.delete(k);
    },
  });
  await h.drafts.load(sid);
  h.drafts.edit(sid, 'Sent body', detail());
  await tick();
  await assert.rejects(h.drafts.clearIfMatches(sid, 'Sent body'));
  assert.equal(h.drafts.snapshot(sid).draft.body, 'Sent body');
  failDelete = false;
  await h.drafts.clearIfMatches(sid, 'Sent body');
  assert.equal(h.drafts.snapshot(sid).draft, null);
  h.drafts.edit(sid, 'New draft', detail());
  await tick();
  await h.drafts.clearIfMatches(sid, 'Sent body');
  assert.equal(h.drafts.snapshot(sid).draft.body, 'New draft');
});
test('an indexed draft whose content was never committed restores empty; corrupt content fails closed', async () => {
  const h = draftHarness();
  h.values.set(draftIndex, JSON.stringify({ userId: 1, ids: [sid] }));
  await h.drafts.load(sid);
  assert.equal(h.drafts.snapshot(sid).ready, true);
  assert.equal(h.drafts.snapshot(sid).draft, null);
  h.values.set(`${draftIndex}.1.${sid}`, '{not json');
  const restored = new PracticeDrafts(1, h.storage, h.serial);
  await restored.load(sid);
  assert.equal(restored.snapshot(sid).ready, false);
  assert.ok(restored.snapshot(sid).error);
});

test('a saved send whose draft cleanup fails recovers both stores without repeating the network write', async () => {
  const values = new Map();
  let failDelete = true;
  const d = draftHarness({
    get: async (key) => values.get(key) ?? null,
    set: async (key, value) => values.set(key, value),
    remove: async (key) => {
      if (failDelete) throw new Error('Locked');
      values.delete(key);
    },
  });
  await d.drafts.load(sid);
  d.drafts.edit(sid, 'Saved send', detail());
  await tick();
  const change = { ...d.drafts.snapshot(sid).draft, request_id: randomUUID() };
  const h = harness({
    receipt: async () => ({
      receipt: {
        operation: 'send',
        response: { session_id: sid, sequence: 8 },
      },
    }),
  });
  h.deps.onConfirmed = async (c) =>
    d.drafts.clearIfMatches(c.sessionId, c.body);
  await h.controller.restore();
  await h.controller.begin(change);
  assert.equal(h.writes.length, 1);
  assert.ok(h.controller.snapshot().pending);
  assert.ok(h.raw());
  failDelete = false;
  await h.controller.check();
  assert.equal(h.writes.length, 1);
  assert.equal(h.controller.snapshot().pending, null);
  assert.equal(d.drafts.snapshot(sid).draft, null);
  assert.equal(h.raw(), null);
});
