import type { ConceptQuestion } from './concept-model.ts';

export const responseChoices = [
  { value: 'unreviewed', label: 'Not reviewed' },
  { value: 'agree', label: 'Agree' },
  { value: 'disagree', label: 'Disagree' },
] as const;
export type FeedbackDecision = (typeof responseChoices)[number]['value'];
export interface FeedbackAnnotation {
  revision: number;
  decision: FeedbackDecision;
  note: string;
  updated_at: string | null;
}
/** Public identities only; the server resolves private misconception mappings. */
export interface FeedbackSource {
  sessionId: string;
  submission_sequence: number;
  findingId: string;
}
export interface ResponseEdit {
  kind: 'annotate';
  submission_sequence: number;
  findingId: string;
  base_revision: number;
  decision: FeedbackDecision;
  note: string;
}
export interface FocusedReview {
  session: { id: string; concept_id: string };
  finding: { id: string; title: string };
  accepted: boolean;
  questions: ConceptQuestion[];
  total: number;
  completed: number;
  unavailable: number;
}
const whole = (n: unknown, min = 0): n is number =>
  typeof n === 'number' && Number.isInteger(n) && n >= min && n <= 2147483647;
export const validFindingId = (id: unknown): id is string =>
  typeof id === 'string' && /^[a-zA-Z0-9_-]{1,64}$/.test(id);
export function validFeedbackSource(value: unknown): value is FeedbackSource {
  if (!value || typeof value !== 'object') return false;
  const v = value as FeedbackSource;
  return (
    typeof v.sessionId === 'string' &&
    /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(v.sessionId) &&
    whole(v.submission_sequence, 1) &&
    validFindingId(v.findingId)
  );
}
export const normalizeResponseNote = (note: string) =>
  note.replace(/\r\n?/g, '\n');
export const responseNoteLength = (note: string) =>
  [...normalizeResponseNote(note)].length;
export function validResponseEdit(
  value: unknown,
  draft = false,
): value is ResponseEdit {
  if (!value || typeof value !== 'object') return false;
  const v = value as ResponseEdit;
  return (
    v.kind === 'annotate' &&
    whole(v.submission_sequence, 1) &&
    validFindingId(v.findingId) &&
    whole(v.base_revision) &&
    responseChoices.some((c) => c.value === v.decision) &&
    typeof v.note === 'string' &&
    v.note.length <= 4000 &&
    (draft ||
      (!v.note.includes('\0') &&
        !/[\uD800-\uDFFF]/u.test(v.note) &&
        responseNoteLength(v.note) <= 2000))
  );
}
export const responseKey = (edit: ResponseEdit) =>
  `${edit.submission_sequence}:${edit.findingId}`;
export const copyResponse = (edit: ResponseEdit): ResponseEdit => ({
  kind: 'annotate',
  submission_sequence: edit.submission_sequence,
  findingId: edit.findingId,
  base_revision: edit.base_revision,
  decision: edit.decision,
  note: normalizeResponseNote(edit.note),
});
export function responsePath(source: FeedbackSource) {
  return `/learning/practice/sessions/${encodeURIComponent(source.sessionId)}/submissions/${source.submission_sequence}/feedback/${encodeURIComponent(source.findingId)}`;
}
export function responseRoute(source: FeedbackSource, review = false) {
  return {
    pathname: review
      ? ('/learning/practice/[session]/focused-review' as const)
      : ('/learning/practice/[session]/response' as const),
    params: {
      session: source.sessionId,
      snapshot: String(source.submission_sequence),
      finding: source.findingId,
    },
  };
}
export function feedbackReturnRoute(conceptId: string, source: FeedbackSource) {
  return {
    pathname: '/learning/concepts/[id]/build' as const,
    params: {
      id: conceptId,
      practice_session: source.sessionId,
      work: 'feedback',
      snapshot: String(source.submission_sequence),
      finding: source.findingId,
    },
  };
}
