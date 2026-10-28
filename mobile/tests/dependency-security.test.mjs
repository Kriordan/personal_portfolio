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
const z = cli('zod');

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

test('Expo Zod rejects oversized constrained arrays and sets before visiting elements', async () => {
  let visited = 0;
  let refined = 0;
  const element = z.any().transform(value => { visited++; return value; });
  for (const schema of [z.array(element).max(1), z.array(element).length(1)]) {
    const result = schema.refine(() => { refined++; return true; }).safeParse([1, 2]);
    assert.equal(result.success, false);
    assert.equal(result.error.issues.length, 1);
    assert.equal(result.error.issues[0].code, 'too_big');
    assert.equal((await schema.safeParseAsync([1, 2])).success, false);
  }
  assert.equal(z.set(element).max(1).safeParse(new Set([1, 2])).success, false);
  assert.equal(visited, 0);
  assert.equal(refined, 0);
  const nested = z.object({ values: z.array(element).max(1, 'bounded') }).safeParse({ values: [1, 2] });
  assert.deepEqual(nested.error.issues[0].path, ['values']);
  assert.equal(nested.error.issues[0].message, 'bounded');
  assert.deepEqual(z.array(z.string().transform(value => value.toUpperCase())).max(2).parse(['a']), ['A']);
  assert.equal(z.array(z.string()).safeParse('wrong type').error.issues[0].code, 'invalid_type');
});

test('Expo tooling bounds unconstrained and nested collection work with a fresh budget per parse', async () => {
  let visited = 0;
  const element = z.any().transform(value => { visited++; return value; });
  for (const [schema, input] of [
    [z.array(element), Array(1001).fill(0)],
    [z.set(element), new Set(Array.from({ length: 1001 }, (_, i) => i))],
    [z.map(element, element), new Map(Array.from({ length: 1001 }, (_, i) => [i, i]))],
  ]) {
    assert.equal(schema.safeParse(input).success, false);
    assert.equal((await schema.safeParseAsync(input)).success, false);
  }
  assert.equal(visited, 0);
  assert.equal(z.array(z.array(element)).safeParse([Array(600).fill(0), Array(600).fill(0)]).success, false);
  assert.equal(visited, 600);
  for (let attempt = 0; attempt < 3; attempt++) {
    assert.equal(z.array(z.number()).parse(Array(1000).fill(1)).length, 1000);
  }
  let alternateVisits = 0;
  const union = z.union([
    z.array(z.number().refine(() => false)),
    z.array(z.number().transform(value => { alternateVisits++; return value; })),
  ]);
  assert.equal(union.safeParse(Array(600).fill(1)).success, false);
  assert.equal((await union.safeParseAsync(Array(600).fill(1))).success, false);
  assert.equal(alternateVisits, 0);
  const caught = z.object({
    first: z.array(z.number()).catch([]),
    second: z.array(z.number()),
  });
  assert.equal(caught.safeParse({ first: Array(600).fill(1), second: Array(600).fill(1) }).success, false);
});

test('real Expo plugin and MCP schemas preserve the Zod 3 interface and reject oversized output', () => {
  const { PluginSchema, DevToolsPluginOutputSchema } = cli('./build/src/start/server/DevToolsPlugin.schema.js');
  const { createMCPDevToolsExtensionSchema } = cli('./build/src/start/server/createMCPDevToolsExtensionSchema.js');
  const plugin = PluginSchema.parse({
    packageName: 'fixture-plugin', packageRoot: '/tmp/fixture-plugin',
    cliExtensions: {
      description: 'Fixture', entryPoint: './commands.js',
      commands: [{ name: 'inspect', title: 'Inspect', environments: ['cli', 'mcp'],
        parameters: [{ name: 'limit', type: 'number' }, { name: 'confirm', type: 'confirm' }] }],
    },
  });
  const schema = createMCPDevToolsExtensionSchema(plugin);
  assert.equal(schema._def.typeName, 'ZodObject');
  assert.deepEqual(schema.parse({ command: 'inspect', limit: 3, confirm: true }), { command: 'inspect', limit: 3, confirm: true });
  for (const invalid of [{ command: 'unknown' }, { command: 'inspect', limit: '3' }, { command: 'inspect', extra: true }]) {
    assert.equal(schema.safeParse(invalid).success, false);
  }
  const lines = [{ type: 'text', text: 'ok', level: 'info' }, { type: 'image', url: 'https://example.com/pixel.png' }];
  assert.deepEqual(DevToolsPluginOutputSchema.parse(lines), lines);
  assert.equal(DevToolsPluginOutputSchema.safeParse(Array(1001).fill(lines[0])).success, false);
  assert.equal(PluginSchema.safeParse({ ...plugin, cliExtensions: { ...plugin.cliExtensions, commands: Array(1001).fill(plugin.cliExtensions.commands[0]) } }).success, false);
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
