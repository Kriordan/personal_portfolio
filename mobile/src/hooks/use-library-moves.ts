import { useQuery, useQueryClient } from '@tanstack/react-query';
import { randomUUID } from 'expo-crypto';
import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useMemo } from 'react';

import { useAuth } from '@/lib/auth-context';
import { libraryApi } from '@/lib/library-api';
import { libraryRefreshOptions } from '@/lib/library-cache';
import { idleMove, observeLibraryMove, startLibraryMove, type MoveAttempt } from '@/lib/library-move-cache';
import { libraryKeys, mergeMoveReceipts, movePollInterval } from '@/lib/library-model';

export function useLibraryMoves() {
  const { user } = useAuth();
  const userId = user?.id ?? 0;
  const client = useQueryClient();
  const workflow = useQuery({ ...libraryRefreshOptions, queryKey: libraryKeys.workflow(userId), queryFn: libraryApi.workflow, enabled: !!user, retry: false });
  const owner = workflow.data?.is_owner === true;
  const { data: attempt = idleMove } = useQuery<MoveAttempt>({ queryKey: libraryKeys.moveAttempt(userId), queryFn: () => idleMove, enabled: false, gcTime: Infinity });
  const status = useQuery({ ...libraryRefreshOptions, queryKey: libraryKeys.moves(userId), queryFn: libraryApi.moves,
    enabled: !!user && owner, retry: false,
    refetchInterval: (query) => movePollInterval(query.state.data?.moves ?? [], attempt.pending),
    refetchIntervalInBackground: false,
  });
  const moves = useMemo(() => mergeMoveReceipts(status.data, attempt.move), [status.data, attempt.move]);
  const { refetch: readWorkflow } = workflow;
  const { refetch: readMoves } = status;
  const refresh = useCallback(() => {
    if (!userId) return;
    void readWorkflow();
    if (owner) void readMoves();
  }, [userId, owner, readWorkflow, readMoves]);
  useFocusEffect(refresh);
  useEffect(() => {
    let cancelled = false;
    const session = client.getQueryData(libraryKeys.workflow(userId));
    if (userId && owner) {
      // Sequence observers so a sibling receipt cannot invalidate another
      // receipt's logout guard during cache cancellation.
      void (async () => {
        for (const move of moves) {
          if (cancelled || client.getQueryData(libraryKeys.workflow(userId)) !== session) return;
          await observeLibraryMove(client, userId, move);
        }
      })();
    }
    return () => { cancelled = true; };
  }, [client, userId, owner, moves]);
  const pending = attempt.pending || !!status.data?.busy || moves.some((move) => move.status === 'running');
  const start = useCallback((entryId: string) => {
    if (!userId || pending || !workflow.data?.can_move || !workflow.data.version) return;
    const id = randomUUID();
    void startLibraryMove(client, userId, id, () => libraryApi.move(id, entryId, workflow.data!.version!));
  }, [client, userId, pending, workflow.data]);
  const retryRemoval = useCallback((id: string) => {
    if (!userId || !owner || pending) return;
    const requestId = randomUUID();
    void startLibraryMove(client, userId, requestId, () => libraryApi.retryRemoval(id, requestId));
  }, [client, userId, owner, pending]);
  const confirmedAttempt = !!attempt.move || moves.some((move) => move.id === attempt.requestId);
  return { workflow, status, moves, pending, refresh, start, retryRemoval, error: confirmedAttempt ? undefined : attempt.error };
}
