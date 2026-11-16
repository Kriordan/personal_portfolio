import type { PracticeChange, PracticeDetail } from './practice-model.ts';
import {
  copyWork,
  validWorkEdit,
  type BriefEntry,
} from './practice-work-model.ts';

export interface SnapshotCheck {
  artifact_id: string;
  revision: number;
  language: string;
  status: 'passed' | 'error' | 'not_checked';
  code: string;
  message: string;
  line: number | null;
  column: number | null;
}
export interface PracticeSnapshot {
  sequence: number;
  created_at: string;
  exercise_id: string;
  exercise_version: number;
  exercise_spec_version: number;
  profile_version: string;
  through_sequence: number;
  turn_sequence: number;
  brief_revision: number;
  checker_version: string;
  checks: SnapshotCheck[];
}
export interface SnapshotDetail {
  session: PracticeDetail['session'];
  submission: PracticeSnapshot;
  session_brief: PracticeDetail['session_brief'];
  artifacts: {
    artifact_id: string;
    title: string;
    current_revision: number;
  }[];
}
export interface SnapshotInput {
  expected_sequence: number;
  edits: {
    artifact_id: string;
    base_revision: number;
    language: string;
    body: string;
  }[];
  brief: { base_revision: number; entries: BriefEntry[] };
}
export interface FeedbackRequest {
  id: string | null;
  status: string;
  reason: string | null;
}
export type FeedbackEvidence = {
  source_id: string;
  quote: string;
  line: number;
} & (
  | { kind: 'turn'; sequence: number }
  | { kind: 'artifact'; artifact_id: string; revision: number }
  | { kind: 'note'; entry_id: string; revision: number }
);
export interface FeedbackFinding {
  id: string;
  kind: 'strength' | 'concern' | 'tradeoff' | 'not_observed';
  dimension_label: string;
  title: string;
  explanation: string;
  next_step: string;
  evidence: FeedbackEvidence[];
  remediation: { concept_id: string; section_id: string }[];
}
export interface FeedbackDetail {
  submission_sequence: number;
  request: FeedbackRequest;
  unavailable: string | null;
  busy: string | null;
  can_request: boolean;
  feedback: null | {
    request_id: string;
    created_at: string;
    summary: string;
    findings: FeedbackFinding[];
    coverage: {
      complete_snapshot: boolean;
      through_sequence: number;
      turn_count: number;
      learner_turn_count: number;
      artifact_revisions: { artifact_id: string; revision: number }[];
      brief_revision: number;
      hints_given: number;
    };
  };
}
export const wholeRevision = (n: unknown, minimum = 0): n is number =>
  typeof n === 'number' &&
  Number.isInteger(n) &&
  n >= minimum &&
  n <= 2147483647;
export function validSnapshotInput(input: SnapshotInput) {
  return (
    wholeRevision(input.expected_sequence) &&
    Array.isArray(input.edits) &&
    input.edits.length > 0 &&
    input.edits.length <= 20 &&
    new Set(input.edits.map((e) => e?.artifact_id)).size ===
      input.edits.length &&
    input.edits.every(
      (e) =>
        e &&
        validWorkEdit({
          kind: 'artifact',
          artifactId: e.artifact_id,
          base_revision: e.base_revision,
          language: e.language,
          body: e.body,
        }),
    ) &&
    !!input.brief &&
    validWorkEdit({
      kind: 'brief',
      base_revision: input.brief.base_revision,
      entries: input.brief.entries,
    })
  );
}
/** Snapshot only the displayed saved work. Local edits must be resolved first. */
export function snapshotChange(
  detail: PracticeDetail,
  requestId: string,
): PracticeChange {
  const brief = copyWork({
    kind: 'brief',
    base_revision: detail.session_brief.revision,
    entries: detail.session_brief.entries,
  });
  if (brief.kind !== 'brief') throw new Error('Invalid brief');
  return {
    kind: 'submit',
    request_id: requestId,
    conceptId: detail.session.concept_id,
    sessionId: detail.session.id,
    expected_sequence: detail.messages.at(-1)?.sequence ?? 0,
    edits: detail.artifacts.map((a) => ({
      artifact_id: a.artifact_id,
      base_revision: a.revision,
      language: a.language,
      body: a.body,
    })),
    brief: { base_revision: brief.base_revision, entries: brief.entries },
  };
}
export function snapshotBlock(
  detail: PracticeDetail,
  local: {
    ready: boolean;
    error: boolean;
    saving: boolean;
    edits: number;
    message: string;
  },
) {
  if (!local.ready || local.error || local.saving)
    return 'Wait until this device’s drafts are loaded and protected.';
  if (local.edits)
    return 'Save or discard your Build drafts before creating a snapshot.';
  if (local.message.trim())
    return 'Send or clear your unsent message in Discuss before creating a snapshot.';
  if (!['active', 'paused'].includes(detail.session.status))
    return 'This session is closed.';
  if (
    ['pending', 'running'].includes(detail.reply.status) ||
    detail.feedback_pending
  )
    return 'Wait for the current AI request to finish before saving another snapshot. You can keep editing.';
  return null;
}
export function snapshotIsOlder(
  detail: PracticeDetail,
  snapshot: PracticeSnapshot,
) {
  return (
    (detail.messages.at(-1)?.sequence ?? 0) !== snapshot.turn_sequence ||
    detail.session_brief.revision !== snapshot.brief_revision ||
    detail.artifacts.some(
      (a) =>
        snapshot.checks.find((c) => c.artifact_id === a.artifact_id)
          ?.revision !== a.revision,
    )
  );
}
export const feedbackKinds = {
  strength: 'Strength',
  concern: 'Concern to review',
  tradeoff: 'Trade-off',
  not_observed: 'Not observed',
};
export function feedbackNotice(reason: string | null | undefined) {
  if (!reason) return '';
  if (reason === 'budget')
    return 'The remaining AI allowance cannot cover this assessment. Your snapshot is saved; the spending limits have not changed.';
  if (reason === 'context_too_large')
    return 'This complete snapshot is too large for one assessment. Nothing was silently omitted. You can revisit saved feedback or start a smaller, focused exercise.';
  if (reason === 'disabled' || reason === 'owner_only')
    return 'AI feedback is unavailable for this account right now. Your snapshot and syntax checks are still available.';
  return 'Feedback was interrupted or could not be saved. It will not retry automatically. A new attempt may use more of your AI allowance.';
}
/** Sources are original learner records, never newer notes or a substitute turn. */
export function evidenceText(
  evidence: FeedbackEvidence,
  detail: PracticeDetail,
  snapshot: SnapshotDetail,
) {
  if (snapshot.session.id !== detail.session.id) return null;
  let body: string | undefined;
  if (
    evidence.kind === 'turn' &&
    evidence.sequence <= snapshot.submission.turn_sequence
  )
    body = detail.messages.find(
      (m) => m.sequence === evidence.sequence && m.role === 'learner',
    )?.body;
  if (
    evidence.kind === 'note' &&
    evidence.revision === snapshot.submission.brief_revision &&
    evidence.revision === snapshot.session_brief.revision
  )
    body = snapshot.session_brief.entries.find(
      (n) => n.id === evidence.entry_id,
    )?.text;
  return body?.includes(evidence.quote) ? body : null;
}
