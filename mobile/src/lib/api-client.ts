import { API_BASE_URL, API_PREFIX } from '@/lib/config';
import { tokenStorage } from '@/lib/token-storage';
import { withRequestTimeout } from '@/lib/request-timeout';

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
  /** JSON-serializable body, or FormData for multipart uploads. */
  body?: unknown;
  /** Skip attaching the access token (e.g. for login). */
  anonymous?: boolean;
  /** Stops waiting, not server execution. Omitted for existing callers. */
  timeoutMs?: number;
  /** An opaque operation UUID, never a URL or account identifier. */
  requestId?: string;
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

async function rawRequest(path: string, options: RequestOptions, accessToken: string | null, signal?: AbortSignal): Promise<Response> {
  if (signal?.aborted) throw new Error('Request aborted');
  const headers: Record<string, string> = {};
  if (options.requestId && /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(options.requestId))
    headers['X-Request-ID'] = options.requestId;
  const isFormData = options.body instanceof FormData;
  if (options.body !== undefined && !isFormData) {
    // For FormData, fetch sets multipart/form-data with the boundary itself.
    headers['Content-Type'] = 'application/json';
  }
  if (accessToken && !options.anonymous) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }
  return fetch(`${API_BASE_URL}${API_PREFIX}${path}`, {
    signal,
    method: options.method ?? 'GET',
    headers,
    body:
      options.body === undefined
        ? undefined
        : isFormData
          ? (options.body as FormData)
          : JSON.stringify(options.body),
  });
}

function requireSession(version: number): void {
  if (version !== tokenStorage.getSessionVersion())
    throw new Error('Session changed. Discarding the previous request.');
}

// Deduplicate within one session only. A late refresh must never restore a
// signed-out account or share its token with a newly signed-in account.
let refresh: { version: number; promise: Promise<string | null> } | null = null;

/** Exported for the Socket.IO client, which needs a fresh token after a rejected connect. */
export async function refreshAccessToken(version = tokenStorage.getSessionVersion()): Promise<string | null> {
  requireSession(version);
  if (!refresh || refresh.version !== version) {
    const promise = (async () => {
      const refreshToken = await tokenStorage.getRefreshToken();
      requireSession(version);
      if (!refreshToken) return null;
      const response = await fetch(`${API_BASE_URL}${API_PREFIX}/auth/refresh`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${refreshToken}` },
      });
      requireSession(version);
      if (!response.ok) return null;
      const data = (await response.json()) as { access_token: string };
      requireSession(version);
      await tokenStorage.setTokens({ accessToken: data.access_token }, version);
      requireSession(version);
      return data.access_token;
    })().finally(() => {
      if (refresh?.promise === promise) refresh = null;
    });
    refresh = { version, promise };
  }
  return refresh.promise;
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
  return withRequestTimeout((signal) => performRequest<T>(path, options, signal), options.timeoutMs);
}

async function performRequest<T>(path: string, options: RequestOptions, signal?: AbortSignal): Promise<T> {
  const version = tokenStorage.getSessionVersion();
  const accessToken = options.anonymous ? null : await tokenStorage.getAccessToken();
  requireSession(version);
  let response = await rawRequest(path, options, accessToken, signal);
  requireSession(version);

  if (response.status === 401 && !options.anonymous) {
    const newToken = await refreshAccessToken(version);
    requireSession(version);
    if (newToken) {
      response = await rawRequest(path, options, newToken, signal);
    }
    requireSession(version);
    if (response.status === 401) {
      onUnauthorized?.();
    }
  }

  const body = await parseBody(response);
  requireSession(version);
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
