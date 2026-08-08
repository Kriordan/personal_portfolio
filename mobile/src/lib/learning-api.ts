import { apiRequest } from '@/lib/api-client';

// Shapes mirror project/api/learning.py and project/services/learning_service.py.

/** A rendered review card produced by learning_service.build_cards(). */
export interface ReviewCard {
  card_id: string;
  note_id: string;
  note_title: string;
  type: 'qa' | 'incident' | 'cloze' | 'command' | 'code_diff' | string;
  tags: string[];
  prompt: string;
  response: string;
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

export interface NoteDetail {
  id: string;
  title: string;
  created_at?: string;
  tags?: string[];
  summary: string;
  /** Rendered review cards (not the raw note flashcard JSON). */
  flashcards: ReviewCard[];
}

export interface NotesOverview {
  notes: NoteSummary[];
  total_due: number;
}

export interface RateCardInput {
  card_id: string;
  rating: number;
  response_ms?: number;
  session_id?: string;
}

export interface RateCardResponse {
  card_id: string;
  learning_state: string;
  interval: number;
  repetitions: number;
  easiness: number;
  next_review: string;
  next_review_display: string;
  scheduler_version: string;
}

/** Rating values matching the web review UI. */
export const RATINGS = [
  { value: 0, label: 'Again' },
  { value: 3, label: 'Hard' },
  { value: 4, label: 'Good' },
  { value: 5, label: 'Easy' },
] as const;

export const learningApi = {
  getNotes(): Promise<NotesOverview> {
    return apiRequest<NotesOverview>('/learning/notes');
  },

  getNote(noteId: string): Promise<{ note: NoteDetail }> {
    return apiRequest<{ note: NoteDetail }>(`/learning/notes/${encodeURIComponent(noteId)}`);
  },

  getReviewQueue(): Promise<{ cards: ReviewCard[] }> {
    return apiRequest<{ cards: ReviewCard[] }>('/learning/review');
  },

  rateCard(input: RateCardInput): Promise<RateCardResponse> {
    return apiRequest<RateCardResponse>('/learning/rate', {
      method: 'POST',
      body: input,
    });
  },
};

export const learningKeys = {
  all: ['learning'] as const,
  notes: () => ['learning', 'notes'] as const,
  note: (noteId: string) => ['learning', 'note', noteId] as const,
  review: () => ['learning', 'review'] as const,
};
