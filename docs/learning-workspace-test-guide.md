# Tabbed practice workspace: a short inspection exercise

Use the disposable demo so you can experiment freely. It has a temporary database
and a fake interviewer; it never uses your saved progress or calls a paid model.

```sh
poetry run python scripts/learning-preview-fixture.py --concept
```

Open <http://127.0.0.1:5057/login> and sign in with
`learning1@example.test` / `LearningPreview123!`. Open the idempotency lesson and
start a practice session. Stop the server with Ctrl+C when finished.

## 1. Follow a draft through the tabs

Write a few lines in **Build → API**, then switch to Schema and Discuss. In the
DevTools Console, inspect the form:

```js
const form = document.querySelector('[data-practice-form]');
const fields = new FormData(form);
fields.get('artifacts-0-body');
fields.get('request_id');
fields.get('artifacts-0-base_revision');
```

The hidden API editor still belongs to the form. Switching tabs changes which
panel is visible, not its text. Look in Elements for `hidden`, `role="tabpanel"`,
and `aria-selected`; use the arrow keys on the tabs and watch them change.

In Application → Local Storage, find `learning-practice-ui:…`. It contains view
and scroll preferences only. Your artifact and message text should not appear.
Closing or reloading with an unsaved draft should still warn you.

## 2. Watch a real Send

In Network, enable **Preserve log**. Write a message and send it. Inspect the POST
payload: the message, all artifacts, note fields, CSRF token, request UUID, and
expected revisions travel together. Follow the **303 → GET**, then the periodic
`/reply?after=…` requests. A successful send returns focus to the message box.

While the fake interviewer is answering, type another draft. Its reply should
leave that draft and focus alone. After several exchanges, scroll up through the
conversation while a reply is pending: arriving messages should offer
**New messages**, not pull you away from what you are reading.

## 3. Lose a save response and inspect the retry

With the demo running, use HTTPie:

```sh
http POST :5057/fixture/state practice=lost
```

Edit an artifact and click **Save work**. The rescue page says the result could
not be confirmed, and retains your submitted text. In Network, record the POST's
`request_id`. Reset the fixture, then click **Try saving again**:

```sh
http POST :5057/fixture/state practice=success
http :5057/fixture/results
```

The retry should use the same request ID and create no extra artifact revision.
Try `practice=failure` to simulate a failure before anything commits. Restore
`practice=success` afterward. These control endpoints exist only in the demo.

For a conflict, open the same session in two tabs. Save an API change in one,
then submit a different API change from the other. The error summary should get
focus, reveal the API panel, and preserve your conflicting draft for comparison.

## 4. Inspect layout and resumption

Use the device toolbar at **390 px**: Build shows the active work panel; Discuss
shows the conversation. Save and pause, return through Learning, and resume. Your
confirmed work and selected work tab should return. The selected view is local to
this browser; saved session content comes from the server on every device.

For a small performance exercise, record a Performance trace while switching
between API, Schema, and Discuss. There should be no network write or AI request
from a tab switch. Inspect the click handler and layout work in the trace.

Automated verification commands and results are in the
[checkpoint log](engineering-learning-milestone-1.md). These exercises are for
following the data yourself, not replacing that regression coverage.
