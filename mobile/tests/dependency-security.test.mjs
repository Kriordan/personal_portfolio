import assert from 'node:assert/strict';
import { constants, createHash, generateKeyPairSync, privateEncrypt, sign } from 'node:crypto';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import test from 'node:test';

const require = createRequire(import.meta.url);
const expo = createRequire(require.resolve('expo/package.json'));
const cli = createRequire(expo.resolve('@expo/cli/package.json'));
const router = createRequire(require.resolve('expo-router/package.json'));
const query = router('query-string');

test('Router query parsing preserves normal, Unicode, duplicate and malformed values', () => {
  assert.deepEqual({ ...query.parse('name=hello+world&emoji=%F0%9F%9A%80&tag=a&tag=b&empty=&flag') }, {
    name: 'hello world', emoji: '🚀', tag: ['a', 'b'], empty: '', flag: null,
  });
  const original = { next: '/jobwizard/jobs/123?mode=edit', text: 'café & tea', empty: '' };
  assert.deepEqual({ ...query.parse(query.stringify(original)) }, original);
  assert.equal(query.parse('value=%41%ZZ%E2%82%AC').value, 'A%ZZ€');
  assert.equal(query.parse('value=%252F').value, '%2F');
});

test('Router malformed-percent decoding completes within a bounded subprocess', () => {
  // Keep a regressed decoder from hanging the test runner itself.
  const child = spawnSync(process.execPath, ['--input-type=commonjs', '-e', `
    const assert = require('node:assert/strict');
    const query = require(${JSON.stringify(router.resolve('query-string'))});
    for (const fragment of ['%C0', '%FF', '%E0%A4', '%C2', '%41%FE']) {
      const value = query.parse('value=' + fragment.repeat(20000)).value;
      assert.equal(typeof value, 'string');
      assert.ok(value.length > 0);
    }
  `], { timeout: 5000, encoding: 'utf8' });
  assert.ifError(child.error);
  assert.equal(child.status, 0, child.stderr);
});

test('Expo JSON Schema rejects oversized arrays before visiting their elements', () => {
  const { validate, ValidationError } = cli('@expo/schema-utils');
  let visited = 0;
  const values = [1, 2];
  Object.defineProperty(values, 0, { get() { visited++; return 1; } });
  assert.throws(() => validate({ type: 'array', maxItems: 1, items: { type: 'number' } }, values), ValidationError);
  assert.equal(visited, 0);
  assert.doesNotThrow(() => validate({ type: 'array', maxItems: 1, items: { type: 'number' } }, [1]));
});

test('real Expo JSON and MCP schemas accept valid plugin data and reject malformed data', () => {
  const { PluginSchema, DevToolsPluginOutputSchema } = cli('./build/src/start/server/devtools/DevToolsPlugin.schema.js');
  const { createMCPDevToolsExtensionSchema } = cli('./build/src/start/server/mcp/createMCPDevToolsExtensionSchema.js');
  const { validate, ValidationError } = cli('@expo/schema-utils');
  const plugin = {
    packageName: 'fixture-plugin', packageRoot: '/tmp/fixture-plugin',
    cliExtensions: {
      description: 'Fixture', entryPoint: './commands.js',
      commands: [{ name: 'inspect', title: 'Inspect', environments: ['cli', 'mcp'],
        parameters: [{ name: 'limit', type: 'number' }, { name: 'confirm', type: 'confirm' }] }],
    },
  };
  assert.doesNotThrow(() => validate(PluginSchema, plugin));
  assert.throws(() => validate(PluginSchema, { ...plugin, packageName: '' }), ValidationError);
  assert.throws(() => validate(PluginSchema, {
    ...plugin, cliExtensions: { ...plugin.cliExtensions, commands: [] },
  }), ValidationError);
  // The new CLI accepts Zod from an optional MCP provider; it no longer installs Zod 3.
  const hooks = createRequire(require.resolve('eslint-plugin-react-hooks/package.json'));
  const schema = createMCPDevToolsExtensionSchema(plugin, hooks('zod/v4'));
  assert.deepEqual(schema.parse({ command: 'inspect', limit: 3, confirm: true }), { command: 'inspect', limit: 3, confirm: true });
  for (const invalid of [{ command: 'unknown' }, { command: 'inspect', limit: '3' }, { command: 'inspect', extra: true }]) {
    assert.equal(schema.safeParse(invalid).success, false);
  }
  const lines = [{ type: 'text', text: 'ok', level: 'info' }, { type: 'image', url: 'https://example.com/pixel.png' }];
  assert.doesNotThrow(() => validate(DevToolsPluginOutputSchema, lines));
  for (const invalid of [[{ type: 'text', text: 'missing level' }], [{ type: 'image', url: 'invalid url' }]]) {
    assert.throws(() => validate(DevToolsPluginOutputSchema, invalid), ValidationError);
  }
});

