# Flashcard rendering checks

After installing the reviewed root lockfile with `npm ci --ignore-scripts`, open
`flashcards-security.html` in a browser. It loads local copies of Marked,
DOMPurify, and the application's actual flashcard renderer. No server, login,
external CDN, or extra test dependency is needed.

The page must show `PASS: 13 checks`. It covers ordinary Markdown, code blocks,
unsafe links, script/event-handler removal, mutation payloads, and plain-text
fallback when DOMPurify is unavailable (including an integrity-check failure).

For headless Chrome, use a temporary profile with `--headless --dump-dom
--virtual-time-budget=3000` and a file URL for this page. Verify that the output
contains `data-test-result="pass"`; Chrome's exit status alone does not report
failed assertions. These regression checks do not prove the sanitizer handles
every possible malicious input.
