import { useQuery } from '@tanstack/react-query';
import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { learningRefreshOptions } from '@/lib/learning-cache';
import { wholeRevision } from '@/lib/practice-feedback-model';
import { practiceKeys, validSessionId } from '@/lib/practice-model';
import { practiceApi } from '@/lib/practice-runtime';

export function usePracticeFeedback(
  userId: number,
  id: string,
  sequence: number,
) {
  const [visible, setVisible] = useState(false);
  const enabled = validSessionId(id) && wholeRevision(sequence, 1);
  const snapshot = useQuery({
    ...learningRefreshOptions,
    queryKey: practiceKeys.submission(userId, id, sequence),
    queryFn: () => practiceApi.submission(id, sequence),
    enabled,
  });
  const evaluation = useQuery({
    ...learningRefreshOptions,
    queryKey: practiceKeys.feedback(userId, id, sequence),
    queryFn: () => practiceApi.feedback(id, sequence),
    enabled,
    refetchInterval: (q) =>
      visible && enabled
        ? ['pending', 'running'].includes(q.state.data?.request.status ?? '')
          ? 2000
          : 15_000
        : false,
    refetchIntervalInBackground: false,
  });
  const { refetch: readSnapshot } = snapshot;
  const { refetch: readFeedback } = evaluation;
  const refresh = useCallback(() => {
    if (enabled) {
      void readSnapshot();
      void readFeedback();
    }
  }, [enabled, readSnapshot, readFeedback]);
  useFocusEffect(
    useCallback(() => {
      setVisible(true);
      refresh();
      return () => setVisible(false);
    }, [refresh]),
  );
  return { snapshot, evaluation, refresh };
}
