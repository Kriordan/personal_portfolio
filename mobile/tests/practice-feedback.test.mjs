import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createPracticeClient } from '../src/lib/practice-client.ts';
import { PracticeOperation } from '../src/lib/practice-operation.ts';
import { isPracticeChange, practiceKeys } from '../src/lib/practice-model.ts';
import {
  evidenceText,
  feedbackNotice,
  snapshotBlock,
  snapshotChange,
  snapshotIsOlder,
} from '../src/lib/practice-feedback-model.ts';

const sid = '76f7750a-6a22-4594-b6c1-a807fc9aab41';
const rid = 'abf91dc0-d95e-4a00-bb7f-a9f77a433871';
const aid = 'abf91dc0-d95e-4a00-bb7f-a9f77a433872';
const tick = () => new Promise((resolve) => setImmediate(resolve));
const detail = () => ({
  session: { id: sid, concept_id: 'idempotency', status: 'active' },
  artifacts: [
    {
      artifact_id: 'api',
      revision: 2,
      language: 'json',
      body: '{"saved":true}',
    },
    { artifact_id: 'sql', revision: 0, language: 'sql', body: '' },
  ],
  session_brief: {
    revision: 1,
    entries: [
      {
        id: 'decision-1',
        type: 'decision',
        text: 'Scope the key to its owner.',
        pinned: true,
        sources: [{ turn: 3 }],
      },
    ],
  },
  messages: [
    { sequence: 3, role: 'learner', body: 'A retry uses the same key.' },
    { sequence: 4, role: 'assistant', body: 'Explain that choice.' },
  ],
  reply: { status: 'completed' },
  feedback_pending: null,
});
const submit = () => snapshotChange(detail(), rid);
const feedback = () => ({
  kind: 'feedback',
  sessionId: sid,
  conceptId: 'idempotency',
  request_id: rid,
  submission_sequence: 7,
});
const snapshot = () => ({
  sequence: 7,
  through_sequence: 6,
  turn_sequence: 4,
  brief_revision: 1,
  checks: detail().artifacts.map((a) => ({
    artifact_id: a.artifact_id,
    revision: a.revision,
    language: a.language,
  })),
});
const result = (c) =>
  c.kind === 'submit'
    ? {
        session_id: sid,
        submission: snapshot(),
        brief: { revision: 1, changed: false },
        artifacts: {
          api: { revision: 2, changed: false },
          sql: { revision: 0, changed: false },
        },
      }
    : {
        session_id: sid,
        submission_sequence: 7,
        request: { id: aid, status: 'pending', reason: null },
      };
function harness(
  api = {},
  storageOverrides = {},
  onConfirmed = async () => {},
) {
  let raw = null,
    online = true;
  const writes = [];
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
    onConfirmed,
    api: {
      change: async (c) => {
        writes.push(c);
        return result(c);
      },
      receipt: async () => ({ receipt: null }),
      ...api,
    },
  };
  return {
    controller: new PracticeOperation(1, deps),
    deps,
    storage,
    writes,
    raw: () => raw,
    offline: () => {
      online = false;
    },
  };
}

