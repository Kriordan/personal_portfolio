import {
  storedOperation,
  type CaptureStatus,
  type JobOperation,
  type JobResult,
} from './jobwizard-model.ts';
export interface JobActivity {
  ready: boolean;
  phase: 'idle' | 'saving' | 'checking' | 'uncertain' | 'rejected';
  attempt: JobOperation | null;
  error: string | null;
  confirmed: {
    operation: JobOperation;
    result: JobResult | { capture: CaptureStatus };
  } | null;
}
interface Dependencies {
  storage: {
    read(): Promise<string | null>;
    write(value: string): Promise<void>;
    clear(): Promise<void>;
  };
  api: {
    submit(op: JobOperation): Promise<JobResult | { capture: CaptureStatus }>;
    getReceipt(id: string): Promise<{ receipt: JobResult | null }>;
    getCapture(
      id: number,
      requestId: string,
    ): Promise<{ capture: CaptureStatus }>;
  };
  online(): boolean;
  uuid(): string;
  onConfirmed(
    result: JobResult | { capture: CaptureStatus },
    active: () => boolean,
  ): void;
}
/** One unresolved operation per account. Recovery never sends a mutation. */
export class JobSession {
  private state: JobActivity = {
    ready: false,
    phase: 'idle',
    attempt: null,
    error: null,
    confirmed: null,
  };
  private listeners = new Set<() => void>();
  private active = true;
  private locked = false;
  private checking = false;
  private restoring: Promise<void> | null = null;
  private userId: number;
  private deps: Dependencies;
  constructor(userId: number, deps: Dependencies) {
    this.userId = userId;
    this.deps = deps;
  }
  snapshot = () => this.state;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  dispose = () => {
    this.active = false;
    this.listeners.clear();
  };
  private update(next: Partial<JobActivity>) {
    if (this.active) {
      this.state = { ...this.state, ...next };
      this.listeners.forEach((fn) => fn());
    }
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
      const saved = raw ? JSON.parse(raw) : null;
      if (saved?.userId === this.userId && !storedOperation(saved.operation))
        throw new Error('Invalid recovery state');
      const attempt =
        saved?.userId === this.userId
          ? (saved.operation as JobOperation)
          : null;
      this.update({
        ready: true,
        attempt,
        phase: attempt ? 'uncertain' : 'idle',
        error: null,
      });
      if (attempt) await this.check();
    } catch {
      this.update({
        error:
          'Couldn’t load saved operation state. Try again before making changes.',
      });
    }
  }
  begin = async (
    operation: Omit<JobOperation, 'input'> & {
      input: Omit<JobOperation['input'], 'request_id'>;
    },
  ) => {
    if (!this.active || !this.state.ready || this.locked || this.state.attempt)
      return;
    if (!this.deps.online()) {
      this.update({
        error:
          'You’re offline. Your draft is still here. Reconnect, then save again.',
      });
      return;
    }
    const op: JobOperation = {
      ...operation,
      input: { ...operation.input, request_id: this.deps.uuid() },
    };
    this.update({ attempt: op, confirmed: null });
    await this.submit(op);
  };
  retry = async () => {
    if (
      !this.active ||
      this.locked ||
      this.checking ||
      !this.state.attempt ||
      this.state.phase === 'rejected'
    )
      return;
    if (!this.deps.online()) {
      this.update({ error: 'Reconnect before retrying the same operation.' });
      return;
    }
    await this.submit(this.state.attempt);
  };
  private async submit(operation: JobOperation) {
    this.locked = true;
    this.update({ phase: 'saving', error: null });
    let persisted = false;
    try {
      await this.deps.storage.write(
        JSON.stringify({ userId: this.userId, operation }),
      );
      persisted = true;
      if (!this.active) return;
      await this.accept(operation, await this.deps.api.submit(operation));
    } catch (error) {
      if (!this.active) return;
      const status = (error as { status?: number })?.status;
      if (!persisted)
        this.update({
          phase: 'idle',
          attempt: null,
          error:
            'Couldn’t store recovery state. Nothing was sent; your draft is still here.',
        });
      else if (status && [400, 401, 403, 404, 409].includes(status))
        this.update({
          phase: 'rejected',
          error:
            status === 409
              ? 'This job changed elsewhere. Keep your draft and compare the latest version before saving again.'
              : 'The operation was rejected. Check the fields and reload the job before trying again.',
        });
      else
        this.update({
          phase: 'uncertain',
          error:
            'Completion isn’t confirmed yet. Checking the server; no new operation will run automatically.',
        });
    } finally {
      this.locked = false;
    }
    if (this.active && this.state.phase === 'uncertain') await this.check();
  }
  check = async () => {
    const operation = this.state.attempt;
    if (
      !this.active ||
      this.locked ||
      this.checking ||
      !operation ||
      this.state.phase === 'rejected' ||
      !this.deps.online()
    )
      return;
    this.checking = true;
    this.update({ phase: 'checking' });
    try {
      const result =
        operation.kind === 'capture'
          ? await this.deps.api.getCapture(
              operation.jobId!,
              operation.input.request_id,
            )
          : (await this.deps.api.getReceipt(operation.input.request_id))
              .receipt;
      if (result) await this.accept(operation, result);
      else
        this.update({
          phase: 'uncertain',
          error:
            'No saved result is confirmed yet. Check again or explicitly retry the same operation; its request ID prevents duplication.',
        });
    } catch {
      this.update({
        phase: 'uncertain',
        error:
          'Couldn’t check completion. Your original operation is kept for recovery.',
      });
    } finally {
      this.checking = false;
    }
  };
  private async accept(
    operation: JobOperation,
    result: JobResult | { capture: CaptureStatus },
  ) {
    if (!this.active) return;
    if (operation.kind === 'capture') {
      if (!('capture' in result)) throw new Error('Invalid receipt');
      if (result.capture.unavailable) {
        this.update({
          phase: 'rejected',
          error:
            'Screenshot capture is unavailable. Your job is already saved.',
        });
        return;
      }
      if (
        !result.capture.requested ||
        result.capture.requested.status === 'running'
      ) {
        this.update({
          phase: 'uncertain',
          error: result.capture.busy
            ? 'Capturing screenshot. You can leave this screen; status will be checked when you return.'
            : 'Capture isn’t confirmed. Check status before retrying the same attempt.',
        });
        return;
      }
      if (result.capture.requested.id !== operation.input.request_id)
        throw new Error('Invalid receipt');
    } else if (
      !('job' in result) ||
      result.request_id !== operation.input.request_id ||
      result.job.user_id !== this.userId ||
      (operation.jobId !== null && result.job.id !== operation.jobId)
    )
      throw new Error('Invalid receipt');
    await this.deps.storage.clear();
    if (!this.active) return;
    this.update({
      attempt: null,
      phase: 'idle',
      error: null,
      confirmed: { operation, result },
    });
    this.deps.onConfirmed(result, () => this.active);
  }
  clearRejection = async () => {
    if (!this.active || this.locked || this.state.phase !== 'rejected')
      return false;
    try {
      await this.deps.storage.clear();
      if (!this.active) return false;
      this.update({ phase: 'idle', attempt: null, error: null });
      return true;
    } catch {
      this.update({ error: 'Couldn’t clear the rejected attempt. Try again.' });
      return false;
    }
  };
}
