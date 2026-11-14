import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import configureApp from '../app.config.ts';

const config = JSON.parse(readFileSync(new URL('../app.json', import.meta.url))).expo;
const keys = ['EAS_BUILD_PROFILE', 'APP_VARIANT', 'EXPO_PUBLIC_API_URL', 'EAS_BUILD'];

function resolve(env = {}) {
  const saved = Object.fromEntries(keys.map((key) => [key, process.env[key]]));
  try {
    for (const key of keys) {
      if (env[key] === undefined) delete process.env[key];
      else process.env[key] = env[key];
    }
    return configureApp({ config });
  } finally {
    for (const key of keys) {
      if (saved[key] === undefined) delete process.env[key];
      else process.env[key] = saved[key];
    }
  }
}

test('preview builds and update jobs resolve the same update configuration', () => {
  const shared = { APP_VARIANT: 'preview', EXPO_PUBLIC_API_URL: 'https://keithriordan.herokuapp.com' };
  const build = resolve({ ...shared, EAS_BUILD_PROFILE: 'preview' });
  const update = resolve(shared);
  assert.deepEqual(build.updates, update.updates);
  assert.deepEqual(update.runtimeVersion, { policy: 'fingerprint' });
  assert.equal(update.updates.enabled, true);
  assert.equal(update.updates.checkAutomatically, 'ON_LOAD');
  assert.equal(update.updates.fallbackToCacheTimeout, 0);
});

test('an update job cannot silently bundle an absent or local API origin', () => {
  for (const origin of [undefined, '', 'http://localhost:5001', 'https://127.0.0.1', 'http://example.test']) {
    assert.throws(() => resolve({ APP_VARIANT: 'preview', EXPO_PUBLIC_API_URL: origin }), /EXPO_PUBLIC_API_URL/);
  }
});

test('development and production profiles cannot opt into preview updates through APP_VARIANT', () => {
  assert.equal(resolve().updates.enabled, false);
  for (const profile of ['development', 'production']) {
    assert.equal(resolve({ EAS_BUILD_PROFILE: profile, APP_VARIANT: 'preview',
      EXPO_PUBLIC_API_URL: 'https://keithriordan.herokuapp.com' }).updates.enabled, false);
  }
});
