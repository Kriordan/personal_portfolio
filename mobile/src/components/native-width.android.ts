import { fillMaxWidth } from '@expo/ui/jetpack-compose/modifiers';
import type { NativeWidthLayout } from './native-width';

export const fillWidth: NativeWidthLayout = {
  style: {},
  modifiers: [fillMaxWidth()],
};
