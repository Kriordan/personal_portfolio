import assert from 'node:assert/strict';
import { test } from 'node:test';
import { failureTags, scrubMobileEvent } from '../src/lib/monitoring-policy.ts';

const id = '12345678-1234-1234-1234-123456789012';

test('operation correlation survives auth refresh and rejects content-bearing IDs', async (context) => {
  const { readFileSync } = await import('node:fs');
  const ts = (await import('typescript')).default;
  const source = readFileSync(new URL('../src/lib/api-client.ts', import.meta.url), 'utf8')
    .replace("import { API_BASE_URL, API_PREFIX } from '@/lib/config';", "const API_BASE_URL = 'https://fixture.test'; const API_PREFIX = '/api/v1';")
    .replace("import { tokenStorage } from '@/lib/token-storage';", "const tokenStorage = { getAccessToken: async () => 'access', getRefreshToken: async () => 'refresh', setTokens: async () => {} };")
    .replace("'@/lib/request-timeout'", JSON.stringify(new URL('../src/lib/request-timeout.ts', import.meta.url).href));
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
  const { apiRequest } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
  const calls = [];
  context.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push({ url, options });
    if (url.endsWith('/auth/refresh')) return new Response('{"access_token":"renewed"}');
    return new Response('{}', { status: calls.length === 1 ? 401 : 200 });
  });
  const request = { request_id: id, listing_url: 'https://job-boards.greenhouse.io/acme/jobs/123' };
  await apiRequest('/jobwizard/extractions', { method: 'POST', body: request, requestId: id });
  assert.equal(calls.length, 3);
  assert.equal(calls[0].options.headers['X-Request-ID'], id);
  assert.equal(calls[2].options.headers['X-Request-ID'], id);
  assert.equal(calls[0].options.body, calls[2].options.body);
  assert.equal(calls[1].options.headers['X-Request-ID'], undefined);
  await apiRequest('/jobwizard/extractions', { requestId: 'private@example.test' });
  assert.equal(calls[3].options.headers['X-Request-ID'], undefined);
});

test('only unexpected HTTP outcomes produce bounded diagnostic tags', () => {
  for (const status of [0, 401, 403, 404, 409, 410, 429]) {
    assert.equal(failureTags({ phase: 'read', requestId: id, status, code: 'unknown' }), null);
  }
  assert.equal(failureTags({ phase: 'read', requestId: id, status: 400, code: 'unsupported' }), null);
  assert.equal(failureTags({ phase: 'read', requestId: 'private@example.test', status: 500 }), null);
  assert.deepEqual(failureTags({ phase: 'read', requestId: id, status: 400, code: 'invalid_job' }), {
    operation: 'jobwizard.extraction', phase: 'read', request_id: id, status: '400', code: 'invalid_job',
  });
  assert.equal(failureTags({ phase: 'summary', requestId: id, status: 500, code: 'RAW PROVIDER BODY' }).code, 'unknown');
});

test('automatic error payload drops content and credentials but retains stack locations', () => {
  const secret = 'PRIVATE_CANARY_9472';
  const hint = { attachments: [{ filename: secret, data: secret }] };
  const event = scrubMobileEvent({
    event_id: 'test', release: 'app@1.0.0+2', environment: 'preview',
    message: secret, user: { email: secret }, request: { data: secret },
    extra: { notes: secret }, contexts: { job: { title: secret },
      device: { model: 'iPhone', name: secret }, os: { version: '27.0' } },
    breadcrumbs: [{ message: secret }], transaction: secret,
    tags: { request_id: id, operation: 'jobwizard.extraction', phase: 'read', code: 'invalid_job', private: secret },
    exception: { values: [{ type: 'TypeError', value: secret, stacktrace: {
      frames: [{ filename: `app:///index.bundle?token=${secret}`, lineno: 23, function: 'loadJob', vars: { token: secret }, context_line: secret }],
    } }] },
  }, hint);
  assert.equal(JSON.stringify(event).includes(secret), false);
  assert.equal(event.user.ip_address, '0.0.0.0');
  assert.equal(event.exception.values[0].stacktrace.frames[0].filename, 'app:///index.bundle');
  assert.equal(event.exception.values[0].stacktrace.frames[0].lineno, 23);
  assert.equal(event.tags.request_id, id);
  assert.equal(event.contexts.device.model, 'iPhone');
  assert.equal(event.contexts.os.version, '27.0');
  assert.equal(hint.attachments, undefined);
});

