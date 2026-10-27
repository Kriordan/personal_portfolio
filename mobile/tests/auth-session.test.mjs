import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { test } from 'node:test';
import ts from 'typescript';
import { createSessionTokens } from '../src/lib/session-tokens.ts';

const deferred = () => {
  let resolve;
  const promise = new Promise((yes) => { resolve = yes; });
  return { promise, resolve };
};
const tick = () => new Promise((resolve) => setImmediate(resolve));

async function client(context) {
  let version = 0, access = 'account-a', refresh = 'refresh-a';
  const storage = {
    getSessionVersion: () => version,
    getAccessToken: async () => access,
    getRefreshToken: async () => refresh,
    setTokens: async (tokens, expected = version) => {
      if (expected !== version) return false;
      access = tokens.accessToken;
      return true;
    },
  };
  const key = randomUUID();
  globalThis[key] = storage;
  context.after(() => { delete globalThis[key]; });
  const source = readFileSync(new URL('../src/lib/api-client.ts', import.meta.url), 'utf8')
    .replace("import { API_BASE_URL, API_PREFIX } from '@/lib/config';", "const API_BASE_URL = 'https://fixture.test'; const API_PREFIX = '/api/v1';")
    .replace("import { tokenStorage } from '@/lib/token-storage';", `const tokenStorage = globalThis[${JSON.stringify(key)}];`)
    .replace("'@/lib/request-timeout'", JSON.stringify(new URL('../src/lib/request-timeout.ts', import.meta.url).href));
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
  const api = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
  return {
    ...api, storage,
    switchAccount: () => { version++; access = 'account-b'; refresh = 'refresh-b'; },
  };
}

test('a delayed 401 cannot replay an old save under the new account', async (context) => {
  const api = await client(context), gate = deferred(), calls = [];
  context.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push({ url, authorization: options.headers.Authorization });
    if (calls.length === 1) return gate.promise;
    if (url.endsWith('/auth/refresh')) return Response.json({ access_token: 'renewed-b' });
    return Response.json({ saved: true });
  });
  const pending = api.apiRequest('/jobwizard/jobs', { method: 'POST', body: { title: 'Account A draft' } });
  const rejected = assert.rejects(pending, /session changed/i);
  await tick();
  api.switchAccount();
  gate.resolve(new Response('{}', { status: 401 }));
  await rejected;
  assert.equal(calls.length, 1, 'no refresh or write may use account B');
});

test('a late refresh cannot replace the new account token or log it out', async (context) => {
  const api = await client(context), gate = deferred();
  let logouts = 0;
  api.setUnauthorizedListener(() => { logouts++; });
  context.mock.method(globalThis, 'fetch', async (url) => url.endsWith('/auth/refresh')
    ? gate.promise : new Response('{}', { status: 401 }));
  const pending = api.apiRequest('/jobwizard/jobs');
  const rejected = assert.rejects(pending, /session changed/i);
  await tick();
  api.switchAccount();
  gate.resolve(Response.json({ access_token: 'renewed-a' }));
  await rejected;
  assert.equal(await api.storage.getAccessToken(), 'account-b');
  assert.equal(logouts, 0);
});

test('late successful reads and failed refreshes cannot update the new session', async (context) => {
  for (const status of [200, 401]) {
    const api = await client(context), gate = deferred();
    let calls = 0, logouts = 0;
    api.setUnauthorizedListener(() => { logouts++; });
    const mock = context.mock.method(globalThis, 'fetch', async () => {
      calls++;
      if (status === 401 && calls === 1) return new Response('{}', { status: 401 });
      return gate.promise;
    });
    const pending = api.apiRequest('/auth/me');
    const rejected = assert.rejects(pending, /session changed/i);
    await tick();
    api.switchAccount();
    gate.resolve(new Response('{}', { status }));
    await rejected;
    assert.equal(logouts, 0);
    mock.mock.restore();
  }
});

