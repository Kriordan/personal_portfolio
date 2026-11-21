# Checkpoint 2: inspect the running system

Pick one short experiment per session. Start the disposable app from the repository root:

```sh
poetry run python scripts/learning-preview-fixture.py --concept
```

Open [the local login](http://127.0.0.1:5057/login), sign in as `learning1@example.test` / `LearningPreview123!`, and open **Learning → Idempotency and uncertain outcomes**. The fixture disables dotenv and uses temporary SQLite data. Use this fixture for the experiments below; **Ctrl+C** stops it, and restarting resets it. PostgreSQL migration/concurrency checks are separate.

## Network: follow a review save

1. Open DevTools → **Network**, enable **Preserve log**, and select **All** or **Doc**. These are HTML form navigations, so a Fetch/XHR-only filter hides them.
2. Select **Review due questions**, then **Show answer**. Inspect the GET query parameters: `card_id`, `content_version`, `expected_revision`, and `request_id`. Compare the two response bodies: the answer appears only after revealing it.
3. Select **Good**. Inspect the POST form fields, including the rating and CSRF token. Expect a **303** redirect followed by a **200** GET. Inspect the `Location` and `Cache-Control` response headers; review pages are private and not stored in caches.
4. Right-click the POST → **Copy as cURL**, and run it unchanged in a terminal. It should reuse the original receipt without adding another review. Change only the rating, keeping the same request ID: expect **409**. Remove the CSRF field: expect **400**.

Keep the copied cookies and other form fields intact. A client following redirects may show the final 200 instead of the initial 303. [Chrome Network reference](https://developer.chrome.com/docs/devtools/network).

## Console and Sources: inspect state, then pause execution

Before and after saving a review, run this in the browser Console:

```javascript
await fetch('/fixture/results').then(response => response.json())
```

Compare user `"1"`'s `logs`, `receipts`, and `ratings`, including after replaying the POST. This read endpoint exists only in the disposable fixture.

On a revealed-answer page, inspect the pinned version:

```javascript
document.querySelector('input[name="content_version"]').value
```

Return to the lesson. In **Sources**, open `learning-concept.js` and set a breakpoint on the assignment to `count.textContent`. Click **Next step**. Inspect `step` and `trace` in Scope/Watch, step over, and compare the displayed order count. Resume execution afterward. Those variables are local to the script; they are available while paused in the relevant scope, not in the ordinary unpaused Console.

## HTTPie or Postman: inspect the JSON API

Run this block together: fixture access tokens deliberately expire after ten seconds.

```sh
login_json=$(http --ignore-stdin --body POST :5057/api/v1/auth/login \
  email=learning1@example.test password='LearningPreview123!')
token=$(printf '%s' "$login_json" | poetry run python -c \
  'import json, sys; print(json.load(sys.stdin)["access_token"])')
http --ignore-stdin --verbose GET :5057/api/v1/learning/review \
  "Authorization:Bearer $token" note_id==all-types limit==1
```

Inspect the request headers and JSON response: find `card_id`, `progress_revision`, and `total_due`. Repeat the block with `limit==0` for a **400** validation response. Omit the Authorization header for **401**. An expired token also returns 401; log in again, or call `/api/v1/auth/refresh` using the login response's `refresh_token` as the Bearer token.

HTTPie's `==` supplies query parameters; `=` supplies JSON string fields. In Postman, reproduce the login and Bearer-authenticated GET, or import a localhost cURL request. [HTTPie reference](https://httpie.io/docs/cli).

Compare the authentication mechanisms: the web form uses a session cookie plus CSRF; the JSON API uses a Bearer token. This existing JSON API serves legacy notes; the new concept flow currently uses the web routes.

## Performance: observe one interaction

Record a short **Performance** trace while clicking **Next step** and **Start again**. Find the click handler and any style/layout/paint work. Compare that with a page reload: distinguish network waiting from main-thread work. The simulation buttons make no application requests.

Keep viewport, cache, and throttling settings consistent when comparing recordings. The goal is to explain the trace, not chase a score. [Chrome Performance reference](https://developer.chrome.com/docs/devtools/performance).
