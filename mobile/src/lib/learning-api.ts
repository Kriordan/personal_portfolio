import { apiRequest } from '@/lib/api-client';
import type {
  NoteDetail,
  NotesOverview,
  RateCardInput,
  RateCardResponse,
  ReviewQueue,
} from './learning-model';

export * from './learning-model';
export const learningApi = {
  getNotes: () => apiRequest<NotesOverview>('/learning/notes'),
  getNote: (id: string) =>
    apiRequest<{ note: NoteDetail }>(
      `/learning/notes/${encodeURIComponent(id)}`,
    ),
  getReviewQueue: (noteId?: string) =>
    apiRequest<ReviewQueue>(
      `/learning/review?limit=20${noteId ? `&note_id=${encodeURIComponent(noteId)}` : ''}`,
    ),
  rateCard: (input: RateCardInput) =>
    apiRequest<RateCardResponse>('/learning/rate', {
      method: 'POST',
      body: input,
      timeoutMs: 30_000,
    }),
  getReceipt: (id: string) =>
    apiRequest<{ receipt: RateCardResponse | null }>(
      `/learning/ratings/${encodeURIComponent(id)}`,
      { timeoutMs: 10_000 },
    ),
};
