export interface ConceptProgress {
  concept_id: string;
  revision: number;
  reading_version: number | null;
  reading_section: string | null;
  enrolled_at: string;
  updated_at: string;
}
export interface ConceptSummary {
  id: string;
  title: string;
  version: number;
  summary: string;
  draft: boolean;
  due_count: number;
  progress: ConceptProgress | null;
}
export interface Concept {
  id: string;
  version: number;
  kind: 'concept';
  title: string;
  private_pilot_draft?: boolean;
  local_draft?: boolean;
  content: {
    summary: string;
    learning_objectives: string[];
    prerequisite_knowledge: string[];
    sections: { id: string; title: string; markdown: string }[];
    references: { title: string; url: string }[];
  };
}
export interface ConceptDetail {
  concept: Concept;
  progress: ConceptProgress | null;
  due_count: number;
}
export interface ConceptQuestion {
  card_id: string;
  content_version: number;
  progress_revision: number;
  note_id: string;
  note_title: string;
  prompt: string;
  remediation_section_id: string;
}
export interface ConceptAnswer extends Omit<
  ConceptQuestion,
  'progress_revision'
> {
  answer: string;
  explanation: string;
}
export interface ConceptQueue {
  cards: ConceptQuestion[];
  total_due: number;
  progress: ConceptProgress | null;
}
export type StudyChange =
  | { kind: 'enroll'; conceptId: string }
  | {
      kind: 'position';
      conceptId: string;
      content_version: number;
      section_id: string;
      expected_revision: number;
      request_id: string;
    };
export const conceptKeys = {
  all: ['learning', 'concepts'] as const,
  list: (userId: number) => ['learning', 'concepts', userId, 'list'] as const,
  detail: (userId: number, id: string) =>
    ['learning', 'concepts', userId, 'detail', id] as const,
  review: (userId: number, id: string) =>
    ['learning', 'concepts', userId, 'review', id] as const,
};
export function initialSection(
  concept: Concept,
  progress: ConceptProgress | null,
  requested?: string,
) {
  return (
    concept.content.sections.find((section) => section.id === requested)?.id ??
    concept.content.sections.find(
      (section) => section.id === progress?.reading_section,
    )?.id ??
    concept.content.sections[0]?.id
  );
}
export function isStudyChange(value: unknown): value is StudyChange {
  if (!value || typeof value !== 'object') return false;
  const change = value as StudyChange;
  if (
    typeof change.conceptId !== 'string' ||
    !/^[a-z0-9][a-z0-9-]{0,99}$/.test(change.conceptId)
  )
    return false;
  if (change.kind === 'enroll') return true;
  return (
    change.kind === 'position' &&
    Number.isInteger(change.content_version) &&
    change.content_version > 0 &&
    change.content_version < 2147483647 &&
    Number.isInteger(change.expected_revision) &&
    change.expected_revision > 0 &&
    change.expected_revision < 2147483647 &&
    typeof change.section_id === 'string' &&
    change.section_id.length > 0 &&
    change.section_id.length <= 128 &&
    typeof change.request_id === 'string' &&
    /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(change.request_id)
  );
}

export interface ConceptApi {
  list: () => Promise<{ concepts: ConceptSummary[] }>;
  detail: (id: string) => Promise<ConceptDetail>;
  queue: (id: string) => Promise<ConceptQueue>;
  reveal: (
    id: string,
    card: ConceptQuestion,
  ) => Promise<{ card: ConceptAnswer }>;
  progress: (id: string) => Promise<{ progress: ConceptProgress | null }>;
  save: (change: StudyChange) => Promise<{ progress: ConceptProgress }>;
}
