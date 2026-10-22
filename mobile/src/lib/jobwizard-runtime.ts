import { onlineManager } from '@tanstack/react-query';
import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import { AccessibilityInfo, Platform } from 'react-native';
import { jobwizardApi } from './jobwizard-api';
import { reconcileJob } from './jobwizard-cache';
import { JobSession } from './jobwizard-session';
import { queryClient } from './query-client';
import { clearExtractionSession } from './job-extraction-runtime';

const key = 'jobwizard.pending.v1';
let tail: Promise<unknown> = Promise.resolve();
function serial<T>(fn: () => Promise<T>) {
  const next = tail.then(fn, fn);
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
let current: { userId: number; session: JobSession } | null = null;
export function jobSession(userId: number) {
  if (current?.userId !== userId) {
    current?.session.dispose();
    current = {
      userId,
      session: new JobSession(userId, {
        storage,
        api: jobwizardApi,
        online: () => onlineManager.isOnline(),
        uuid: Crypto.randomUUID,
        onConfirmed: (result, active) => {
          if (!active()) return;
          AccessibilityInfo.announceForAccessibility(
            'job' in result
              ? 'Job saved.'
              : result.capture.requested?.status === 'succeeded'
                ? 'Screenshot captured.'
                : 'Screenshot capture ended. Check its status.',
          );
          void reconcileJob(
            queryClient,
            userId,
            'job' in result ? result : null,
            active,
          );
        },
      }),
    };
  }
  return current.session;
}
export async function clearJobSession() {
  current?.session.dispose();
  current = null;
  await Promise.all([storage.clear(), clearExtractionSession()]);
}
