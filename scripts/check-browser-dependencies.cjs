const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const manifest = require('../package.json');
const lock = require('../package-lock.json');
const version = manifest.dependencies.dompurify;
assert.match(version, /^\d+\.\d+\.\d+$/, 'DOMPurify must be pinned');
assert.equal(lock.packages[''].dependencies.dompurify, version);
assert.equal(lock.packages['node_modules/dompurify'].version, version);
assert.equal(require('dompurify').version, version, 'Run npm ci before checking');
const bundle = fs.readFileSync(path.join(root, 'node_modules/dompurify/dist/purify.min.js'));
const integrity = `sha384-${createHash('sha384').update(bundle).digest('base64')}`;
let references = 0;
for (const file of fs.readdirSync(path.join(root, 'project'), { recursive: true })) {
  if (!file.endsWith('.html')) continue;
  const html = fs.readFileSync(path.join(root, 'project', file), 'utf8');
  for (const tag of html.matchAll(/<script\b[^>]*\bdompurify[^>]*>/gi)) {
    assert.ok(tag[0].includes(`src="https://cdn.jsdelivr.net/npm/dompurify@${version}/dist/purify.min.js"`), file);
    assert.ok(tag[0].includes(`integrity="${integrity}"`), `${file}: stale SRI`);
    assert.ok(tag[0].includes('crossorigin="anonymous"'), `${file}: missing CORS`);
    references += 1;
  }
}
assert.ok(references >= 2, 'Expected both learning templates to load DOMPurify');
console.log(`PASS: ${references} DOMPurify CDN references match ${version} and package SHA-384`);
