/** The existing server's artifact and learner-brief contracts. No evaluator content. */
export const ARTIFACT_LIMIT = 64 * 1024;
export const BRIEF_ENTRY_LIMIT = 2 * 1024;
export const BRIEF_ENTRY_COUNT = 50;
export const briefTypes = [
  'assumption',
  'question',
  'decision',
  'next_step',
] as const;
export type BriefSource =
  { turn: number } | { artifact_id: string; revision: number };
export interface BriefEntry {
  id: string;
  type: (typeof briefTypes)[number];
  text: string;
  pinned: boolean;
  basis?: 'learner';
  sources?: BriefSource[];
}
export type WorkEdit =
  | {
      kind: 'artifact';
      artifactId: string;
      base_revision: number;
      language: string;
      body: string;
    }
  | { kind: 'brief'; base_revision: number; entries: BriefEntry[] };

const whole = (n: unknown, minimum = 0): n is number =>
  typeof n === 'number' &&
  Number.isInteger(n) &&
  n >= minimum &&
  n <= 2147483647;
export const validArtifactId = (id: unknown): id is string =>
  typeof id === 'string' &&
  id.length <= 128 &&
  /^[a-z][a-z0-9-]*(?::[a-z0-9-]+)?$/.test(id);
const textBytes = (s: string) =>
  new TextEncoder().encode(s.replace(/\r\n?/g, '\n')).length;
const languages = [
  'text',
  'markdown',
  'pseudocode',
  'sql',
  'python',
  'typescript',
  'json',
  'yaml',
];
function validSource(source: BriefSource) {
  if (!source || typeof source !== 'object') return false;
  return 'turn' in source
    ? Object.keys(source).length === 1 && whole(source.turn, 1)
    : Object.keys(source).length === 2 &&
        validArtifactId(source.artifact_id) &&
        whole(source.revision, 1);
}
/** Drafts may contain unfinished entries or over-byte-limit Unicode; sends may not. */
export function validWorkEdit(
  value: unknown,
  draft = false,
): value is WorkEdit {
  if (!value || typeof value !== 'object') return false;
  const v = value as WorkEdit;
  if (!whole(v.base_revision)) return false;
  if (v.kind === 'artifact')
    return (
      validArtifactId(v.artifactId) &&
      languages.includes(v.language) &&
      typeof v.body === 'string' &&
      v.body.length <= ARTIFACT_LIMIT &&
      (draft || (textBytes(v.body) <= ARTIFACT_LIMIT && !v.body.includes('\0')))
    );
  if (
    v.kind !== 'brief' ||
    !Array.isArray(v.entries) ||
    v.entries.length > BRIEF_ENTRY_COUNT
  )
    return false;
  const seen = new Set<string>();
  return v.entries.every((entry) => {
    if (
      !entry ||
      typeof entry !== 'object' ||
      typeof entry.id !== 'string' ||
      !/^[a-z0-9][a-z0-9-]{0,63}$/.test(entry.id) ||
      seen.has(entry.id)
    )
      return false;
    seen.add(entry.id);
    return (
      briefTypes.includes(entry.type) &&
      typeof entry.pinned === 'boolean' &&
      (entry.basis === undefined || entry.basis === 'learner') &&
      typeof entry.text === 'string' &&
      entry.text.length <= BRIEF_ENTRY_LIMIT &&
      (draft ||
        (!!entry.text.trim() &&
          textBytes(entry.text) <= BRIEF_ENTRY_LIMIT &&
          !entry.text.includes('\0'))) &&
      (entry.sources === undefined ||
        (Array.isArray(entry.sources) &&
          entry.sources.length <= 10 &&
          entry.sources.every(validSource) &&
          new Set(entry.sources.map((s) => JSON.stringify(s))).size ===
            entry.sources.length))
    );
  });
}
export const workKey = (edit: WorkEdit) =>
  edit.kind === 'brief' ? 'brief' : `artifact:${edit.artifactId}`;
/** Pick fields explicitly so local mutation metadata never becomes server content. */
export function copyWork(edit: WorkEdit): WorkEdit {
  return edit.kind === 'artifact'
    ? {
        kind: 'artifact',
        artifactId: edit.artifactId,
        base_revision: edit.base_revision,
        language: edit.language,
        body: edit.body,
      }
    : {
        kind: 'brief',
        base_revision: edit.base_revision,
        entries: edit.entries.map((entry) => ({
          id: entry.id,
          type: entry.type,
          text: entry.text,
          pinned: entry.pinned,
          basis: 'learner',
          sources: (entry.sources ?? []).map((s) =>
            'turn' in s
              ? { turn: s.turn }
              : { artifact_id: s.artifact_id, revision: s.revision },
          ),
        })),
      };
}
export const sameWork = (left: WorkEdit, right: WorkEdit) =>
  JSON.stringify(copyWork(left)) === JSON.stringify(copyWork(right));
export function workProblem(edit: WorkEdit) {
  const artifact = edit.kind === 'artifact';
  if (validWorkEdit(edit)) return null;
  return artifact
    ? 'Keep this artifact within 64 KiB of text and remove any null characters before saving.'
    : 'Each note needs text within 2 KiB, with at most 50 notes. Your unfinished draft stays on this device.';
}
