// Regression checks for the scoped UUID override and XML/Metro security updates.
const assert = require('node:assert/strict');
const { Buffer } = require('node:buffer');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const xcode = require('xcode');
const semver = require('semver');
const manifest = require('../package.json');
const expo = require('expo/package.json');
const bundled = require('expo/bundledNativeModules.json');

assert.ok(semver.satisfies(expo.version, '57.x'), 'Review SDK upgrades as a coordinated change');
for (const name of Object.keys(manifest.dependencies)) {
  if (!bundled[name]) continue;
  const installed = require(`${name}/package.json`).version;
  assert.ok(semver.satisfies(installed, bundled[name]),
    `${name}@${installed} is incompatible with Expo ${expo.version}; expected ${bundled[name]}`);
}
console.log(`PASS: installed dependencies match Expo ${expo.version}'s bundled compatibility ranges`);

// Exercise the copy used by React DevTools. Never execute the quoted output.
const devtoolsRoot = path.dirname(require.resolve('react-devtools-core/package.json'));
const shellQuote = require(require.resolve('shell-quote', { paths: [devtoolsRoot] }));
const argumentsWithMetacharacters = ['devtools', 'file with spaces', "a'b", 'semi;colon', 'dollar$sign'];
assert.deepEqual(shellQuote.parse(shellQuote.quote(argumentsWithMetacharacters)), argumentsWithMetacharacters);
for (const terminator of ['\n', '\r', '\u2028', '\u2029']) {
  assert.throws(() => shellQuote.quote(['echo', 'ok', { comment: 'comment' }, `a${terminator}unexpected-command`]), TypeError);
}
console.log('PASS: shell quoting preserves arguments and rejects line terminators after comments');

for (const plist of [require('@expo/plist').default, require('plist')]) {
  const value = { name: 'Portfolio & safety', enabled: true, count: 2, items: ['a', 'b'] };
  // Parsers may return a null-prototype dictionary as a security measure.
  assert.deepEqual({ ...plist.parse(plist.build(value)) }, value);
}
console.log('PASS: both plist implementations round-trip through patched XML parsers');

const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'portfolio-xcode-test-'));
try {
  const filename = path.join(directory, 'test.pbxproj');
  fs.writeFileSync(filename, `// !$*UTF8*$!
{
  archiveVersion = 1;
  classes = {};
  objectVersion = 60;
  objects = {
    000000000000000000000001 = {
      isa = PBXProject;
      mainGroup = 000000000000000000000002;
    };
    000000000000000000000002 = {
      isa = PBXGroup;
      children = ();
      sourceTree = "<group>";
    };
  };
  rootObject = 000000000000000000000001;
}
`);
  const project = xcode.project(filename);
  project.parseSync();
  const identifiers = new Set();
  for (let i = 0; i < 100; i += 1) {
    const identifier = project.generateUuid();
    assert.match(identifier, /^[A-F0-9]{24}$/);
    assert.ok(!identifiers.has(identifier));
    identifiers.add(identifier);
  }
  fs.writeFileSync(filename, project.writeSync());
  const restored = xcode.project(filename);
  restored.parseSync();
  assert.deepEqual(restored.hash.project.rootObject, project.hash.project.rootObject);
  console.log('PASS: Xcode UUID generation and project parse/write round-trip');
} finally {
  fs.rmSync(directory, { recursive: true, force: true });
}

const metroRoot = path.dirname(require.resolve('metro/package.json'));
const { getAssetSize } = require(path.join(metroRoot, 'src/Assets.js'));
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aoyQAAAAASUVORK5CYII=', 'base64');
const size = getAssetSize('png', png, 'pixel.png');
assert.equal(size.width, 1);
assert.equal(size.height, 1);

// Zero-length ICNS chunks triggered an infinite loop in the removed image-size.
const malformed = Buffer.alloc(16);
malformed.write('icns');
malformed.writeUInt32BE(16, 4);
malformed.write('ic07', 8);
for (const type of ['icns', 'jxl', 'heif']) {
  assert.equal(getAssetSize(type, malformed, `untrusted.${type}`), null);
}
assert.throws(() => getAssetSize('png', malformed, 'disguised.png'));
console.log('PASS: Metro reads PNG dimensions and rejects unsupported/malformed image data');
