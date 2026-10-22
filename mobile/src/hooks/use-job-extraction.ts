import { focusManager, onlineManager } from '@tanstack/react-query';
import { useEffect, useSyncExternalStore } from 'react';
import { useAuth } from '@/lib/auth-context';
import { extractionSession } from '@/lib/job-extraction-runtime';
export function useJobExtraction() {
  const { user } = useAuth();
  const session = extractionSession(user?.id ?? 0);
  const state = useSyncExternalStore(
    session.subscribe,
    session.snapshot,
    session.snapshot,
  );
  useEffect(() => {
    if (!user) return;
    if (!session.snapshot().ready) void session.restore();
    const refresh = () => {
      if (focusManager.isFocused()) void session.check();
    };
    const offFocus = focusManager.subscribe(refresh),
      offOnline = onlineManager.subscribe(refresh);
    const timer = setInterval(() => {
      if (session.snapshot().uncertain && focusManager.isFocused())
        void session.check();
    }, 5000);
    return () => {
      offFocus();
      offOnline();
      clearInterval(timer);
    };
  }, [session, user]);
  return { ...state, session };
}
