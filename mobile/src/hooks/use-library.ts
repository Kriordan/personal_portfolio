import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useFocusEffect } from 'expo-router';
import { useCallback } from 'react';

import { useAuth } from '@/lib/auth-context';
import { libraryApi } from '@/lib/library-api';
import { idleSync, libraryRefreshOptions, startLibrarySync, type LibrarySyncState } from '@/lib/library-cache';
import { libraryKeys, validPlaylistId } from '@/lib/library-model';

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
  const start = () => { if (isAuthenticated) void startLibrarySync(client, libraryApi.sync); };
  return { ...data, start };
}
