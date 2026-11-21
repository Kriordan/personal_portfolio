import type { QueryClient } from '@tanstack/react-query';
import { conceptKeys } from './concept-model.ts';
import { learningKeys } from './learning-model.ts';

export const learningRefreshOptions = {
  refetchOnMount: 'always',
  refetchOnWindowFocus: 'always',
  refetchOnReconnect: 'always',
} as const;
export const learningQueueOptions = {
  staleTime: Infinity,
  gcTime: 0,
  refetchOnMount: 'always',
  refetchOnWindowFocus: false,
  refetchOnReconnect: false,
} as const;
export async function reconcileLearningRating(
  client: QueryClient,
  active: () => boolean,
) {
  if (!active()) return;
  await Promise.all([
    client.cancelQueries({ queryKey: learningKeys.notes() }),
    client.cancelQueries({ queryKey: learningKeys.details() }),
    client.cancelQueries({ queryKey: conceptKeys.all }),
  ]);
  if (!active()) return;
  await Promise.all([
    client.invalidateQueries({ queryKey: learningKeys.notes() }),
    client.invalidateQueries({ queryKey: learningKeys.details() }),
    // A review attempt stays pinned until its screen deliberately loads another queue.
    client.invalidateQueries({
      queryKey: conceptKeys.all,
      predicate: (query) => !query.queryKey.includes('review'),
    }),
  ]);
}
