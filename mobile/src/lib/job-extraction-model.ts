export interface Evidence {
  block_id: string;
  quote: string;
}
export interface SuggestedField {
  value: string;
  evidence: Evidence[];
}
export interface SuggestedBullet {
  category: string;
  text: string;
  evidence: Evidence[];
}
export interface Extraction {
  id: string;
  job_id: number | null;
  source_revision: number | null;
  source_url: string;
  retry_of: string | null;
  status:
    | 'running'
    | 'ready'
    | 'complete'
    | 'failed'
    | 'interrupted'
    | 'accepted';
  stage: 'read' | 'summary';
  fetched_at: string | null;
  expires_at: string;
  fields: {
    title?: SuggestedField | null;
    company_name?: SuggestedField | null;
  };
  warnings: string[];
  result: {
    bullets: SuggestedBullet[];
    more_details: boolean;
    has_conflicts: boolean;
  } | null;
  error_message: string | null;
  can_summarize: boolean;
}
export interface ExtractionRequest {
  request_id: string;
  listing_url: string;
  job_id?: number;
  expected_revision?: number;
  retry_of?: string;
}
export interface ReviewedDetails {
  extraction_id: string;
  bullets: { index: number; text: string }[];
}
/** Empty selection may skip a new summary, but must never erase an existing one. */
export function reviewSelectionError(
  fields: { title?: string; company_name?: string },
  bullets: ReviewedDetails['bullets'] | undefined,
  hasExistingDetails: boolean,
) {
  if (
    Object.values(fields).some(
      (value) => !value.trim() || [...value].length > 200,
    )
  )
    return 'Title and company need 1–200 characters.';
  if (bullets && !bullets.length && hasExistingDetails)
    return 'Select a detail or choose Keep current details.';
  if (
    bullets?.some(
      (bullet) => !bullet.text.trim() || [...bullet.text].length > 300,
    )
  )
    return 'Each selected detail needs 1–300 characters. Edit it or deselect it.';
  return null;
}
export function reviewedDetailsError(
  source: { url: string; revision?: number },
  url: string,
  revision?: number,
) {
  if (source.url !== url.trim())
    return 'The URL changed. Discard the selected bullets before saving, or suggest fresh details.';
  if (source.revision !== revision)
    return 'Your text is preserved, but the selected bullets belong to an older job version. Discard the selected bullets, then suggest fresh details before saving.';
  return null;
}
export interface AcceptedDetails {
  source_url: string;
  fetched_at: string;
  extraction_id: string;
  outdated: boolean;
  partial: boolean;
  bullets: (SuggestedBullet & { edited: boolean })[];
}
// Follow the current draft until the reviewer makes an explicit choice.
export function suggestedFieldSelected(
  choice: boolean | null,
  current: string,
) {
  return choice ?? !current.trim();
}
export interface ReviewFieldChoice {
  selected: boolean;
  compared: string;
}
/** An earlier choice must not replace text edited after leaving Review. */
export function reviewFieldSelected(
  choice: ReviewFieldChoice | null,
  current: string,
) {
  return suggestedFieldSelected(
    choice?.compared === current ? choice.selected : null,
    current,
  );
}
export function extractionMatches(
  extraction: Extraction,
  url: string,
  jobId: number | null,
  revision?: number,
) {
  return (
    extraction.source_url === url.trim() &&
    extraction.job_id === jobId &&
    (jobId === null || extraction.source_revision === revision)
  );
}
export function validExtractionRequest(
  value: unknown,
): value is ExtractionRequest {
  if (!value || typeof value !== 'object') return false;
  const request = value as ExtractionRequest;
  return (
    typeof request.request_id === 'string' &&
    /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(request.request_id) &&
    typeof request.listing_url === 'string' &&
    request.listing_url.length <= 2048 &&
    (request.job_id === undefined ||
      (Number.isSafeInteger(request.job_id) &&
        request.job_id > 0 &&
        Number.isSafeInteger(request.expected_revision) &&
        request.expected_revision! >= 0))
  );
}
