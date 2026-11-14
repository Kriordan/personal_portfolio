import { randomUUID } from 'expo-crypto';
import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { IntervalAvailability } from '@/components/interval-content';
import { IntervalEditor } from '@/components/interval-editor';
import { ScreenState } from '@/components/screen';
import { useIntervalLibrary } from '@/hooks/use-intervals';
import type { Workout } from '@/lib/interval-model';

export default function WorkoutEditorScreen() { return <IntervalAvailability><Editor /></IntervalAvailability>; }

function Editor() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const library = useIntervalLibrary();
  const [fresh] = useState<Workout>(() => ({ id: randomUUID(), name: '', blocks: [] }));
  if (library.isPending) return <ScreenState loading title="Loading workout" />;
  if (!library.data) return <ScreenState title="Couldn’t load your workouts" onRetry={() => void library.refetch()} />;
  const workout = id === 'new' ? fresh : library.data.workouts.find((item) => item.id === id);
  if (!workout) return <ScreenState title="Workout not found" message="Return to Intervals to choose another workout." />;
  return <IntervalEditor key={id} initial={workout} isNew={id === 'new'} />;
}
