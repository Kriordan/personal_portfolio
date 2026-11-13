import type { ConceptApi, ConceptProgress } from './concept-model.ts';

type Request = <T>(
  path: string,
  options?: {
    method?: 'GET' | 'POST' | 'PUT';
    body?: unknown;
    timeoutMs?: number;
  },
) => Promise<T>;
const path = (id: string) => '/learning/concepts/' + encodeURIComponent(id);
export function createConceptClient(request: Request): ConceptApi {
  return {
    list: () => request('/learning/concepts', { timeoutMs: 20_000 }),
    detail: (id) => request(path(id), { timeoutMs: 20_000 }),
    queue: (id) => request(path(id) + '/review', { timeoutMs: 20_000 }),
    reveal: (id, card) =>
      request(
        path(id) +
          '/review/reveal?' +
          new URLSearchParams({
            card_id: card.card_id,
            content_version: String(card.content_version),
            expected_revision: String(card.progress_revision),
          }),
        { timeoutMs: 20_000 },
      ),
    progress: (id) => request(path(id) + '/progress', { timeoutMs: 20_000 }),
    save: (change) => {
      if (change.kind === 'enroll')
        return request<{ progress: ConceptProgress }>(
          path(change.conceptId) + '/enrollment',
          {
            method: 'POST',
            body: {},
            timeoutMs: 20_000,
          },
        );
      const { kind: _kind, conceptId, ...body } = change;
      return request<{ progress: ConceptProgress }>(
        path(conceptId) + '/reading-position',
        {
          method: 'PUT',
          body,
          timeoutMs: 20_000,
        },
      );
    },
  };
}
