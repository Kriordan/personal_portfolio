import { onlineManager } from '@tanstack/react-query';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import { apiRequest } from './api-client';
import { createPracticeClient } from './practice-client';
import {
  clearStoredDrafts,
  PracticeDrafts,
  type DraftStorage,
} from './practice-drafts';
import { practiceKeys } from './practice-model';
import { PracticeOperation } from './practice-operation';
import { queryClient } from './query-client';

export const practiceApi = createPracticeClient(apiRequest);
const key = 'learning.practice.pending.v1';
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
      else
        await SecureStore.setItemAsync(key, value, {
          keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
        });
    }),
  clear: () =>
    serial(async () => {
      if (Platform.OS === 'web') globalThis.localStorage?.removeItem(key);
      else await SecureStore.deleteItemAsync(key);
    }),
};
const draftStorage: DraftStorage = {
  get: async (k) =>
    Platform.OS === 'web'
      ? (globalThis.localStorage?.getItem(k) ?? null)
      : SecureStore.getItemAsync(k),
  set: async (k, value) => {
    if (Platform.OS === 'web') globalThis.localStorage.setItem(k, value);
    else
      await SecureStore.setItemAsync(k, value, {
        keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
      });
  },
  remove: async (k) => {
    if (Platform.OS === 'web') globalThis.localStorage?.removeItem(k);
    else await SecureStore.deleteItemAsync(k);
  },
};
let current: {
  userId: number;
  operation: PracticeOperation;
  drafts: PracticeDrafts;
} | null = null;
export function practiceOperation(userId: number) {
  if (current?.userId !== userId) {
    current?.operation.dispose();
    current?.drafts.dispose();
    const drafts = new PracticeDrafts(userId, draftStorage, serial);
    current = {
      userId,
      drafts,
      operation: new PracticeOperation(userId, {
        storage,
        api: practiceApi,
        online: () => onlineManager.isOnline(),
        onConfirmed: async (change, _result, active) => {
          if (active() && change.kind === 'send')
            await drafts.clearIfMatches(change.sessionId, change.body);
          if (!active()) return;
          await queryClient.cancelQueries({ queryKey: practiceKeys.all });
          if (active())
            void queryClient.invalidateQueries({ queryKey: practiceKeys.all });
        },
      }),
    };
  }
  return current.operation;
}
export function practiceDrafts(userId: number) {
  practiceOperation(userId);
  return current!.drafts;
}
export async function clearPracticeSession() {
  current?.operation.dispose();
  current?.drafts.dispose();
  current = null;
  await Promise.all([
    storage.clear(),
    serial(() => clearStoredDrafts(draftStorage)),
  ]);
}
