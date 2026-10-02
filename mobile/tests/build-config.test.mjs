import assert from 'node:assert/strict';
import { test } from 'node:test';
import configure from '../app.config.ts';

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
      assert.equal(configure(context), context.config);
    }
    process.env.EAS_BUILD_PROFILE = 'development';
    delete process.env.EXPO_PUBLIC_API_URL;
    assert.equal(configure(context), context.config);
  } finally {
    if (oldProfile === undefined) delete process.env.EAS_BUILD_PROFILE;
    else process.env.EAS_BUILD_PROFILE = oldProfile;
    if (oldUrl === undefined) delete process.env.EXPO_PUBLIC_API_URL;
    else process.env.EXPO_PUBLIC_API_URL = oldUrl;
  }
});
