import {
  validWorkEdit,
  type BriefEntry,
  type WorkEdit,
} from './practice-work-model.ts';

export const validSessionId = (id: unknown): id is string =>
  typeof id === 'string' &&
  /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(id);
export const messageBytes = (body: string) =>
  new TextEncoder().encode(body).length;
export const MESSAGE_LIMIT = 8192;
export interface PracticeSessionInfo {
  id: string;
  concept_id: string;
  exercise_id: string;
  exercise_version: number;
  exercise_title: string;
  status: string;
  interaction_style: string;
  created_at: string;
  updated_at: string;
}
export interface PracticeMessage {
  sequence: number;
  role: string;
  body: string;
  created_at: string;
  hint: boolean;
  artifact_revisions: { artifact_id: string; revision: number }[];
  brief_revision: number | null;
}
export interface PracticeArtifact {
  artifact_id: string;
  title: string;
  format: string;
  instructions: string;
  languages: string[];
  revision: number;
  language: string;
  body: string;
  saved_at: string | null;
}
export interface ReplyState {
  id: string | null;
  status: string;
  error: string | null;
  turn_sequence: number | null;
  answered: boolean;
  can_request: boolean;
  can_continue_recent: boolean;
  unavailable: string | null;
  too_large_part: string | null;
}
export interface PracticeDetail {
  session: PracticeSessionInfo;
  brief: {
    scenario: string;
    learning_objectives: string[];
    functional_requirements: string[];
    nonfunctional_requirements: string[];
  };
  session_brief: {
    revision: number;
    entries: BriefEntry[];
  };
  artifacts: PracticeArtifact[];
  messages: PracticeMessage[];
  reply: ReplyState;
  revealed_requirements: { id: string; fact: string; sequence: number }[];
  context_choices: { sequence: number; from_sequence: number }[];
  check_in_due: boolean;
  learner_turns: number;
  feedback_pending: unknown;
  ai_budget: null | {
    exhausted: boolean;
    warning: boolean;
    spent_microusd: number;
    cap_microusd: number;
    total?: {
      exhausted: boolean;
      spent_microusd: number;
      cap_microusd: number;
    };
  };
}
export interface ArtifactVersion {
  artifact: Pick<PracticeArtifact, 'artifact_id' | 'title' | 'format'>;
  revision: {
    revision: number;
    language: string;
    body: string;
    created_at: string;
  };
  current_revision: number;
}
export type PracticeChange = { request_id: string; conceptId: string } & (
  | { kind: 'start'; exerciseId: string }
  | {
      kind: 'send';
      sessionId: string;
      body: string;
      expected_sequence: number;
      artifact_revisions: Record<string, number>;
      brief_revision: number;
    }
  | {
      kind: 'reply';
      sessionId: string;
      expected_sequence: number;
      context?: 'recent';
    }
  | { kind: 'pause' | 'resume'; sessionId: string }
  | (WorkEdit & { sessionId: string })
);
export interface PracticeResult {
  session_id: string;
  sequence?: number;
  artifacts?: Record<string, { revision: number; changed: boolean }>;
  brief?: { revision: number; changed: boolean };
}
export interface PracticeReceipt {
  operation: string;
  response: PracticeResult;
}
export interface PracticeApi {
  list: () => Promise<{ sessions: PracticeSessionInfo[] }>;
  detail: (id: string) => Promise<PracticeDetail>;
  revision: (
    id: string,
    artifact: string,
    revision: number,
  ) => Promise<ArtifactVersion>;
  change: (change: PracticeChange) => Promise<PracticeResult>;
  receipt: (id: string) => Promise<{ receipt: PracticeReceipt | null }>;
}
export const practiceKeys = {
  all: ['learning', 'practice'] as const,
  list: (user: number) => ['learning', 'practice', user, 'list'] as const,
  detail: (user: number, id: string) =>
    ['learning', 'practice', user, 'session', id] as const,
  revision: (user: number, id: string, artifact: string, revision: number) =>
    ['learning', 'practice', user, 'revision', id, artifact, revision] as const,
};
export const latestSequence = (detail: PracticeDetail) =>
  detail.messages.at(-1)?.sequence ?? 0;
export const replyLive = (reply: ReplyState) =>
  ['pending', 'running'].includes(reply.status);
export function sendChange(
  detail: PracticeDetail,
  body: string,
  requestId: string,
): PracticeChange {
  return {
    kind: 'send',
    request_id: requestId,
    conceptId: detail.session.concept_id,
    sessionId: detail.session.id,
    body,
    expected_sequence: latestSequence(detail),
    artifact_revisions: Object.fromEntries(
      detail.artifacts.map((a) => [a.artifact_id, a.revision]),
    ),
    brief_revision: detail.session_brief.revision,
  };
}
const whole = (n: unknown) =>
  typeof n === 'number' && Number.isInteger(n) && n >= 0 && n <= 2147483647;
export function isPracticeChange(value: unknown): value is PracticeChange {
  if (!value || typeof value !== 'object') return false;
  const c = value as PracticeChange;
  if (
    !validSessionId(c.request_id) ||
    typeof c.conceptId !== 'string' ||
    !/^[a-z0-9-]{1,100}$/.test(c.conceptId)
  )
    return false;
  if (c.kind === 'start')
    return (
      typeof c.exerciseId === 'string' &&
      /^[a-z0-9-]{1,128}$/.test(c.exerciseId)
    );
  if (!('sessionId' in c) || !validSessionId(c.sessionId)) return false;
  if (c.kind === 'pause' || c.kind === 'resume') return true;
  if (c.kind === 'artifact' || c.kind === 'brief') return validWorkEdit(c);
  if (c.kind === 'reply')
    return (
      whole(c.expected_sequence) &&
      (c.context === undefined || c.context === 'recent')
    );
  return (
    c.kind === 'send' &&
    typeof c.body === 'string' &&
    !!c.body.trim() &&
    messageBytes(c.body) <= MESSAGE_LIMIT &&
    whole(c.expected_sequence) &&
    whole(c.brief_revision) &&
    !!c.artifact_revisions &&
    typeof c.artifact_revisions === 'object' &&
    !Array.isArray(c.artifact_revisions) &&
    Object.entries(c.artifact_revisions).every(
      ([id, revision]) => /^[a-z0-9-]{1,128}$/.test(id) && whole(revision),
    )
  );
}
export function replyNotice(reply: ReplyState): string {
  if (replyLive(reply))
    return 'The interviewer is replying. You can leave and return; the reply will be saved.';
  if (reply.answered) return '';
  if (reply.can_continue_recent)
    return 'This conversation is too long for one reply. You can explicitly continue with recent messages; the full history stays saved.';
  if (reply.unavailable === 'essential_too_large')
    return 'The saved work is too large for the interviewer. Shorten the indicated work on the web, then send a new message. Nothing has been omitted.';
  if (reply.unavailable === 'budget')
    return 'The spending allowance cannot cover another reply. Your conversation and work are still available.';
  if (reply.unavailable)
    return 'AI replies are unavailable right now. You can still read your work and save a message.';
  if (reply.can_request)
    return 'Your message is saved. Request a reply when you’re ready; retries use the existing spending allowance.';
  return '';
}
