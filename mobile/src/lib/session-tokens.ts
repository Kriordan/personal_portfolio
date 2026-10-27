interface TokenStore {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
  remove(key: string): Promise<void>;
}

const accessKey = 'auth.access_token';
const refreshKey = 'auth.refresh_token';

/** Account changes invalidate work immediately; disk operations stay ordered. */
export function createSessionTokens(store: TokenStore) {
  let version = 0;
  let tail: Promise<unknown> = Promise.resolve();
  function serial<T>(run: () => Promise<T>): Promise<T> {
    const next = tail.then(run, run);
    tail = next.catch(() => {});
    return next;
  }
  return {
    getSessionVersion: () => version,
    getAccessToken: () => serial(() => store.get(accessKey)),
    getRefreshToken: () => serial(() => store.get(refreshKey)),
    setTokens(tokens: { accessToken: string; refreshToken?: string }, expectedVersion = version) {
      if (expectedVersion !== version) return Promise.resolve(false);
      // A login starts a new session; an access-token refresh does not.
      const owner = tokens.refreshToken === undefined ? version : ++version;
      return serial(async () => {
        if (owner !== version) return false;
        await store.set(accessKey, tokens.accessToken);
        if (tokens.refreshToken !== undefined) await store.set(refreshKey, tokens.refreshToken);
        return owner === version;
      });
    },
    clear() {
      ++version;
      return serial(async () => {
        await Promise.all([store.remove(accessKey), store.remove(refreshKey)]);
      });
    },
  };
}
