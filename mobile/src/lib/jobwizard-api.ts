import { apiRequest } from '@/lib/api-client';

// Shapes mirror project/api/jobwizard.py and jobwizard_service.serialize_job().

export interface Job {
  id: number;
  title: string;
  company_name: string;
  listing_url: string;
  listing_image: string;
  posted_date: string | null;
  user_id: number;
}

export interface JobInput {
  title: string;
  company_name: string;
  listing_url: string;
}

// Same bucket the web template links screenshots from (jobwizard/templates/job.html).
const SCREENSHOT_BASE_URL = 'https://jobwizard-test.s3.amazonaws.com';

export function jobScreenshotUrl(job: Job): string | null {
  return job.listing_image ? `${SCREENSHOT_BASE_URL}/${job.listing_image}` : null;
}

export const jobwizardApi = {
  getJobs(): Promise<{ jobs: Job[] }> {
    return apiRequest<{ jobs: Job[] }>('/jobwizard/jobs');
  },

  getJob(jobId: number): Promise<{ job: Job }> {
    return apiRequest<{ job: Job }>(`/jobwizard/jobs/${jobId}`);
  },

  createJob(input: JobInput): Promise<{ job: Job }> {
    return apiRequest<{ job: Job }>('/jobwizard/jobs', { method: 'POST', body: input });
  },
};

export const jobwizardKeys = {
  all: ['jobwizard'] as const,
  jobs: () => ['jobwizard', 'jobs'] as const,
  job: (jobId: number) => ['jobwizard', 'job', jobId] as const,
};
