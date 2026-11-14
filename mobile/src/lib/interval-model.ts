export interface Interval {
  kind: 'interval';
  id: string;
  name: string;
  seconds: number;
}

export interface RepeatGroup {
  kind: 'repeat';
  id: string;
  repeats: number;
  intervals: Interval[];
}

export type WorkoutBlock = Interval | RepeatGroup;
export interface Workout { id: string; name: string; blocks: WorkoutBlock[] }
export interface IntervalLibrary { version: 1; workouts: Workout[]; volume: number }
export interface RunInterval extends Interval {
  start: number;
  end: number;
  round?: number;
  rounds?: number;
}
export const intervalLimits = { segments: 500, seconds: 14_400, name: 80, workouts: 100 };

const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);
const label = (value: unknown): value is string =>
  typeof value === 'string' && value.trim().length > 0 && value.length <= intervalLimits.name;
const positive = (value: unknown): value is number =>
  typeof value === 'number' && Number.isSafeInteger(value) && value > 0;

/** Also used on disk input; validate before expanding any repeat count. */
export function validateWorkout(value: unknown): string | null {
  if (!object(value) || !label(value.id) || !label(value.name))
    return 'Give the workout a name of 1–80 characters.';
  if (!Array.isArray(value.blocks) || !value.blocks.length || value.blocks.length > intervalLimits.segments)
    return 'Add at least one interval, with at most 500 blocks.';
  let count = 0;
  let duration = 0;
  const ids = new Set<string>();
  function interval(item: unknown): item is Interval {
    if (!object(item) || item.kind !== 'interval' || !label(item.id) || ids.has(item.id)
      || !label(item.name) || !positive(item.seconds) || item.seconds > intervalLimits.seconds) return false;
    ids.add(item.id);
    return true;
  }
  for (const block of value.blocks) {
    if (!object(block)) return 'This workout contains an invalid block.';
    if (block.kind === 'interval') {
      if (!interval(block)) return 'Each interval needs a name and a positive whole number of seconds.';
      count++;
      duration += block.seconds;
    } else if (block.kind === 'repeat') {
      if (!label(block.id) || ids.has(block.id) || !positive(block.repeats) || block.repeats > intervalLimits.segments
        || !Array.isArray(block.intervals) || !block.intervals.length || block.intervals.length > intervalLimits.segments)
        return 'Each repeat group needs intervals and 1–500 rounds.';
      ids.add(block.id);
      let seconds = 0;
      for (const child of block.intervals) {
        if (!interval(child)) return 'Repeat groups can contain named intervals only.';
        seconds += child.seconds;
      }
      count += block.repeats * block.intervals.length;
      duration += block.repeats * seconds;
    } else return 'This workout contains an invalid block.';
    if (count > intervalLimits.segments || duration > intervalLimits.seconds)
      return 'Keep workouts within 500 intervals and four hours.';
  }
  return null;
}

export function expandWorkout(workout: Workout): RunInterval[] {
  const error = validateWorkout(workout);
  if (error) throw new Error(error);
  const result: RunInterval[] = [];
  let start = 0;
  const append = (item: Interval, round?: number, rounds?: number) => {
    const end = start + item.seconds;
    result.push({ ...item, name: item.name.trim(), start, end, ...(round ? { round, rounds } : {}) });
    start = end;
  };
  for (const block of workout.blocks) {
    if (block.kind === 'interval') append(block);
    else for (let round = 1; round <= block.repeats; round++)
      for (const item of block.intervals) append(item, round, block.repeats);
  }
  return result;
}

export function intervalAt(timeline: RunInterval[], elapsed: number): number {
  return timeline.findIndex((item) => item.end > Math.max(0, elapsed));
}

export function formatDuration(seconds: number): string {
  const whole = Math.max(0, Math.ceil(seconds));
  const minutes = Math.floor(whole / 60);
  return `${minutes}:${String(whole % 60).padStart(2, '0')}`;
}

export function duplicateBlock(block: WorkoutBlock, id: () => string): WorkoutBlock {
  return block.kind === 'interval' ? { ...block, id: id() } : {
    ...block, id: id(), intervals: block.intervals.map((item) => ({ ...item, id: id() })),
  };
}

export function moveBlock<T>(items: T[], index: number, direction: -1 | 1): T[] {
  const target = index + direction;
  if (index < 0 || index >= items.length || target < 0 || target >= items.length) return items;
  const next = [...items];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

export function defaultIntervalLibrary(): IntervalLibrary {
  return { version: 1, volume: 1, workouts: [{
    id: 'run-walk', name: 'Run / Walk', blocks: [
      { kind: 'interval', id: 'warmup', name: 'Warm-up', seconds: 300 },
      { kind: 'repeat', id: 'rounds', repeats: 8, intervals: [
        { kind: 'interval', id: 'jog', name: 'Jog', seconds: 120 },
        { kind: 'interval', id: 'walk', name: 'Walk', seconds: 60 },
      ] },
      { kind: 'interval', id: 'cooldown', name: 'Cool down', seconds: 300 },
    ],
  }] };
}

/** Corrupt/newer data is an error, never silently replaced by the example. */
export function readIntervalLibrary(raw: string | null): IntervalLibrary {
  if (raw === null) return defaultIntervalLibrary();
  const value: unknown = JSON.parse(raw);
  if (!object(value) || value.version !== 1 || !Array.isArray(value.workouts)
    || value.workouts.length > intervalLimits.workouts || typeof value.volume !== 'number'
    || !Number.isFinite(value.volume) || value.volume < 0.1 || value.volume > 1
    || value.workouts.some((item) => validateWorkout(item) !== null)
    || new Set(value.workouts.map((item: Workout) => item.id)).size !== value.workouts.length)
    throw new Error('Saved workouts could not be read. They have not been changed.');
  return value as unknown as IntervalLibrary;
}
