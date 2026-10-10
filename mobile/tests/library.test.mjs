import assert from 'node:assert/strict';
import { test } from 'node:test';
import { QueryClient, QueryObserver, focusManager, onlineManager } from '@tanstack/react-query';
import { browseLibrary, libraryKeys, openLibraryVideo, validPlaylistId, videoWatchUrl } from '../src/lib/library-model.ts';
import { libraryRefreshOptions, startLibrarySync } from '../src/lib/library-cache.ts';
import { RequestTimeoutError, withRequestTimeout } from '../src/lib/request-timeout.ts';

const tick = () => new Promise((resolve) => setImmediate(resolve));
const data = { playlists: [{ id: 'pl-1', title: 'Music', description: 'Quiet piano' }] };
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };

test('local search preserves server order and covers descriptions, whitespace and empty results', () => {
  const items = [...data.playlists, { id: 'pl-2', title: 'PIANO lessons', description: null }];
  assert.deepEqual(browseLibrary(items, ' piano '), items);
  assert.equal(browseLibrary(items, 'music')[0].id, 'pl-1');
  assert.deepEqual(browseLibrary(items, 'missing'), []);
  assert.deepEqual(browseLibrary(items, '   '), items);
  assert.deepEqual(items.map((item) => item.id), ['pl-1', 'pl-2']);
});

test('route IDs and external URLs cannot inject a destination or query argument', async () => {
  for (const id of [undefined, [], '', ' ', '../secret', 'pl/1', 'x?other']) assert.equal(validPlaylistId(id), false);
  assert.equal(validPlaylistId('PL_a-123'), true);
  assert.equal(videoWatchUrl(' '), null);
  assert.equal(videoWatchUrl('a&list=b'), 'https://www.youtube.com/watch?v=a%26list%3Db');
  let opened;
  assert.equal(await openLibraryVideo('abc', async (url) => { opened = url; }), true);
  assert.equal(opened, 'https://www.youtube.com/watch?v=abc');
  assert.equal(await openLibraryVideo('', () => { throw Error('must not call'); }), false);
  assert.equal(await openLibraryVideo('abc', async () => { throw Error('no browser'); }), false);
});

for (const recovery of ['foreground', 'reconnect', 'remount']) test(`Library ${recovery} recovers data within freshness window`, async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000 } } });
  client.mount();
  let reads = 0;
  const observer = new QueryObserver(client, { ...libraryRefreshOptions, queryKey: libraryKeys.playlists(), queryFn: async () => ({ version: ++reads }) });
  let unsubscribe = observer.subscribe(() => {});
  try {
    await tick();
    assert.equal(reads, 1);
    if (recovery === 'foreground') { focusManager.setFocused(false); focusManager.setFocused(true); }
    else if (recovery === 'reconnect') { onlineManager.setOnline(false); onlineManager.setOnline(true); }
    else { unsubscribe(); unsubscribe = observer.subscribe(() => {}); }
    await tick();
    assert.equal(reads, 2);
  } finally { unsubscribe(); client.unmount(); client.clear(); focusManager.setFocused(undefined); onlineManager.setOnline(true); }
});

test('refresh failure retains cached content and logout cancels late reads', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(libraryKeys.playlists(), data);
  await assert.rejects(client.fetchQuery({ queryKey: libraryKeys.playlists(), queryFn: async () => { throw Error('offline'); } }));
  assert.deepEqual(client.getQueryData(libraryKeys.playlists()), data);
  const read = deferred();
  const pending = client.fetchQuery({ queryKey: libraryKeys.playlists(), queryFn: () => read.promise }).catch(() => {});
  client.clear(); read.resolve(data); await pending;
  assert.equal(client.getQueryData(libraryKeys.playlists()), undefined);
});

test('sync locks synchronously across observers, retains cached data, and invalidates after success', async () => {
  const client = new QueryClient();
  client.setQueryData(libraryKeys.playlists(), data);
  client.setQueryData(libraryKeys.playlist('pl-1'), { videos: [] });
  const work = deferred(); let calls = 0;
  const sync = () => { calls++; return work.promise; };
  const first = startLibrarySync(client, sync);
  const second = startLibrarySync(client, sync);
  assert.equal(client.getQueryData(libraryKeys.sync).status, 'pending');
  await tick(); assert.equal(calls, 1);
  work.resolve({ message: 'complete' }); await Promise.all([first, second]);
  assert.deepEqual(client.getQueryData(libraryKeys.playlists()), data);
  assert.equal(client.getQueryState(libraryKeys.playlists()).isInvalidated, true);
  assert.equal(client.getQueryState(libraryKeys.playlist('pl-1')).isInvalidated, true);
  assert.equal(client.getQueryData(libraryKeys.sync).status, 'success');
  client.clear();
});

