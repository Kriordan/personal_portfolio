import type { DraftStorage } from './practice-drafts.ts';
import { validSessionId, type PracticeDetail } from './practice-model.ts';
import {
  copyWork,
  sameWork,
  validWorkEdit,
  workKey,
  type WorkEdit,
} from './practice-work-model.ts';

export interface WorkDraftState<T = WorkEdit> {
  ready: boolean;
  edits: T[];
  saving: boolean;
  error: string | null;
}
const empty: WorkDraftState<never> = {
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
export async function clearStoredWorkDrafts(
  storage: DraftStorage,
  namespace = workDraftIndex,
) {
  const index = indexRecord(await storage.get(namespace));
  if (index)
    for (const id of index.ids)
      await storage.remove(`${namespace}.${index.userId}.${id}`);
  await storage.remove(namespace);
}
export interface EditCodec<T> {
  namespace: string;
  label: string;
  limit: number;
  valid: (edit: unknown) => edit is T;
  copy: (edit: T) => T;
  key: (edit: T) => string;
  same: (left: T, right: T) => boolean;
}
/** Unconfirmed edits only. The server remains the source of saved work and revisions. */
export class PracticeEditDrafts<T extends { base_revision: number }> {
  private values = new Map<string, WorkDraftState<T>>();
  private listeners = new Set<() => void>();
  private active = true;
  private loading = new Map<string, Promise<void>>();
  private flushing = new Map<string, Promise<void>>();
  private versions = new Map<string, number>();
  private userId: number;
  private storage: DraftStorage;
  private serial: <T>(run: () => Promise<T>) => Promise<T>;
  private codec: EditCodec<T>;
  private key = (id: string) => `${this.codec.namespace}.${this.userId}.${id}`;
  constructor(
    userId: number,
    storage: DraftStorage,
    serial: <T>(run: () => Promise<T>) => Promise<T>,
    codec: EditCodec<T>,
  ) {
    this.userId = userId;
    this.storage = storage;
    this.serial = serial;
    this.codec = codec;
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
  private update(id: string, patch: Partial<WorkDraftState<T>>) {
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
            const index = indexRecord(
              await this.storage.get(this.codec.namespace),
            );
            const raw =
              index?.userId === this.userId && index.ids.includes(id)
                ? await this.storage.get(this.key(id))
                : null;
            const edits: T[] = raw ? JSON.parse(raw) : [];
            if (
              !Array.isArray(edits) ||
              edits.length > this.codec.limit ||
              !edits.every(this.codec.valid) ||
              new Set(edits.map(this.codec.key)).size !== edits.length
            )
              throw new Error('Invalid work draft');
            this.update(id, { ready: true, edits, error: null });
          } catch {
            this.update(id, {
              error: `Couldn’t load this device’s ${this.codec.label} drafts. Try again before editing or sending.`,
            });
          }
        }).finally(() => this.loading.delete(id)),
      );
    return this.loading.get(id)!;
  };
  edit = (id: string, edit: T) => {
    if (!this.active || !this.snapshot(id).ready || !this.codec.valid(edit))
      return;
    const edits = this.snapshot(id).edits.filter(
      (old) => this.codec.key(old) !== this.codec.key(edit),
    );
    if (edits.length >= this.codec.limit) return;
    this.replace(id, [...edits, this.codec.copy(edit)]);
    void this.flush(id);
  };
  /** Explicit comparison/confirmation changes the base; typing never adopts web changes. */
  rebase = (id: string, current: T) => {
    const draft = this.snapshot(id).edits.find(
      (e) => this.codec.key(e) === this.codec.key(current),
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
  private replace(id: string, edits: T[]) {
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
            let index = indexRecord(
              await this.storage.get(this.codec.namespace),
            );
            if (index && index.userId !== this.userId) {
              await clearStoredWorkDrafts(this.storage, this.codec.namespace);
              index = null;
            }
            const ids = index?.ids ?? [];
            if (edits.length) {
              // Index first so even an interrupted write can be found on sign-out.
              if (!ids.includes(id)) {
                if (ids.length >= 20) throw new Error('Draft session limit');
                await this.storage.set(
                  this.codec.namespace,
                  JSON.stringify({ userId: this.userId, ids: [...ids, id] }),
                );
              }
              await this.storage.set(this.key(id), JSON.stringify(edits));
            } else {
              await this.storage.remove(this.key(id));
              await this.storage.set(
                this.codec.namespace,
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
            error: `${this.codec.label} edits aren’t protected on this device yet. Keep the app open and try again. Up to 20 sessions can have local drafts.`,
          });
          return;
        }
      }
    })().finally(() => this.flushing.delete(id));
    this.flushing.set(id, promise);
    return promise;
  }
  clearIfMatches = async (id: string, saved: T) => {
    await this.load(id);
    if (!this.active) return;
    if (!this.snapshot(id).ready) throw new Error('Work drafts unavailable');
    const old = this.snapshot(id).edits.find(
      (e) => this.codec.key(e) === this.codec.key(saved),
    );
    if (!old || !this.codec.same(old, saved)) return;
    this.replace(
      id,
      this.snapshot(id).edits.filter(
        (e) => this.codec.key(e) !== this.codec.key(saved),
      ),
    );
    await this.flush(id);
    if (this.snapshot(id).error) {
      if (
        !this.snapshot(id).edits.some(
          (e) => this.codec.key(e) === this.codec.key(old),
        )
      )
        this.update(id, { edits: [...this.snapshot(id).edits, old] });
      throw new Error('Work draft cleanup failed');
    }
  };
}
export class PracticeWorkDrafts extends PracticeEditDrafts<WorkEdit> {
  constructor(
    userId: number,
    storage: DraftStorage,
    serial: <T>(run: () => Promise<T>) => Promise<T>,
  ) {
    super(userId, storage, serial, {
      namespace: workDraftIndex,
      label: 'Build',
      limit: 21,
      valid: (edit): edit is WorkEdit => validWorkEdit(edit, true),
      copy: copyWork,
      key: workKey,
      same: sameWork,
    });
  }
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
