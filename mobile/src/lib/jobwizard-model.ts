import type {
  AcceptedDetails,
  ReviewedDetails,
} from './job-extraction-model';
export interface JobInput {
  title: string;
  company_name: string;
  listing_url: string;
}
export interface Job extends JobInput {
  id: number;
  user_id: number;
  listing_image: string;
  posted_date: string | null;
  saved_at: string | null;
  updated_at: string | null;
  archived_at: string | null;
  revision: number;
  can_open_listing: boolean;
  accepted_details?: AcceptedDetails | null;
}
export interface CaptureAttempt {
  id: string;
  status: 'running' | 'succeeded' | 'failed' | 'interrupted';
  started_at: string;
  finished_at: string | null;
  error_code: string | null;
  error_message?: string | null;
}
export interface CaptureStatus {
  latest: CaptureAttempt | null;
  requested: CaptureAttempt | null;
  configured: boolean;
  supported?: boolean;
  provider?: string;
  busy?: boolean;
  unavailable?: boolean;
  legacy_unavailable: boolean;
  image: {
    url: string;
    expires_at: string;
    width: number;
    height: number;
    captured_at: string;
    outdated: boolean;
  } | null;
}
export function captureAttemptMessage(attempt: CaptureAttempt) {
  if (attempt.status === 'running') return 'Capturing screenshot…';
  if (attempt.status === 'succeeded')
    return 'Screenshot saved. Review the preview to check the listing content.';
  return `${attempt.error_message ?? (attempt.status === 'interrupted' ? 'Capture was interrupted.' : 'Capture failed.')} Your job is still saved.`;
}
export type JobView = 'active' | 'archived' | 'all';
export type JobSort = 'newest' | 'oldest' | 'company' | 'title';
export const jobViews = [
  { value: 'active', label: 'Active' },
  { value: 'archived', label: 'Archived' },
  { value: 'all', label: 'All jobs' },
] as const;
export const jobSorts = [
  { value: 'newest', label: 'Newest saved' },
  { value: 'oldest', label: 'Oldest saved' },
  { value: 'company', label: 'Company A–Z' },
  { value: 'title', label: 'Title A–Z' },
] as const;
export function validJobId(value: unknown): value is number {
  return (
    typeof value === 'number' &&
    Number.isSafeInteger(value) &&
    value > 0 &&
    value <= 2_147_483_647
  );
}
export function routeJobId(value: unknown) {
  return typeof value === 'string' &&
    /^[1-9]\d*$/.test(value) &&
    validJobId(Number(value))
    ? Number(value)
    : 0;
}
export function safeJobUrl(value: string) {
  if (!value || value.length > 2048 || /[\s\x00-\x1f\x7f\\]/.test(value))
    return false;
  try {
    const url = new URL(value);
    return (
      ['http:', 'https:'].includes(url.protocol) &&
      !!url.hostname &&
      !url.username &&
      !url.password
    );
  } catch {
    return false;
  }
}
export function jobDomain(job: JobInput) {
  try {
    return new URL(job.listing_url).hostname;
  } catch {
    return 'Listing link unavailable';
  }
}
const textCompare = new Intl.Collator(undefined, {
  sensitivity: 'base',
  numeric: true,
}).compare;
export function browseJobs(
  jobs: readonly Job[],
  search: string,
  view: JobView,
  sort: JobSort,
) {
  const words = search
    .trim()
    .toLocaleLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  return jobs
    .filter(
      (job) =>
        (view === 'all' || !!job.archived_at === (view === 'archived')) &&
        words.every((word) =>
          `${job.title} ${job.company_name} ${jobDomain(job)}`
            .toLocaleLowerCase()
            .includes(word),
        ),
    )
    .sort((a, b) => {
      if (sort === 'title' || sort === 'company')
        return (
          textCompare(
            sort === 'title' ? a.title : a.company_name,
            sort === 'title' ? b.title : b.company_name,
          ) || a.id - b.id
        );
      const left = a.saved_at ? Date.parse(a.saved_at) : NaN,
        right = b.saved_at ? Date.parse(b.saved_at) : NaN;
      if (!Number.isFinite(left) || !Number.isFinite(right))
        return Number.isFinite(left)
          ? -1
          : Number.isFinite(right)
            ? 1
            : a.id - b.id;
      return (sort === 'oldest' ? left - right : right - left) || a.id - b.id;
    });
}
export function jobValidation(input: JobInput, existing?: JobInput) {
  if (!input.title.trim()) return 'Enter a job title.';
  if (input.title !== existing?.title && [...input.title.trim()].length > 200)
    return 'Keep the title within 200 characters.';
  if (!input.company_name.trim()) return 'Enter a company name.';
  if (
    input.company_name !== existing?.company_name &&
    [...input.company_name.trim()].length > 200
  )
    return 'Keep the company within 200 characters.';
  if (
    input.listing_url !== existing?.listing_url &&
    !safeJobUrl(input.listing_url.trim())
  )
    return 'Enter a valid HTTP(S) listing URL, without spaces or embedded credentials (up to 2,048 characters).';
  return null;
}
export const jobwizardKeys = {
  all: ['jobwizard'] as const,
  account: (user: number) => ['jobwizard', user] as const,
  jobs: (user: number) => ['jobwizard', user, 'jobs'] as const,
  job: (user: number, id: number) => ['jobwizard', user, 'job', id] as const,
  capture: (user: number, id: number) =>
    ['jobwizard', user, 'capture', id] as const,
};
export type JobWrite = {
  request_id: string;
  expected_revision?: number;
  archived?: boolean;
  reviewed_details?: ReviewedDetails;
} & Partial<JobInput>;
export interface JobOperation {
  kind: 'save' | 'capture';
  jobId: number | null;
  input: JobWrite;
}
export interface JobResult {
  job: Job;
  request_id: string;
}
export function storedOperation(value: unknown): value is JobOperation {
  if (!value || typeof value !== 'object') return false;
  const op = value as JobOperation,
    input = op.input;
  if (
    !['save', 'capture'].includes(op.kind) ||
    (op.jobId !== null && !validJobId(op.jobId)) ||
    !input ||
    typeof input.request_id !== 'string' ||
    !/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(input.request_id)
  )
    return false;
  if (
    op.jobId !== null &&
    (!Number.isInteger(input.expected_revision) ||
      input.expected_revision! < 0)
  )
    return false;
  if (op.kind === 'capture') return op.jobId !== null;
  if (op.jobId !== null && typeof input.archived === 'boolean') return true;
  return (
    typeof input.title === 'string' &&
    typeof input.company_name === 'string' &&
    typeof input.listing_url === 'string'
  );
}
