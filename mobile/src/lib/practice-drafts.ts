import {
  isPracticeChange,
  validSessionId,
  type PracticeChange,
  type PracticeDetail,
  sendChange,
} from './practice-model.ts';

export interface DraftStorage {
  get: (key: string) => Promise<string | null>;
  set: (key: string, value: string) => Promise<void>;
  remove: (key: string) => Promise<void>;
}
export type Draft = Extract<PracticeChange, { kind: 'send' }>;
export interface DraftState {
  ready: boolean;
  draft: Draft | null;
  saving: boolean;
  error: string | null;
}
const empty: DraftState = {
  ready: false,
  draft: null,
  saving: false,
  error: null,
};
export const draftIndex = 'learning.practice.drafts.v1';
const key = (user: number, id: string) => `${draftIndex}.${user}.${id}`;
const placeholderId = '00000000-0000-4000-8000-000000000000';
function indexRecord(
  raw: string | null,
): { userId: number; ids: string[] } | null {
  if (!raw) return null;
  const value = JSON.parse(raw);
  if (
    !value ||
    !Number.isInteger(value.userId) ||
    value.userId < 1 ||
    !Array.isArray(value.ids) ||
    value.ids.length > 20 ||
    !value.ids.every(validSessionId)
  )
    throw new Error('Invalid draft index');
  return value;
}
/** Called inside the shared storage queue after disposing all account controllers. */
export async function clearStoredDrafts(storage: DraftStorage) {
  const record = indexRecord(await storage.get(draftIndex));
  if (record)
    for (const id of record.ids) await storage.remove(key(record.userId, id));
  await storage.remove(draftIndex);
}
/** Account/session scoped drafts. No network, offline mutation queue, or automatic sends. */
export class PracticeDrafts {
  private values = new Map<string, DraftState>();
  private listeners = new Set<() => void>();
  private active = true;
  private loading = new Map<string, Promise<void>>();
  private versions = new Map<string, number>();
  private flushing = new Map<string, Promise<void>>();
  private storage: DraftStorage;
  private userId: number;
  // The runtime serializes this with the mutation journal and logout cleanup.
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
    this.listeners.clear();
    this.values.clear();
  };
  private update(id: string, patch: Partial<DraftState>) {
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
            const index = indexRecord(await this.storage.get(draftIndex));
            const raw =
              index?.userId === this.userId && index.ids.includes(id)
                ? await this.storage.get(key(this.userId, id))
                : null;
            const draft: Draft | null = raw ? JSON.parse(raw) : null;
            if (
              draft &&
              (typeof draft.body !== 'string' ||
                draft.body.length > 8192 ||
                !isPracticeChange({ ...draft, body: 'draft' }) ||
                draft.kind !== 'send' ||
                draft.sessionId !== id)
            )
              throw new Error('Invalid draft');
            this.update(id, { ready: true, draft, error: null });
          } catch {
            this.update(id, {
              error:
                'Couldn’t load this device’s draft. Try again before editing.',
            });
          }
        }).finally(() => this.loading.delete(id)),
      );
    return this.loading.get(id)!;
  };
  edit = (id: string, body: string, detail: PracticeDetail) => {
    if (!this.active || !this.snapshot(id).ready || body.length > 8192) return;
    const old = this.snapshot(id).draft;
    // Keep the original context while typing; a cross-device change requires
    // explicit review. The actual mutation UUID is created only on Send.
    const draft = body
      ? { ...(old ?? (sendChange(detail, body, placeholderId) as Draft)), body }
      : null;
    this.update(id, { draft, error: null, saving: true });
    this.versions.set(id, (this.versions.get(id) ?? 0) + 1);
    void this.flush(id);
  };
  rebase = (id: string, detail: PracticeDetail) => {
    const draft = this.snapshot(id).draft;
    if (!this.active || !draft) return;
    this.update(id, {
      draft: sendChange(detail, draft.body, placeholderId) as Draft,
      saving: true,
      error: null,
    });
    this.versions.set(id, (this.versions.get(id) ?? 0) + 1);
    void this.flush(id);
  };
  retrySave = (id: string) => {
    if (this.active && this.snapshot(id).ready) {
      this.update(id, { saving: true });
      void this.flush(id);
    }
  };
  private flush(id: string) {
    if (this.flushing.has(id)) return this.flushing.get(id)!;
    const promise = (async () => {
      while (this.active) {
        const version = this.versions.get(id),
          draft = this.snapshot(id).draft;
        try {
          await this.serial(async () => {
            if (!this.active) return;
            let index = indexRecord(await this.storage.get(draftIndex));
            if (index && index.userId !== this.userId) {
              await clearStoredDrafts(this.storage);
              index = null;
            }
            const ids = index?.ids ?? [];
            if (draft) {
              // Index first: a crash cannot leave an untracked private draft.
              if (!ids.includes(id)) {
                if (ids.length >= 20) throw new Error('Draft limit');
                await this.storage.set(
                  draftIndex,
                  JSON.stringify({ userId: this.userId, ids: [...ids, id] }),
                );
              }
              await this.storage.set(
                key(this.userId, id),
                JSON.stringify(draft),
              );
            } else {
              await this.storage.remove(key(this.userId, id));
              await this.storage.set(
                draftIndex,
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
              'This draft isn’t saved on this device yet. Keep the app open and try saving again. At most 20 conversations can have local drafts.',
          });
          return;
        }
      }
    })().finally(() => this.flushing.delete(id));
    this.flushing.set(id, promise);
    return promise;
  }
  clearIfMatches = async (id: string, body: string) => {
    await this.load(id);
    if (!this.active) return;
    if (!this.snapshot(id).ready) throw new Error('Draft unavailable');
    const draft = this.snapshot(id).draft;
    if (draft?.body !== body) return;
    this.update(id, { draft: null, saving: true });
    this.versions.set(id, (this.versions.get(id) ?? 0) + 1);
    await this.flush(id);
    if (this.snapshot(id).error) {
      if (!this.snapshot(id).draft) this.update(id, { draft });
      throw new Error('Draft cleanup failed');
    }
  };
}

export function draftOutdated(draft: Draft | null, detail: PracticeDetail) {
  if (!draft) return false;
  const current = sendChange(detail, draft.body, placeholderId) as Draft;
  return (
    draft.expected_sequence !== current.expected_sequence ||
    draft.brief_revision !== current.brief_revision ||
    JSON.stringify(Object.entries(draft.artifact_revisions).sort()) !==
      JSON.stringify(Object.entries(current.artifact_revisions).sort())
  );
}