test('offline sync never queues and uncertain outcomes never replay on recovery', async () => {
  const client = new QueryClient(); client.mount();
  let calls = 0;
  const sync = async () => { calls++; throw new RequestTimeoutError(); };
  try {
    onlineManager.setOnline(false);
    await startLibrarySync(client, sync);
    assert.equal(calls, 0);
    assert.match(client.getQueryData(libraryKeys.sync).message, /offline/);
    onlineManager.setOnline(true); await tick(); assert.equal(calls, 0);
    await startLibrarySync(client, sync);
    assert.equal(client.getQueryData(libraryKeys.sync).uncertain, true);
    onlineManager.setOnline(false); onlineManager.setOnline(true);
    focusManager.setFocused(false); focusManager.setFocused(true);
    await tick(); assert.equal(calls, 1);
  } finally { client.unmount(); client.clear(); onlineManager.setOnline(true); focusManager.setFocused(undefined); }
});

test('logout then another sync cannot be overwritten by an old completion', async () => {
  const client = new QueryClient();
  const work = deferred();
  const pending = startLibrarySync(client, () => work.promise);
  await tick(); client.clear();
  await startLibrarySync(client, async () => { throw Object.assign(Error('secret'), { status: 503 }); });
  const state = client.getQueryData(libraryKeys.sync);
  work.resolve({ message: 'old success' }); await pending;
  assert.equal(client.getQueryData(libraryKeys.sync), state);
  assert.equal(state.status, 'error');
  assert.doesNotMatch(state.message, /secret/);
  client.clear();
});

test('successful sync cancels stale in-flight reads; subsequent refresh errors remain distinct', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(libraryKeys.playlists(), data);
  const old = deferred(); let reads = 0;
  const observer = new QueryObserver(client, { queryKey: libraryKeys.playlists(), queryFn: () => { if (++reads === 1) return old.promise; throw Error('read failed'); } });
  const unsubscribe = observer.subscribe(() => {});
  await tick();
  await startLibrarySync(client, async () => ({ message: 'complete' }));
  old.resolve({ playlists: [] }); await tick();
  assert.equal(client.getQueryData(libraryKeys.sync).status, 'success');
  assert.equal(observer.getCurrentResult().isError, true);
  assert.deepEqual(observer.getCurrentResult().data, data);
  unsubscribe(); client.clear();
});

test('request deadline bounds an unresponsive transport and aborts; ordinary calls are unchanged', async (context) => {
  context.mock.timers.enable({ apis: ['setTimeout'] });
  let signal;
  const pending = withRequestTimeout((value) => { signal = value; return new Promise(() => {}); }, 30_000);
  const rejected = assert.rejects(pending, RequestTimeoutError);
  context.mock.timers.tick(30_000); await rejected;
  assert.equal(signal.aborted, true);
  assert.equal(await withRequestTimeout(async (value) => { assert.equal(value, undefined); return 42; }), 42);
  context.mock.timers.reset();
});

test('API timeout during token refresh prevents a late sync POST; normal 401 refresh still works', async (context) => {
  const { readFileSync } = await import('node:fs');
  const ts = (await import('typescript')).default;
  const source = readFileSync(new URL('../src/lib/api-client.ts', import.meta.url), 'utf8')
    .replace("import { API_BASE_URL, API_PREFIX } from '@/lib/config';", "const API_BASE_URL = 'https://fixture.test'; const API_PREFIX = '/api/v1';")
    .replace("import { tokenStorage } from '@/lib/token-storage';", "const tokenStorage = { getAccessToken: async () => 'access', getRefreshToken: async () => 'refresh', setTokens: async () => {} };")
    .replace("'@/lib/request-timeout'", JSON.stringify(new URL('../src/lib/request-timeout.ts', import.meta.url).href));
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
  const { apiRequest } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
  const refresh = deferred(); let posts = 0;
  context.mock.method(globalThis, 'fetch', async (url) => {
    if (url.endsWith('/auth/refresh')) return refresh.promise;
    posts++;
    return new Response('{}', { status: 401 });
  });
  context.mock.timers.enable({ apis: ['setTimeout'] });
  const pending = apiRequest('/library/sync', { method: 'POST', timeoutMs: 30_000 });
  const rejected = assert.rejects(pending, RequestTimeoutError);
  await tick();
  context.mock.timers.tick(30_000); await rejected;
  refresh.resolve(new Response('{"access_token":"renewed"}', { status: 200 }));
  await tick(); assert.equal(posts, 1);
  context.mock.timers.reset(); context.mock.restoreAll();
  let requests = 0;
  context.mock.method(globalThis, 'fetch', async (url) => {
    requests++;
    if (url.endsWith('/auth/refresh')) return new Response('{"access_token":"new"}');
    return requests === 1 ? new Response('{}', { status: 401 }) : new Response('{"message":"complete"}');
  });
  assert.deepEqual(await apiRequest('/library/sync', { method: 'POST', timeoutMs: 30_000 }), { message: 'complete' });
  assert.equal(requests, 3);
});

