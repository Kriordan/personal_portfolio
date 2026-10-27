import {
  validExtractionRequest,
  type Extraction,
  type ExtractionRequest,
} from './job-extraction-model.ts';
interface Dependencies {
  storage: {
    read(): Promise<string | null>;
    write(value: string): Promise<void>;
    clear(): Promise<void>;
  };
  api: {
    start(request: ExtractionRequest): Promise<{ extraction: Extraction }>;
    summarize(id: string): Promise<{ extraction: Extraction }>;
    get(id: string): Promise<{ extraction: Extraction }>;
  };
  uuid(): string;
  online(): boolean;
  foreground(): boolean;
}
interface State {
  ready: boolean;
  working: boolean;
  uncertain: boolean;
  missing: boolean;
  request: ExtractionRequest | null;
  result: Extraction | null;
  error: string | null;
  stage: 'read' | 'summary';
}
/** Persist only the account and frozen request. Recovery is always a status read. */
export class ExtractionSession {
  private state: State = {
    ready: false,
    working: false,
    uncertain: false,
    missing: false,
    request: null,
    result: null,
    error: null,
    stage: 'read',
  };
  private listeners = new Set<() => void>();
  private active = true;
  private lock = false;
  private loading: Promise<void> | null = null;
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
  private update(values: Partial<State>) {
    if (this.active) {
      this.state = { ...this.state, ...values };
      this.listeners.forEach((fn) => fn());
    }
  }
  restore = () => {
    if (!this.loading)
      this.loading = this.load().finally(() => {
        this.loading = null;
      });
    return this.loading;
  };
  private async load() {
    try {
      const raw = await this.deps.storage.read();
      if (!this.active) return;
      const saved = raw ? JSON.parse(raw) : null;
      if (
        saved?.userId === this.userId &&
        !validExtractionRequest(saved.request)
      )
        throw new Error();
      this.update({
        ready: true,
        request: saved?.userId === this.userId ? saved.request : null,
        error: null,
      });
      await this.check();
    } catch {
      this.update({
        error:
          'Couldn’t restore suggestion status. Try again; manual saving is available.',
      });
    }
  }
  private receive(result: Extraction) {
    if (
      result.id !== this.state.request?.request_id ||
      result.source_url !== this.state.request.listing_url ||
      result.job_id !== (this.state.request.job_id ?? null)
    )
      throw new Error('Invalid receipt');
    this.update({
      result,
      stage: result.stage,
      uncertain: result.status === 'running',
      missing: false,
      error: result.error_message,
    });
  }
  private async forgetRequest() {
    try {
      await this.deps.storage.clear();
      this.update({ request: null });
    } catch {
      // Keep the frozen UUID when durable cleanup fails; replay remains safe.
    }
  }
  check = async () => {
    const request = this.state.request;
    if (!this.active || this.lock || !request || !this.deps.online()) return;
    this.lock = true;
    try {
      this.receive((await this.deps.api.get(request.request_id)).extraction);
    } catch (error) {
      if (!this.active) return;
      const status = (error as { status?: number }).status;
      if (status === 410) await this.forgetRequest();
      this.update({
        ...([404, 410].includes(status ?? 0) ? { result: null } : {}),
        uncertain: status !== 410,
        missing: status === 404,
        error:
          status === 410
            ? 'Suggestions expired after 24 hours. Read the listing again.'
            : status === 404
              ? 'No saved result was found for the previous suggestion request. Retry that same request to resolve it safely.'
              : 'Completion is not confirmed. Check status or deliberately retry the same request.',
      });
    } finally {
      this.lock = false;
    }
  };
  begin = async (
    input: Omit<ExtractionRequest, 'request_id'>,
    mayContinue: () => boolean = () => false,
  ) => {
    if (
      !this.active ||
      !this.state.ready ||
      this.lock ||
      this.state.uncertain
    )
      return;
    if (!this.deps.online()) {
      this.update({
        error: 'Reconnect to suggest details. Manual saving is available.',
      });
      return;
    }
    const request = { ...input, request_id: this.deps.uuid() };
    this.lock = true;
    try {
      await this.deps.storage.write(
        JSON.stringify({ userId: this.userId, request }),
      );
      if (!this.active) return;
      this.update({
        request,
        result: null,
        error: null,
        uncertain: false,
        missing: false,
        stage: 'read',
      });
    } catch {
      this.update({
        error: 'Couldn’t store recovery information. Nothing was sent.',
      });
      return;
    } finally {
      this.lock = false;
    }
    await this.send('read');
    if (
      this.active &&
      this.deps.foreground() &&
      mayContinue() &&
      this.state.result?.can_summarize
    )
      await this.continue();
  };
  retrySame = async (mayContinue: () => boolean = () => false) => {
    if (!this.state.result) {
      await this.send('read');
      if (
        this.active &&
        this.deps.foreground() &&
        mayContinue() &&
        this.snapshot().result?.can_summarize
      )
        await this.continue();
    }
  };
  continue = async () => {
    if (this.state.result?.status === 'ready') await this.send('summary');
  };
  private async send(stage: 'read' | 'summary') {
    const request = this.state.request;
    if (!this.active || this.lock || !request || !this.deps.online()) return;
    this.lock = true;
    this.update({ working: true, stage, error: null, missing: false });
    try {
      this.receive(
        (
          await (stage === 'read'
            ? this.deps.api.start(request)
            : this.deps.api.summarize(request.request_id))
        ).extraction,
      );
    } catch (error) {
      // A late response from an old account must never clear the new account's
      // durable recovery record or start another stage.
      if (!this.active) return;
      const status = (error as { status?: number }).status;
      const code = (error as { body?: { code?: unknown } }).body?.code;
      const definitive =
        (status && [400, 401, 403, 404, 409, 410, 429].includes(status)) ||
        (status === 503 && code === 'unavailable');
      // These read-stage rejections occur before provider work. Do not restore
      // them as an uncertain paid operation after returning to the form.
      if (status === 410 || (stage === 'read' && definitive && !this.state.result))
        await this.forgetRequest();
      this.update({
        ...(status === 410 ? { result: null } : {}),
        uncertain: !definitive,
        missing: false,
        error: definitive
          ? (error as Error).message ||
            'The suggestion request was rejected. Check the listing URL and try again.'
          : 'Completion is not confirmed. Check status before retrying.',
      });
    } finally {
      this.lock = false;
      this.update({ working: false });
    }
    if (this.active && this.state.uncertain) await this.check();
  }
}
