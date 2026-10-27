import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import { createSessionTokens } from './session-tokens';

// expo-secure-store is unavailable on web; fall back to localStorage there.
// Web is a dev convenience target only, so the weaker storage is acceptable.
const isWeb = Platform.OS === 'web';

async function getItem(key: string): Promise<string | null> {
  if (isWeb) {
    return globalThis.localStorage?.getItem(key) ?? null;
  }
  return SecureStore.getItemAsync(key);
}

async function setItem(key: string, value: string): Promise<void> {
  if (isWeb) {
    globalThis.localStorage?.setItem(key, value);
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

async function deleteItem(key: string): Promise<void> {
  if (isWeb) {
    globalThis.localStorage?.removeItem(key);
    return;
  }
  await SecureStore.deleteItemAsync(key);
}

export interface StoredTokens {
  accessToken: string;
  refreshToken: string;
}

export const tokenStorage = createSessionTokens({
  get: getItem, set: setItem, remove: deleteItem,
});
