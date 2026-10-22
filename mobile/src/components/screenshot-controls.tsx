import { Pressable, StyleSheet, View } from 'react-native';
import { ThemedText } from './themed-text';
import { useTheme } from '@/hooks/use-theme';

export type ScreenshotCanvasProps = {
  uri: string;
  width: number;
  height: number;
  label: string;
  onError: () => void;
};

export function ScreenshotControls({
  onZoom,
  onPage,
  onReset,
}: {
  onZoom: (factor: number) => void;
  onPage: (direction: number) => void;
  onReset: () => void;
}) {
  const theme = useTheme();
  const actions = [
    { text: '−', label: 'Zoom out', press: () => onZoom(1 / 1.5) },
    { text: '+', label: 'Zoom in', press: () => onZoom(1.5) },
    { text: '↑', label: 'Scroll screenshot up', press: () => onPage(-1) },
    { text: '↓', label: 'Scroll screenshot down', press: () => onPage(1) },
    { text: '↺', label: 'Reset to full width and top', press: onReset },
  ];
  return (
    <View style={[styles.controls, { backgroundColor: theme.background }]}>
      {actions.map(({ text, label, press }) => (
        <Pressable
          key={label}
          accessibilityRole="button"
          accessibilityLabel={label}
          onPress={press}
          style={({ pressed }) => [
            styles.button,
            {
              opacity: pressed ? 0.6 : 1,
              backgroundColor: theme.backgroundElement,
            },
          ]}
        >
          <ThemedText style={styles.symbol}>{text}</ThemedText>
        </Pressable>
      ))}
    </View>
  );
}
const styles = StyleSheet.create({
  controls: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, padding: 10 },
  button: {
    minWidth: 44,
    minHeight: 44,
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
  },
  symbol: { fontSize: 24, lineHeight: 32 },
});
