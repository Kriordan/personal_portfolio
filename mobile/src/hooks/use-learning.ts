import { focusManager, onlineManager, useQuery } from '@tanstack/react-query';
import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useSyncExternalStore } from 'react';

import { useAuth } from '@/lib/auth-context';
import { learningApi, learningKeys, validNoteId } from '@/lib/learning-api';
import { learningRefreshOptions } from '@/lib/learning-cache';
import { learningSession } from '@/lib/learning-runtime';

export function useLearningNotes() {
  const { isAuthenticated } = useAuth();
  const query = useQuery({
    ...learningRefreshOptions,
    queryKey: learningKeys.notes(),
    queryFn: learningApi.getNotes,
    enabled: isAuthenticated === true,
  });
  const { refetch } = query;
  useFocusEffect(
    useCallback(() => {
      if (isAuthenticated) void refetch();
    }, [isAuthenticated, refetch]),
  );
  return query;
}
export function useLearningNote(id: string) {
  const { isAuthenticated } = useAuth();
  const enabled = isAuthenticated === true && validNoteId(id);
  const query = useQuery({
    ...learningRefreshOptions,
    queryKey: learningKeys.note(id),
    queryFn: () => learningApi.getNote(id),
    enabled,
  });
  const { refetch } = query;
  useFocusEffect(
    useCallback(() => {
      if (enabled) void refetch();
    }, [enabled, refetch]),
  );
  return query;
}
export function useLearningActivity(userId: number) {
  const session = learningSession(userId);
  const state = useSyncExternalStore(
    session.subscribe,
    session.snapshot,
    session.snapshot,
  );
  useEffect(() => {
    if (!session.snapshot().ready) void session.restore();
    const recover = () => {
      if (focusManager.isFocused()) void session.check();
    };
    const focus = focusManager.subscribe(recover);
    const online = onlineManager.subscribe(recover);
    const timer = setInterval(recover, 10_000);
    return () => {
      focus();
      online();
      clearInterval(timer);
    };
  }, [session]);
  useFocusEffect(
    useCallback(() => {
      void session.check();
    }, [session]),
  );
  return { ...state, session };
}
