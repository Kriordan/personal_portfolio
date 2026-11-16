import { Platform, StyleSheet, View } from 'react-native';
import { Card, NativeAction, ScreenState } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { intervalNative } from '@/lib/interval-native';
import { formatDuration, type WorkoutBlock } from '@/lib/interval-model';
import { useTheme } from '@/hooks/use-theme';
import type { ReactNode } from 'react';

export function IntervalAvailability({ children }: { children: ReactNode }) {
  if (Platform.OS !== 'ios') return <ScreenState title="Intervals is coming to more devices"
    message="This first version is available in the iPhone app." />;
  if (!intervalNative) return <ScreenState title="Install the latest iPhone build"
    message="Intervals needs the new native audio player. Your other tools are still available." />;
  return children;
}

export function WorkoutOutline({ blocks }: { blocks: WorkoutBlock[] }) {
  const theme = useTheme();
  return <View style={intervalStyles.outline}>
    {blocks.map((block) => block.kind === 'interval'
      ? <View key={block.id} style={intervalStyles.outlineRow}>
        <ThemedText type="small" style={intervalStyles.grow}>{block.name}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">{formatDuration(block.seconds)}</ThemedText>
      </View>
      : <View key={block.id} style={[intervalStyles.group, { borderColor: theme.accent, backgroundColor: theme.accentSoft }]}>
        <ThemedText type="smallBold" themeColor="accent">Repeat × {block.repeats}</ThemedText>
        <WorkoutOutline blocks={block.intervals} />
      </View>)}
  </View>;
}

export function ActiveWorkoutCard({ name, preparing, onOpen }: { name: string; preparing: boolean; onOpen(): void }) {
  return <Card>
    <ThemedText type="smallBold" themeColor="accent">{preparing ? 'PREPARING YOUR WORKOUT' : 'WORKOUT IN PROGRESS'}</ThemedText>
    <ThemedText type="subtitle">{name}</ThemedText>
    <NativeAction label="Return to workout" onPress={onOpen} />
  </Card>;
}

export const intervalStyles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  grow: { flex: 1 },
  outline: { gap: 10 },
  outlineRow: { flexDirection: 'row', alignItems: 'baseline', gap: 12 },
  group: { borderLeftWidth: 3, borderRadius: 10, padding: 14, gap: 12 },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
});
