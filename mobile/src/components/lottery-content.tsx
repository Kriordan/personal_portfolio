import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Linking, Pressable, StyleSheet, View } from 'react-native';
import { Card, InlineError, NativeAction } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useTheme } from '@/hooks/use-theme';
import {
  useLotteryClock,
  useLotteryDraws,
  useLotteryPreferences,
} from '@/hooks/use-lottery';
import {
  dataIsStale,
  dollars,
  drawPlanExpired,
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
  const expired = query.data ? drawPlanExpired(query.data.plan, now) : true;
  return (
    <Card>
      <View style={styles.gap}>
        <ThemedText type="smallBold" themeColor="accent">
          LOTTERY QUICK REFERENCE
        </ThemedText>
        <ThemedText type="subtitle" accessibilityRole="header">
          At your next stop
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          Next drawing only · skip tickets you already have.
        </ThemedText>
      </View>
      <LotteryStates
        state={prefs.preferences.state}
        onChange={(state) => prefs.set({ state })}
      />
      {query.data && !expired ? (
        <>
          <ThemedText type="small" themeColor="textSecondary">
            {query.data.plan.date_label} · Eastern time
          </ThemedText>
          {query.data.plan.games.map((game) => (
            <View key={game.name} style={styles.drawRow}>
              <ThemedText type="smallBold">
                {game.name} · {dollars(game.price)}
              </ThemedText>
              <ThemedText>
                {game.next_draw.label} ·{' '}
                {dataIsStale(query.data.status, now)
                  ? 'Jackpot needs an update'
                  : jackpotLabel(game.jackpot)}
              </ThemedText>
              <ThemedText type="small" themeColor="textSecondary">
                {game.sales_closed
                  ? 'Tonight’s sales are closed. Confirm when future-draw sales reopen.'
                  : `Buy before ${game.cutoff} on draw day.`}
              </ThemedText>
            </View>
          ))}
          <ThemedText type="small" themeColor="textSecondary">
            Checked {query.data.status.checked}.
          </ThemedText>
        </>
      ) : (
        <ThemedText themeColor="textSecondary">
          {query.isPending
            ? 'Loading saved drawing details…'
            : 'Reload to update the next drawings. The weekly reference is still available below.'}
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
      <View style={styles.links}>
        <View style={styles.link}>
          <NativeAction
            label="Draw planner"
            onPress={() => router.push('/draw-games')}
            secondary
          />
        </View>
        <View style={styles.link}>
          <NativeAction
            label="Scratch-offs"
            onPress={() => router.push('/scratch-offs')}
            secondary
          />
        </View>
      </View>
    </Card>
  );
}
const styles = StyleSheet.create({
  gap: { gap: 6 },
  links: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  link: { flex: 1, minWidth: 130 },
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
  drawRow: { gap: 4, paddingVertical: 6 },
});
