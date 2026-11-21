import { useLocalSearchParams, useRouter } from 'expo-router';
import { Activity } from 'react';
import { Keyboard, Pressable, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LotteryDrawPlanner } from '@/components/lottery-draw-planner';
import { LotteryScratchOffs } from '@/components/lottery-scratch-offs';
import { ThemedText } from '@/components/themed-text';
import { MaxContentWidth } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

const sections = [
  { value: 'scratch-offs', label: 'Scratch-offs' },
  { value: 'draw-planner', label: 'Draw planner' },
] as const;

export default function LottoScreen() {
  const theme = useTheme();
  const router = useRouter();
  const { section } = useLocalSearchParams<{ section?: string }>();
  const selected = section === 'draw-planner' ? section : 'scratch-offs';

  return (
    <View style={[styles.fill, { backgroundColor: theme.background }]}>
      <SafeAreaView edges={['left', 'right']}>
        <View
          accessibilityRole="tablist"
          accessibilityLabel="Lotto sections"
          style={styles.sections}
        >
          {sections.map(({ value, label }) => (
            <Pressable
              key={value}
              accessibilityRole="tab"
              accessibilityState={{ selected: selected === value }}
              onPress={() => {
                Keyboard.dismiss();
                router.setParams({ section: value });
              }}
              style={({ pressed }) => [
                styles.section,
                {
                  backgroundColor:
                    selected === value
                      ? theme.accentSoft
                      : theme.backgroundElement,
                  borderColor: selected === value ? theme.accent : theme.border,
                  opacity: pressed ? 0.7 : 1,
                },
              ]}
            >
              <ThemedText
                type="smallBold"
                themeColor={selected === value ? 'accent' : 'textSecondary'}
                style={styles.label}
              >
                {label}
              </ThemedText>
            </Pressable>
          ))}
        </View>
      </SafeAreaView>
      <Activity mode={selected === 'scratch-offs' ? 'visible' : 'hidden'}>
        <LotteryScratchOffs />
      </Activity>
      <Activity mode={selected === 'draw-planner' ? 'visible' : 'hidden'}>
        <LotteryDrawPlanner />
      </Activity>
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  sections: {
    flexDirection: 'row',
    gap: 8,
    paddingHorizontal: 20,
    paddingVertical: 12,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
  },
  section: {
    flex: 1,
    minHeight: 48,
    padding: 12,
    borderWidth: 1,
    borderRadius: 14,
    borderCurve: 'continuous',
    alignItems: 'center',
    justifyContent: 'center',
  },
  label: { textAlign: 'center' },
});
