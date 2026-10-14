import assert from 'node:assert/strict';
import { test } from 'node:test';
import { QueryClient, onlineManager } from '@tanstack/react-query';
import { libraryKeys, mergeMoveReceipts, movePollInterval } from '../src/lib/library-model.ts';
import { observeLibraryMove, startLibraryMove } from '../src/lib/library-move-cache.ts';

const tick = () => new Promise((resolve) => setImmediate(resolve));
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const receipt = { id: 'move-1', source_entry_id: 'entry-1', source_playlist_id: 'added', destination_playlist_id: 'watched',
  video_url_id: 'same-video', video_title: 'Video', source_title: 'Added', destination_title: 'Watched', status: 'succeeded',
  stage: 'done', error: null, started_at: '2026-10-10T12:00:00Z', updated_at: '2026-10-10T12:00:10Z', can_retry_removal: false };

test('moves reject offline and never replay an uncertain POST on reconnect', async () => {
  const client = new QueryClient();
  let sends = 0;
  onlineManager.setOnline(false);
  await startLibraryMove(client, 1, 'request', async () => { sends++; return { move: receipt }; });
  assert.equal(sends, 0);
  onlineManager.setOnline(true);
  await startLibraryMove(client, 1, 'request', async () => { sends++; throw Error('timeout'); });
  onlineManager.setOnline(false);
  onlineManager.setOnline(true);
  await tick();
  assert.equal(sends, 1);
  assert.equal(client.getQueryData(libraryKeys.moveAttempt(1)).uncertain, true);
  client.clear();
});

test('a double tap sends one move and logout drops a late response', async () => {
  const client = new QueryClient();
  const response = deferred();
  let sends = 0;
  const send = () => { sends++; return response.promise; };
  const first = startLibraryMove(client, 1, 'first', send);
  await startLibraryMove(client, 1, 'second', send);
  assert.equal(sends, 1);
  client.clear();
  response.resolve({ move: receipt });
  await first;
  assert.equal(client.getQueryData(libraryKeys.moveAttempt(1)), undefined);
  assert.equal(client.getQueryData(libraryKeys.moveAttempt(2)), undefined);
  client.clear();
});

test('confirmation removes only the source entry and invalidates all shared occurrences', async () => {
  const client = new QueryClient();
  const source = { playlist: { id: 'added' }, videos: [{ id: 'entry-1', video_url_id: 'same-video' }, { id: 'entry-2', video_url_id: 'same-video' }] };
  client.setQueryData(libraryKeys.playlist('added'), source);
  client.setQueryData(libraryKeys.playlist('other'), source);
  await observeLibraryMove(client, 1, { ...receipt, status: 'partial' });
  assert.equal(client.getQueryData(libraryKeys.playlist('added')).videos.length, 2);
  await observeLibraryMove(client, 1, { ...receipt, updated_at: '2026-10-10T12:00:20Z' });
  assert.deepEqual(client.getQueryData(libraryKeys.playlist('added')).videos.map((video) => video.id), ['entry-2']);
  assert.equal(client.getQueryData(libraryKeys.playlist('other')).videos.length, 2);
  assert.equal(client.getQueryState(libraryKeys.playlist('other')).isInvalidated, true);
  client.clear();
});

test('stale polling cannot replace terminal POST, newer partial/removal results can', () => {
  const older = { ...receipt, status: 'running', updated_at: '2026-10-10T12:00:00Z' };
  assert.deepEqual(mergeMoveReceipts({ moves: [older], busy: false }, receipt), [receipt]);
  const newer = { ...receipt, updated_at: '2026-10-10T12:00:30Z' };
  assert.deepEqual(mergeMoveReceipts({ moves: [newer], busy: false }, receipt), [newer]);
});

test('unconfirmed polling backs off without allowing a retry', () => {
  const unknown = { ...receipt, status: 'unknown', updated_at: '2026-10-10T12:10:00Z' };
  assert.equal(movePollInterval([unknown], false, Date.parse('2026-10-10T12:00:20Z')), 3000);
  assert.equal(movePollInterval([unknown], false, Date.parse('2026-10-10T12:10:00Z')), 30000);
  assert.equal(unknown.can_retry_removal, false);
});
