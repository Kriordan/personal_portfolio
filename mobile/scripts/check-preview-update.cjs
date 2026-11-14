const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const { getConfig } = require('@expo/config');
const { createFingerprintAsync } = require('expo/fingerprint');

assert.equal(process.env.APP_VARIANT, 'preview', 'Select the preview EAS environment');
assert.equal(process.env.EXPO_PUBLIC_API_URL, 'https://keithriordan.herokuapp.com',
  'Preview updates must use the same API as the installed preview');
assert.equal(process.env.EXPO_PUBLIC_SENTRY_ENABLED, '1', 'Preserve preview error reporting');
for (const name of ['EXPO_PUBLIC_SENTRY_DSN', 'SENTRY_ORG', 'SENTRY_PROJECT', 'SENTRY_AUTH_TOKEN']) {
  assert.ok(process.env[name]?.trim(), `Missing ${name}; publish through the Expo workflow`);
}
const { exp } = getConfig(process.cwd());
assert.equal(exp.updates?.enabled, true, 'Preview updates must be enabled');
assert.equal(exp.runtimeVersion?.policy, 'fingerprint', 'Native compatibility must use fingerprints');
assert.equal(exp.updates?.url, 'https://u.expo.dev/02007b1c-386b-4348-8e84-7cc98d6ae38d');

async function checkMatchingBuild() {
  // Match expo-updates' managed-project fingerprint, excluding generated projects.
  const { hash } = await createFingerprintAsync(process.cwd(), {
    platforms: ['ios'], ignorePaths: ['android/**/*', 'ios/**/*'],
  });
  // Pre-packaged workflow workers do not expose a global `eas` executable.
  const builds = JSON.parse(execFileSync('npx', [
    '--yes', 'eas-cli@27.10.0',
    'build:list', '--platform', 'ios', '--build-profile', 'preview',
    '--channel', 'preview', '--distribution', 'internal', '--status', 'finished',
    '--runtime-version', hash, '--limit', '1', '--json', '--non-interactive',
  ], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }));
  assert.ok(builds.length > 0,
    `No finished iPhone preview matches runtime ${hash}. Create a new native preview before publishing.`);
  console.log(`Preview API, Sentry uploads, and matching native runtime verified: ${hash}`);
}

checkMatchingBuild().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
