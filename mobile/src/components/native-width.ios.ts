import { frame } from '@expo/ui/swift-ui/modifiers';
import type { NativeWidthLayout } from './native-width';

export const fillWidth: NativeWidthLayout = {
  style: {},
  modifiers: [frame({ maxWidth: Infinity })],
};
