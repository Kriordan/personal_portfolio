import { Platform } from 'react-native';

/**
 * API base URL resolution, in order of precedence:
 * 1. EXPO_PUBLIC_API_URL (set in .env or shell; inlined at build time)
 * 2. Platform default for local development:
 *    - Android emulator cannot reach the host via 127.0.0.1, so use 10.0.2.2
 *    - iOS simulator and web can use 127.0.0.1 directly
 *
 * Physical devices must set EXPO_PUBLIC_API_URL to the host machine's LAN IP,
 * e.g. EXPO_PUBLIC_API_URL=http://192.168.1.20:5001
 */
const DEFAULT_DEV_API_URL = Platform.select({
  android: 'http://10.0.2.2:5001',
  default: 'http://127.0.0.1:5001',
});

export const API_BASE_URL: string = process.env.EXPO_PUBLIC_API_URL ?? DEFAULT_DEV_API_URL;

export const API_PREFIX = '/api/v1';
