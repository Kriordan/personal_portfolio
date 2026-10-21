import type { QueryClient } from '@tanstack/react-query';
import { jobwizardKeys, type JobResult } from './jobwizard-model.ts';
export const jobRefreshOptions = {
  refetchOnMount: 'always',
  refetchOnWindowFocus: 'always',
  refetchOnReconnect: 'always',
} as const;
export async function reconcileJob(
  client: QueryClient,
  userId: number,
  result: JobResult | null,
  active: () => boolean,
) {
  if (!active()) return;
  await client.cancelQueries({ queryKey: jobwizardKeys.account(userId) });
  if (!active()) return;
  if (result) {
    client.setQueryData(jobwizardKeys.job(userId, result.job.id), {
      job: result.job,
    });
    client.setQueryData<{ jobs: (typeof result.job)[] }>(
      jobwizardKeys.jobs(userId),
      (previous) =>
        previous
          ? {
              jobs: [
                result.job,
                ...previous.jobs.filter((job) => job.id !== result.job.id),
              ],
            }
          : previous,
    );
  }
  await client.invalidateQueries({ queryKey: jobwizardKeys.account(userId) });
}
