import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useFocusEffect } from 'expo-router';
import { randomUUID } from 'expo-crypto';
import { useCallback, useEffect } from 'react';

import { useAuth } from '@/lib/auth-context';
import { libraryApi } from '@/lib/library-api';
import { currentSyncRun, idleSync, libraryRefreshOptions, observeSyncCompletion, startLibrarySync, syncPollInterval, type LibrarySyncState } from '@/lib/library-cache';
import { libraryKeys, validPlaylistId } from '@/lib/library-model';
import { changeLibraryPin, idlePin, type PinAttempt } from '@/lib/library-cache';

export function useLibraryPins() {
  const { user } = useAuth();
  const client = useQueryClient();
  const userId = user?.id ?? 0;
  const query = useQuery({ ...libraryRefreshOptions, queryKey: libraryKeys.pins(userId), queryFn: libraryApi.getPins, enabled: !!user });
  const { data: attempt = idlePin } = useQuery<PinAttempt>({ queryKey: libraryKeys.pinAttempt(userId), queryFn: () => idlePin, enabled: false, gcTime: Infinity });
  const { refetch } = query;
  useFocusEffect(useCallback(() => { if (userId) void refetch(); }, [userId, refetch]));
  return { query, pins: query.data?.pins ?? [], pending: attempt.pending, error: attempt.error,
    ready: !!user && !!query.data,
    set: useCallback((id: string, pinned: boolean) => { if (userId) void changeLibraryPin(client, userId, () => libraryApi.setPin(id, pinned)); }, [client, userId]),
  };
}

export function useLibrary() {
  const { isAuthenticated } = useAuth();
  const query = useQuery({ ...libraryRefreshOptions, queryKey: libraryKeys.playlists(), queryFn: libraryApi.getPlaylists, enabled: isAuthenticated === true });
  const { refetch } = query;
  useFocusEffect(useCallback(() => { if (isAuthenticated) void refetch(); }, [isAuthenticated, refetch]));
  return query;
}

export function usePlaylist(id: string) {
  const { isAuthenticated } = useAuth();
  const enabled = isAuthenticated === true && validPlaylistId(id);
  const query = useQuery({ ...libraryRefreshOptions, queryKey: libraryKeys.playlist(id), queryFn: () => libraryApi.getPlaylist(id), enabled });
  const { refetch } = query;
  useFocusEffect(useCallback(() => { if (enabled) void refetch(); }, [enabled, refetch]));
  return query;
}

export function useLibrarySync() {
  const client = useQueryClient();
  const { isAuthenticated } = useAuth();
  const { data = idleSync } = useQuery<LibrarySyncState>({ queryKey: libraryKeys.sync, queryFn: () => idleSync, enabled: false, gcTime: Infinity, staleTime: Infinity });
  const statusQuery = useQuery({
    ...libraryRefreshOptions, queryKey: libraryKeys.syncStatus(data.requestId),
    queryFn: () => libraryApi.syncStatus(data.requestId), enabled: isAuthenticated === true,
    refetchInterval: (query) => syncPollInterval(data, query.state.data),
    refetchIntervalInBackground: false, retry: false,
  });
  const run = currentSyncRun(data, statusQuery.data);
  const { refetch } = statusQuery;
  useFocusEffect(useCallback(() => { if (isAuthenticated) void refetch(); }, [isAuthenticated, refetch]));
  useEffect(() => { if (isAuthenticated && run) void observeSyncCompletion(client, run); }, [client, isAuthenticated, run]);
  const pending = run?.status === 'running' || !!statusQuery.data?.busy || (data.status === 'pending' && !run);
  const start = () => {
    if (!isAuthenticated || pending) return;
    const id = randomUUID();
    void startLibrarySync(client, () => libraryApi.sync(id), id);
  };
  return { ...data, run, pending, start, statusQuery, lastSuccess: statusQuery.data?.last_success ?? (run?.status === 'succeeded' ? run : null) };
}
