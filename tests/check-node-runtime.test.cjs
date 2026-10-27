const assert = require('node:assert/strict');
const { test } = require('node:test');
const { isSupportedNode } = require('../scripts/check-node-runtime.cjs');

test('rejects unpatched, unsupported, and prerelease Node runtimes', () => {
  for (const version of ['24.14.0', '24.22.0', '22.23.3', '26.12.0', '24.22.1-rc.1', 'garbage']) {
    assert.equal(isSupportedNode(version), false, version);
  }
});

test('accepts the security fix and later stable patches in the supported major', () => {
  for (const version of ['24.22.1', 'v24.22.1', '24.22.2', '24.23.0']) {
    assert.equal(isSupportedNode(version), true, version);
  }
});
