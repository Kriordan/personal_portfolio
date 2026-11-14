import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createPracticeClient } from '../src/lib/practice-client.ts';
import { PracticeOperation } from '../src/lib/practice-operation.ts';
import { isPracticeChange } from '../src/lib/practice-model.ts';
import {
  PracticeWorkDrafts,
  clearStoredWorkDrafts,
  savedWork,
  workDraftIndex,
  workBlocksSend,
} from '../src/lib/practice-work-drafts.ts';
import {
  ARTIFACT_LIMIT,
  copyWork,
  sameWork,
  validWorkEdit,
  workKey,
  workProblem,
} from '../src/lib/practice-work-model.ts';

const sid = '76f7750a-6a22-4594-b6c1-a807fc9aab41';
const otherSid = '76f7750a-6a22-4594-b6c1-a807fc9aab42';
const rid = 'abf91dc0-d95e-4a00-bb7f-a9f77a433871';
const aid = 'abf91dc0-d95e-4a00-bb7f-a9f77a433872';
const tick = () => new Promise((done) => setImmediate(done));
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
};
const artifact = (body = 'POST /orders\nIdempotency-Key: request-id') => ({
  kind: 'artifact',
  artifactId: 'api',
  base_revision: 2,
  language: 'text',
  body,
});
const note = () => ({
  id: 'decision-1',
  type: 'decision',
  text: 'Scope the key by account.',
  pinned: true,
  basis: 'learner',
  sources: [{ turn: 2 }, { artifact_id: 'api', revision: 1 }],
});
const brief = () => ({ kind: 'brief', base_revision: 1, entries: [note()] });
const change = (edit = artifact()) => ({
  ...edit,
  sessionId: sid,
  conceptId: 'idempotency',
  request_id: rid,
});
const result = (edit = artifact()) => ({
  session_id: sid,
  status: 'active',
  ...(edit.kind === 'brief'
    ? { brief: { revision: edit.base_revision + 1, changed: true } }
    : {
        artifacts: {
          [edit.artifactId]: {
            revision: edit.base_revision + 1,
            changed: true,
          },
        },
      }),
});
const detail = () => ({
  session: { id: sid, concept_id: 'idempotency' },
  artifacts: [
    {
      artifact_id: 'api',
      revision: 2,
      language: 'text',
      body: 'saved API',
      languages: ['text', 'json', 'yaml'],
    },
  ],
  session_brief: { revision: 1, entries: [note()] },
});
function harness(overrides = {}) {
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
  const drafts = new PracticeWorkDrafts(1, storage, serial);
  return {
    values,
    storage,
    serial,
    drafts,
    flush: async () => {
      await tick();
      await tail;
      await tick();
    },
  };
}
async function operationHarness(h, apiOverrides = {}, journalOverrides = {}) {
  let journal = null;
  let calls = 0;
  const storage = {
    read: () => h.serial(async () => journal),
    write: (value) =>
      h.serial(async () => {
        journal = value;
      }),
    clear: () =>
      h.serial(async () => {
        journal = null;
      }),
    ...journalOverrides,
  };
  const deps = {
    storage,
    online: () => true,
    api: {
      change: async (c) => {
        calls++;
        return result(c);
      },
      receipt: async () => ({ receipt: null }),
      ...apiOverrides,
    },
    onConfirmed: async (c) => h.drafts.clearIfMatches(c.sessionId, c),
  };
  const operation = new PracticeOperation(1, deps);
  await operation.restore();
  return { operation, deps, calls: () => calls, journal: () => journal };
}

