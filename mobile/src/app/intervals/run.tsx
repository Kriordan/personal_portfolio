import { useRouter } from 'expo-router';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { Card, InlineError, NativeAction, PageHeading, Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { IntervalAvailability } from '@/components/interval-content';
import { useIntervalLibrary, useIntervalSession } from '@/hooks/use-intervals';
import { useTheme } from '@/hooks/use-theme';
import { confirmAction } from '@/lib/confirm-action';
import { formatDuration, intervalAt } from '@/lib/interval-model';
import { intervalSession } from '@/lib/interval-runtime';

export default function IntervalRunScreen() { return <IntervalAvailability><Run /></IntervalAvailability>; }

function Run() {
  const session = useIntervalSession();
  const library = useIntervalLibrary();
  const router = useRouter();
  const theme = useTheme();
  const back = () => router.replace('/intervals');
  if (!session?.workout) return <Screen>
    <PageHeading title="Ready when you are" subtitle="Choose a workout to get started." />
    <NativeAction label="Choose workout" onPress={back} />
  </Screen>;
  const { workout, timeline, audio, busy, error } = session;
  const total = timeline.at(-1)!.end;
  const index = intervalAt(timeline, audio.position);
  const current = timeline[index];
  const next = timeline[index + 1];
  const preparing = audio.state === 'preparing' || audio.state === 'ready';
  const complete = audio.state === 'completed';
  const failed = audio.state === 'error';
  const end = () => confirmAction('End workout?', 'Your saved workout will be ready for your next run.', 'End workout', () => {
    void intervalSession!.stop().then(back);
  });
  return <Screen>
    <PageHeading title={workout.name} eyebrow={complete ? 'WORKOUT COMPLETE' : preparing ? 'GETTING READY' : audio.state === 'paused' ? 'PAUSED' : 'IN PROGRESS'} />
    {preparing ? <Card>
      <ActivityIndicator color={theme.accent} size="large" />
      <ThemedText type="subtitle">Preparing your spoken cues…</ThemedText>
      <ThemedText themeColor="textSecondary">Keep the app open for a moment. You can lock your phone once the workout starts.</ThemedText>
      <NativeAction label="Cancel" secondary onPress={() => { void intervalSession!.stop().then(back); }} />
    </Card> : <>
      <Card>
        <ThemedText type="title" style={styles.center}>{complete ? 'All done.' : current?.name ?? 'Ready'}</ThemedText>
        {current?.round && !complete ? <ThemedText themeColor="textSecondary" style={styles.center}>Round {current.round} of {current.rounds}</ThemedText> : null}
        <ThemedText accessibilityLabel={complete ? 'Workout complete' : `${formatDuration(Math.max(0, (current?.end ?? total) - audio.position))} remaining`}
          accessibilityLiveRegion="none" maxFontSizeMultiplier={1.5} adjustsFontSizeToFit numberOfLines={1}
          style={[styles.countdown, { color: theme.accent }]}>{complete ? formatDuration(total) : formatDuration((current?.end ?? total) - audio.position)}</ThemedText>
        <ThemedText themeColor="textSecondary" style={styles.center}>
          {complete ? 'Workout duration' : `${formatDuration(total - audio.position)} left overall`}
        </ThemedText>
        <View accessible accessibilityRole="progressbar" accessibilityLabel="Workout progress"
          accessibilityValue={{ min: 0, max: 100, now: Math.round(audio.position / total * 100) }}
          style={[styles.progress, { backgroundColor: theme.backgroundSelected }]}>
          <View style={[styles.fill, { width: `${Math.min(100, audio.position / total * 100)}%`, backgroundColor: theme.accent }]} />
        </View>
        {!complete ? <ThemedText style={styles.center}>Next · {next ? `${next.name} · ${formatDuration(next.seconds)}` : 'Finish'}</ThemedText> : null}
      </Card>
      {audio.reason ? <ThemedText themeColor="textSecondary">{audio.reason}</ThemedText> : null}
      {error ? <InlineError message={error} /> : null}
      {failed ? <NativeAction label="Try again" disabled={busy} onPress={() => { void intervalSession!.start(workout, library.data?.volume ?? 1); }} />
        : complete ? <NativeAction label="Done" onPress={() => { void intervalSession!.stop().then(back); }} />
        : <>
          <NativeAction label={audio.state === 'paused' ? 'Resume' : 'Pause'} disabled={busy}
            onPress={() => { void (audio.state === 'paused' ? intervalSession!.resume() : intervalSession!.pause()); }} />
          <NativeAction label="Skip to next interval" secondary disabled={busy} onPress={() => { void intervalSession!.skip(); }} />
        </>}
      {!complete ? <NativeAction label="End workout" secondary onPress={end} /> : null}
    </>}
  </Screen>;
}
const styles = StyleSheet.create({
  center: { textAlign: 'center' },
  countdown: { fontSize: 88, lineHeight: 108, fontWeight: '700', fontVariant: ['tabular-nums'], textAlign: 'center', marginVertical: 16 },
  progress: { height: 8, borderRadius: 4, overflow: 'hidden', marginVertical: 10 },
  fill: { height: '100%', borderRadius: 4 },
});
