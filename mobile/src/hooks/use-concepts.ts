import { focusManager, onlineManager, useQuery } from '@tanstack/react-query';
import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useSyncExternalStore } from 'react';
import { conceptApi } from '@/lib/concept-api';
import { conceptKeys } from '@/lib/concept-model';
import { conceptStudy } from '@/lib/concept-runtime';
import { learningRefreshOptions } from '@/lib/learning-cache';
import { validNoteId } from '@/lib/learning-model';

export function useConcepts(userId: number | undefined) {
  const query = useQuery({
    ...learningRefreshOptions,
    queryKey: conceptKeys.list(userId),
    queryFn: conceptApi.list,
    enabled: userId !== undefined,
  });
  const { refetch } = query;
  useFocusEffect(
    useCallback(() => {
      if (userId !== undefined) void refetch({ cancelRefetch: false });
    }, [userId, refetch]),
  );
  return query;
}
export function useConcept(userId: number, id: string) {
  const query = useQuery({
    ...learningRefreshOptions,
    queryKey: conceptKeys.detail(userId, id),
    queryFn: () => conceptApi.detail(id),
    enabled: validNoteId(id),
  });
  const { refetch } = query;
  useFocusEffect(
    useCallback(() => {
      if (validNoteId(id)) void refetch();
    }, [id, refetch]),
  );
  return query;
}
export function useConceptStudy(userId: number) {
  const study = conceptStudy(userId);
  const state = useSyncExternalStore(
    study.subscribe,
    study.snapshot,
    study.snapshot,
  );
  useEffect(() => {
    if (!study.snapshot().ready) void study.restore();
    const recover = () => {
      if (focusManager.isFocused()) void study.check();
    };
    const focus = focusManager.subscribe(recover);
    const online = onlineManager.subscribe(recover);
    const timer = setInterval(recover, 10_000);
    return () => {
      focus();
      online();
      clearInterval(timer);
    };
  }, [study]);
  useFocusEffect(
    useCallback(() => {
      void study.check();
    }, [study]),
  );
  return { ...state, study };
}