test('artifact and brief adapters use existing PUT contracts, original bases and stable request IDs', async () => {
  const calls = [];
  const api = createPracticeClient(async (...args) => {
    calls.push(args);
    return {};
  });
  await api.change(change());
  await api.change(change(brief()));
  assert.equal(calls[0][0], `/learning/practice/sessions/${sid}/artifacts/api`);
  assert.deepEqual(calls[0][1], {
    method: 'PUT',
    body: {
      request_id: rid,
      base_revision: 2,
      language: 'text',
      body: artifact().body,
    },
    timeoutMs: 20_000,
    requestId: rid,
  });
  assert.equal(calls[1][0], `/learning/practice/sessions/${sid}/brief`);
  assert.deepEqual(calls[1][1].body, {
    request_id: rid,
    base_revision: 1,
    entries: [note()],
  });
  assert.equal(calls[1][1].method, 'PUT');
  assert.equal(isPracticeChange(change()), true);
  assert.equal(isPracticeChange(change(brief())), true);
});
test('Discuss stays blocked until every Build edit is confirmed or explicitly discarded', async () => {
  const h = harness();
  assert.equal(workBlocksSend(h.drafts.snapshot(sid)), true);
  await h.drafts.load(sid);
  assert.equal(workBlocksSend(h.drafts.snapshot(sid)), false);
  h.drafts.edit(sid, artifact());
  h.drafts.edit(sid, brief());
  assert.equal(workBlocksSend(h.drafts.snapshot(sid)), true);
  await h.flush();
  await h.drafts.clearIfMatches(sid, artifact());
  assert.equal(workBlocksSend(h.drafts.snapshot(sid)), true);
  await h.drafts.clearIfMatches(sid, brief());
  assert.equal(workBlocksSend(h.drafts.snapshot(sid)), false);
  assert.equal(
    workBlocksSend({
      ready: true,
      edits: [],
      saving: false,
      error: 'unconfirmed cleanup',
    }),
    true,
  );
});
test('limits match server UTF-8 and line-ending rules while unfinished drafts stay editable', () => {
  assert.equal(validWorkEdit(artifact('a'.repeat(ARTIFACT_LIMIT))), true);
  assert.equal(validWorkEdit(artifact('💡'.repeat(16_384))), true);
  const tooLarge = artifact('💡'.repeat(16_385));
  assert.equal(validWorkEdit(tooLarge, true), true);
  assert.equal(validWorkEdit(tooLarge), false);
  assert.match(workProblem(tooLarge), /64 KiB/);
  assert.equal(validWorkEdit(artifact('a\r\n'.repeat(20_000))), true);
  assert.equal(validWorkEdit(artifact('x\0')), false);
  assert.equal(validWorkEdit(artifact('')), true);
  const incomplete = { ...brief(), entries: [{ ...note(), text: '' }] };
  assert.equal(validWorkEdit(incomplete, true), true);
  assert.equal(validWorkEdit(incomplete), false);
  assert.equal(
    validWorkEdit(
      {
        ...brief(),
        entries: Array.from({ length: 51 }, (_, i) => ({
          ...note(),
          id: `e${i}`,
        })),
      },
      true,
    ),
    false,
  );
  assert.equal(
    validWorkEdit({
      ...brief(),
      entries: [{ ...note(), text: '💡'.repeat(513) }],
    }),
    false,
  );
  assert.equal(isPracticeChange({ ...change(), base_revision: -1 }), false);
});
test('brief edits preserve evidence, pinning and IDs; impossible sources and duplicate IDs are refused', () => {
  const value = brief();
  const copied = copyWork(value);
  value.entries[0].sources[0].turn = 999;
  assert.equal(copied.entries[0].sources[0].turn, 2);
  assert.equal(copied.entries[0].pinned, true);
  assert.equal(validWorkEdit({ ...brief(), entries: [note(), note()] }), false);
  assert.equal(
    validWorkEdit({ ...brief(), entries: [{ ...note(), basis: 'scenario' }] }),
    false,
  );
  assert.equal(
    validWorkEdit({
      ...brief(),
      entries: [{ ...note(), sources: [{ turn: 0 }] }],
    }),
    false,
  );
  assert.equal(
    validWorkEdit({
      ...brief(),
      entries: [
        { ...note(), sources: [{ artifact_id: '../private', revision: 1 }] },
      ],
    }),
    false,
  );
  const current = detail();
  const saved = savedWork(current, 'brief');
  saved.entries[0].text = 'draft';
  assert.equal(current.session_brief.entries[0].text, note().text);
  assert.equal(savedWork(current, 'artifact:missing'), null);
});
test('multiple work drafts and intentional empty artifacts survive restart with original bases', async () => {
  const h = harness();
  await h.drafts.load(sid);
  h.drafts.edit(sid, artifact());
  h.drafts.edit(sid, brief());
  h.drafts.edit(sid, {
    ...artifact(''),
    artifactId: 'schema',
    language: 'sql',
    base_revision: 0,
  });
  await h.flush();
  h.drafts.dispose();
  const reopened = new PracticeWorkDrafts(1, h.storage, h.serial);
  await reopened.load(sid);
  assert.equal(reopened.snapshot(sid).edits.length, 3);
  assert.equal(
    reopened.snapshot(sid).edits.find((e) => e.artifactId === 'schema').body,
    '',
  );
  assert.equal(
    reopened.snapshot(sid).edits.find((e) => e.artifactId === 'api')
      .base_revision,
    2,
  );
  assert.deepEqual(
    reopened.snapshot(sid).edits.find((e) => e.kind === 'brief').entries,
    brief().entries,
  );
});
test('typing coalesces without losing the latest edit or unrelated notes', async () => {
  const gate = deferred();
  let writes = 0;
  const h = harness({
    set: async (key, value) => {
      if (key.endsWith(sid) && writes++ === 0) await gate.promise;
      h.values.set(key, value);
    },
  });
  await h.drafts.load(sid);
  h.drafts.edit(sid, artifact('first'));
  await tick();
  h.drafts.edit(sid, artifact('second'));
  h.drafts.edit(sid, brief());
  h.drafts.edit(sid, artifact('last'));
  gate.resolve();
  await h.flush();
  const reopened = new PracticeWorkDrafts(1, h.storage, h.serial);
  await reopened.load(sid);
  assert.equal(
    reopened.snapshot(sid).edits.find((e) => e.artifactId === 'api').body,
    'last',
  );
  assert.equal(
    reopened.snapshot(sid).edits.find((e) => e.kind === 'brief').entries[0]
      .text,
    note().text,
  );
  assert.ok(writes <= 2);
});
test('web refreshes never adopt a new base; only an explicit comparison decision rebases the draft', async () => {
  const h = harness();
  await h.drafts.load(sid);
  h.drafts.edit(sid, artifact());
  await h.flush();
  const updated = detail();
  updated.artifacts[0].revision = 7;
  updated.artifacts[0].body = 'web proposal';
  await h.drafts.load(sid);
  assert.equal(h.drafts.snapshot(sid).edits[0].base_revision, 2);
  h.drafts.rebase(sid, savedWork(updated, 'artifact:api'));
  await h.flush();
  assert.equal(h.drafts.snapshot(sid).edits[0].base_revision, 7);
  assert.equal(h.drafts.snapshot(sid).edits[0].body, artifact().body);
});
test('confirming one part removes only that exact draft and preserves newer edits and other parts', async () => {
  const h = harness();
  await h.drafts.load(sid);
  const sent = artifact();
  h.drafts.edit(sid, sent);
  h.drafts.edit(sid, brief());
  await h.flush();
  h.drafts.edit(sid, artifact('newer typing'));
  await h.flush();
  await h.drafts.clearIfMatches(sid, sent);
  assert.equal(h.drafts.snapshot(sid).edits.length, 2);
  await h.drafts.clearIfMatches(sid, artifact('newer typing'));
  assert.deepEqual(h.drafts.snapshot(sid).edits.map(workKey), ['brief']);
  await h.drafts.clearIfMatches(sid, brief());
  assert.equal(h.drafts.snapshot(sid).edits.length, 0);
  assert.equal(h.values.has(`${workDraftIndex}.1.${sid}`), false);
});
test('storage failure is visible; retry protects unfinished and maximum-size drafts without truncation', async () => {
  let fail = true;
  const h = harness({
    set: async (key, value) => {
      if (fail) throw new Error('Locked');
      h.values.set(key, value);
    },
  });
  await h.drafts.load(sid);
  const large = artifact('💡'.repeat(16_385));
  h.drafts.edit(sid, large);
  await h.flush();
  assert.ok(h.drafts.snapshot(sid).error);
  assert.equal(h.drafts.snapshot(sid).edits[0].body, large.body);
  fail = false;
  h.drafts.retrySave(sid);
  await h.flush();
  assert.equal(h.drafts.snapshot(sid).error, null);
  const reopened = new PracticeWorkDrafts(1, h.storage, h.serial);
  await reopened.load(sid);
  assert.equal(reopened.snapshot(sid).edits[0].body, large.body);
});
test('sign-out fences late writes, clears every indexed session, and another account sees no drafts', async () => {
  const gate = deferred();
  let hold = false;
  const h = harness({
    set: async (key, value) => {
      if (hold && key.endsWith(sid)) await gate.promise;
      h.values.set(key, value);
    },
  });
  await h.drafts.load(sid);
  await h.drafts.load(otherSid);
  h.drafts.edit(otherSid, brief());
  await h.flush();
  hold = true;
  h.drafts.edit(sid, artifact());
  await tick();
  h.drafts.dispose();
  const cleanup = h.serial(() => clearStoredWorkDrafts(h.storage));
  gate.resolve();
  await cleanup;
  await h.flush();
  assert.equal(h.values.size, 0);
  const next = new PracticeWorkDrafts(2, h.storage, h.serial);
  await next.load(sid);
  assert.deepEqual(next.snapshot(sid).edits, []);
});
test('account isolation, corrupt storage, and the draft-session cap fail closed without eviction', async () => {
  const h = harness();
  await h.drafts.load(sid);
  h.drafts.edit(sid, artifact());
  await h.flush();
  const other = new PracticeWorkDrafts(2, h.storage, h.serial);
  await other.load(sid);
  assert.deepEqual(other.snapshot(sid).edits, []);
  h.values.set(`${workDraftIndex}.1.${sid}`, '{broken');
  const corrupt = new PracticeWorkDrafts(1, h.storage, h.serial);
  await corrupt.load(sid);
  assert.equal(corrupt.snapshot(sid).ready, false);
  assert.ok(corrupt.snapshot(sid).error);
  const capped = harness();
  const ids = Array.from(
    { length: 20 },
    (_, i) => `76f7750a-6a22-4594-b6c1-${String(i).padStart(12, '0')}`,
  );
  capped.values.set(workDraftIndex, JSON.stringify({ userId: 1, ids }));
  await capped.drafts.load(sid);
  capped.drafts.edit(sid, artifact());
  await capped.flush();
  assert.ok(capped.drafts.snapshot(sid).error);
  assert.deepEqual(JSON.parse(capped.values.get(workDraftIndex)).ids, ids);
});
test('a lost PUT response recovers the save receipt after restart without repeating the write', async () => {
  const h = harness();
  await h.drafts.load(sid);
  h.drafts.edit(sid, artifact());
  await h.flush();
  let writes = 0,
    readsAvailable = false;
  const api = {
    change: async () => {
      writes++;
      throw new Error('Lost response');
    },
    receipt: async () => {
      if (!readsAvailable) throw new Error('Offline');
      return { receipt: { operation: 'save', response: result() } };
    },
  };
  const op = await operationHarness(h, api);
  await op.operation.begin(change());
  assert.ok(op.journal());
  assert.equal(h.drafts.snapshot(sid).edits.length, 1);
  op.operation.dispose();
  h.drafts.dispose();
  const reopened = new PracticeWorkDrafts(1, h.storage, h.serial);
  readsAvailable = true;
  const restarted = new PracticeOperation(1, {
    ...op.deps,
    onConfirmed: (c) => reopened.clearIfMatches(c.sessionId, c),
  });
  await restarted.restore();
  assert.equal(writes, 1);
  assert.equal(restarted.snapshot().pending, null);
  assert.deepEqual(reopened.snapshot(sid).edits, []);
  assert.equal(op.journal(), null);
});
test('explicit PUT retries retain the exact note snapshot and request ID; missing receipts are uncertain', async () => {
  const h = harness();
  await h.drafts.load(sid);
  h.drafts.edit(sid, brief());
  await h.flush();
  const writes = [];
  const op = await operationHarness(h, {
    change: async (c) => {
      writes.push(c);
      throw new Error('Lost');
    },
  });
  const input = change(brief());
  await op.operation.begin(input);
  input.entries[0].text = 'mutated elsewhere';
  await op.operation.check();
  await op.operation.retry();
  assert.equal(writes.length, 2);
  assert.deepEqual(writes[1], writes[0]);
  assert.equal(writes[1].entries[0].text, note().text);
  assert.equal(writes[1].request_id, rid);
  assert.equal(op.operation.snapshot().phase, 'uncertain');
});
test('duplicate taps cannot create another save; mismatched target or receipt operation cannot confirm', async () => {
  const h = harness();
  await h.drafts.load(sid);
  h.drafts.edit(sid, artifact());
  await h.flush();
  const gate = deferred();
  let writes = 0;
  const op = await operationHarness(h, {
    change: async () => {
      writes++;
      await gate.promise;
      return result();
    },
  });
  const first = op.operation.begin(change());
  await tick();
  await op.operation.begin({ ...change(), request_id: aid });
  gate.resolve();
  await first;
  assert.equal(writes, 1);
  for (const receipt of [
    { operation: 'send', response: result() },
    { operation: 'save', response: { ...result(), session_id: otherSid } },
    {
      operation: 'save',
      response: {
        session_id: sid,
        artifacts: { schema: { revision: 3, changed: true } },
      },
    },
  ]) {
    const caseOp = await operationHarness(h, {
      change: async () => {
        throw new Error('Lost');
      },
      receipt: async () => ({ receipt }),
    });
    await caseOp.operation.begin(change());
    assert.ok(caseOp.operation.snapshot().pending);
  }
});
test('stale saves preserve the draft until refresh and an explicit new save', async () => {
  const h = harness();
  await h.drafts.load(sid);
  h.drafts.edit(sid, artifact());
  await h.flush();
  const error = Object.assign(new Error('Stale'), {
    status: 409,
    body: { code: 'stale_artifact' },
  });
  const op = await operationHarness(h, {
    change: async () => {
      throw error;
    },
  });
  await op.operation.begin(change());
  assert.equal(op.operation.snapshot().phase, 'rejected');
  await op.operation.retry();
  assert.equal(await op.operation.dismissRejected(), true);
  assert.ok(sameWork(h.drafts.snapshot(sid).edits[0], artifact()));
  assert.equal(op.journal(), null);
});
test('failed local cleanup retains the original request for receipt recovery, including sibling drafts', async () => {
  let fail = false,
    writes = 0;
  const h = harness({
    set: async (key, value) => {
      if (fail && key.endsWith(sid)) throw new Error('Locked');
      h.values.set(key, value);
    },
  });
  await h.drafts.load(sid);
  h.drafts.edit(sid, artifact());
  h.drafts.edit(sid, brief());
  await h.flush();
  const op = await operationHarness(h, {
    change: async () => {
      writes++;
      return result();
    },
    receipt: async () => ({
      receipt: { operation: 'save', response: result() },
    }),
  });
  fail = true;
  await op.operation.begin(change());
  assert.ok(op.journal());
  assert.equal(h.drafts.snapshot(sid).edits.length, 2);
  fail = false;
  await op.operation.check();
  assert.equal(writes, 1);
  assert.equal(op.journal(), null);
  assert.deepEqual(h.drafts.snapshot(sid).edits.map(workKey), ['brief']);
});
test('journal storage failure prevents any PUT; sign-out fences a late save result', async () => {
  const h = harness();
  await h.drafts.load(sid);
  h.drafts.edit(sid, artifact());
  await h.flush();
  const failed = await operationHarness(
    h,
    {},
    {
      write: async () => {
        throw new Error('Locked');
      },
    },
  );
  await failed.operation.begin(change());
  assert.equal(failed.calls(), 0);
  const gate = deferred();
  const op = await operationHarness(h, { change: () => gate.promise });
  const saving = op.operation.begin(change());
  await tick();
  op.operation.dispose();
  gate.resolve(result());
  await saving;
  assert.equal(h.drafts.snapshot(sid).edits.length, 1);
  const nextAccount = new PracticeOperation(2, op.deps);
  await nextAccount.restore();
  assert.equal(nextAccount.snapshot().pending, null);
});
