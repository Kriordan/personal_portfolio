import type { ModifierConfig } from '@expo/ui/jetpack-compose/modifiers';
import type { ViewStyle } from 'react-native';

export interface NativeWidthLayout {
  style: Pick<ViewStyle, 'width'>;
  modifiers?: ModifierConfig[];
}

// Web accepts percentages. Native Expo UI dimensions require native modifiers.
export const fillWidth: NativeWidthLayout = { style: { width: '100%' } };
