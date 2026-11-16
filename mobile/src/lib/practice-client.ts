import type { PracticeApi } from './practice-model.ts';
type Request = <T>(
  path: string,
  options?: {
    method?: 'GET' | 'POST' | 'PUT';
    body?: unknown;
    timeoutMs?: number;
    requestId?: string;
  },
) => Promise<T>;
const root = '/learning/practice';
const session = (id: string) => `${root}/sessions/${encodeURIComponent(id)}`;
export function createPracticeClient(request: Request): PracticeApi {
  const read = <T>(path: string) => request<T>(path, { timeoutMs: 20_000 });
  return {
    list: () => read(`${root}/sessions`),
    detail: (id) => read(session(id)),
    submission: (id, sequence) =>
      read(`${session(id)}/submissions/${sequence}`),
    feedback: (id, sequence) =>
      read(`${session(id)}/submissions/${sequence}/feedback`),
    revision: (id, artifact, revision) =>
      read(
        `${session(id)}/artifacts/${encodeURIComponent(artifact)}/revisions/${revision}`,
      ),
    receipt: (id) => read(`${root}/receipts/${encodeURIComponent(id)}`),
    change: (change) => {
      const { kind, conceptId, request_id } = change;
      if (kind === 'submit' || kind === 'feedback')
        return request(
          `${session(change.sessionId)}/submissions${
            kind === 'feedback'
              ? `/${change.submission_sequence}/feedback`
              : ''
          }`,
          {
            method: 'POST',
            body:
              kind === 'submit'
                ? {
                    request_id,
                    expected_sequence: change.expected_sequence,
                    edits: change.edits,
                    brief: change.brief,
                  }
                : { request_id },
            timeoutMs: 20_000,
            requestId: request_id,
          },
        );
      if (kind === 'artifact' || kind === 'brief')
        return request(
          `${session(change.sessionId)}/${kind === 'brief' ? 'brief' : `artifacts/${encodeURIComponent(change.artifactId)}`}`,
          {
            method: 'PUT',
            body:
              kind === 'artifact'
                ? {
                    request_id,
                    base_revision: change.base_revision,
                    language: change.language,
                    body: change.body,
                  }
                : {
                    request_id,
                    base_revision: change.base_revision,
                    entries: change.entries,
                  },
            timeoutMs: 20_000,
            requestId: request_id,
          },
        );
      let path = `${root}/sessions`;
      let body: object = {
        request_id,
        concept_id: conceptId,
        ...(kind === 'start' ? { exercise_id: change.exerciseId } : {}),
      };
      if (kind !== 'start') {
        path = `${session(change.sessionId)}/${kind === 'send' ? 'turns' : kind}`;
        body =
          kind === 'send'
            ? {
                request_id,
                body: change.body,
                expected_sequence: change.expected_sequence,
                artifact_revisions: change.artifact_revisions,
                brief_revision: change.brief_revision,
              }
            : kind === 'reply'
              ? {
                  request_id,
                  expected_sequence: change.expected_sequence,
                  ...(change.context ? { context: change.context } : {}),
                }
              : { request_id };
      }
      return request(path, {
        method: 'POST',
        body,
        timeoutMs: 20_000,
        requestId: request_id,
      });
    },
  };
}