// Exercise the runtime reporter too: the pure policy tests cannot detect a
// disconnected beforeSend hook, duplicate reports, or a throwing SDK adapter.
let monitoringModuleId = 0;
async function loadMonitoring({ enabled = '1', platform = 'ios', development = false, dsn = 'https://public@example.invalid/1', failCapture = false } = {}) {
  const { readFileSync } = await import('node:fs');
  const ts = (await import('typescript')).default;
  let source = readFileSync(new URL('../src/lib/monitoring.ts', import.meta.url), 'utf8')
    .replace("import * as Sentry from '@sentry/react-native';", `
      export const calls = { initialized: 0, events: [], options: null };
      const Sentry = {
        init(options) { calls.initialized++; calls.options = options; },
        setUser() {}, setTag() {},
        captureMessage(message, context) {
          if (${failCapture}) throw new Error('Transport unavailable');
          calls.events.push(calls.options.beforeSend({ message, ...context, extra: { private: 'PRIVATE_CANARY' } }));
        },
      };
      const __DEV__ = ${development};
    `)
    .replace("import Constants from 'expo-constants';", "const Constants = { expoConfig: { extra: { monitoringCommit: 'abcdef1234567' } } };")
    .replace("import { Platform } from 'react-native';", `const Platform = { OS: ${JSON.stringify(platform)} };`)
    .replace("'./monitoring-policy'", JSON.stringify(new URL('../src/lib/monitoring-policy.ts', import.meta.url).href))
    .replaceAll('process.env.EXPO_PUBLIC_SENTRY_ENABLED', JSON.stringify(enabled))
    .replaceAll('process.env.EXPO_PUBLIC_SENTRY_DSN', JSON.stringify(dsn))
    .replaceAll('process.env.EXPO_PUBLIC_SENTRY_ENVIRONMENT', "'test'");
  source += `\n// isolated test module ${++monitoringModuleId}\n`;
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
  return import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
}

test('runtime reporting stays inactive without native release opt-in', async () => {
  for (const options of [{ enabled: '0' }, { development: true }, { platform: 'web' }, { dsn: '' }]) {
    const runtime = await loadMonitoring(options);
    runtime.initializeMonitoring();
    runtime.reportOperationFailure({ phase: 'read', requestId: id, status: 500, code: 'failed' });
    assert.equal(runtime.calls.initialized, 0);
    assert.deepEqual(runtime.calls.events, []);
  }
});

test('runtime reports one scrubbed event for an unexpected outcome and keeps recovery outcomes quiet', async () => {
  const runtime = await loadMonitoring();
  runtime.initializeMonitoring();
  runtime.initializeMonitoring();
  assert.equal(runtime.calls.initialized, 1);
  for (const status of [0, 401, 403, 404, 409, 410, 429])
    runtime.reportOperationFailure({ phase: 'read', requestId: id, status, code: 'unknown' });
  for (const code of ['unsupported', 'unavailable'])
    runtime.reportOperationFailure({ phase: 'read', requestId: id, status: 503, code });
  assert.deepEqual(runtime.calls.events, []);
  const failure = { phase: 'read', requestId: id, status: 400, code: 'invalid_request' };
  runtime.reportOperationFailure(failure);
  runtime.reportOperationFailure(failure);
  assert.equal(runtime.calls.events.length, 1);
  assert.equal(runtime.calls.events[0].tags.request_id, id);
  assert.equal(JSON.stringify(runtime.calls.events).includes('PRIVATE_CANARY'), false);
});

test('a throwing monitoring transport does not escape to the operation caller', async () => {
  const runtime = await loadMonitoring({ failCapture: true });
  runtime.initializeMonitoring();
  assert.doesNotThrow(() => runtime.reportOperationFailure({ phase: 'summary', requestId: id, status: 500, code: 'provider_auth' }));
});
