import { useQuery } from '@tanstack/react-query';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import {
  ApiError,
  authApi,
  setUnauthorizedListener,
  type ApiUser,
} from '@/lib/api-client';
import { disconnectListSocket } from '@/lib/list-socket';
import { queryClient } from '@/lib/query-client';
import { tokenStorage } from '@/lib/token-storage';

interface AuthState {
  /** Null until session restoration finishes. */
  isAuthenticated: boolean | null;
  user: ApiUser | null;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);
const profileKey = ['auth', 'me'] as const;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const profile = useQuery({
    queryKey: profileKey,
    queryFn: authApi.me,
    enabled: isAuthenticated === true,
  });
  const user = profile.data?.user ?? null;

  useEffect(() => {
    // If a request 401s even after refresh, the session is unrecoverable.
    // Registered before session restoration so a failed restore is caught too.
    setUnauthorizedListener(() => {
      disconnectListSocket();
      tokenStorage.clear();
      queryClient.clear();
      setIsAuthenticated(false);
    });
    return () => setUnauthorizedListener(null);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      const refreshToken = await tokenStorage.getRefreshToken();
      if (refreshToken === null) {
        if (!cancelled) setIsAuthenticated(false);
        return;
      }
      // The profile query validates the session and recovers after reconnect.
      if (!cancelled) setIsAuthenticated(true);
    }

    restoreSession();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    // A 401 is handled by the unauthorized listener; a missing account also
    // invalidates the session. Network failures preserve it for query recovery.
    if (!(profile.error instanceof ApiError) || profile.error.status !== 404)
      return;
    let cancelled = false;
    async function clearMissingAccount() {
      disconnectListSocket();
      await tokenStorage.clear();
      if (cancelled) return;
      queryClient.clear();
      setIsAuthenticated(false);
    }
    void clearMissingAccount();
    return () => {
      cancelled = true;
    };
  }, [profile.error]);

  const signOut = useCallback(async () => {
    disconnectListSocket();
    await authApi.logout();
    await tokenStorage.clear();
    queryClient.clear();
    setIsAuthenticated(false);
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const response = await authApi.login(email, password);
    await tokenStorage.setTokens({
      accessToken: response.access_token,
      refreshToken: response.refresh_token,
    });
    queryClient.setQueryData(profileKey, { user: response.user });
    setIsAuthenticated(true);
  }, []);

  const value = useMemo(
    () => ({ isAuthenticated, user, signIn, signOut }),
    [isAuthenticated, user, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
