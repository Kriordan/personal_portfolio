import { onlineManager, type QueryClient } from '@tanstack/react-query';

import { libraryKeys, type LibraryPin, type LibrarySyncRun, type LibrarySyncReport } from './library-model.ts';

export const libraryRefreshOptions = {
  refetchOnMount: 'always',
  refetchOnWindowFocus: 'always',
  refetchOnReconnect: 'always',
} as const;

export type LibrarySyncState = {
  status: 'idle' | 'pending' | 'success' | 'error';
  message?: string;
  uncertain?: boolean;
  requestId?: string;
  run?: LibrarySyncRun;
  startedAt?: number;
};
export const idleSync: LibrarySyncState = { status: 'idle' };

export type PinAttempt = { pending: boolean; error?: string };
export const idlePin: PinAttempt = { pending: false };

/** Confirmed server state only. No offline queue, optimistic flicker, or replay. */
export async function changeLibraryPin(client: QueryClient, userId: number, save: () => Promise<{ pins: LibraryPin[] }>) {
  const key = libraryKeys.pinAttempt(userId);
  if (client.getQueryData<PinAttempt>(key)?.pending) return;
  if (!onlineManager.isOnline()) {
    client.setQueryData(key, { pending: false, error: 'Reconnect to change your pins. Nothing has been queued.' });
    return;
  }
  client.setQueryData(key, { pending: true });
  const attempt = client.getQueryData(key);
  const active = () => client.getQueryData(key) === attempt;
  await client.cancelQueries({ queryKey: libraryKeys.pins(userId) });
  if (!active()) return;
  try {
    const result = await save();
    if (!active()) return;
    await client.cancelQueries({ queryKey: libraryKeys.pins(userId) });
    if (!active()) return;
    client.setQueryData(libraryKeys.pins(userId), result);
    client.setQueryData(key, idlePin);
  } catch {
    if (active()) {
      client.setQueryData(key, { pending: false, error: 'Couldn’t confirm your pin change. Refresh to check its saved state.' });
      void client.invalidateQueries({ queryKey: libraryKeys.pins(userId) });
    }
  }
}

function syncFailure(error: unknown): LibrarySyncState {
  const status = error && typeof error === 'object' && 'status' in error ? error.status : undefined;
  if (status === 503) return { status: 'error', message: 'YouTube sync isn’t configured or its authorization has expired. Ask the library maintainer to reconnect it.' };
  if (status === 502) return { status: 'error', message: 'YouTube couldn’t complete the import. Your saved library is still available. Try syncing again later.' };
  if (status === 500) return { status: 'error', message: 'The import failed. Your saved library is still available. Try again later.' };
  if (status === 401 || status === 403) return { status: 'error', message: 'Sign in again before syncing the library.' };
  return { status: 'error', uncertain: true, message: 'Sync completion is unknown. The server may still be working. Refresh the saved catalog before deciding whether to sync again.' };
}

/** Synchronous cache lock survives navigation; cache clearing invalidates late results. */
export function startLibrarySync(client: QueryClient, sync: () => Promise<{ message?: string; run?: LibrarySyncRun }>, requestId?: string): Promise<void> {
  if (client.getQueryData<LibrarySyncState>(libraryKeys.sync)?.status === 'pending') return Promise.resolve();
  if (!onlineManager.isOnline()) {
    client.setQueryData<LibrarySyncState>(libraryKeys.sync, { status: 'error', message: 'You’re offline. Reconnect, then sync deliberately. Nothing has been queued.' });
    return Promise.resolve();
  }
  client.setQueryDefaults(libraryKeys.sync, { gcTime: Infinity });
  client.setQueryData<LibrarySyncState>(libraryKeys.sync, { status: 'pending', requestId, startedAt: Date.now() });
  const pending = client.getQueryData(libraryKeys.sync);
  const active = () => client.getQueryData(libraryKeys.sync) === pending;
  const mutation = client.getMutationCache().build(client, {
    mutationKey: ['library', 'import'], retry: false, networkMode: 'always',
    mutationFn: sync,
    onSuccess: async (result) => {
      if (!active()) return;
      await client.cancelQueries({ queryKey: libraryKeys.all });
      if (!active()) return;
      client.setQueryData<LibrarySyncState>(libraryKeys.sync, { status: 'success', requestId, run: result.run, message: 'Library sync completed.' });
      void client.invalidateQueries({ queryKey: libraryKeys.all, predicate: (query) => query.queryKey[1] !== 'sync' });
    },
    onError: (error) => {
      if (!active()) return;
      const failure = syncFailure(error);
      const busy = error && typeof error === 'object' && 'status' in error && error.status === 409;
      client.setQueryData(libraryKeys.sync, { ...failure, startedAt: (pending as LibrarySyncState).startedAt, requestId: busy ? undefined : requestId,
        ...(busy ? { uncertain: true, message: 'Another shared sync is running. Checking its status…' } : {}),
        ...(failure.uncertain && requestId ? { message: 'Waiting for server confirmation. We’ll keep checking; the import will not be sent again.' } : {}),
      });
      void client.invalidateQueries({ queryKey: ['library', 'sync-status'] });
    },
  });
  return mutation.execute(undefined).then(() => {}, () => {});
}

export function syncPollInterval(attempt: LibrarySyncState, report?: LibrarySyncReport, now = Date.now()): number {
  if (report?.busy) return 3_000;
  const run = attempt.requestId ? report?.requested : report?.latest;
  if (run && run.status !== 'running') return 30_000;
  return (attempt.status === 'pending' || attempt.uncertain) && now - (attempt.startedAt ?? now) < 120_000 ? 3_000 : 30_000;
}

/** Keep an old GET response from replacing a newer terminal POST receipt. */
export function currentSyncRun(attempt: LibrarySyncState, report?: LibrarySyncReport): LibrarySyncRun | null {
  if (report?.busy && report.latest?.status === 'running' && report.latest.id !== attempt.run?.id) return report.latest;
  const requested = attempt.requestId ? report?.requested : report?.latest;
  const ownRun = requested ?? attempt.run;
  // A later shared import supersedes this device's earlier receipt, including
  // completion while this screen was asleep or showing a playlist.
  if (ownRun && report?.latest && report.latest.started_at > ownRun.started_at) return report.latest;
  if (attempt.run && attempt.run.status !== 'running' && (!requested || requested.id === attempt.run.id)) return attempt.run;
  return requested ?? attempt.run ?? null;
}

/** Completion discovered by polling must refresh data just like a POST success. */
export async function observeSyncCompletion(client: QueryClient, run: LibrarySyncRun): Promise<void> {
  if (run.status !== 'succeeded' || client.getQueryData(libraryKeys.observedSync) === run.id) return;
  client.setQueryData(libraryKeys.observedSync, run.id);
  const active = () => client.getQueryData(libraryKeys.observedSync) === run.id;
  const catalog = (query: { queryKey: readonly unknown[] }) => ['playlists', 'playlist'].includes(String(query.queryKey[1]));
  await client.cancelQueries({ queryKey: libraryKeys.all, predicate: catalog });
  if (active()) void client.invalidateQueries({ queryKey: libraryKeys.all, predicate: catalog });
}
