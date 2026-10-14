import { useQuery, useQueryClient } from '@tanstack/react-query';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

import { playlistSorts, videoSorts, type LibrarySort } from '@/lib/library-model';

let writes = Promise.resolve();

/** Tiny device preferences reuse the installed storage module; no account data. */
export function useLibrarySort(kind: 'playlists' | 'videos') {
  const options = kind === 'playlists' ? playlistSorts : videoSorts;
  const fallback: LibrarySort = kind === 'playlists' ? 'updated' : 'newest';
  const key = `library-sort-v1-${kind}`;
  const queryKey = ['preferences', key] as const;
  const client = useQueryClient();
  const query = useQuery({ queryKey, staleTime: Infinity, queryFn: async (): Promise<LibrarySort> => {
    try {
      const saved = Platform.OS === 'web' ? localStorage.getItem(key) : await SecureStore.getItemAsync(key);
      return options.some((option) => option.value === saved) ? saved as LibrarySort : fallback;
    } catch { return fallback; }
  } });
  const select = (value: LibrarySort) => {
    if (!options.some((option) => option.value === value)) return;
    client.setQueryData(queryKey, value);
    writes = writes.then(async () => {
      if (Platform.OS === 'web') localStorage.setItem(key, value);
      else await SecureStore.setItemAsync(key, value);
    }).catch(() => {});
  };
  return { value: query.data ?? fallback, options, select, ready: !query.isPending };
}
