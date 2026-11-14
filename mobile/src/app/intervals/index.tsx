import { Host, Slider } from '@expo/ui';
import { accessibilityLabel } from '@expo/ui/swift-ui/modifiers';
import { randomUUID } from 'expo-crypto';
import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useRef, useState } from 'react';
import { View } from 'react-native';
import { Card, InlineError, NativeAction, PageHeading, Screen, ScreenState } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { IntervalActions } from '@/components/interval-actions';
import { ActiveWorkoutCard, IntervalAvailability, WorkoutOutline, intervalStyles } from '@/components/interval-content';
import { useIntervalLibrary, useIntervalSession } from '@/hooks/use-intervals';
import { useTheme } from '@/hooks/use-theme';
import { confirmAction } from '@/lib/confirm-action';
import { duplicateBlock, expandWorkout, formatDuration, intervalLimits, type Workout } from '@/lib/interval-model';
import { intervalNative } from '@/lib/interval-native';
import { intervalSession } from '@/lib/interval-runtime';

export default function IntervalsScreen() { return <IntervalAvailability><Workouts /></IntervalAvailability>; }

function Workouts() {
  const router = useRouter();
  const theme = useTheme();
  const library = useIntervalLibrary();
  const session = useIntervalSession();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const mutationLock = useRef(false);
  const previewing = useRef(false);
  useFocusEffect(useCallback(() => () => {
    if (previewing.current) { previewing.current = false; void intervalNative?.stop().catch(() => {}); }
  }, []));
  const active = session?.workout && !['idle', 'completed', 'error'].includes(session.audio.state);
  const runRoute = () => router.push('/intervals/run');
  if (library.isPending) return <ScreenState loading title="Loading workouts" />;
  if (!library.data) return <ScreenState title="Couldn’t load your workouts" message="Your saved data has not been changed."
    onRetry={() => void library.refetch()} />;
  const volume = library.data.volume;
  const mutate = async (run: () => Promise<unknown>) => {
    if (mutationLock.current) return;
    mutationLock.current = true; setBusy(true); setError(null);
    try { await run(); }
    catch { setError('Couldn’t complete that action. Check available storage and try again.'); }
    finally { mutationLock.current = false; setBusy(false); }
  };
  const start = (workout: Workout) => {
    if (mutationLock.current) return;
    if (active) { runRoute(); return; }
    void intervalSession?.start(workout, volume);
    runRoute();
  };
  return <Screen>
    <PageHeading title="Intervals" subtitle="Set it up. Find your rhythm." />
    {active && session.workout ? <ActiveWorkoutCard name={session.workout.name} preparing={session.audio.state === 'preparing'} onOpen={runRoute} /> : null}
    <NativeAction label="New workout" disabled={busy || library.data.workouts.length >= intervalLimits.workouts}
      onPress={() => router.push('/intervals/new')} />
    {error ? <InlineError message={error} /> : null}
    {library.data.workouts.length === 0 ? <Card><ThemedText>Create your first workout with timed intervals and repeat groups.</ThemedText></Card> : null}
    {library.data.workouts.map((workout) => {
      const timeline = expandWorkout(workout);
      return <Card key={workout.id}>
        <View style={intervalStyles.row}>
          <View style={intervalStyles.grow}>
            <ThemedText type="subtitle">{workout.name}</ThemedText>
            <ThemedText themeColor="textSecondary">{formatDuration(timeline.at(-1)!.end)} · {timeline.length} intervals</ThemedText>
          </View>
          <IntervalActions label={`Actions for ${workout.name}`} actions={[
            { label: 'Edit', disabled: busy, run: () => router.push(`/intervals/${workout.id}`) },
            { label: 'Duplicate', disabled: busy || library.data.workouts.length >= intervalLimits.workouts, run: () => void mutate(() => library.change((current) => ({
              ...current, workouts: [...current.workouts, { ...workout, id: randomUUID(), name: `${workout.name.slice(0, 73)} (copy)`, blocks: workout.blocks.map((block) => duplicateBlock(block, randomUUID)) }],
            }))) },
            { label: 'Delete', disabled: busy, run: () => confirmAction('Delete workout?', workout.name, 'Delete', () => void mutate(() => library.change((current) => ({
              ...current, workouts: current.workouts.filter((item) => item.id !== workout.id),
            })))) },
          ]} />
        </View>
        <WorkoutOutline blocks={workout.blocks} />
        <NativeAction label={active ? 'Return to active workout' : 'Start workout'} disabled={busy} onPress={() => start(workout)} />
      </Card>;
    })}
    <Card>
      <ThemedText type="subtitle">Spoken cues</ThemedText>
      <ThemedText themeColor="textSecondary">Hear the next interval three seconds early, then a tone at the change. Your music keeps playing.</ThemedText>
      <ThemedText>Cue volume · {Math.round(volume * 100)}%</ThemedText>
      <Host matchContents={{ vertical: true }} seedColor={theme.accent}>
        <Slider value={volume} min={0.1} max={1} step={0.1} disabled={busy || !!active}
          modifiers={[accessibilityLabel('Cue volume')]}
          onValueChange={(next) => { void library.change((current) => ({ ...current, volume: Math.round(next * 10) / 10 })).catch(() => setError('Couldn’t save the cue volume. Try again.')); }} />
      </Host>
      <NativeAction label={busy ? 'Preparing…' : 'Preview sound'} secondary disabled={busy || !!active}
        onPress={() => void mutate(async () => {
          previewing.current = true;
          try { await intervalNative!.setVolume(volume); if (previewing.current) await intervalNative!.preview(); }
          finally { previewing.current = false; }
        })} />
      <ThemedText type="small" themeColor="textSecondary">Workouts are saved on this phone. Once signed in, you can use them offline.</ThemedText>
    </Card>
  </Screen>;
}
