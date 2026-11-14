import { requireOptionalNativeModule } from 'expo';
import type { IntervalAudioPort } from './interval-session';

// An older installed development binary can still open the rest of the app.
export const intervalNative = requireOptionalNativeModule<IntervalAudioPort>('IntervalTimer');
