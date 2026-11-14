import { expandWorkout, type RunInterval, type Workout } from './interval-model.ts';

export type AudioState = 'idle' | 'preparing' | 'ready' | 'running' | 'paused' | 'completed' | 'error';
export interface AudioSnapshot {
  state: AudioState;
  position: number;
  duration: number;
  reason: string | null;
}
export interface IntervalAudioPort {
  prepare(program: string): Promise<AudioSnapshot>;
  play(): Promise<AudioSnapshot>;
  pause(): Promise<AudioSnapshot>;
  skip(): Promise<AudioSnapshot>;
  stop(): Promise<AudioSnapshot>;
  snapshot(): Promise<AudioSnapshot>;
  setVolume(volume: number): Promise<void>;
  preview(): Promise<void>;
  addListener(name: 'onStatus', callback: (snapshot: AudioSnapshot) => void): { remove(): void };
  readLibrary(): Promise<string | null>;
  writeLibrary(json: string): Promise<void>;
}
export interface IntervalSession {
  workout: Workout | null;
  timeline: RunInterval[];
  audio: AudioSnapshot;
  error: string | null;
  busy: boolean;
}
const idle = (): AudioSnapshot => ({ state: 'idle', position: 0, duration: 0, reason: null });
const initial = (): IntervalSession => ({ workout: null, timeline: [], audio: idle(), error: null, busy: false });

/** Lives outside routes. Generation guards keep logout/cancel from starting late audio. */
export function createIntervalSession(port: IntervalAudioPort) {
  let value = initial();
  let generation = 0;
  let stopping: Promise<unknown> = Promise.resolve();
  const listeners = new Set<() => void>();
  const update = (change: Partial<IntervalSession>) => {
    value = { ...value, ...change };
    listeners.forEach((listener) => listener());
  };
  port.addListener('onStatus', (audio) => {
    if (value.workout) update({ audio });
  });
  const command = async (run: () => Promise<AudioSnapshot>) => {
    if (value.busy || !value.workout) return;
    const owner = generation;
    update({ busy: true, error: null });
    try {
      const audio = await run();
      if (owner === generation) update({ audio });
    } catch {
      if (owner === generation) update({ error: 'Couldn’t change playback. Try again.' });
    } finally {
      if (owner === generation) update({ busy: false });
    }
  };
  return {
    getSnapshot: () => value,
    subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    async start(workout: Workout, volume: number) {
      if (value.busy || (value.workout && ['preparing', 'ready', 'running', 'paused'].includes(value.audio.state))) return;
      const timeline = expandWorkout(workout);
      const owner = ++generation;
      // The running definition is immutable, even if the saved workout is edited.
      update({ workout: JSON.parse(JSON.stringify(workout)) as Workout, timeline, audio: { ...idle(), state: 'preparing' }, busy: true, error: null });
      try {
        await stopping;
        if (owner !== generation) return;
        await port.setVolume(volume);
        if (owner !== generation) return;
        await port.prepare(JSON.stringify({ name: workout.name, segments: timeline.map(({ name, seconds }) => ({ name, seconds })) }));
        if (owner !== generation) return;
        const audio = await port.play();
        if (owner === generation) update({ audio });
      } catch {
        if (owner === generation) update({ audio: { ...idle(), state: 'error' }, error: 'Couldn’t prepare the spoken cues. Your workout is saved. Try again.' });
      } finally {
        if (owner === generation) update({ busy: false });
      }
    },
    pause: () => command(() => port.pause()),
    resume: () => command(() => port.play()),
    skip: () => command(() => port.skip()),
    async stop() {
      ++generation;
      update(initial());
      // stop is queued before any later start; native cancellation is also fenced.
      stopping = port.stop();
      await stopping;
    },
  };
}
