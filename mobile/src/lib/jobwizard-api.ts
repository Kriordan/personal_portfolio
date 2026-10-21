import { apiRequest } from '@/lib/api-client';
import type {
  CaptureStatus,
  Job,
  JobOperation,
  JobResult,
} from './jobwizard-model';
export * from './jobwizard-model';
export const jobwizardApi = {
  getJobs: () => apiRequest<{ jobs: Job[] }>('/jobwizard/jobs'),
  getJob: (id: number) => apiRequest<{ job: Job }>(`/jobwizard/jobs/${id}`),
  getCapture: (id: number, requestId?: string) =>
    apiRequest<{ capture: CaptureStatus }>(
      `/jobwizard/jobs/${id}/capture${requestId ? `?request_id=${encodeURIComponent(requestId)}` : ''}`,
      { timeoutMs: 12_000 },
    ),
  getReceipt: (id: string) =>
    apiRequest<{ receipt: JobResult | null }>(
      `/jobwizard/receipts/${encodeURIComponent(id)}`,
      { timeoutMs: 12_000 },
    ),
  submit: (
    op: JobOperation,
  ): Promise<JobResult | { capture: CaptureStatus }> =>
    op.kind === 'capture'
      ? apiRequest(`/jobwizard/jobs/${op.jobId}/capture`, {
          method: 'POST',
          body: op.input,
          timeoutMs: 25_000,
        })
      : apiRequest(
          `/jobwizard/jobs${op.jobId === null ? '' : `/${op.jobId}`}`,
          {
            method: op.jobId === null ? 'POST' : 'PATCH',
            body: op.input,
            timeoutMs: 15_000,
          },
        ),
};
