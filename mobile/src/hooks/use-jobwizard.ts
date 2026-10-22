import { focusManager, onlineManager, useQuery } from '@tanstack/react-query';
import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useSyncExternalStore } from 'react';
import { useAuth } from '@/lib/auth-context';
import { jobwizardApi, jobwizardKeys, validJobId } from '@/lib/jobwizard-api';
import { jobSession } from '@/lib/jobwizard-runtime';
import { jobRefreshOptions } from '@/lib/jobwizard-cache';
function useRouteRefresh(enabled: boolean, refetch: () => Promise<unknown>) {
  useFocusEffect(
    useCallback(() => {
      if (enabled) void refetch();
    }, [enabled, refetch]),
  );
}
export function useJobs() {
  const { user, isAuthenticated } = useAuth(),
    enabled = isAuthenticated === true && !!user;
  const query = useQuery({
    ...jobRefreshOptions,
    queryKey: jobwizardKeys.jobs(user?.id ?? 0),
    queryFn: jobwizardApi.getJobs,
    enabled,
  });
  useRouteRefresh(enabled, query.refetch);
  return query;
}
export function useJob(id: number) {
  const { user, isAuthenticated } = useAuth(),
    enabled = isAuthenticated === true && !!user && validJobId(id);
  const query = useQuery({
    ...jobRefreshOptions,
    queryKey: jobwizardKeys.job(user?.id ?? 0, id),
    queryFn: () => jobwizardApi.getJob(id),
    enabled,
  });
  useRouteRefresh(enabled, query.refetch);
  return query;
}
export function useJobCapture(id: number, exists: boolean) {
  const { user, isAuthenticated } = useAuth(),
    enabled = isAuthenticated === true && !!user && validJobId(id) && exists;
  const query = useQuery({
    ...jobRefreshOptions,
    queryKey: jobwizardKeys.capture(user?.id ?? 0, id),
    queryFn: () => jobwizardApi.getCapture(id),
    enabled,
    refetchInterval: (q) =>
      q.state.data?.capture.busy ||
      q.state.data?.capture.latest?.status === 'running'
        ? 3_000
        : 12 * 60_000,
  });
  useRouteRefresh(enabled, query.refetch);
  return query;
}
export function useJobActivity() {
  const { user } = useAuth();
  const session = jobSession(user?.id ?? 0);
  const state = useSyncExternalStore(
    session.subscribe,
    session.snapshot,
    session.snapshot,
  );
  useEffect(() => {
    if (!user) return;
    if (!session.snapshot().ready) void session.restore();
    const check = () => {
      if (focusManager.isFocused()) void session.check();
    };
    const offFocus = focusManager.subscribe(check),
      offOnline = onlineManager.subscribe(check),
      timer = setInterval(check, 5_000);
    return () => {
      offFocus();
      offOnline();
      clearInterval(timer);
    };
  }, [session, user]);
  useFocusEffect(
    useCallback(() => {
      if (user) void session.check();
    }, [session, user]),
  );
  return { ...state, session };
}
