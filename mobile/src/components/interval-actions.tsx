import { Pressable, View } from 'react-native';
import { ThemedText } from './themed-text';

export interface IntervalMenuAction { label: string; run(): void; disabled?: boolean }
export function IntervalActions({ actions, label = 'More actions' }: { actions: IntervalMenuAction[]; label?: string }) {
  return <View accessibilityLabel={label} style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12 }}>
    {actions.map((action) => <Pressable key={action.label} accessibilityRole="button"
      disabled={action.disabled} onPress={action.run} style={{ minHeight: 44, justifyContent: 'center' }}>
      <ThemedText themeColor="accent">{action.label}</ThemedText>
    </Pressable>)}
  </View>;
}