test('sorting is numeric, deterministic, null-safe and never mutates shared query data', async () => {
  const { sortLibrary } = await import('../src/lib/library-model.ts');
  const rows = [
    { id: 'b', title: 'Lesson 10', published_at: '2026-01-02', updated_at: '2026-02-01', position: 0 },
    { id: 'a', title: 'lesson 2', published_at: '2026-01-01', updated_at: '2026-03-01', position: 1 },
    { id: 'c', title: 'lesson 2', published_at: null, updated_at: 'invalid', position: null },
  ];
  const ids = (sort) => sortLibrary(rows, sort).map((row) => row.id);
  assert.deepEqual(ids('title'), ['a', 'c', 'b']);
  assert.deepEqual(ids('title-desc'), ['b', 'a', 'c']);
  assert.deepEqual(ids('updated'), ['a', 'b', 'c']);
  assert.deepEqual(ids('newest'), ['b', 'a', 'c']);
  assert.deepEqual(ids('oldest'), ['a', 'b', 'c']);
  assert.deepEqual(ids('position'), ['b', 'a', 'c']);
  assert.deepEqual(rows.map((row) => row.id), ['b', 'a', 'c']);
  assert.deepEqual(sortLibrary(browseLibrary(rows, 'lesson 2'), 'oldest').map((row) => row.id), ['a', 'c']);
});

test('a timed-out POST is resolved by its server receipt and automatically invalidates stale catalog reads', async () => {
  const { currentSyncRun, observeSyncCompletion, syncPollInterval } = await import('../src/lib/library-cache.ts');
  const client = new QueryClient();
  client.setQueryData(libraryKeys.playlists(), data);
  const id = 'sync-request';
  await startLibrarySync(client, async () => { throw new RequestTimeoutError(); }, id);
  const attempt = client.getQueryData(libraryKeys.sync);
  assert.equal(attempt.requestId, id);
  const old = { id: 'older', status: 'succeeded' };
  const absent = { latest: old, last_success: old, requested: null, busy: false };
  assert.equal(currentSyncRun(attempt, absent), null, 'an older success must not confirm a new request');
  const run = { id, status: 'succeeded' };
  const report = { ...absent, latest: run, requested: run };
  assert.equal(currentSyncRun(attempt, report), run);
  assert.equal(syncPollInterval(attempt, report), 30_000);
  const stale = deferred();
  const pending = client.fetchQuery({ queryKey: libraryKeys.playlists(), queryFn: () => stale.promise }).catch(() => {});
  await observeSyncCompletion(client, run);
  stale.resolve({ playlists: ['stale'] }); await pending;
  assert.deepEqual(client.getQueryData(libraryKeys.playlists()), data);
  assert.equal(client.getQueryState(libraryKeys.playlists()).isInvalidated, true);
  client.clear();
});

test('late running reports cannot overwrite a completed POST and active imports on other devices remain visible', async () => {
  const { currentSyncRun, syncPollInterval } = await import('../src/lib/library-cache.ts');
  const done = { id: 'mine', status: 'succeeded', started_at: '2026-10-10T12:00:00+00:00' };
  const attempt = { status: 'success', requestId: 'mine', run: done };
  const running = { id: 'mine', status: 'running' };
  assert.equal(currentSyncRun(attempt, { latest: running, requested: running, last_success: null, busy: true }), done);
  const other = { id: 'other', status: 'running', started_at: '2026-10-10T13:00:00+00:00' };
  assert.equal(currentSyncRun(attempt, { latest: other, requested: done, last_success: done, busy: true }), other);
  const later = { ...other, status: 'succeeded' };
  assert.equal(currentSyncRun(attempt, { latest: later, requested: done, last_success: later, busy: false }), later, 'a later shared completion supersedes the earlier local receipt');
  assert.equal(syncPollInterval({ status: 'error', uncertain: true, startedAt: 0 }, undefined, 121_000), 30_000);
});
