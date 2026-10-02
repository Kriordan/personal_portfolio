/** Shared semantic colors; native controls retain their platform appearance. */

import '@/global.css';

import { Platform } from 'react-native';

export const Colors = {
  light: {
    text: '#18232B',
    background: '#F3F5F7',
    backgroundElement: '#FFFFFF',
    backgroundSelected: '#E6EDF5',
    textSecondary: '#586672',
    accent: '#245FC4',
    accentSoft: '#E6EEFC',
    border: '#DEE4EA',
    danger: '#B42332',
    success: '#247047',
  },
  dark: {
    text: '#F2F5F8',
    background: '#101418',
    backgroundElement: '#1C232A',
    backgroundSelected: '#2B3743',
    textSecondary: '#ACB8C4',
    accent: '#9ABFFF',
    accentSoft: '#24364F',
    border: '#33404B',
    danger: '#FFA3AA',
    success: '#8DD7AD',
  },
} as const;

export type ThemeColor = keyof typeof Colors.light & keyof typeof Colors.dark;

export const Fonts = Platform.select({
  ios: {
    /** iOS `UIFontDescriptorSystemDesignDefault` */
    sans: 'system-ui',
    /** iOS `UIFontDescriptorSystemDesignSerif` */
    serif: 'ui-serif',
    /** iOS `UIFontDescriptorSystemDesignRounded` */
    rounded: 'ui-rounded',
    /** iOS `UIFontDescriptorSystemDesignMonospaced` */
    mono: 'ui-monospace',
  },
  default: {
    sans: 'normal',
    serif: 'serif',
    rounded: 'normal',
    mono: 'monospace',
  },
  web: {
    sans: 'var(--font-display)',
    serif: 'var(--font-serif)',
    rounded: 'var(--font-rounded)',
    mono: 'var(--font-mono)',
  },
});

export const Spacing = {
  half: 2,
  one: 4,
  two: 8,
  three: 16,
  four: 24,
  five: 32,
  six: 64,
} as const;

export const BottomTabInset = Platform.select({ ios: 50, android: 80 }) ?? 0;
export const MaxContentWidth = 800;
