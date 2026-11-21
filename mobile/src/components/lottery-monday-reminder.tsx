import { useRouter } from 'expo-router';
import { Modal, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { NativeAction } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useMondayLotteryReminder } from '@/hooks/use-lottery';
import { useTheme } from '@/hooks/use-theme';

export function LotteryMondayReminder({ now }: { now: number }) {
  const reminder = useMondayLotteryReminder(now);
  const theme = useTheme();
  const router = useRouter();
  return (
    <Modal
      visible={reminder.visible}
      transparent
      animationType="fade"
      onRequestClose={reminder.dismiss}
    >
      <SafeAreaView style={styles.overlay}>
        <ScrollView
          style={[styles.dialog, { backgroundColor: theme.backgroundElement }]}
          contentContainerStyle={styles.content}
          accessibilityViewIsModal
        >
          <ThemedText type="subtitle" accessibilityRole="header">
            This week’s lottery draws
          </ThemedText>
          <ThemedText>
            Before 10 p.m. Eastern today, ask for:
          </ThemedText>
          <View style={styles.games}>
            <ThemedText type="smallBold">
              Powerball · 1 play for 3 consecutive draws · $6
            </ThemedText>
            <ThemedText type="smallBold">
              Mega Millions · 1 play for 2 consecutive draws · $10
            </ThemedText>
          </View>
          <ThemedText type="small" themeColor="textSecondary">
            $16 covers the week without optional Powerball add-ons. Skip drawings
            you already have tickets for and confirm the printed dates.
          </ThemedText>
          <NativeAction
            label="Open draw planner"
            onPress={() => {
              reminder.dismiss();
              router.push({ pathname: '/lotto', params: { section: 'draw-planner' } });
            }}
          />
          <NativeAction label="Got it" secondary onPress={reminder.dismiss} />
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
    backgroundColor: '#0008',
  },
  dialog: {
    flexGrow: 0,
    width: '100%',
    maxWidth: 420,
    borderRadius: 20,
    borderCurve: 'continuous',
  },
  content: { padding: 24, gap: 16 },
  games: { gap: 10 },
});
