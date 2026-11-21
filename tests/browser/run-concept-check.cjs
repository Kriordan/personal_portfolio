// Run the actual lesson renderer and retry simulation with local dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'learning-concept-check-'));
const chrome = process.env.CHROME_BIN || (process.platform === 'darwin'
  ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' : 'google-chrome');
const scriptURL = pathToFileURL(path.join(root, 'project/static/js/learning-concept.js')).href;
const tests = `
(async () => {
  let checks = 0;
  const check = (condition, name) => { if (!condition) throw new Error(name); checks++; };
  const markdown = document.getElementById('markdown');
  check(markdown.querySelector('strong')?.textContent === 'Understand retries', 'ordinary Markdown');
  check(!markdown.querySelector('img,svg,iframe,script,style'), 'no executable content or remote media');
  check(!markdown.querySelector('a[href^="javascript:"]'), 'unsafe links removed');
  check(markdown.querySelector('a[href^="https:"]').rel === 'noreferrer', 'external links protect referrer');
  check(window.fixtureExecuted !== true, 'event handler did not run');
  const failure = document.getElementById('retry-failure');
  const reuse = document.getElementById('retry-key');
  const next = document.getElementById('retry-next');
  const reset = document.getElementById('retry-reset');
  const count = document.getElementById('retry-count');
  const status = document.getElementById('retry-status');
  check(!next.disabled && count.textContent === '0', 'starts before the first attempt');
  for (const mode of ['before', 'after', 'success']) {
    for (const same of [true, false]) {
      failure.value = mode;
      reuse.checked = same;
      failure.dispatchEvent(new Event('change'));
      next.click(); next.click();
      check(count.textContent === (mode === 'before' ? '0' : '1'), mode + ': correct commit boundary');
      next.click(); next.click(); next.click();
      check(count.textContent === (mode !== 'before' && !same ? '2' : '1'), mode + ': correct retry effect');
      check(next.disabled, 'trace has a bounded end');
    }
  }
  check(status.textContent.includes('Two orders'), 'new key explains duplicate effect');
  reset.click();
  check(count.textContent === '0' && !next.disabled, 'reset returns to initial state');
  next.focus();
  for (let i = 0; i < 5; i++) next.click();
  check(document.activeElement === reset, 'finishing with the keyboard keeps focus on Start again');
  reset.click();
  failure.focus();
  for (let i = 0; i < 5; i++) next.click();
  check(document.activeElement === failure, 'completion does not steal focus from another control');
  const fallback = document.createElement('div');
  fallback.dataset.conceptMarkdown = '';
  const raw = '**Text** <img src=x onerror="window.fixtureExecuted=true">';
  fallback.textContent = raw;
  document.body.appendChild(fallback);
  window.DOMPurify = undefined;
  const script = document.createElement('script'); script.src = ${JSON.stringify(scriptURL)};
  await new Promise((resolve, reject) => { script.onload = resolve; script.onerror = reject; document.body.appendChild(script); });
  check(fallback.textContent === raw && !fallback.querySelector('img,strong'), 'missing sanitizer leaves inert text');
  document.body.dataset.testResult = 'pass';
  document.getElementById('result').textContent = 'PASS: ' + checks + ' concept browser checks';
})().catch(error => { document.getElementById('result').textContent = 'FAIL: ' + error.message; });
`;
try {
  const html = path.join(temporary, 'test.html');
  const dependencies = ['node_modules/marked/lib/marked.umd.js', 'node_modules/dompurify/dist/purify.min.js']
    .map(file => `<script src="${pathToFileURL(path.join(root, file)).href}"></script>`).join('');
  const lab = fs.readFileSync(path.join(root, 'project/learning/templates/learning/_retry_visualization.html'), 'utf8');
  fs.writeFileSync(html, '<!doctype html><meta charset="utf-8"><title>Concept tests</title><body>' +
    '<div id="markdown" data-concept-markdown>**Understand retries**\n\n[safe](https://example.test) [unsafe](javascript:alert(1))\n\n&lt;img src="https://example.test/pixel" onerror="window.fixtureExecuted=true"&gt;&lt;svg onload="window.fixtureExecuted=true"&gt;&lt;/svg&gt;</div>' + lab +
    '<pre id="result">Running</pre>' + dependencies + `<script src="${scriptURL}"></script><script>${tests}</script>`);
  const result = spawnSync(chrome, ['--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    ...(process.env.CI === 'true' ? ['--no-sandbox'] : []), `--user-data-dir=${path.join(temporary, 'profile')}`,
    '--dump-dom', '--virtual-time-budget=3000', pathToFileURL(html).href],
    { encoding: 'utf8', timeout: 30000, maxBuffer: 5 * 1024 * 1024 });
  if (result.error) throw result.error;
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /data-test-result="pass"/, result.stdout);
  console.log(result.stdout.match(/PASS: \d+ concept browser checks/)[0]);
} finally {
  fs.rmSync(temporary, { recursive: true, force: true });
}
