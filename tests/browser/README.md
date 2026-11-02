# Flashcard rendering checks

After installing the reviewed root lockfile with `npm ci --ignore-scripts`, open
`flashcards-security.html` in a browser. It loads local copies of Marked,
DOMPurify, and the application's actual flashcard renderer. No server, login,
external CDN, or extra test dependency is needed.

The page must show `PASS: 23 checks`. It covers ordinary Markdown, code blocks,
unsafe links, script/event-handler removal, mutation payloads, and plain-text
fallback when DOMPurify is unavailable (including an integrity-check failure).
It also exercises save retries, receipt recovery, stale queues, completion,
Web Crypto session IDs, and a malicious legacy `doneUrl` that must not override
the server-rendered Done link. The malicious configuration is fixture-only;
the production template never accepts a client-supplied Done destination.

For headless Chrome, use a temporary profile with `--headless --dump-dom
--virtual-time-budget=3000` and a file URL for this page. Verify that the output
contains `data-test-result="pass"`; Chrome's exit status alone does not report
failed assertions. These regression checks do not prove the sanitizer handles
every possible malicious input.

`npm run test:browser` automates that headless check and fails on assertion,
browser, or timeout errors. Set `CHROME_BIN` to select an executable (for example,
Chrome Canary on macOS); Linux CI uses `google-chrome`. `npm test` also checks that
the locked DOMPurify version, both CDN references, and SHA-384 integrity match the
installed browser bundle. The [October dependency review](../../docs/security/dependabot-2026-10-05.md)
documents the audit exceptions and remaining exposure.

The same command now runs `run-concept-check.cjs`: 27 checks against the actual
lesson renderer and retry simulation. It verifies the Markdown allowlist, unsafe
links, remote-media removal, missing-sanitizer fallback, all six combinations of
failure position/key reuse, and reset/end states. Dependencies load locally; no
AI service or external website is contacted by these fixtures.

`run-practice-check.cjs` runs the practice workspace script on small isolated pages
(43 checks, including polling, retries, and reply states): the leave-page prompt appears only for unsaved changes (text,
notation, ticked boxes, and an unsent message, including one kept after saving
or re-rendered after a rejected or failed request) and not while saving; byte
counts use UTF-8 like the server limit; and the error summary receives focus,
with or without the workspace form. Saving, sending, conflicts, and recovery do
not depend on this script.

## Full practice workspace regression

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
  poetry run python -m unittest tests.test_practice_browser
```

This test runs the real Flask templates and native forms inside headless Chrome,
with a temporary localhost server, disposable SQLite data, CSRF enabled, and a
scripted AI provider. It checks shared tabs/drafts, focus and scroll continuity,
keyboard operation, pause/resume, hidden-panel conflicts, an unconfirmed save and
receipt replay, failed-send recovery, mobile layout, blocked browser storage, and
saving without JavaScript. External resources are blocked by the fixture CSP.
It is discovered by the backend CI suite. Chrome is required in CI; local runs
without Chrome skip with an explicit reason. Set `CHROME_BIN` to override its path.
No new npm dependency is needed. PostgreSQL races/migrations have separate tests.

## Learning home and library navigation

`poetry run python -m unittest tests.test_learning_hub_browser` runs 56 checks
against real Flask pages in Chrome. It covers the continuation link and saved
artifact, practice tab restoration, public articles, private flashcards,
search/pagination, escaped note titles, the existing rating endpoint and receipt,
progress after reload, independent concept review counts, 390/320-pixel layouts,
skip-link focus, and navigation with scripts blocked. The fixture seeds the
review queue's randomness and blocks external resources. It uses the same
disposable database/browser approach as the practice regression and runs in
backend unittest discovery. Route and isolation checks live in
`tests/test_learning_hub.py`; interactive developer exercises are in the
[Learning home guide](../../docs/learning-home-test-guide.md).