test('new account refresh does not join or get cleared by the previous refresh', async (context) => {
  const api = await client(context), old = deferred(), current = deferred(), calls = [];
  context.mock.method(globalThis, 'fetch', async (_url, options) => {
    calls.push(options.headers.Authorization);
    return calls.length === 1 ? old.promise : current.promise;
  });
  const first = api.refreshAccessToken();
  const rejected = assert.rejects(first, /session changed/i);
  await tick();
  api.switchAccount();
  const second = api.refreshAccessToken();
  await tick();
  old.resolve(Response.json({ access_token: 'stale' }));
  await rejected;
  const third = api.refreshAccessToken();
  current.resolve(Response.json({ access_token: 'renewed-b' }));
  assert.deepEqual(await Promise.all([second, third]), ['renewed-b', 'renewed-b']);
  assert.deepEqual(calls, ['Bearer refresh-a', 'Bearer refresh-b']);
});

test('serialized token writes cannot resurrect a signed-out account', async () => {
  const values = new Map(), gate = deferred();
  const tokens = createSessionTokens({
    get: async (key) => values.get(key) ?? null,
    set: async (key, value) => {
      if (value === 'late-a') await gate.promise;
      values.set(key, value);
    },
    remove: async (key) => { values.delete(key); },
  });
  await tokens.setTokens({ accessToken: 'a', refreshToken: 'refresh-a' });
  const oldVersion = tokens.getSessionVersion();
  const late = tokens.setTokens({ accessToken: 'late-a' }, oldVersion);
  await tick();
  const logout = tokens.clear();
  assert.notEqual(tokens.getSessionVersion(), oldVersion, 'invalidation is synchronous');
  const login = tokens.setTokens({ accessToken: 'b', refreshToken: 'refresh-b' });
  gate.resolve();
  await Promise.all([late, logout, login]);
  assert.equal(await tokens.getAccessToken(), 'b');
  assert.equal(await tokens.getRefreshToken(), 'refresh-b');
  assert.equal(await tokens.setTokens({ accessToken: 'stale' }, oldVersion), false);
  await tokens.clear();
  assert.equal(await tokens.getAccessToken(), null);
  assert.equal(await tokens.getRefreshToken(), null);
});

test('account changes during token reads or response parsing discard the request', async (context) => {
  const beforeSend = await client(context), token = deferred();
  beforeSend.storage.getAccessToken = () => token.promise;
  let sends = 0;
  context.mock.method(globalThis, 'fetch', async () => {
    sends++;
    return Response.json({ private: 'account-a' });
  });
  const unsent = beforeSend.apiRequest('/jobwizard/jobs', { method: 'POST', body: {} });
  const unsentRejected = assert.rejects(unsent, /session changed/i);
  beforeSend.switchAccount();
  token.resolve('account-a');
  await unsentRejected;
  assert.equal(sends, 0);

  const parsing = await client(context), body = deferred();
  context.mock.method(globalThis, 'fetch', async () => ({ ok: true, status: 200, text: () => body.promise }));
  const reading = parsing.apiRequest('/jobwizard/jobs');
  const readingRejected = assert.rejects(reading, /session changed/i);
  await tick();
  parsing.switchAccount();
  body.resolve('{"private":"account-a"}');
  await readingRejected;
});

test('a failed token deletion still waits for its sibling before the next login', async () => {
  const values = new Map(), removal = deferred();
  const tokens = createSessionTokens({
    get: async (key) => values.get(key) ?? null,
    set: async (key, value) => { values.set(key, value); },
    remove: async (key) => {
      if (key === 'auth.access_token') throw new Error('storage unavailable');
      await removal.promise;
      values.delete(key);
    },
  });
  await tokens.setTokens({ accessToken: 'a', refreshToken: 'refresh-a' });
  const cleanup = assert.rejects(tokens.clear(), /storage unavailable/);
  const login = tokens.setTokens({ accessToken: 'b', refreshToken: 'refresh-b' });
  await tick();
  assert.equal(values.get('auth.access_token'), 'a', 'new writes wait for all old deletes');
  removal.resolve();
  await Promise.all([cleanup, login]);
  assert.equal(await tokens.getAccessToken(), 'b');
  assert.equal(await tokens.getRefreshToken(), 'refresh-b');
});
