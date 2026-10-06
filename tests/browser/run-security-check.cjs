const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { spawnSync } = require('node:child_process');

const chrome = process.env.CHROME_BIN || (process.platform === 'darwin'
  ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' : 'google-chrome');
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'portfolio-browser-test-'));
try {
  const result = spawnSync(chrome, [
    '--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    ...(process.env.CI === 'true' ? ['--no-sandbox'] : []),
    `--user-data-dir=${profile}`, '--dump-dom', '--virtual-time-budget=3000',
    pathToFileURL(path.join(__dirname, 'flashcards-security.html')).href,
  ], { encoding: 'utf8', timeout: 30_000, maxBuffer: 5 * 1024 * 1024 });
  if (result.error) throw result.error;
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /data-test-result="pass"/, result.stdout);
  console.log(result.stdout.match(/PASS: \d+ checks; DOMPurify [\d.]+/)[0]);
} finally {
  fs.rmSync(profile, { recursive: true, force: true });
}
