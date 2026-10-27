import { apiRequest } from '@/lib/api-client';
import type {
  DrawResponse,
  LotteryStatus,
  ScratchGame,
  ScratchResponse,
} from './lottery-model';
export const lotteryApi = {
  scratch: (query: string) =>
    apiRequest<ScratchResponse>(`/lottery/scratch-offs?${query}`),
  game: (state: string, number: string, target: number) =>
    apiRequest<{ game: ScratchGame; target: number; status: LotteryStatus }>(
      `/lottery/scratch-offs/${encodeURIComponent(state)}/${encodeURIComponent(number)}?target=${target}`,
    ),
  draws: (state: string) =>
    apiRequest<DrawResponse>(`/lottery/draws?state=${state}`),
};
