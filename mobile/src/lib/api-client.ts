import { API_BASE_URL, API_PREFIX } from '@/lib/config';
import { tokenStorage } from '@/lib/token-storage';

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown) {
    const message =
      body && typeof body === 'object' && 'error' in body && typeof body.error === 'string'
        ? body.error
        : `Request failed with status ${status}`;
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

export interface ApiUser {
  id: number;
  email: string;
  username: string;
  email_verified: boolean;
  is_admin: boolean;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  user: ApiUser;
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  /** Skip attaching the access token (e.g. for login). */
  anonymous?: boolean;
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function rawRequest(path: string, options: RequestOptions, accessToken: string | null): Promise<Response> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  if (accessToken && !options.anonymous) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }
  return fetch(`${API_BASE_URL}${API_PREFIX}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
}

// Deduplicate concurrent refresh attempts so parallel 401s trigger one refresh.
let refreshPromise: Promise<string | null> | null = null;

/** Exported for the Socket.IO client, which needs a fresh token after a rejected connect. */
export async function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const refreshToken = await tokenStorage.getRefreshToken();
      if (!refreshToken) return null;
      const response = await fetch(`${API_BASE_URL}${API_PREFIX}/auth/refresh`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${refreshToken}` },
      });
      if (!response.ok) return null;
      const data = (await response.json()) as { access_token: string };
      await tokenStorage.setTokens({ accessToken: data.access_token });
      return data.access_token;
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

type UnauthorizedListener = () => void;
let onUnauthorized: UnauthorizedListener | null = null;

/** Registered by the auth provider so an unrecoverable 401 forces logout. */
export function setUnauthorizedListener(listener: UnauthorizedListener | null): void {
  onUnauthorized = listener;
}

/**
 * Perform an authenticated JSON request against the Flask API.
 * On 401, attempts a single token refresh and retries once.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const accessToken = options.anonymous ? null : await tokenStorage.getAccessToken();
  let response = await rawRequest(path, options, accessToken);

  if (response.status === 401 && !options.anonymous) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      response = await rawRequest(path, options, newToken);
    }
    if (response.status === 401) {
      onUnauthorized?.();
    }
  }

  const body = await parseBody(response);
  if (!response.ok) {
    throw new ApiError(response.status, body);
  }
  return body as T;
}

export const authApi = {
  login(email: string, password: string): Promise<LoginResponse> {
    return apiRequest<LoginResponse>('/auth/login', {
      method: 'POST',
      body: { email, password },
      anonymous: true,
    });
  },

  /** Fetch the current user; used to restore/validate the session at startup. */
  me(): Promise<{ user: ApiUser }> {
    return apiRequest<{ user: ApiUser }>('/auth/me');
  },

  /** Stateless on the server; the caller must also clear local tokens. */
  async logout(): Promise<void> {
    try {
      await apiRequest<{ message: string }>('/auth/logout', { method: 'POST' });
    } catch {
      // Token may already be expired; local cleanup is what matters.
    }
  },
};
