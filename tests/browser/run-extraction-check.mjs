// Exercise the actual Browserless DOM reader in a fresh, local headless browser.
// No network, stored profile, provider credentials, or paid API calls.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';
import { readListingDocument } from '../../project/jobwizard/browserless_extract.mjs';

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'portfolio-extraction-test-'));
const chrome = process.env.CHROME_BIN || (process.platform === 'darwin'
  ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' : 'google-chrome');
const tests = `
  const read = ${readListingDocument.toString()};
  let count = 0;
  const check = (condition, name) => { if (!condition) throw new Error(name); count++; };
  const profile = {heading:'h1', description:'.description'};
  document.body.innerHTML = '<main><h1>Engineer</h1><div>Remote in Canada</div><div class="description"><h2>Requirements</h2><p>Python <b>or equivalent</b> experience.</p><p style="display:none">HIDDEN PAY 999999</p><form>PRIVATE FORM DATA</form><nav>UNRELATED NAV</nav><button>BUTTON TEXT</button><p aria-hidden="true">ARIA HIDDEN</p></div><div class="description"><p>FINAL salary CAD 100000 per year.</p></div></main><div style="display:none"><div class="description">HIDDEN ROOT</div></div>';
  const source = read(profile);
  check(!source.error, 'reader succeeds');
  check(source.heading === 'Engineer', 'correct heading');
  check(source.description.includes('Python or equivalent experience.'), 'inline text retained');
  check(source.description.includes('FINAL salary'), 'last Gem section retained');
  check(source.header_text.includes('Remote in Canada'), 'header restrictions retained');
  check(!/HIDDEN|PRIVATE|UNRELATED|BUTTON/.test(source.description), 'hidden and non-description content excluded');
  document.body.innerHTML = '<h1>Engineer</h1><div class="description"><p>Outer content</p><div class="description"><p>Nested once</p></div></div>';
  check(read(profile).description.split('Nested once').length === 2, 'nested selectors not duplicated');
  document.body.innerHTML = '<h1>Engineer</h1><div class="description">' + 'x'.repeat(80001) + '</div>';
  check(read(profile).error === 'source_too_large', 'source is rejected, not silently truncated');
  document.body.innerHTML = '<h1>Engineer</h1><p>No description loaded</p>';
  check(read(profile).error === 'page_not_ready', 'empty description fails');
  document.body.dataset.testResult = 'pass';
  document.body.textContent = 'PASS: ' + count + ' extraction DOM checks';
`;
try {
  const html = path.join(root, 'test.html');
  fs.writeFileSync(html, '<!doctype html><title>Extraction checks</title><body><script>try {' + tests + '} catch(error) {document.body.textContent="FAIL: " + error.message;}<\/script>');
  const result = spawnSync(chrome, ['--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    ...(process.env.CI === 'true' ? ['--no-sandbox'] : []), `--user-data-dir=${path.join(root, 'profile')}`,
    '--dump-dom', '--virtual-time-budget=3000', pathToFileURL(html).href],
    {encoding:'utf8',timeout:30000,maxBuffer:500000});
  if (result.error) throw result.error;
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /data-test-result="pass"/, result.stdout);
  console.log(result.stdout.match(/PASS: \d+ extraction DOM checks/)[0]);
} finally {
  fs.rmSync(root, {recursive:true, force:true});
}
