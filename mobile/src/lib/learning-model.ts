import {
  validFeedbackSource,
  responsePath,
  responseRoute,
  type FeedbackSource,
} from './feedback-response-model.ts';

export interface ReviewCard {
  card_id: string;
  note_id: string;
  note_title: string;
  type: string;
  tags: string[];
  prompt: string;
  response: string;
  progress_revision: number;
  content_version?: number;
  response_sections?: { label: string; text: string; code: boolean }[];
}
export interface NoteSummary {
  id: string;
  title: string;
  created_at?: string;
  tags?: string[];
  summary: string;
  flashcard_count: number;
  due_count: number;
}
export interface NoteDetail extends NoteSummary {
  flashcards: ReviewCard[];
}
export interface NotesOverview {
  notes: NoteSummary[];
  total_due: number;
}
export interface ReviewQueue {
  cards: ReviewCard[];
  total_due: number;
}
export interface RateCardInput {
  request_id: string;
  expected_revision: number;
  card_id: string;
  rating: number;
  response_ms: number;
  session_id: string;
  content_version?: number;
  feedback_source?: FeedbackSource;
}
export interface RateCardResponse {
  request_id: string;
  card_id: string;
  rating: number;
  progress_revision: number;
  learning_state: string;
  interval: number;
  repetitions: number;
  easiness: number;
  next_review: string;
  next_review_display: string;
  scheduler_version: string;
  saved_at: string;
  content_version?: number;
}
export const RATINGS = [
  { value: 0, label: 'Again', description: 'I couldn’t recall it' },
  { value: 3, label: 'Hard', description: 'Correct, with difficulty' },
  { value: 4, label: 'Good', description: 'Correct, with some effort' },
  { value: 5, label: 'Easy', description: 'I knew it immediately' },
] as const;
export const NOTE_SORTS = [
  { value: 'due', label: 'Most due first' },
  { value: 'title', label: 'Title A–Z' },
  { value: 'newest', label: 'Newest created' },
] as const;
export type NoteSort = (typeof NOTE_SORTS)[number]['value'];
export const NOTE_FILTERS = [
  { value: 'all', label: 'All notes' },
  { value: 'due', label: 'Due notes' },
] as const;
export type NoteFilter = (typeof NOTE_FILTERS)[number]['value'];
const collator = new Intl.Collator(undefined, {
  numeric: true,
  sensitivity: 'base',
});
export function validNoteId(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    value.length <= 100 &&
    /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(value)
  );
}
/** Preserve the kind of review when recovering a stale, persisted rating. */
export function reviewRoute(
  input: Pick<RateCardInput, 'card_id' | 'content_version' | 'feedback_source'>,
) {
  if (input.feedback_source) return responseRoute(input.feedback_source, true);
  const id = input.card_id.split(':')[0];
  return input.content_version !== undefined && validNoteId(id)
    ? { pathname: '/learning/concepts/[id]/review' as const, params: { id } }
    : { pathname: '/learning/review' as const };
}
export function ratingPath(
  input: Pick<RateCardInput, 'card_id' | 'content_version' | 'feedback_source'>,
) {
  if (input.feedback_source)
    return `${responsePath(input.feedback_source)}/review`;
  return input.content_version === undefined
    ? '/learning/rate'
    : '/learning/concepts/' +
        encodeURIComponent(input.card_id.split(':')[0]) +
        '/rate';
}
/** Local recovery metadata never becomes server request content. */
export function ratingBody(input: RateCardInput) {
  if (input.feedback_source)
    return {
      request_id: input.request_id,
      card_id: input.card_id,
      rating: input.rating,
      content_version: input.content_version,
      expected_revision: input.expected_revision,
    };
  const { feedback_source: _source, ...body } = input;
  return body;
}
export function browseNotes(
  notes: readonly NoteSummary[],
  search: string,
  filter: NoteFilter,
  sort: NoteSort,
) {
  const terms = search.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return notes
    .filter((note) => {
      const text =
        `${note.title} ${note.summary} ${(note.tags ?? []).join(' ')}`.toLocaleLowerCase();
      return (
        (filter === 'all' || note.due_count > 0) &&
        terms.every((term) => text.includes(term))
      );
    })
    .sort((a, b) => {
      const primary =
        sort === 'due'
          ? b.due_count - a.due_count
          : sort === 'newest'
            ? (Date.parse(b.created_at ?? '') || 0) -
              (Date.parse(a.created_at ?? '') || 0)
            : 0;
      return (
        primary ||
        collator.compare(a.title, b.title) ||
        a.id.localeCompare(b.id)
      );
    });
}
export const learningKeys = {
  all: ['learning'] as const,
  notes: () => ['learning', 'notes'] as const,
  details: () => ['learning', 'note'] as const,
  note: (id: string) => ['learning', 'note', id] as const,
  review: (userId: number, noteId?: string) =>
    ['learning', 'review', userId, noteId ?? 'all'] as const,
};
export function isStoredAttempt(value: unknown): value is RateCardInput {
  if (!value || typeof value !== 'object') return false;
  const input = value as RateCardInput;
  return (
    typeof input.request_id === 'string' &&
    /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(input.request_id) &&
    typeof input.card_id === 'string' &&
    input.card_id.length <= 128 &&
    input.card_id.includes(':') &&
    Number.isInteger(input.expected_revision) &&
    input.expected_revision >= 0 &&
    (input.content_version === undefined ||
      (Number.isInteger(input.content_version) &&
        input.content_version > 0 &&
        input.content_version <= 2147483647)) &&
    RATINGS.some((rating) => rating.value === input.rating) &&
    Number.isInteger(input.response_ms) &&
    input.response_ms >= 0 &&
    input.response_ms <= 86_400_000 &&
    typeof input.session_id === 'string' &&
    input.session_id.length > 0 &&
    input.session_id.length <= 64 &&
    (input.feedback_source === undefined ||
      (input.content_version !== undefined &&
        validFeedbackSource(input.feedback_source)))
  );
}
