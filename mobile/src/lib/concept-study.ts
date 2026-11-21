import {
  isStudyChange,
  type ConceptApi,
  type ConceptProgress,
  type StudyChange,
} from './concept-model.ts';
import type { AttemptStorage } from './learning-session.ts';

interface Dependencies {
  storage: AttemptStorage;
  api: Pick<ConceptApi, 'save' | 'progress'>;
  online: () => boolean;
  onConfirmed: (
    id: string,
    progress: ConceptProgress,
    active: () => boolean,
  ) => void;
}
export interface StudyState {
  ready: boolean;
  phase: 'idle' | 'saving' | 'checking' | 'uncertain' | 'conflict';
  pending: StudyChange | null;
  error: string | null;
  saved: ConceptProgress | null;
}
/** Persists only the pending intent. Recovery reads; it never reapplies a bookmark automatically. */
export class ConceptStudy {
  private state: StudyState = {
    ready: false,
    phase: 'idle',
    pending: null,
    error: null,
    saved: null,
  };
  private listeners = new Set<() => void>();
  private active = true;
  private busy = false;
  private restoring: Promise<void> | null = null;
  private userId: number;
  private deps: Dependencies;
  constructor(userId: number, deps: Dependencies) {
    this.userId = userId;
    this.deps = deps;
  }
  snapshot = () => this.state;
  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => {
      this.listeners.delete(fn);
    };
  };
  dispose = () => {
    this.active = false;
    this.listeners.clear();
  };
  private update(value: Partial<StudyState>) {
    if (!this.active) return;
    this.state = { ...this.state, ...value };
    this.listeners.forEach((fn) => fn());
  }
  restore = () => {
    if (!this.restoring)
      this.restoring = this.load().finally(() => {
        this.restoring = null;
      });
    return this.restoring;
  };
  private async load() {
    try {
      const raw = await this.deps.storage.read();
      if (!this.active) return;
      const record = raw ? JSON.parse(raw) : null;
      if (record?.userId === this.userId && !isStudyChange(record.change))
        throw new Error('Invalid study state');
      const pending: StudyChange | null =
        record?.userId === this.userId ? record.change : null;
      this.update({
        ready: true,
        pending,
        phase: pending ? 'uncertain' : 'idle',
        error: null,
      });
      if (pending) await this.check();
    } catch {
      this.update({
        ready: false,
        error:
          'Couldn’t load your pending save. Try again before saving progress.',
      });
    }
  }
  begin = async (change: StudyChange) => {
    if (!this.active || !this.state.ready || this.busy || this.state.pending)
      return;
    if (!isStudyChange(change)) return;
    if (!this.deps.online()) {
      this.update({
        error: 'You’re offline. Reconnect before saving your place.',
      });
      return;
    }
    this.update({ pending: change, saved: null });
    await this.submit(change);
  };
  retry = async () => {
    if (
      !this.active ||
      this.busy ||
      !this.state.pending ||
      this.state.phase === 'conflict'
    )
      return;
    if (!this.deps.online()) {
      this.update({ error: 'Reconnect before retrying this save.' });
      return;
    }
    await this.submit(this.state.pending);
  };
  private async submit(change: StudyChange) {
    this.busy = true;
    this.update({ phase: 'saving', error: null });
    try {
      await this.deps.storage.write(
        JSON.stringify({ userId: this.userId, change }),
      );
      if (!this.active) return;
      const { progress } = await this.deps.api.save(change);
      if (!this.matches(change, progress))
        throw new Error('Unrecognized progress');
      await this.confirm(change, progress);
    } catch (error) {
      if (!this.active) return;
      const status = (error as { status?: number })?.status;
      this.update(
        status && [400, 401, 403, 404, 409].includes(status)
          ? {
              phase: 'conflict',
              error:
                'Your saved place changed or is unavailable. Reload it before making another change.',
            }
          : {
              phase: 'uncertain',
              error:
                'Save not yet confirmed. Keeping your original request for recovery.',
            },
      );
    } finally {
      this.busy = false;
    }
    if (this.state.phase === 'uncertain') await this.check();
  }
  private matches(
    change: StudyChange,
    progress: ConceptProgress | null,
  ): boolean {
    return (
      !!progress &&
      progress.concept_id === change.conceptId &&
      Number.isInteger(progress.revision) &&
      progress.revision > 0 &&
      (change.kind === 'enroll' ||
        (progress.revision === change.expected_revision + 1 &&
          progress.reading_version === change.content_version &&
          progress.reading_section === change.section_id))
    );
  }
  check = async () => {
    const pending = this.state.pending;
    if (
      !this.active ||
      this.busy ||
      !pending ||
      this.state.phase === 'conflict' ||
      !this.deps.online()
    )
      return;
    this.busy = true;
    this.update({ phase: 'checking' });
    try {
      const { progress } = await this.deps.api.progress(pending.conceptId);
      if (!this.active) return;
      if (progress && this.matches(pending, progress))
        await this.confirm(pending, progress);
      else if (
        pending.kind === 'position' &&
        (!progress || progress.revision !== pending.expected_revision)
      ) {
        this.update({
          phase: 'conflict',
          error:
            'Your saved place changed elsewhere. Reload to keep the latest position.',
        });
      } else
        this.update({
          phase: 'uncertain',
          error:
            'No saved result is confirmed. Check again or retry the same save.',
        });
    } catch {
      this.update({
        phase: 'uncertain',
        error: 'Couldn’t confirm the save. Your original request is retained.',
      });
    } finally {
      this.busy = false;
    }
  };
  private async confirm(change: StudyChange, progress: ConceptProgress) {
    if (!this.active) return;
    await this.deps.storage.clear();
    if (!this.active) return;
    this.update({ pending: null, phase: 'idle', error: null, saved: progress });
    this.deps.onConfirmed(change.conceptId, progress, () => this.active);
  }
  dismissConflict = async () => {
    if (!this.active || this.busy || this.state.phase !== 'conflict')
      return false;
    try {
      await this.deps.storage.clear();
      if (!this.active) return false;
      this.update({ pending: null, phase: 'idle', error: null, saved: null });
      return true;
    } catch {
      this.update({ error: 'Couldn’t clear the rejected request. Try again.' });
      return false;
    }
  };
}
