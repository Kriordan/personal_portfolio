import { focusManager, onlineManager } from '@tanstack/react-query';
import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import { apiRequest } from './api-client';
import { ExtractionSession } from './job-extraction-session';
import type { Extraction, ExtractionRequest } from './job-extraction-model';
const key = 'jobwizard.extraction.v1';
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
let current: { userId: number; session: ExtractionSession } | null = null;
export function extractionSession(userId: number) {
  if (current?.userId !== userId) {
    current?.session.dispose();
    current = {
      userId,
      session: new ExtractionSession(userId, {
        storage,
        uuid: Crypto.randomUUID,
        online: () => onlineManager.isOnline(),
        foreground: () => focusManager.isFocused(),
        api: {
          start: (request: ExtractionRequest) =>
            apiRequest<{ extraction: Extraction }>('/jobwizard/extractions', {
              method: 'POST',
              body: request,
              timeoutMs: 23_000,
            }),
          summarize: (id: string) =>
            apiRequest<{ extraction: Extraction }>(
              `/jobwizard/extractions/${encodeURIComponent(id)}/summary`,
              { method: 'POST', body: {}, timeoutMs: 15_000 },
            ),
          get: (id: string) =>
            apiRequest<{ extraction: Extraction }>(
              `/jobwizard/extractions/${encodeURIComponent(id)}`,
              { timeoutMs: 12_000 },
            ),
        },
      }),
    };
  }
  return current.session;
}
export async function clearExtractionSession() {
  current?.session.dispose();
  current = null;
  await storage.clear();
}
