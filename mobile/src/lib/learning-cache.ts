import type { QueryClient } from '@tanstack/react-query';
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
  ]);
  if (!active()) return;
  await Promise.all([
    client.invalidateQueries({ queryKey: learningKeys.notes() }),
    client.invalidateQueries({ queryKey: learningKeys.details() }),
  ]);
}
