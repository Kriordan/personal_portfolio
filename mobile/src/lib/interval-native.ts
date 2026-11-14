import type { IntervalAudioPort } from './interval-session';

// Android and web must never try loading the iOS module.
export const intervalNative: IntervalAudioPort | null = null;
