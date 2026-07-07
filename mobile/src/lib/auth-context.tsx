import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { ApiError, authApi, setUnauthorizedListener, type ApiUser } from '@/lib/api-client';
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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [user, setUser] = useState<ApiUser | null>(null);

  useEffect(() => {
    // If a request 401s even after refresh, the session is unrecoverable.
    // Registered before session restoration so a failed restore is caught too.
    setUnauthorizedListener(() => {
      tokenStorage.clear();
      queryClient.clear();
      setUser(null);
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
      // Render the authenticated shell immediately; validation happens below.
      if (!cancelled) setIsAuthenticated(true);
      try {
        const { user: restoredUser } = await authApi.me();
        if (!cancelled) setUser(restoredUser);
      } catch (error) {
        // A 401 is already handled by the unauthorized listener. A 404 means
        // the account no longer exists, so the session is invalid too.
        if (error instanceof ApiError && error.status === 404) {
          await tokenStorage.clear();
          queryClient.clear();
          if (!cancelled) {
            setUser(null);
            setIsAuthenticated(false);
          }
        }
        // Network/server errors keep the session; user data loads on retry.
      }
    }

    restoreSession();
    return () => {
      cancelled = true;
    };
  }, []);

  const signOut = useCallback(async () => {
    await authApi.logout();
    await tokenStorage.clear();
    queryClient.clear();
    setUser(null);
    setIsAuthenticated(false);
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const response = await authApi.login(email, password);
    await tokenStorage.setTokens({
      accessToken: response.access_token,
      refreshToken: response.refresh_token,
    });
    setUser(response.user);
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
