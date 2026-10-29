// Run the actual practice workspace script in headless Chrome: unsaved-change guard,
// UTF-8 byte counting, and focus on the error summary.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'learning-practice-check-'));
const chrome = process.env.CHROME_BIN || (process.platform === 'darwin'
  ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' : 'google-chrome');
const scriptURL = pathToFileURL(path.join(root, 'project/static/js/learning-practice.js')).href;

const harness = `
  let checks = 0;
  const check = (condition, name) => { if (!condition) throw new Error(name); checks++; };
  const leaving = () => {
    const event = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
  };
  const finish = (label) => {
    document.body.dataset.testResult = 'pass';
    document.getElementById('result').textContent = 'PASS: ' + checks + ' ' + label;
  };
`;
const pages = {
  clean: {
    body: `<div id="practice-alert" tabindex="-1" role="alert">Nothing was saved.</div>
      <form data-practice-form>
        <select id="notation"><option value="text" selected>Text</option><option value="json">JSON</option></select>
        <textarea id="api">saved text</textarea><output data-byte-count="api" data-limit="65536"></output>
        <textarea id="small">abc</textarea><output id="small-count" data-byte-count="small" data-limit="8"></output>
      </form>`,
    tests: `
      check(document.activeElement.id === 'practice-alert', 'error summary receives focus');
      check(document.querySelector('[data-byte-count="api"]').textContent === '0.0 of 64 KiB', 'byte count shown');
      check(!leaving(), 'unchanged page leaves without a prompt');
      const small = document.getElementById('small');
      const count = document.getElementById('small-count');
      small.value = 'é€😀';  // 4 UTF-16 units but 9 UTF-8 bytes
      small.dispatchEvent(new Event('input'));
      check(count.classList.contains('is-over'), 'limit counts UTF-8 bytes, not characters');
      small.value = 'abc';
      small.dispatchEvent(new Event('input'));
      check(!count.classList.contains('is-over'), 'under the limit clears the warning');
      check(!leaving(), 'restoring the saved text is not a change');
      document.getElementById('notation').value = 'json';
      check(leaving(), 'a changed notation prompts before leaving');
      document.getElementById('notation').value = 'text';
      document.getElementById('api').value = 'edited text';
      check(leaving(), 'edited text prompts before leaving');
      document.querySelector('[data-practice-form]').dispatchEvent(new Event('submit', { cancelable: true }));
      check(!leaving(), 'saving does not prompt');
      finish('practice browser checks');
    `,
  },
  unsaved: {
    body: `<form data-practice-form data-unsaved><textarea id="api">rescued text</textarea></form>`,
    tests: `
      check(leaving(), 'a re-rendered page with unsaved text prompts before any edit');
      finish('re-render checks');
    `,
  },
  absent: {
    body: `<p>No practice form on this page.</p>`,
    tests: `
      check(!leaving(), 'pages without the form are unaffected');
      finish('no-form checks');
    `,
  },
};

const run = (name, { body, tests }) => {
  const html = path.join(temporary, `${name}.html`);
  fs.writeFileSync(html, '<!doctype html><meta charset="utf-8"><title>Practice tests</title><body>' + body +
    `<pre id="result">Running</pre><script src="${scriptURL}"></script>` +
    `<script>try {${harness}${tests}} catch (error) { document.getElementById('result').textContent = 'FAIL: ' + error.message; }</script>`);
  const result = spawnSync(chrome, ['--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    ...(process.env.CI === 'true' ? ['--no-sandbox'] : []), `--user-data-dir=${path.join(temporary, `profile-${name}`)}`,
    '--dump-dom', '--virtual-time-budget=3000', pathToFileURL(html).href],
    { encoding: 'utf8', timeout: 30000, maxBuffer: 5 * 1024 * 1024 });
  if (result.error) throw result.error;
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /data-test-result="pass"/, result.stdout);
  return Number(result.stdout.match(/PASS: (\d+)/)[1]);
};

try {
  const total = Object.entries(pages).reduce((sum, [name, page]) => sum + run(name, page), 0);
  console.log(`PASS: ${total} practice browser checks`);
} finally {
  fs.rmSync(temporary, { recursive: true, force: true });
}
