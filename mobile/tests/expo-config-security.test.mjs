import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

const require = createRequire(import.meta.url);
const expo = createRequire(require.resolve('expo/package.json'));
const { modifyConfigAsync } = expo('@expo/config');

async function modifyFixture(config, changes) {
  const directory = mkdtempSync(join(tmpdir(), 'expo-config-security-'));
  try {
    writeFileSync(join(directory, 'package.json'), JSON.stringify({ name: 'config-fixture', version: '1.0.0' }));
    writeFileSync(join(directory, 'app.json'), JSON.stringify({ expo: { name: 'Fixture', slug: 'fixture', ...config } }));
    const result = await modifyConfigAsync(directory, changes, { skipSDKVersionRequirement: true, skipPlugins: true });
    assert.equal(result.type, 'success');
    assert.deepEqual(JSON.parse(readFileSync(join(directory, 'app.json'), 'utf8')).expo, result.config);
    return result.config;
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

function assertSafe(value) {
  assert.equal(Object.getPrototypeOf(value), Object.prototype);
  assert.equal(Object.hasOwn(value, '__proto__'), false);
  assert.equal(value.injectedFlag, undefined);
  assert.equal({}.injectedFlag, undefined);
}

test('Expo config modifications cannot poison results through target or source keys', async () => {
  const poisoned = () => JSON.parse('{"__proto__":{"injectedFlag":true},"safe":"kept"}');
  for (const placeholder of [null, 0, false, '']) {
    const result = await modifyFixture({ extra: { session: placeholder } }, { extra: { session: poisoned() } });
    assertSafe(result.extra.session);
    assert.equal(result.extra.session.safe, 'kept');
  }
  const target = await modifyFixture({ extra: poisoned() }, { extra: { added: true } });
  assertSafe(target.extra);
  assert.equal(target.extra.safe, 'kept');
  const plugin = await modifyFixture({ plugins: [['fixture-plugin', { session: null }]] }, {
    plugins: [['fixture-plugin', { session: poisoned() }]],
  });
  assertSafe(plugin.plugins[0][1].session);
  const array = await modifyFixture({ extra: { items: [poisoned()] } }, { extra: { items: [poisoned()] } });
  for (const item of array.extra.items) assertSafe(item);
});

test('Expo config modifications preserve nested settings, arrays and existing plugin options', async () => {
  const result = await modifyFixture({
    ios: { infoPlist: { UIBackgroundModes: ['audio'], ExistingFlag: true } },
    extra: { flags: { original: true }, values: ['first'] },
    plugins: [['fixture-plugin', { nested: { original: true }, values: ['first'] }], 'untouched-plugin'],
  }, {
    ios: { infoPlist: { AddedFlag: true } },
    extra: { flags: { added: true }, values: ['second'] },
    plugins: [['fixture-plugin', { nested: { added: true }, values: ['second'] }], 'new-plugin'],
  });
  assert.deepEqual(result.ios.infoPlist, { UIBackgroundModes: ['audio'], ExistingFlag: true, AddedFlag: true });
  assert.deepEqual(result.extra, { flags: { original: true, added: true }, values: ['first', 'second'] });
  assert.deepEqual(result.plugins, [
    ['fixture-plugin', { nested: { original: true, added: true }, values: ['first', 'second'] }],
    'untouched-plugin', 'new-plugin',
  ]);
});

test('Expo no longer installs the vulnerable merge or legacy CLI schema packages', () => {
  const { packages } = require('../package-lock.json');
  for (const [location, pkg] of Object.entries(packages)) {
    assert.ok(!location.endsWith('/deepmerge'), `Unexpected deepmerge at ${location}`);
    assert.ok(!pkg.dependencies?.deepmerge, `Unexpected deepmerge consumer: ${location}`);
    assert.ok(!location.endsWith('/zod-upstream') && !location.endsWith('/zod-v3'), `Unexpected legacy Zod adapter: ${location}`);
    if (location.endsWith('/zod')) assert.match(pkg.version, /^4\./);
  }
});
