import { focusManager, onlineManager, useQuery } from '@tanstack/react-query';
import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useState, useSyncExternalStore } from 'react';
import { learningRefreshOptions } from '@/lib/learning-cache';
import { practiceKeys, replyLive, validSessionId } from '@/lib/practice-model';
import {
  practiceApi,
  practiceDrafts,
  practiceOperation,
  practiceWorkDrafts,
} from '@/lib/practice-runtime';

export function usePracticeList(userId: number) {
  const query = useQuery({
    ...learningRefreshOptions,
    queryKey: practiceKeys.list(userId),
    queryFn: practiceApi.list,
  });
  const { refetch } = query;
  useFocusEffect(
    useCallback(() => {
      void refetch();
    }, [refetch]),
  );
  return query;
}
export function usePracticeDetail(userId: number, id: string) {
  const [visible, setVisible] = useState(false);
  const query = useQuery({
    ...learningRefreshOptions,
    queryKey: practiceKeys.detail(userId, id),
    enabled: validSessionId(id),
    queryFn: () => practiceApi.detail(id),
    refetchInterval: (q) =>
      visible && validSessionId(id)
        ? q.state.data && replyLive(q.state.data.reply)
          ? 2000
          : 15_000
        : false,
    refetchIntervalInBackground: false,
  });
  const { refetch } = query;
  useFocusEffect(
    useCallback(() => {
      setVisible(true);
      if (validSessionId(id)) void refetch();
      return () => setVisible(false);
    }, [id, refetch]),
  );
  return query;
}
export function usePracticeOperation(userId: number) {
  const operation = practiceOperation(userId);
  const state = useSyncExternalStore(
    operation.subscribe,
    operation.snapshot,
    operation.snapshot,
  );
  useEffect(() => {
    if (!operation.snapshot().ready) void operation.restore();
    const recover = () => {
      if (focusManager.isFocused()) void operation.check();
    };
    const focus = focusManager.subscribe(recover),
      online = onlineManager.subscribe(recover);
    const timer = setInterval(recover, 10_000);
    return () => {
      focus();
      online();
      clearInterval(timer);
    };
  }, [operation]);
  useFocusEffect(
    useCallback(() => {
      void operation.check();
    }, [operation]),
  );
  return { ...state, operation };
}
export function usePracticeDraft(userId: number, id: string) {
  const drafts = practiceDrafts(userId);
  const snapshot = useCallback(() => drafts.snapshot(id), [drafts, id]);
  const state = useSyncExternalStore(drafts.subscribe, snapshot, snapshot);
  useEffect(() => {
    void drafts.load(id);
  }, [drafts, id]);
  return { ...state, drafts };
}
export function usePracticeWork(userId: number, id: string) {
  const drafts = practiceWorkDrafts(userId);
  const snapshot = useCallback(() => drafts.snapshot(id), [drafts, id]);
  const state = useSyncExternalStore(drafts.subscribe, snapshot, snapshot);
  useEffect(() => {
    void drafts.load(id);
  }, [drafts, id]);
  return { ...state, drafts };
}
