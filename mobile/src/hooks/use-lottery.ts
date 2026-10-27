import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useFocusEffect } from 'expo-router';
import * as SecureStore from 'expo-secure-store';
import { useCallback, useEffect, useState } from 'react';
import { Platform } from 'react-native';
import { useAuth } from '@/lib/auth-context';
import { lotteryApi } from '@/lib/lottery-api';
import {
  lotteryDefaults,
  readLotteryPreferences,
  scratchQuery,
  type LotteryPreferences,
} from '@/lib/lottery-model';

let preferenceWrites = Promise.resolve();
export function useLotteryPreferences() {
  const { user, userError, retryUser } = useAuth();
  const client = useQueryClient();
  const userId = user?.id;
  const key = ['lottery', 'preferences', userId];
  const storageKey = `lottery.preferences.${userId}`;
  const query = useQuery({
    queryKey: key,
    enabled: !!userId,
    networkMode: 'always',
    staleTime: Infinity,
    retry: false,
    queryFn: async () =>
      readLotteryPreferences(
        Platform.OS === 'web'
          ? (globalThis.localStorage?.getItem(storageKey) ?? null)
          : await SecureStore.getItemAsync(storageKey),
      ),
  });
  const [saveError, setSaveError] = useState(false);
  const preferences = query.data ?? lotteryDefaults;
  return {
    preferences,
    accountError: !user && userError,
    retryAccount: retryUser,
    ready: !!userId && !query.isPending,
    saveError: saveError || query.isError,
    set: (change: Partial<LotteryPreferences>) => {
      if (!userId || query.isPending) return;
      const next = {
        ...(client.getQueryData<LotteryPreferences>(key) ?? lotteryDefaults),
        ...change,
      };
      client.setQueryData(key, next);
      preferenceWrites = preferenceWrites
        .catch(() => {})
        .then(async () => {
          if (Platform.OS === 'web')
            globalThis.localStorage?.setItem(storageKey, JSON.stringify(next));
          else await SecureStore.setItemAsync(storageKey, JSON.stringify(next));
        });
      void preferenceWrites.then(
        () => setSaveError(false),
        () => setSaveError(true),
      );
    },
  };
}
export function useScratchOffs(
  preferences: LotteryPreferences,
  ready: boolean,
  search = '',
) {
  const { user } = useAuth();
  const params = scratchQuery(preferences, search);
  return useQuery({
    queryKey: ['lottery', 'scratch', user?.id, params],
    queryFn: () => lotteryApi.scratch(params),
    enabled: ready,
    staleTime: 60000,
  });
}
export function useLotteryDraws(state: string, ready = true) {
  const { user } = useAuth();
  const query = useQuery({
    queryKey: ['lottery', 'draws', user?.id, state],
    queryFn: () => lotteryApi.draws(state),
    enabled: ready && !!user,
    staleTime: 30000,
    refetchInterval: 60000,
  });
  const { refetch } = query;
  useFocusEffect(
    useCallback(() => {
      if (ready && user) void refetch();
    }, [ready, user, refetch]),
  );
  return query;
}
// Re-evaluate age and draw cutoffs even if a phone stays on the same screen offline.
export function useLotteryClock() {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  return now;
}