test('ESLint uses fixed Zod 4 and rejects constrained oversized collections without visiting entries', () => {
  const hooks = createRequire(require.resolve('eslint-plugin-react-hooks/package.json'));
  const v4 = hooks('zod/v4');
  assert.equal(hooks('zod/package.json').version, '4.6.7');
  let visited = 0;
  const element = v4.any().transform(value => { visited++; return value; });
  assert.equal(v4.array(element).max(1).safeParse([1, 2]).success, false);
  assert.equal(v4.set(element).max(1).safeParse(new Set([1, 2])).success, false);
  assert.equal(v4.map(element, element).max(1).safeParse(new Map([[1, 1], [2, 2]])).success, false);
  assert.equal(visited, 0);
});

test('Expo signing tools reject extra nested DigestAlgorithm elements with real RSA padding', () => {
  const certificateTools = createRequire(cli.resolve('@expo/code-signing-certificates/package.json'));
  const libraries = [cli('node-forge'), certificateTools('node-forge')];
  const message = Buffer.from('local security regression fixture');
  const { publicKey, privateKey } = generateKeyPairSync('rsa', { modulusLength: 2048, publicExponent: 3 });
  const valid = sign('sha256', message, privateKey);
  const digest = createHash('sha256').update(message).digest('binary');
  for (const forge of libraries) {
    const key = forge.pki.publicKeyFromPem(publicKey.export({ type: 'spki', format: 'pem' }));
    assert.equal(key.verify(digest, valid.toString('binary')), true);
    const { asn1 } = forge;
    const sequence = children => asn1.create(asn1.Class.UNIVERSAL, asn1.Type.SEQUENCE, true, children);
    const malformed = sequence([
      sequence([
        asn1.create(asn1.Class.UNIVERSAL, asn1.Type.OID, false, asn1.oidToDer(forge.pki.oids.sha256).getBytes()),
        asn1.create(asn1.Class.UNIVERSAL, asn1.Type.NULL, false, ''),
        asn1.create(asn1.Class.UNIVERSAL, asn1.Type.OCTETSTRING, false, 'unexpected nested data'),
      ]),
      asn1.create(asn1.Class.UNIVERSAL, asn1.Type.OCTETSTRING, false, digest),
    ]);
    const signature = privateEncrypt({ key: privateKey, padding: constants.RSA_PKCS1_PADDING }, Buffer.from(asn1.toDer(malformed).getBytes(), 'binary'));
    assert.throws(() => key.verify(digest, signature.toString('binary')), /DigestInfo/);
  }
});

test('Expo signing tools reject forged Ed25519 signatures using an identity public key', () => {
  const { ed25519 } = cli('node-forge');
  const message = Buffer.from('signature fixture');
  const keys = ed25519.generateKeyPair();
  const signature = ed25519.sign({ message, privateKey: keys.privateKey });
  assert.equal(ed25519.verify({ message, signature, publicKey: keys.publicKey }), true);
  const identityKey = Buffer.alloc(32);
  identityKey[0] = 1;
  const forgedSignature = Buffer.alloc(64);
  forgedSignature[0] = 1;
  assert.equal(ed25519.verify({ message, signature: forgedSignature, publicKey: identityKey }), false);
});

test('scoped minimatch updates preserve fingerprint ignores and parser path matching', () => {
  const fingerprint = createRequire(expo.resolve('@expo/fingerprint/package.json'));
  const parser = createRequire(require.resolve('@typescript-eslint/typescript-estree/package.json'));
  const { isIgnoredPath, buildPathMatchObjects, buildDirMatchObjects } = fingerprint('./build/utils/Path.js');
  const patterns = ['**/node_modules/**', 'assets/**', '!assets/keep.png'];
  assert.equal(isIgnoredPath('../node_modules/pkg/index.js', patterns), true);
  assert.equal(isIgnoredPath('assets/image.png', patterns), true);
  assert.equal(isIgnoredPath('assets/keep.png', patterns), false);
  assert.equal(isIgnoredPath('src/app/index.tsx', patterns), false);
  assert.ok(buildDirMatchObjects(buildPathMatchObjects(['build/**'])).some(match => match.match('build')));
  for (const consumer of [fingerprint, parser]) {
    assert.equal(consumer('minimatch/package.json').version, '11.0.8');
    const { minimatch } = consumer('minimatch');
    assert.equal(minimatch('src/.hidden.ts', 'src/*.ts', { dot: true }), true);
    assert.equal(minimatch('src/app/index.tsx', 'src/**/*.{ts,tsx}'), true);
    assert.equal(minimatch('src/app/image.png', 'src/**/*.{ts,tsx}'), false);
    const child = spawnSync(process.execPath, ['--input-type=commonjs', '-e', `
      const assert = require('node:assert/strict');
      const { Minimatch } = require(${JSON.stringify(consumer.resolve('minimatch'))});
      assert.throws(() => new Minimatch('**/../a/b/'.repeat(32) + 'x', {
        optimizationLevel: 2, braceExpandMax: 100,
      }), RangeError);
    `], { timeout: 5000, encoding: 'utf8' });
    assert.ifError(child.error);
    assert.equal(child.status, 0, child.stderr);
  }
});
