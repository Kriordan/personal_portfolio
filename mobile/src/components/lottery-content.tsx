import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Linking, Pressable, StyleSheet, View } from 'react-native';
import { Card, InlineError, NativeAction } from '@/components/screen';
import { LotteryMondayReminder } from '@/components/lottery-monday-reminder';
import { ThemedText } from '@/components/themed-text';
import { useTheme } from '@/hooks/use-theme';
import {
  useLotteryClock,
  useLotteryDraws,
  useLotteryPreferences,
} from '@/hooks/use-lottery';
import {
  dataIsStale,
  homeDrawsExpired,
  jackpotLabel,
  type LotteryState,
  type LotteryStatus,
} from '@/lib/lottery-model';

export function LotteryChoice({
  label,
  selected,
  onPress,
  checkbox = false,
}: {
  label: string;
  selected: boolean;
  onPress(): void;
  checkbox?: boolean;
}) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole={checkbox ? 'checkbox' : 'button'}
      accessibilityState={checkbox ? { checked: selected } : { selected }}
      onPress={onPress}
      style={({ pressed }) => [
        styles.choice,
        {
          backgroundColor: selected
            ? theme.accentSoft
            : theme.backgroundElement,
          borderColor: selected ? theme.accent : theme.border,
          opacity: pressed ? 0.7 : 1,
        },
      ]}
    >
      <ThemedText
        type="smallBold"
        themeColor={selected ? 'accent' : 'textSecondary'}
      >
        {label}
      </ThemedText>
    </Pressable>
  );
}
export function LotteryStates({
  state,
  onChange,
}: {
  state: LotteryState;
  onChange(state: LotteryState): void;
}) {
  return (
    <View style={styles.choices}>
      <LotteryChoice
        label="New York"
        selected={state === 'ny'}
        onPress={() => onChange('ny')}
      />
      <LotteryChoice
        label="Connecticut"
        selected={state === 'ct'}
        onPress={() => onChange('ct')}
      />
    </View>
  );
}
export function LotteryStatusNote({
  status,
  compact = false,
}: {
  status: LotteryStatus;
  compact?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <View style={styles.gap}>
      {!compact ? (
        <ThemedText type="small" themeColor="textSecondary">
          Source: {status.source_date ?? 'Awaiting first import'}
        </ThemedText>
      ) : null}
      {status.failure ? (
        <InlineError
          message={`Last refresh failed: ${status.failure}. Showing the last saved results.`}
        />
      ) : null}
      {status.interrupted ? (
        <InlineError message="The last refresh did not finish. Showing the last saved results." />
      ) : null}
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded }}
        onPress={() => setExpanded(!expanded)}
        style={styles.textAction}
      >
        <ThemedText type="small" themeColor="accent">
          {compact
            ? `Source: ${status.source_date ?? 'Awaiting first import'} · ${expanded ? 'Hide status' : 'Status'}`
            : expanded
              ? 'Hide refresh status'
              : 'Refresh status'}
        </ThemedText>
      </Pressable>
      {expanded ? (
        <View style={styles.gap}>
          <ThemedText type="small">
            Last successful check: {status.checked}
          </ThemedText>
          <ThemedText type="small">
            Daily job: {status.scheduled_status}
            {status.scheduled_at ? ` · ${status.scheduled_at}` : ''}
          </ThemedText>
          <ThemedText type="small" themeColor="textSecondary">
            Daily at 13:00 UTC. Pull to reload the saved results.
          </ThemedText>
        </View>
      ) : null}
    </View>
  );
}
export function OfficialLotteryLink({
  url,
  label = 'Official game details',
}: {
  url: string;
  label?: string;
}) {
  const [error, setError] = useState(false);
  return (
    <View>
      <NativeAction
        label={label}
        secondary
        onPress={() => {
          if (!/^https:\/\/(nylottery\.ny\.gov|ctlottery\.com)\//.test(url)) {
            setError(true);
            return;
          }
          void Linking.openURL(url).catch(() => setError(true));
        }}
      />
      {error ? (
        <InlineError message="Couldn’t open the official page." />
      ) : null}
    </View>
  );
}
export function DrawQuickReference() {
  const prefs = useLotteryPreferences();
  const query = useLotteryDraws(prefs.preferences.state, prefs.ready);
  const now = useLotteryClock();
  const router = useRouter();
  const home = query.data?.home;
  const expired = !home || homeDrawsExpired(home, now);
  return (
    <>
      <Card>
        <View style={styles.homeHeading}>
          <ThemedText type="subtitle" accessibilityRole="header">
            Lotto
          </ThemedText>
          <Pressable
            accessibilityRole="link"
            onPress={() => router.push('/lotto')}
            style={styles.textAction}
          >
            <ThemedText type="smallBold" themeColor="accent">
              Open Lotto
            </ThemedText>
          </Pressable>
        </View>
        {home && !expired && query.data ? (
          <>
            <View style={styles.gap}>
              <ThemedText type="smallBold" themeColor="textSecondary">
                NEXT DRAWING
              </ThemedText>
              <ThemedText>{home.upcoming.name}</ThemedText>
              <ThemedText type="small" themeColor="textSecondary">
                {home.upcoming.label}
              </ThemedText>
              <ThemedText type="smallBold" themeColor="accent">
                {dataIsStale(query.data.status, now)
                  ? 'Jackpot needs an update'
                  : jackpotLabel(home.upcoming.jackpot)}
              </ThemedText>
            </View>
            <View style={styles.gap}>
              <ThemedText type="smallBold" themeColor="textSecondary">
                LATEST RESULT
              </ThemedText>
              <ThemedText>{home.latest.name} · {home.latest.label}</ThemedText>
              {home.latest.result ? (
                <>
                  <View style={styles.numbers}>
                    <ThemedText type="smallBold">
                      {home.latest.result.numbers.join(' · ')}
                    </ThemedText>
                    <ThemedText type="smallBold" themeColor="accent">
                      {home.latest.result.bonus_label} {home.latest.result.bonus}
                    </ThemedText>
                  </View>
                  {home.latest.result.power_play !== null ? (
                    <ThemedText type="small" themeColor="textSecondary">
                      Power Play {home.latest.result.power_play}×
                    </ThemedText>
                  ) : null}
                </>
              ) : (
                <ThemedText type="small" themeColor="textSecondary">
                  Awaiting results.
                </ThemedText>
              )}
            </View>
          </>
        ) : (
          <ThemedText themeColor="textSecondary">
            {query.isPending
              ? 'Loading saved drawing details…'
              : 'Pull to refresh drawing details, or open Lotto.'}
          </ThemedText>
        )}
        {prefs.accountError ? (
          <InlineError
            message="Couldn’t load your account."
            onRetry={prefs.retryAccount}
          />
        ) : null}
        {query.isError ? (
          <InlineError
            message="Couldn’t reload drawing details."
            onRetry={() => void query.refetch()}
          />
        ) : null}
      </Card>
      <LotteryMondayReminder now={now} />
    </>
  );
}
const styles = StyleSheet.create({
  gap: { gap: 6 },
  homeHeading: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  numbers: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  choices: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  choice: {
    minHeight: 44,
    paddingHorizontal: 14,
    paddingVertical: 11,
    justifyContent: 'center',
    borderWidth: 1,
    borderRadius: 14,
    borderCurve: 'continuous',
  },
  textAction: {
    minHeight: 44,
    justifyContent: 'center',
    alignSelf: 'flex-start',
  },
});