test('snapshot and feedback adapters send separate exact contracts and read account-scoped history', async () => {
  const calls = [];
  const api = createPracticeClient(async (...args) => {
    calls.push(args);
    return {};
  });
  const c = submit();
  await api.change(c);
  assert.equal(calls[0][0], `/learning/practice/sessions/${sid}/submissions`);
  assert.deepEqual(calls[0][1].body, {
    request_id: rid,
    expected_sequence: 4,
    edits: c.edits,
    brief: c.brief,
  });
  await api.change(feedback());
  assert.equal(
    calls[1][0],
    `/learning/practice/sessions/${sid}/submissions/7/feedback`,
  );
  assert.deepEqual(calls[1][1], {
    method: 'POST',
    body: { request_id: rid },
    timeoutMs: 20000,
    requestId: rid,
  });
  await api.submission(sid, 7);
  await api.feedback(sid, 7);
  assert.equal(calls[2][1].method, undefined);
  assert.equal(calls[3][1].method, undefined);
  assert.notDeepEqual(
    practiceKeys.feedback(1, sid, 7),
    practiceKeys.feedback(2, sid, 7),
  );
  assert.notDeepEqual(
    practiceKeys.submission(1, sid, 7),
    practiceKeys.submission(1, sid, 8),
  );
});
test('snapshots freeze every saved artifact, empty revision, note source and conversation boundary', () => {
  const d = detail(),
    c = snapshotChange(d, rid);
  d.artifacts[0].body = 'later';
  d.session_brief.entries[0].sources[0].turn = 99;
  d.messages.push({ sequence: 5 });
  assert.equal(c.edits[0].body, '{"saved":true}');
  assert.equal(c.edits[1].base_revision, 0);
  assert.equal(c.brief.entries[0].sources[0].turn, 3);
  assert.equal(c.expected_sequence, 4);
  assert.equal(isPracticeChange(c), true);
  for (const bad of [
    { ...c, edits: [] },
    { ...c, edits: [c.edits[0], c.edits[0]] },
    { ...c, brief: null },
    { ...c, expected_sequence: -1 },
    { ...c, edits: [{ ...c.edits[0], body: '💡'.repeat(16385) }] },
    { ...feedback(), submission_sequence: 0 },
    { ...feedback(), submission_sequence: 2147483648 },
  ])
    assert.equal(isPracticeChange(bad), false);
});
test('snapshot creation waits for protected drafts, unsent messages, and current AI requests', () => {
  const local = {
    ready: true,
    error: false,
    saving: false,
    edits: 0,
    message: '',
  };
  assert.equal(snapshotBlock(detail(), local), null);
  for (const patch of [
    { ready: false },
    { error: true },
    { saving: true },
    { edits: 1 },
    { message: 'unsent' },
  ])
    assert.ok(snapshotBlock(detail(), { ...local, ...patch }));
  const d = detail();
  d.session.status = 'paused';
  assert.equal(snapshotBlock(d, local), null);
  d.feedback_pending = { sequence: 7, status: 'running' };
  assert.match(snapshotBlock(d, local), /keep editing/);
  d.feedback_pending = null;
  d.reply.status = 'pending';
  assert.ok(snapshotBlock(d, local));
});
test('lost snapshot and feedback responses recover after restart without any second POST', async () => {
  for (const c of [submit(), feedback()]) {
    let writes = 0,
      reads = false;
    const h = harness({
      change: async () => {
        writes++;
        throw Error('lost after commit');
      },
      receipt: async () => {
        if (!reads) throw Error('offline');
        return { receipt: { operation: c.kind, response: result(c) } };
      },
    });
    await h.controller.restore();
    await h.controller.begin(c);
    assert.equal(h.controller.snapshot().phase, 'uncertain');
    h.controller.dispose();
    reads = true;
    const restored = new PracticeOperation(1, h.deps);
    await restored.restore();
    assert.equal(restored.snapshot().phase, 'idle');
    assert.deepEqual(restored.snapshot().saved.result, result(c));
    assert.equal(writes, 1);
    assert.equal(h.raw(), null);
  }
});
test('an absent receipt never repeats a write; explicit retries preserve frozen payload and UUID', async () => {
  for (const c of [submit(), feedback()]) {
    const calls = [];
    const h = harness({
      change: async (v) => {
        calls.push(structuredClone(v));
        if (calls.length === 1) throw Error('lost');
        return result(v);
      },
    });
    await h.controller.restore();
    await h.controller.begin(c);
    if (c.kind === 'submit') c.edits[0].body = 'typed later';
    else c.submission_sequence = 999;
    await h.controller.check();
    await h.controller.check();
    assert.equal(calls.length, 1);
    await h.controller.retry();
    assert.deepEqual(calls[0], calls[1]);
    assert.equal(h.controller.snapshot().phase, 'idle');
  }
});
test('duplicate taps and a late account change cannot start another assessment or confirm another account', async () => {
  let finish,
    writes = 0,
    confirms = 0;
  const waiting = new Promise((resolve) => {
    finish = resolve;
  });
  const h = harness(
    {
      change: async () => {
        writes++;
        await waiting;
        return result(feedback());
      },
    },
    {},
    async () => {
      confirms++;
    },
  );
  await h.controller.restore();
  const request = h.controller.begin(feedback());
  await tick();
  await h.controller.begin(feedback());
  h.controller.dispose();
  const other = new PracticeOperation(2, h.deps);
  await other.restore();
  assert.equal(other.snapshot().pending, null);
  finish();
  await request;
  assert.equal(writes, 1);
  assert.equal(confirms, 0);
});
test('storage failures and offline state refuse writes; failed cleanup preserves a recoverable receipt', async () => {
  const h = harness(
    {},
    {
      write: async () => {
        throw Error('storage');
      },
    },
  );
  await h.controller.restore();
  await h.controller.begin(feedback());
  assert.equal(h.writes.length, 0);
  assert.equal(h.controller.snapshot().phase, 'rejected');
  const offline = harness();
  await offline.controller.restore();
  offline.offline();
  await offline.controller.begin(submit());
  assert.equal(offline.writes.length, 0);
  let fail = true,
    posts = 0;
  const cleanup = harness(
    {
      change: async (c) => {
        posts++;
        return result(c);
      },
      receipt: async () => ({
        receipt: { operation: 'feedback', response: result(feedback()) },
      }),
    },
    {},
    async () => {
      if (fail) throw Error('cleanup');
    },
  );
  await cleanup.controller.restore();
  await cleanup.controller.begin(feedback());
  assert.ok(cleanup.raw());
  fail = false;
  await cleanup.controller.check();
  assert.equal(cleanup.raw(), null);
  assert.equal(posts, 1);
});
test('receipts must match the snapshot boundary, artifact heads, session and operation', async () => {
  const c = submit();
  for (const alter of [
    (r) => {
      r.submission.turn_sequence++;
    },
    (r) => {
      r.submission.checks[0].revision++;
    },
    (r) => {
      r.submission.checks.pop();
    },
    (r) => {
      r.submission.brief_revision++;
    },
    (r) => {
      r.session_id = aid;
    },
  ]) {
    const wrong = result(c);
    alter(wrong);
    const h = harness({
      change: async () => wrong,
      receipt: async () => ({
        receipt: { operation: 'submit', response: wrong },
      }),
    });
    await h.controller.restore();
    await h.controller.begin(c);
    assert.equal(h.controller.snapshot().phase, 'uncertain');
    assert.ok(h.raw());
  }
  for (const [operation, response] of [
    ['reply', result(feedback())],
    ['feedback', { ...result(feedback()), submission_sequence: 8 }],
  ]) {
    const h = harness({
      change: async () => {
        throw Error('lost');
      },
      receipt: async () => ({ receipt: { operation, response } }),
    });
    await h.controller.restore();
    await h.controller.begin(feedback());
    assert.equal(h.controller.snapshot().phase, 'uncertain');
  }
});
test('stale web work rejects the snapshot until explicit refresh without silently resubmitting', async () => {
  let posts = 0;
  const h = harness({
    change: async () => {
      posts++;
      throw Object.assign(Error('stale'), {
        status: 409,
        body: { code: 'stale_view' },
      });
    },
  });
  await h.controller.restore();
  await h.controller.begin(submit());
  assert.equal(h.controller.snapshot().phase, 'rejected');
  await h.controller.retry();
  await h.controller.check();
  assert.equal(posts, 1);
  assert.equal(await h.controller.dismissRejected(), true);
});
test('budget and whole-snapshot size refusals confirm safely and never trigger automatic new attempts', async () => {
  for (const reason of [
    'budget',
    'context_too_large',
    'disabled',
    'owner_only',
  ]) {
    let posts = 0;
    const response = {
      ...result(feedback()),
      request: { id: null, status: 'unavailable', reason },
    };
    const h = harness({
      change: async () => {
        posts++;
        return response;
      },
    });
    await h.controller.restore();
    await h.controller.begin(feedback());
    await h.controller.check();
    await h.controller.retry();
    assert.equal(posts, 1);
    assert.equal(h.controller.snapshot().saved.result.request.reason, reason);
    assert.ok(feedbackNotice(reason));
  }
  assert.match(
    feedbackNotice('context_too_large'),
    /Nothing was silently omitted/,
  );
  assert.match(feedbackNotice('timeout'), /will not retry automatically/);
});
test('older assessments are identified by turns, brief and exact artifact revisions', () => {
  const d = detail(),
    s = snapshot();
  assert.equal(snapshotIsOlder(d, s), false);
  for (const change of [
    (v) => {
      v.messages.push({ sequence: 9 });
    },
    (v) => {
      v.artifacts[0].revision++;
    },
    (v) => {
      v.session_brief.revision++;
    },
  ]) {
    const changed = structuredClone(d);
    change(changed);
    assert.equal(snapshotIsOlder(changed, s), true);
  }
});
test('citations read original learner turns and saved notes, refusing newer notes and wrong boundaries', () => {
  const d = detail(),
    stored = {
      session: d.session,
      submission: snapshot(),
      session_brief: structuredClone(d.session_brief),
    };
  const note = {
    kind: 'note',
    entry_id: 'decision-1',
    revision: 1,
    quote: 'Scope the key',
  };
  d.session_brief.entries[0].text = 'A different later decision.';
  assert.equal(evidenceText(note, d, stored), 'Scope the key to its owner.');
  assert.equal(evidenceText({ ...note, revision: 2 }, d, stored), null);
  assert.equal(
    evidenceText({ kind: 'turn', sequence: 3, quote: 'same key' }, d, stored),
    'A retry uses the same key.',
  );
  assert.equal(
    evidenceText({ kind: 'turn', sequence: 4, quote: 'Explain' }, d, stored),
    null,
  );
  stored.submission.turn_sequence = 2;
  assert.equal(
    evidenceText({ kind: 'turn', sequence: 3, quote: 'same key' }, d, stored),
    null,
  );
  stored.session = { id: aid };
  assert.equal(evidenceText(note, d, stored), null);
});
