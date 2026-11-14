import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useSyncExternalStore } from 'react';
import { intervalNative } from '@/lib/interval-native';
import { intervalSession } from '@/lib/interval-runtime';
import { createIntervalStore } from '@/lib/interval-store';
import type { IntervalLibrary } from '@/lib/interval-model';

const store = intervalNative ? createIntervalStore(intervalNative) : null;
const key = ['intervals', 'device-library'] as const;
const noop = () => () => {};
const empty = () => null;

export function useIntervalSession() {
  return useSyncExternalStore(intervalSession?.subscribe ?? noop, intervalSession?.getSnapshot ?? empty, empty);
}

export function useIntervalLibrary() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: key,
    enabled: store !== null,
    networkMode: 'always',
    staleTime: Infinity,
    retry: false,
    queryFn: () => store!.read(),
  });
  return { ...query, change: async (edit: (current: IntervalLibrary) => IntervalLibrary) => {
    if (!store) throw new Error('Intervals requires the new iPhone build.');
    const library = await store.change(edit);
    client.setQueryData(key, library);
    return library;
  } };
}
