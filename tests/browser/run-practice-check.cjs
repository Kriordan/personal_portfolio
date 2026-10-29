// Run the actual practice workspace script in headless Chrome: unsaved-change guard
// (text, notation, checkboxes, and an unsent message), UTF-8 byte counting, focus on the
// error summary, and reply polling against a scripted fetch.
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
        <input type="checkbox" id="pin">
        <textarea id="message" data-draft></textarea>
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
      document.getElementById('pin').checked = true;
      check(leaving(), 'ticking a box prompts before leaving');
      document.getElementById('pin').checked = false;
      check(!leaving(), 'unticking it again is not a change');
      document.getElementById('message').value = 'an unsent message';
      check(leaving(), 'an unsent message prompts before leaving');
      document.getElementById('message').value = '  ';
      check(!leaving(), 'a blank message box is not unsaved work');
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
  draft: {
    body: `<form data-practice-form><textarea id="message" data-draft>kept after saving</textarea></form>`,
    tests: `
      check(leaving(), 'a message kept after saving prompts before any edit');
      document.getElementById('message').value = '';
      check(!leaving(), 'clearing the kept message stops the prompt');
      finish('draft checks');
    `,
  },
  polling: {
    budget: 8000,
    before: `
      window.fetchCalls = [];
      window.loadMarker = 'kept';
      const answers = [
        { live: true, latest: 3, status: '<p>The interviewer is replying…</p>',
          turns: [{ sequence: 3, html: '<li id="turn-3">sent from another device</li>' }] },
        { live: false, latest: 4, status: '<p>The interviewer replied.</p>',
          turns: [{ sequence: 3, html: '<li id="turn-3">a duplicate</li>' }, { sequence: 4, html: '<li id="turn-4">the reply</li>' }] },
      ];
      window.fetch = async (url) => {
        window.fetchCalls.push(url);
        const next = answers.shift();
        return { ok: true, status: 200, redirected: false, headers: { get: () => 'application/json' },
          json: async () => ({ reply: { status: next.live ? 'pending' : 'completed', live: next.live },
            status_html: next.status, turns: next.turns, latest_sequence: next.latest }) };
      };
      window.statusWrites = 0;
      new MutationObserver((records) => { window.statusWrites += records.length; })
        .observe(document.getElementById('reply-status'), { childList: true, subtree: true, characterData: true });`,
    body: `<form data-practice-form>
        <input type="hidden" name="expected_sequence" value="2">
        <ol id="transcript"><li id="turn-2">my message</li></ol>
        <div id="reply-status" role="status" data-reply-poll="/poll" data-reply-live><p>The interviewer is replying…</p></div>
        <textarea id="typing">typing in progress</textarea>
        <button name="action" value="send" disabled>Send message</button>
      </form>`,
    tests: `
      document.getElementById('typing').focus();
      setTimeout(() => {
        try {
          check(window.fetchCalls.length === 2, 'polls until the reply arrives, then stops');
          check(window.fetchCalls[0].endsWith('/poll?after=2') && window.fetchCalls[1].endsWith('/poll?after=3'),
            'asks for the turns after the latest one shown');
          check(document.querySelectorAll('#turn-3').length === 1 && document.getElementById('turn-4'),
            'inserts each newer turn once, including one from another device');
          check(document.querySelector('[name=expected_sequence]').value === '4', 'advances expected_sequence');
          check(!document.getElementById('reply-status').hasAttribute('data-reply-live'), 'notes that the reply arrived');
          check(document.getElementById('reply-status').textContent.includes('replied'), 'announces the reply');
          check(window.statusWrites === 1, 'rewrites the status region only when its words change');
          check(!document.querySelector('button[value=send]').disabled, 're-enables Send');
          check(document.activeElement.id === 'typing', 'leaves focus where the learner is typing');
          check(document.getElementById('typing').value === 'typing in progress' && window.loadMarker === 'kept',
            'never reloads the page or touches typing');
          finish('polling checks');
        } catch (error) { document.getElementById('result').textContent = 'FAIL: ' + error.message; }
      }, 5000);
    `,
  },
  pollingStops: {
    budget: 8000,
    before: `
      window.fetchCalls = 0;
      window.fetch = async () => {
        window.fetchCalls += 1;
        return { ok: true, status: 200, redirected: true, headers: { get: () => 'text/html' }, json: async () => ({}) };
      };`,
    body: `<form data-practice-form>
        <input type="hidden" name="expected_sequence" value="2">
        <ol id="transcript"><li id="turn-2">my message</li></ol>
        <div id="reply-status" role="status" data-reply-poll="/poll" data-reply-live><p>The interviewer is replying…</p></div>
        <textarea id="typing">typing in progress</textarea>
        <button name="action" value="send" disabled>Send message</button>
      </form>`,
    tests: `
      setTimeout(() => {
        try {
          check(window.fetchCalls === 1, 'a sign-in redirect stops polling at once');
          check(document.querySelector('[name=expected_sequence]').value === '2', 'and leaves expected_sequence alone');
          check(document.getElementById('typing').value === 'typing in progress', 'and typing alone');
          check(!document.getElementById('reply-status').hasAttribute('data-reply-live'), 'the page stops waiting');
          check(document.getElementById('reply-status').textContent.includes('Reload the page'), 'and says to reload');
          check(!document.querySelector('button[value=send]').disabled, 'Send comes back');
          finish('polling stop checks');
        } catch (error) { document.getElementById('result').textContent = 'FAIL: ' + error.message; }
      }, 6000);
    `,
  },
  pollingRetries: {
    budget: 25000,
    before: `
      window.fetchCalls = 0;
      const answers = [
        () => { throw new TypeError('Failed to fetch'); },
        () => ({ ok: false, status: 503, redirected: false, headers: { get: () => 'text/html' }, json: async () => ({}) }),
        () => ({ ok: true, status: 200, redirected: false, headers: { get: () => 'application/json' },
          json: async () => ({ reply: { status: 'running', live: true }, latest_sequence: 2, turns: [],
            status_html: '<p>The interviewer is replying…</p>' }) }),
        () => ({ ok: true, status: 200, redirected: false, headers: { get: () => 'application/json' },
          json: async () => ({ reply: { status: 'completed', live: false }, latest_sequence: 3,
            turns: [{ sequence: 3, html: '<li id="turn-3">the reply</li>' }],
            status_html: '<p>The interviewer replied.</p>' }) }),
      ];
      window.fetch = async () => { window.fetchCalls += 1; return answers.shift()(); };`,
    body: `<form data-practice-form>
        <input type="hidden" name="expected_sequence" value="2">
        <ol id="transcript"><li id="turn-2">my message</li></ol>
        <div id="reply-status" role="status" data-reply-poll="/poll" data-reply-live><p>The interviewer is replying…</p></div>
        <button name="action" value="send" disabled>Send message</button>
      </form>`,
    tests: `
      setTimeout(() => {
        try {
          check(window.fetchCalls === 4, 'a dropped connection and a server error are retried');
          check(document.getElementById('turn-3') && document.querySelector('[name=expected_sequence]').value === '3',
            'the reply still arrives');
          check(document.getElementById('reply-status').textContent.includes('replied'), 'and is announced');
          check(!document.querySelector('button[value=send]').disabled, 'Send comes back');
          finish('polling retry checks');
        } catch (error) { document.getElementById('result').textContent = 'FAIL: ' + error.message; }
      }, 22000);
    `,
  },
  pollingGivesUp: {
    budget: 110000,
    before: `
      window.fetchCalls = 0;
      window.fetch = async () => {
        window.fetchCalls += 1;
        return { ok: false, status: 503, redirected: false, headers: { get: () => 'text/html' }, json: async () => ({}) };
      };`,
    body: `<form data-practice-form>
        <input type="hidden" name="expected_sequence" value="2">
        <ol id="transcript"><li id="turn-2">my message</li></ol>
        <div id="reply-status" role="status" data-reply-poll="/poll" data-reply-live><p>The interviewer is replying…</p></div>
        <button name="action" value="send" disabled>Send message</button>
      </form>`,
    tests: `
      setTimeout(() => {
        try {
          check(window.fetchCalls === 6, 'server errors are retried with growing waits, then given up');
          check(document.getElementById('reply-status').textContent.includes('Reload the page'), 'saying to reload');
          check(!document.querySelector('button[value=send]').disabled, 'with Send back');
          finish('polling give-up checks');
        } catch (error) { document.getElementById('result').textContent = 'FAIL: ' + error.message; }
      }, 100000);
    `,
  },
  alertOnly: {
    body: `<div id="practice-alert" tabindex="-1" role="alert">Nothing was deleted.</div>`,
    tests: `
      check(document.activeElement.id === 'practice-alert', 'an error summary is focused without the workspace form');
      check(!leaving(), 'and leaving is not blocked');
      finish('alert checks');
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

const run = (name, { body, tests, before = '', budget = 3000 }) => {
  const html = path.join(temporary, `${name}.html`);
  fs.writeFileSync(html, '<!doctype html><meta charset="utf-8"><title>Practice tests</title><body>' + body +
    `<pre id="result">Running</pre><script>${before}</script><script src="${scriptURL}"></script>` +
    `<script>try {${harness}${tests}} catch (error) { document.getElementById('result').textContent = 'FAIL: ' + error.message; }</script>`);
  const result = spawnSync(chrome, ['--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    ...(process.env.CI === 'true' ? ['--no-sandbox'] : []), `--user-data-dir=${path.join(temporary, `profile-${name}`)}`,
    '--dump-dom', `--virtual-time-budget=${budget}`, pathToFileURL(html).href],
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
