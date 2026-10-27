import assert from 'node:assert/strict';
import { test } from 'node:test';
import configure from '../app.config.ts';

test('monitoring build config keeps upload credentials out of the app and requires complete enabled setup', () => {
  const keys = ['EAS_BUILD_PROFILE', 'EAS_BUILD', 'EAS_BUILD_GIT_COMMIT_HASH', 'EXPO_PUBLIC_SENTRY_ENABLED',
    'EXPO_PUBLIC_SENTRY_DSN', 'EXPO_PUBLIC_SENTRY_ENVIRONMENT', 'SENTRY_ORG', 'SENTRY_PROJECT', 'SENTRY_AUTH_TOKEN'];
  const old = Object.fromEntries(keys.map((key) => [key, process.env[key]]));
  const context = { config: { name: 'Preview', slug: 'preview' } };
  try {
    keys.forEach((key) => delete process.env[key]);
    process.env.SENTRY_AUTH_TOKEN = 'PRIVATE_UPLOAD_CANARY';
    process.env.EAS_BUILD_GIT_COMMIT_HASH = 'abcdef1234567';
    const disabled = configure(context);
    assert.equal(disabled.plugins.length, 0);
    assert.equal(disabled.extra.monitoringCommit, 'abcdef1234567');
    assert.equal(JSON.stringify(disabled).includes('PRIVATE_UPLOAD_CANARY'), false);
    process.env.EAS_BUILD = 'true';
    process.env.EXPO_PUBLIC_SENTRY_ENABLED = '1';
    assert.throws(() => configure(context), /Enabled Sentry builds require/);
    process.env.EXPO_PUBLIC_SENTRY_DSN = 'https://public@example.invalid/1';
    process.env.EXPO_PUBLIC_SENTRY_ENVIRONMENT = 'preview';
    process.env.SENTRY_ORG = 'example';
    process.env.SENTRY_PROJECT = 'mobile';
    const enabled = configure(context);
    assert.equal(enabled.plugins.at(-1)[0], '@sentry/react-native/expo');
    assert.equal(JSON.stringify(enabled).includes('PRIVATE_UPLOAD_CANARY'), false);
    delete process.env.SENTRY_AUTH_TOKEN;
    assert.throws(() => configure(context), /Enabled Sentry builds require/);
  } finally {
    for (const key of keys) {
      if (old[key] === undefined) delete process.env[key];
      else process.env[key] = old[key];
    }
  }
});

test('preview and production builds require a device-reachable HTTPS API URL', () => {
  const oldProfile = process.env.EAS_BUILD_PROFILE;
  const oldUrl = process.env.EXPO_PUBLIC_API_URL;
  const context = { config: { name: 'Preview', slug: 'preview' } };
  try {
    for (const profile of ['preview', 'production']) {
      process.env.EAS_BUILD_PROFILE = profile;
      for (const url of [
        '',
        'not a URL',
        'http://api.example.com',
        'https://localhost:5001',
        'https://127.0.0.1',
        'https://10.0.2.2',
        'https://[::1]',
      ]) {
        process.env.EXPO_PUBLIC_API_URL = url;
        assert.throws(() => configure(context), /EXPO_PUBLIC_API_URL/);
      }
      process.env.EXPO_PUBLIC_API_URL = 'https://api.example.com';
      assert.equal(configure(context).name, context.config.name);
      assert.equal(configure(context).slug, context.config.slug);
    }
    process.env.EAS_BUILD_PROFILE = 'development';
    delete process.env.EXPO_PUBLIC_API_URL;
    assert.equal(configure(context).name, context.config.name);
  } finally {
    if (oldProfile === undefined) delete process.env.EAS_BUILD_PROFILE;
    else process.env.EAS_BUILD_PROFILE = oldProfile;
    if (oldUrl === undefined) delete process.env.EXPO_PUBLIC_API_URL;
    else process.env.EXPO_PUBLIC_API_URL = oldUrl;
  }
});
