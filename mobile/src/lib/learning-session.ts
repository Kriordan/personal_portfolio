import {
  isStoredAttempt,
  type RateCardInput,
  type RateCardResponse,
  type ReviewCard,
} from './learning-model.ts';

export interface ConfirmedRating {
  input: RateCardInput;
  result: RateCardResponse;
}
export interface LearningActivity {
  ready: boolean;
  phase: 'idle' | 'saving' | 'checking' | 'uncertain' | 'conflict';
  attempt: RateCardInput | null;
  error: string | null;
  confirmed: readonly ConfirmedRating[];
}
export interface AttemptStorage {
  read: () => Promise<string | null>;
  write: (value: string) => Promise<void>;
  clear: () => Promise<void>;
}
interface Dependencies {
  storage: AttemptStorage;
  api: {
    rateCard: (input: RateCardInput) => Promise<RateCardResponse>;
    getReceipt: (id: string) => Promise<{ receipt: RateCardResponse | null }>;
  };
  online: () => boolean;
  uuid: () => string;
  onConfirmed: (active: () => boolean) => void;
}

/** One account's unresolved attempt survives navigation. Recovery only performs reads. */
export class LearningSession {
  private state: LearningActivity = {
    ready: false,
    phase: 'idle',
    attempt: null,
    error: null,
    confirmed: [],
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
  private update(change: Partial<LearningActivity>) {
    if (!this.active) return;
    this.state = { ...this.state, ...change };
    this.listeners.forEach((listener) => listener());
  }
  restore = () => {
    if (this.restoring) return this.restoring;
    this.restoring = this.load().finally(() => {
      this.restoring = null;
    });
    return this.restoring;
  };
  private async load() {
    try {
      const raw = await this.deps.storage.read();
      if (!this.active) return;
      const stored = raw ? JSON.parse(raw) : null;
      if (
        stored &&
        stored.userId === this.userId &&
        !isStoredAttempt(stored.input)
      )
        throw new Error('Invalid recovery record');
      const attempt =
        stored?.userId === this.userId ? (stored.input as RateCardInput) : null;
      this.update({
        ready: true,
        attempt,
        phase: attempt ? 'uncertain' : 'idle',
        error: null,
      });
      if (attempt) await this.check();
    } catch {
      this.update({
        ready: false,
        error: 'Couldn’t load saved review state. Try again before reviewing.',
      });
    }
  }
  begin = async (
    card: ReviewCard,
    rating: number,
    responseMs: number,
    sessionId: string,
  ) => {
    if (
      !this.active ||
      this.locked ||
      !this.state.ready ||
      this.state.attempt ||
      this.state.phase === 'conflict'
    )
      return;
    if (!this.deps.online()) {
      this.update({
        error:
          'You’re offline. Your answer is still here. Reconnect, then rate it again.',
      });
      return;
    }
    const input: RateCardInput = {
      card_id: card.card_id,
      rating,
      request_id: this.deps.uuid(),
      expected_revision: card.progress_revision,
      session_id: sessionId,
      response_ms: Math.min(86_400_000, Math.max(0, Math.round(responseMs))),
    };
    this.update({ attempt: input });
    await this.submit(input);
  };
  retry = async () => {
    if (
      !this.active ||
      this.locked ||
      this.checking ||
      !this.state.attempt ||
      this.state.phase === 'conflict'
    )
      return;
    if (!this.deps.online()) {
      this.update({
        error: 'You’re offline. Reconnect before retrying the same rating.',
      });
      return;
    }
    await this.submit(this.state.attempt);
  };
  private async submit(input: RateCardInput) {
    this.locked = true;
    this.update({ phase: 'saving', error: null });
    try {
      await this.deps.storage.write(
        JSON.stringify({ userId: this.userId, input }),
      );
      if (!this.active) return;
      const result = await this.deps.api.rateCard(input);
      await this.confirm(input, result);
    } catch (error) {
      if (!this.active) return;
      const status = (error as { status?: number })?.status;
      if (status && [400, 401, 403, 404, 409].includes(status)) {
        this.update({
          phase: 'conflict',
          error:
            status === 409
              ? 'This card changed elsewhere, or its saved attempt differs. Load a fresh queue before continuing.'
              : 'This rating could not be accepted. Load a fresh queue before continuing.',
        });
      } else {
        this.update({
          phase: 'uncertain',
          error:
            'Checking whether your rating saved. Your answer is still here.',
        });
      }
    } finally {
      this.locked = false;
    }
    if (this.active && this.state.phase === 'uncertain') await this.check();
  }
  check = async () => {
    const input = this.state.attempt;
    if (
      !this.active ||
      this.locked ||
      this.checking ||
      !input ||
      this.state.phase === 'conflict' ||
      !this.deps.online()
    )
      return;
    this.checking = true;
    this.update({ phase: 'checking' });
    try {
      const { receipt } = await this.deps.api.getReceipt(input.request_id);
      if (!this.active) return;
      if (receipt) await this.confirm(input, receipt);
      else
        this.update({
          phase: 'uncertain',
          error:
            'No saved result is confirmed yet. Check again, or deliberately retry the same rating; it will only be applied once.',
        });
    } catch {
      this.update({
        phase: 'uncertain',
        error:
          'Couldn’t check the save. Keeping your original rating for recovery.',
      });
    } finally {
      this.checking = false;
    }
  };
  private async confirm(input: RateCardInput, result: RateCardResponse) {
    if (
      result.request_id !== input.request_id ||
      result.card_id !== input.card_id ||
      result.rating !== input.rating ||
      typeof result.next_review_display !== 'string'
    )
      throw new Error('Unrecognized receipt');
    if (!this.active) return;
    await this.deps.storage.clear();
    if (!this.active) return;
    const confirmed = this.state.confirmed.some(
      (entry) => entry.input.request_id === input.request_id,
    )
      ? this.state.confirmed
      : [...this.state.confirmed, { input, result }];
    this.update({ attempt: null, phase: 'idle', error: null, confirmed });
    this.deps.onConfirmed(() => this.active);
  }
  dismissConflict = async () => {
    if (!this.active || this.locked || this.state.phase !== 'conflict')
      return false;
    try {
      await this.deps.storage.clear();
      if (!this.active) return false;
      this.update({ attempt: null, phase: 'idle', error: null });
      return true;
    } catch {
      this.update({ error: 'Couldn’t clear the rejected attempt. Try again.' });
      return false;
    }
  };
}
