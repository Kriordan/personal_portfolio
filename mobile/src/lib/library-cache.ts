import { onlineManager, type QueryClient } from '@tanstack/react-query';

import { libraryKeys } from './library-model.ts';

export const libraryRefreshOptions = {
  refetchOnMount: 'always',
  refetchOnWindowFocus: 'always',
  refetchOnReconnect: 'always',
} as const;

export type LibrarySyncState = {
  status: 'idle' | 'pending' | 'success' | 'error';
  message?: string;
  uncertain?: boolean;
};
export const idleSync: LibrarySyncState = { status: 'idle' };

function syncFailure(error: unknown): LibrarySyncState {
  const status = error && typeof error === 'object' && 'status' in error ? error.status : undefined;
  if (status === 503) return { status: 'error', message: 'YouTube sync isn’t configured or its authorization has expired. Ask the library maintainer to reconnect it.' };
  if (status === 502) return { status: 'error', message: 'YouTube couldn’t complete the import. Your saved library is still available. Try syncing again later.' };
  if (status === 500) return { status: 'error', message: 'The import failed. Your saved library is still available. Try again later.' };
  if (status === 401 || status === 403) return { status: 'error', message: 'Sign in again before syncing the library.' };
  return { status: 'error', uncertain: true, message: 'Sync completion is unknown. The server may still be working. Refresh the saved catalog before deciding whether to sync again.' };
}

/** Synchronous cache lock survives navigation; cache clearing invalidates late results. */
export function startLibrarySync(client: QueryClient, sync: () => Promise<{ message: string }>): Promise<void> {
  if (client.getQueryData<LibrarySyncState>(libraryKeys.sync)?.status === 'pending') return Promise.resolve();
  if (!onlineManager.isOnline()) {
    client.setQueryData<LibrarySyncState>(libraryKeys.sync, { status: 'error', message: 'You’re offline. Reconnect, then sync deliberately. Nothing has been queued.' });
    return Promise.resolve();
  }
  client.setQueryDefaults(libraryKeys.sync, { gcTime: Infinity });
  client.setQueryData<LibrarySyncState>(libraryKeys.sync, { status: 'pending' });
  const pending = client.getQueryData(libraryKeys.sync);
  const active = () => client.getQueryData(libraryKeys.sync) === pending;
  const mutation = client.getMutationCache().build(client, {
    mutationKey: ['library', 'import'], retry: false, networkMode: 'always',
    mutationFn: sync,
    onSuccess: async () => {
      if (!active()) return;
      await client.cancelQueries({ queryKey: libraryKeys.all });
      if (!active()) return;
      client.setQueryData<LibrarySyncState>(libraryKeys.sync, { status: 'success', message: 'Library sync completed.' });
      void client.invalidateQueries({ queryKey: libraryKeys.all, predicate: (query) => query.queryKey[1] !== 'sync' });
    },
    onError: (error) => { if (active()) client.setQueryData(libraryKeys.sync, syncFailure(error)); },
  });
  return mutation.execute(undefined).then(() => {}, () => {});
}
