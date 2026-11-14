import type { DraftStorage } from './practice-drafts.ts';
import { validSessionId, type PracticeDetail } from './practice-model.ts';
import {
  copyWork,
  sameWork,
  validWorkEdit,
  workKey,
  type WorkEdit,
} from './practice-work-model.ts';

export interface WorkDraftState {
  ready: boolean;
  edits: WorkEdit[];
  saving: boolean;
  error: string | null;
}
const empty: WorkDraftState = {
  ready: false,
  edits: [],
  saving: false,
  error: null,
};
export function workBlocksSend(state: WorkDraftState) {
  return (
    !state.ready || state.saving || !!state.error || state.edits.length > 0
  );
}
export const workDraftIndex = 'learning.practice.work.v1';
const key = (user: number, session: string) =>
  `${workDraftIndex}.${user}.${session}`;
function indexRecord(
  raw: string | null,
): { userId: number; ids: string[] } | null {
  if (!raw) return null;
  const record = JSON.parse(raw);
  if (
    !record ||
    !Number.isInteger(record.userId) ||
    record.userId < 1 ||
    !Array.isArray(record.ids) ||
    record.ids.length > 20 ||
    !record.ids.every(validSessionId)
  )
    throw new Error('Invalid work draft index');
  return record;
}
export async function clearStoredWorkDrafts(storage: DraftStorage) {
  const index = indexRecord(await storage.get(workDraftIndex));
  if (index)
    for (const id of index.ids) await storage.remove(key(index.userId, id));
  await storage.remove(workDraftIndex);
}
/** Unconfirmed edits only. The server remains the source of saved work and revisions. */
export class PracticeWorkDrafts {
  private values = new Map<string, WorkDraftState>();
  private listeners = new Set<() => void>();
  private active = true;
  private loading = new Map<string, Promise<void>>();
  private flushing = new Map<string, Promise<void>>();
  private versions = new Map<string, number>();
  private userId: number;
  private storage: DraftStorage;
  private serial: <T>(run: () => Promise<T>) => Promise<T>;
  constructor(
    userId: number,
    storage: DraftStorage,
    serial: <T>(run: () => Promise<T>) => Promise<T>,
  ) {
    this.userId = userId;
    this.storage = storage;
    this.serial = serial;
  }
  snapshot = (id: string) => this.values.get(id) ?? empty;
  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => {
      this.listeners.delete(fn);
    };
  };
  dispose = () => {
    this.active = false;
    this.values.clear();
    this.listeners.clear();
  };
  private update(id: string, patch: Partial<WorkDraftState>) {
    if (!this.active) return;
    this.values.set(id, { ...this.snapshot(id), ...patch });
    this.listeners.forEach((fn) => fn());
  }
  load = (id: string) => {
    if (!this.active || !validSessionId(id) || this.snapshot(id).ready)
      return Promise.resolve();
    if (!this.loading.has(id))
      this.loading.set(
        id,
        this.serial(async () => {
          if (!this.active) return;
          try {
            const index = indexRecord(await this.storage.get(workDraftIndex));
            const raw =
              index?.userId === this.userId && index.ids.includes(id)
                ? await this.storage.get(key(this.userId, id))
                : null;
            const edits: WorkEdit[] = raw ? JSON.parse(raw) : [];
            if (
              !Array.isArray(edits) ||
              edits.length > 21 ||
              !edits.every((e) => validWorkEdit(e, true)) ||
              new Set(edits.map(workKey)).size !== edits.length
            )
              throw new Error('Invalid work draft');
            this.update(id, { ready: true, edits, error: null });
          } catch {
            this.update(id, {
              error:
                'Couldn’t load this device’s Build drafts. Try again before editing or sending.',
            });
          }
        }).finally(() => this.loading.delete(id)),
      );
    return this.loading.get(id)!;
  };
  edit = (id: string, edit: WorkEdit) => {
    if (!this.active || !this.snapshot(id).ready || !validWorkEdit(edit, true))
      return;
    const edits = this.snapshot(id).edits.filter(
      (old) => workKey(old) !== workKey(edit),
    );
    if (edits.length >= 21) return;
    this.replace(id, [...edits, copyWork(edit)]);
    void this.flush(id);
  };
  /** Explicit comparison/confirmation changes the base; typing never adopts web changes. */
  rebase = (id: string, current: WorkEdit) => {
    const draft = this.snapshot(id).edits.find(
      (e) => workKey(e) === workKey(current),
    );
    if (draft)
      this.edit(id, { ...draft, base_revision: current.base_revision });
  };
  retrySave = (id: string) => {
    if (this.active && this.snapshot(id).ready) {
      this.update(id, { saving: true });
      void this.flush(id);
    }
  };
  private replace(id: string, edits: WorkEdit[]) {
    this.versions.set(id, (this.versions.get(id) ?? 0) + 1);
    this.update(id, { edits, saving: true, error: null });
  }
  private flush(id: string) {
    if (this.flushing.has(id)) return this.flushing.get(id)!;
    const promise = (async () => {
      while (this.active) {
        const version = this.versions.get(id),
          edits = this.snapshot(id).edits;
        try {
          await this.serial(async () => {
            if (!this.active) return;
            let index = indexRecord(await this.storage.get(workDraftIndex));
            if (index && index.userId !== this.userId) {
              await clearStoredWorkDrafts(this.storage);
              index = null;
            }
            const ids = index?.ids ?? [];
            if (edits.length) {
              // Index first so even an interrupted write can be found on sign-out.
              if (!ids.includes(id)) {
                if (ids.length >= 20) throw new Error('Draft session limit');
                await this.storage.set(
                  workDraftIndex,
                  JSON.stringify({ userId: this.userId, ids: [...ids, id] }),
                );
              }
              await this.storage.set(
                key(this.userId, id),
                JSON.stringify(edits),
              );
            } else {
              await this.storage.remove(key(this.userId, id));
              await this.storage.set(
                workDraftIndex,
                JSON.stringify({
                  userId: this.userId,
                  ids: ids.filter((s) => s !== id),
                }),
              );
            }
          });
          if (version === this.versions.get(id)) {
            this.update(id, { saving: false, error: null });
            return;
          }
        } catch {
          this.update(id, {
            saving: false,
            error:
              'Build edits aren’t protected on this device yet. Keep the app open and try again. Up to 20 sessions can have local Build drafts.',
          });
          return;
        }
      }
    })().finally(() => this.flushing.delete(id));
    this.flushing.set(id, promise);
    return promise;
  }
  clearIfMatches = async (id: string, saved: WorkEdit) => {
    await this.load(id);
    if (!this.active) return;
    if (!this.snapshot(id).ready) throw new Error('Work drafts unavailable');
    const old = this.snapshot(id).edits.find(
      (e) => workKey(e) === workKey(saved),
    );
    if (!old || !sameWork(old, saved)) return;
    this.replace(
      id,
      this.snapshot(id).edits.filter((e) => workKey(e) !== workKey(saved)),
    );
    await this.flush(id);
    if (this.snapshot(id).error) {
      if (!this.snapshot(id).edits.some((e) => workKey(e) === workKey(old)))
        this.update(id, { edits: [...this.snapshot(id).edits, old] });
      throw new Error('Work draft cleanup failed');
    }
  };
}
export function savedWork(
  detail: PracticeDetail,
  part: string,
): WorkEdit | null {
  if (part === 'brief')
    return copyWork({
      kind: 'brief',
      base_revision: detail.session_brief.revision,
      entries: detail.session_brief.entries,
    });
  const artifact = detail.artifacts.find(
    (a) => `artifact:${a.artifact_id}` === part,
  );
  return artifact
    ? {
        kind: 'artifact',
        artifactId: artifact.artifact_id,
        base_revision: artifact.revision,
        body: artifact.body,
        language: artifact.language,
      }
    : null;
}
