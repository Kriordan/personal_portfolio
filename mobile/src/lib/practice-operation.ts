import {
  isPracticeChange,
  validSessionId,
  type PracticeApi,
  type PracticeChange,
  type PracticeResult,
} from './practice-model.ts';
import type { AttemptStorage } from './learning-session.ts';
import { wholeRevision } from './practice-feedback-model.ts';

interface Dependencies {
  storage: AttemptStorage;
  api: Pick<PracticeApi, 'change' | 'receipt'>;
  online: () => boolean;
  onConfirmed: (
    change: PracticeChange,
    result: PracticeResult,
    active: () => boolean,
  ) => Promise<void>;
}
export interface OperationState {
  ready: boolean;
  pending: PracticeChange | null;
  phase: 'idle' | 'saving' | 'checking' | 'uncertain' | 'rejected';
  error: string | null;
  saved: { change: PracticeChange; result: PracticeResult } | null;
}
/** One journaled mutation per account. All automatic recovery is read-only. */
export class PracticeOperation {
  private state: OperationState = {
    ready: false,
    pending: null,
    phase: 'idle',
    error: null,
    saved: null,
  };
  private active = true;
  private busy = false;
  private restoring: Promise<void> | null = null;
  private listeners = new Set<() => void>();
  private userId: number;
  private deps: Dependencies;
  constructor(userId: number, deps: Dependencies) {
    this.userId = userId;
    this.deps = deps;
  }
  snapshot = () => this.state;
  consumeSaved = () => this.update({ saved: null });
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
  private update(patch: Partial<OperationState>) {
    if (!this.active) return;
    this.state = { ...this.state, ...patch };
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
      if (record?.userId === this.userId && !isPracticeChange(record.change))
        throw new Error('Invalid journal');
      const pending =
        record?.userId === this.userId
          ? (record.change as PracticeChange)
          : null;
      this.update({
        ready: true,
        pending,
        phase: pending ? 'uncertain' : 'idle',
        error: null,
      });
      if (pending) await this.check();
    } catch {
      this.update({
        error:
          'Couldn’t load pending practice changes. Try again before sending.',
        ready: false,
      });
    }
  }
  begin = async (input: PracticeChange) => {
    if (!this.active || !this.state.ready || this.busy || this.state.pending)
      return;
    if (!isPracticeChange(input)) {
      this.update({
        error: 'Check the content and size limits before saving or sending.',
      });
      return;
    }
    if (!this.deps.online()) {
      this.update({
        error:
          'Reconnect before saving or sending. Your draft stays on this device.',
      });
      return;
    }
    const change: PracticeChange = JSON.parse(JSON.stringify(input));
    this.update({ pending: change, saved: null });
    await this.submit(change);
  };
  retry = async () => {
    if (
      !this.active ||
      this.busy ||
      !this.state.pending ||
      this.state.phase === 'rejected'
    )
      return;
    if (!this.deps.online()) {
      this.update({ error: 'Reconnect before retrying.' });
      return;
    }
    await this.submit(this.state.pending);
  };
  private async submit(change: PracticeChange) {
    this.busy = true;
    this.update({ phase: 'saving', error: null });
    let journaled = false;
    try {
      await this.deps.storage.write(
        JSON.stringify({ userId: this.userId, change }),
      );
      journaled = true;
      if (!this.active) return;
      const result = await this.deps.api.change(change);
      if (!this.matches(change, result)) throw new Error('Unrecognized result');
      await this.confirm(change, result);
    } catch (error) {
      const failure = error as {
        status?: number;
        body?: { code?: string; retry_same_request?: boolean };
      };
      const rejected =
        !journaled ||
        (failure.status !== undefined &&
          [400, 403, 404, 409, 413].includes(failure.status)) ||
        failure.body?.retry_same_request === false;
      this.update({
        phase: rejected ? 'rejected' : 'uncertain',
        error: !journaled
          ? 'Couldn’t protect this request on your device. Nothing was sent. Keep your draft and try again.'
          : rejected
            ? change.kind === 'annotate'
              ? 'Your response was not accepted. Refresh and compare it with the current saved response before trying again.'
              : change.kind === 'submit'
                ? 'The snapshot was not accepted. Refresh and review the saved conversation and work before trying again.'
                : change.kind === 'feedback'
                  ? 'Feedback was not requested. Refresh this snapshot before trying again.'
                  : 'This change was not accepted. Refresh the conversation and review your draft before sending again.'
            : 'The result is not confirmed. Your original request is retained; checking or retrying it won’t create a duplicate.',
      });
    } finally {
      this.busy = false;
    }
    if (this.active && this.state.phase === 'uncertain') await this.check();
  }
  private matches(change: PracticeChange, result: PracticeResult) {
    if (
      change.kind === 'annotate' &&
      (result?.submission_sequence !== change.submission_sequence ||
        result.finding_id !== change.findingId ||
        typeof result.changed !== 'boolean' ||
        result.revision !== change.base_revision + Number(result.changed))
    )
      return false;
    if (change.kind === 'submit') {
      const snapshot = result?.submission;
      if (
        !snapshot ||
        !wholeRevision(snapshot.sequence, 1) ||
        snapshot.sequence <= change.expected_sequence ||
        snapshot.turn_sequence !== change.expected_sequence ||
        snapshot.through_sequence !== snapshot.sequence - 1 ||
        !result.brief ||
        !wholeRevision(result.brief.revision) ||
        typeof result.brief.changed !== 'boolean' ||
        result.brief.revision < change.brief.base_revision ||
        result.brief.revision > change.brief.base_revision + 1 ||
        snapshot.brief_revision !== result.brief.revision ||
        !Array.isArray(snapshot.checks) ||
        snapshot.checks.length !== change.edits.length ||
        new Set(snapshot.checks.map((c) => c.artifact_id)).size !==
          change.edits.length ||
        !snapshot.checks.every((check) => {
          const edit = change.edits.find(
            (e) => e.artifact_id === check.artifact_id,
          );
          const outcome = result.artifacts?.[check.artifact_id];
          return (
            edit &&
            outcome &&
            typeof outcome.changed === 'boolean' &&
            wholeRevision(check.revision) &&
            check.revision === outcome.revision &&
            check.revision >= edit.base_revision &&
            check.revision <= edit.base_revision + 1 &&
            check.language === edit.language
          );
        })
      )
        return false;
    }
    if (
      change.kind === 'feedback' &&
      (result?.submission_sequence !== change.submission_sequence ||
        !result.request ||
        !['pending', 'running', 'completed', 'unavailable'].includes(
          result.request.status,
        ) ||
        (result.request.status === 'unavailable'
          ? result.request.id !== null ||
            typeof result.request.reason !== 'string'
          : !validSessionId(result.request.id)))
    )
      return false;
    if (change.kind === 'artifact' || change.kind === 'brief') {
      const outcome =
        change.kind === 'brief'
          ? result?.brief
          : result?.artifacts?.[change.artifactId];
      if (
        !outcome ||
        !Number.isInteger(outcome.revision) ||
        outcome.revision < change.base_revision ||
        typeof outcome.changed !== 'boolean'
      )
        return false;
    }
    return (
      result &&
      validSessionId(result.session_id) &&
      (change.kind === 'start' || result.session_id === change.sessionId) &&
      (change.kind !== 'send' ||
        (Number.isInteger(result.sequence) &&
          result.sequence! > change.expected_sequence))
    );
  }
  check = async () => {
    const change = this.state.pending;
    if (
      !this.active ||
      this.busy ||
      !change ||
      this.state.phase === 'rejected' ||
      !this.deps.online()
    )
      return;
    this.busy = true;
    this.update({ phase: 'checking' });
    try {
      const { receipt } = await this.deps.api.receipt(change.request_id);
      if (!this.active) return;
      if (
        receipt?.operation ===
          (change.kind === 'artifact' || change.kind === 'brief'
            ? 'save'
            : change.kind) &&
        this.matches(change, receipt.response)
      )
        await this.confirm(change, receipt.response);
      else
        this.update({
          phase: 'uncertain',
          error:
            'No matching saved result is confirmed. Check again or retry the same request.',
        });
    } catch {
      this.update({
        phase: 'uncertain',
        error: 'Couldn’t check the result. Your original request is retained.',
      });
    } finally {
      this.busy = false;
    }
  };
  private async confirm(change: PracticeChange, result: PracticeResult) {
    if (!this.active) return;
    // Clear a matching draft before dropping the request ID. A crash at either
    // point can safely recover the same receipt without offering a second send.
    await this.deps.onConfirmed(change, result, () => this.active);
    if (!this.active) return;
    await this.deps.storage.clear();
    this.update({
      pending: null,
      phase: 'idle',
      error: null,
      saved: { change, result },
    });
  }
  dismissRejected = async () => {
    if (!this.active || this.busy || this.state.phase !== 'rejected')
      return false;
    this.busy = true;
    try {
      await this.deps.storage.clear();
      if (!this.active) return false;
      this.update({ pending: null, phase: 'idle', error: null });
      return true;
    } catch {
      this.update({
        error: 'Couldn’t clear this rejected request. Try again.',
      });
      return false;
    } finally {
      this.busy = false;
    }
  };
}
