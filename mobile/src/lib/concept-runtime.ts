import { onlineManager } from '@tanstack/react-query';
import * as SecureStore from 'expo-secure-store';
import { AccessibilityInfo, Platform } from 'react-native';
import { conceptApi } from './concept-api';
import { conceptKeys } from './concept-model';
import { ConceptStudy } from './concept-study';
import { queryClient } from './query-client';

const key = 'learning.study.pending.v1';
let tail: Promise<unknown> = Promise.resolve();
function serial<T>(run: () => Promise<T>): Promise<T> {
  const next = tail.then(run, run);
  tail = next.catch(() => {});
  return next;
}
const storage = {
  read: () =>
    serial(async () =>
      Platform.OS === 'web'
        ? (globalThis.localStorage?.getItem(key) ?? null)
        : SecureStore.getItemAsync(key),
    ),
  write: (value: string) =>
    serial(async () => {
      if (Platform.OS === 'web') globalThis.localStorage.setItem(key, value);
      else await SecureStore.setItemAsync(key, value);
    }),
  clear: () =>
    serial(async () => {
      if (Platform.OS === 'web') globalThis.localStorage?.removeItem(key);
      else await SecureStore.deleteItemAsync(key);
    }),
};
let current: { userId: number; study: ConceptStudy } | null = null;
export function conceptStudy(userId: number) {
  if (current?.userId !== userId) {
    current?.study.dispose();
    current = {
      userId,
      study: new ConceptStudy(userId, {
        storage,
        api: conceptApi,
        online: () => onlineManager.isOnline(),
        onConfirmed: (_id, _progress, active) => {
          if (!active()) return;
          AccessibilityInfo.announceForAccessibility(
            'Learning progress saved.',
          );
          void queryClient
            .cancelQueries({ queryKey: conceptKeys.all })
            .then(() => {
              if (active())
                void queryClient.invalidateQueries({
                  queryKey: conceptKeys.all,
                });
            });
        },
      }),
    };
  }
  return current.study;
}
export async function clearConceptStudy() {
  current?.study.dispose();
  current = null;
  await storage.clear();
}
