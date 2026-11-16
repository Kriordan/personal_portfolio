import { Host } from '@expo/ui';
import { randomUUID } from 'expo-crypto';
import { usePreventRemove } from 'expo-router/react-navigation';
import { useNavigation, useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import { View } from 'react-native';
import { NativeField, NativeFormSheet } from '@/components/native-form';
import { Card, InlineError, NativeAction, PageHeading, Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { IntervalActions } from '@/components/interval-actions';
import { intervalStyles } from '@/components/interval-content';
import { useNativeText } from '@/hooks/use-native-text';
import { useTheme } from '@/hooks/use-theme';
import { useIntervalLibrary } from '@/hooks/use-intervals';
import { confirmAction } from '@/lib/confirm-action';
import { useAuth } from '@/lib/auth-context';
import { duplicateBlock, formatDuration, intervalLimits, moveBlock, validateWorkout, type Interval, type RepeatGroup, type Workout, type WorkoutBlock } from '@/lib/interval-model';

type EditTarget = { kind: 'interval'; value?: Interval; groupId?: string } | { kind: 'repeat'; value: RepeatGroup };

function IntervalSheet({ target, onClose, onSave }: { target: EditTarget; onClose(): void; onSave(block: WorkoutBlock, groupId?: string): void }) {
  const isInterval = target.kind === 'interval';
  const item = isInterval ? target.value : undefined;
  const name = useNativeText(item?.name ?? '');
  const minutes = useNativeText(String(Math.floor((item?.seconds ?? 60) / 60)));
  const seconds = useNativeText(String((item?.seconds ?? 60) % 60));
  const rounds = useNativeText(target.kind === 'repeat' ? String(target.value.repeats) : '2');
  const [error, setError] = useState<string | null>(null);
  const submit = () => {
    if (target.kind === 'repeat') {
      const raw = rounds.read().trim();
      if (!/^\d+$/.test(raw) || Number(raw) < 1 || Number(raw) > 500) { setError('Choose 1–500 rounds.'); return; }
      onSave({ ...target.value, repeats: Number(raw) }); return;
    }
    const label = name.read().trim();
    const min = minutes.read().trim() || '0';
    const sec = seconds.read().trim() || '0';
    if (!label || label.length > 80) { setError('Use an interval name of 1–80 characters.'); return; }
    if (!/^\d+$/.test(min) || !/^\d+$/.test(sec) || Number(sec) > 59
      || Number(min) * 60 + Number(sec) < 1 || Number(min) * 60 + Number(sec) > intervalLimits.seconds) {
      setError('Enter minutes and 0–59 seconds, totaling at least one second and at most four hours.'); return;
    }
    onSave({ kind: 'interval', id: item?.id ?? randomUUID(), name: label, seconds: Number(min) * 60 + Number(sec) }, target.groupId);
  };
  return <NativeFormSheet title={target.kind === 'repeat' ? 'Repeat group' : item ? 'Edit interval' : 'Add interval'}
    presented onDismiss={onClose} onSubmit={submit} submitLabel="Done" pending={false} error={error}>
    {isInterval ? <>
      <NativeField label="Interval name" {...name.input} placeholder="Jog, walk, stretch…" maxLength={80} returnKeyType="next" />
      <NativeField label="Minutes" {...minutes.input} keyboardType="number-pad" />
      <NativeField label="Seconds" {...seconds.input} keyboardType="number-pad" />
    </> : <NativeField label="Number of rounds" {...rounds.input} keyboardType="number-pad" />}
  </NativeFormSheet>;
}

export function IntervalEditor({ initial, isNew }: { initial: Workout; isNew: boolean }) {
  const theme = useTheme();
  const router = useRouter();
  const navigation = useNavigation();
  const library = useIntervalLibrary();
  const { isAuthenticated } = useAuth();
  const name = useNativeText(initial.name);
  const [blocks, setBlocks] = useState(initial.blocks);
  const [target, setTarget] = useState<EditTarget | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const saveLock = useRef(false);
  const [saved, setSaved] = useState(false);
  usePreventRemove(isAuthenticated === true && !saved, ({ data }) => {
    if (saveLock.current) return;
    if (name.read() === initial.name && blocks === initial.blocks) { navigation.dispatch(data.action); return; }
    confirmAction('Discard changes?', 'Your unsaved workout changes will be lost.', 'Discard', () => navigation.dispatch(data.action));
  });
  const total = blocks.reduce((sum, block) => sum + (block.kind === 'interval' ? block.seconds
    : block.repeats * block.intervals.reduce((count, item) => count + item.seconds, 0)), 0);

  const updateGroup = (id: string, edit: (items: Interval[]) => Interval[]) => setBlocks((current) => current.map((block) =>
    block.kind === 'repeat' && block.id === id ? { ...block, intervals: edit(block.intervals) } : block));

  const saveBlock = (block: WorkoutBlock, groupId?: string) => {
    const upsert = <T extends WorkoutBlock>(items: T[], next: T): T[] =>
      items.some((item) => item.id === next.id) ? items.map((item) => item.id === next.id ? next : item) : [...items, next];
    if (groupId && block.kind === 'interval') updateGroup(groupId, (items) => upsert(items, block));
    else setBlocks((items) => upsert(items, block));
    setTarget(null);
  };

  const actions = (block: WorkoutBlock, index: number, length: number, groupId?: string) => [
    { label: block.kind === 'repeat' ? 'Edit rounds' : 'Edit interval', run: () => setTarget(block.kind === 'repeat'
      ? { kind: 'repeat', value: block } : { kind: 'interval', value: block, groupId }) },
    { label: 'Duplicate', disabled: length >= 500, run: () => {
      const copy = duplicateBlock(block, randomUUID);
      if (groupId && copy.kind === 'interval') updateGroup(groupId, (items) => [...items.slice(0, index + 1), copy, ...items.slice(index + 1)]);
      else setBlocks((items) => [...items.slice(0, index + 1), copy, ...items.slice(index + 1)]);
    } },
    ...([-1, 1] as const).map((direction) => ({
      label: direction === -1 ? 'Move up' : 'Move down', disabled: index + direction < 0 || index + direction >= length,
      run: () => groupId ? updateGroup(groupId, (items) => moveBlock(items, index, direction)) : setBlocks((items) => moveBlock(items, index, direction)),
    })),
    { label: 'Delete', run: () => confirmAction('Delete this block?', block.kind === 'repeat' ? 'This removes the group and its intervals.' : block.name, 'Delete', () => {
      if (groupId) updateGroup(groupId, (items) => items.filter((item) => item.id !== block.id));
      else setBlocks((items) => items.filter((item) => item.id !== block.id));
    }) },
  ];

  const save = async () => {
    if (saveLock.current) return;
    const workout = { ...initial, name: name.read().trim(), blocks };
    const invalid = validateWorkout(workout);
    if (invalid) { setError(invalid); return; }
    saveLock.current = true; setSaving(true); setError(null);
    try {
      await library.change((current) => {
        if (isNew && current.workouts.length >= intervalLimits.workouts) throw new Error('Keep up to 100 saved workouts.');
        return { ...current, workouts: isNew ? [...current.workouts, workout] : current.workouts.map((item) => item.id === workout.id ? workout : item) };
      });
      setSaved(true);
      // Rerender the navigation guard before leaving after a successful save.
      setSaving(false);
      requestAnimationFrame(() => router.back());
    } catch {
      setError('Couldn’t save the workout. Your edits are still here. Check available storage and try again.');
      setSaving(false);
    } finally { saveLock.current = false; }
  };

  const intervalRow = (item: Interval, index: number, length: number, groupId?: string) => <View key={item.id} style={intervalStyles.row}>
    <View style={intervalStyles.grow}>
      <ThemedText>{item.name}</ThemedText>
      <ThemedText themeColor="textSecondary">{formatDuration(item.seconds)}</ThemedText>
    </View>
    <IntervalActions label={`Actions for ${item.name}`} actions={actions(item, index, length, groupId)} />
  </View>;

  return <>
    <Screen pointerEvents={saving ? 'none' : 'auto'}>
      <PageHeading title={isNew ? 'Build a workout' : 'Edit workout'} subtitle="Stack your intervals. Repeat the parts you want." />
      <Host matchContents={{ vertical: true }} seedColor={theme.accent}>
        <NativeField label="Workout name" {...name.input} maxLength={80} placeholder="My workout" returnKeyType="done" />
      </Host>
      <ThemedText type="subtitle">Total · {formatDuration(total)}</ThemedText>
      {blocks.map((block, index) => <Card key={block.id}>
        {block.kind === 'interval' ? intervalRow(block, index, blocks.length) : <>
          <View style={intervalStyles.row}>
            <ThemedText type="subtitle" themeColor="accent" style={intervalStyles.grow}>Repeat × {block.repeats}</ThemedText>
            <IntervalActions label={`Actions for repeat group ${index + 1}`} actions={actions(block, index, blocks.length)} />
          </View>
          <View style={[intervalStyles.group, { borderColor: theme.accent, backgroundColor: theme.accentSoft }]}>
            {block.intervals.map((item, child) => intervalRow(item, child, block.intervals.length, block.id))}
            {block.intervals.length === 0 ? <ThemedText themeColor="textSecondary">Add the intervals to repeat together.</ThemedText> : null}
            <NativeAction label="Add interval to group" secondary disabled={block.intervals.length >= 500}
              onPress={() => setTarget({ kind: 'interval', groupId: block.id })} />
          </View>
        </>}
      </Card>)}
      <NativeAction label="Add interval" secondary disabled={blocks.length >= 500} onPress={() => setTarget({ kind: 'interval' })} />
      <NativeAction label="Add repeat group" secondary disabled={blocks.length >= 500}
        onPress={() => setBlocks((items) => [...items, { kind: 'repeat', id: randomUUID(), repeats: 2, intervals: [] }])} />
      {error ? <InlineError message={error} /> : null}
      <NativeAction label={saving ? 'Saving…' : 'Save workout'} disabled={saving} onPress={() => void save()} />
    </Screen>
    {target ? <IntervalSheet target={target} onClose={() => setTarget(null)} onSave={saveBlock} /> : null}
  </>;
}
