import { intervalNative } from './interval-native';
import { createIntervalSession } from './interval-session';

export const intervalSession = intervalNative ? createIntervalSession(intervalNative) : null;
export async function clearIntervalSession() { await intervalSession?.stop(); }
