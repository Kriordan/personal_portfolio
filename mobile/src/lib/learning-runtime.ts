import { onlineManager } from '@tanstack/react-query';
import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import { AccessibilityInfo, Platform } from 'react-native';

import { learningApi } from './learning-api';
import { reconcileLearningRating } from './learning-cache';
import { LearningSession, type AttemptStorage } from './learning-session';
import { queryClient } from './query-client';

const key = 'learning.pending.v1';
let storageTail: Promise<unknown> = Promise.resolve();
function serial<T>(action: () => Promise<T>): Promise<T> {
  const next = storageTail.then(action, action);
  storageTail = next.catch(() => {});
  return next;
}
const storage: AttemptStorage = {
  read: () =>
    serial(async () =>
      Platform.OS === 'web'
        ? (globalThis.localStorage?.getItem(key) ?? null)
        : SecureStore.getItemAsync(key),
    ),
  write: (value) =>
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
let current: { userId: number; session: LearningSession } | null = null;
export function learningSession(userId: number) {
  if (current?.userId !== userId) {
    current?.session.dispose();
    current = {
      userId,
      session: new LearningSession(userId, {
        storage,
        api: learningApi,
        online: () => onlineManager.isOnline(),
        uuid: Crypto.randomUUID,
        onConfirmed: (active) => {
          if (active())
            AccessibilityInfo.announceForAccessibility(
              'Rating saved. Your review progress has been updated.',
            );
          void reconcileLearningRating(queryClient, active);
        },
      }),
    };
  }
  return current.session;
}
export async function clearLearningSession() {
  current?.session.dispose();
  current = null;
  await storage.clear();
}
