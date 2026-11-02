# Concept workspace: a 10-minute developer walkthrough

Use the running disposable preview at <http://127.0.0.1:5057/learning/>.
To start it yourself: `poetry run python scripts/learning-preview-fixture.py --concept`.
Sign in with `learning1@example.test` / `LearningPreview123!`. This fixture uses
temporary progress and a fake interviewer; restarting it resets its sample data.

## 1. Follow one session through Network

Start idempotency practice, write a small API outline in Build, and **Save work**.
Open DevTools → Network → **Preserve log**, with the All or Doc filter.

- Follow Learn → Review → Show answer. Compare `practice_session` in each URL:
  it must match the UUID in the original practice URL.
- Inspect the reveal GET: it carries the card, content version, progress revision,
  and request UUID. The answer is absent from the initial question response.
- Rate Good. Inspect the POST form data and 303 `Location`; the selected session
  survives. Return to Build and confirm your saved API outline is still there.
- Edit the outline without saving and click Learn. Cancel the leave-page warning,
  then Save work. Mode navigation does not autosave drafts.

In Elements, inspect Show answer's form: `practice_session` is a hidden input.
A native GET form replaces its action's query string, so the input is necessary.
For a stronger continuity check, create a second session and repeat from the
first session's URL. It should still return to the first.

## 2. Inspect the lesson in Console and Sources

Select **Trace retries and crashes**. The hash becomes `#retries`; the simulation
is beside that explanation. In Console:

```js
[...document.querySelectorAll('[data-lesson-section]')]
  .map(section => ({id: section.id, hidden: section.hidden}))
document.querySelector('[data-lesson-link][aria-current]')?.getAttribute('href')
```

Only one section is visible. In Sources, place a breakpoint in `revealSection`
in `learning-concept.js`, choose another section, and inspect `target`/`section`.
Use Step over, then Resume. A short Performance recording should show DOM/layout
work without an application request when changing sections or running the lab.
Try the device toolbar at 390 pixels; the section picker replaces the sidebar.

## 3. Check the login boundary with HTTPie

```sh
http --headers :5057/learning/
http --headers :5057/learning/references
http --headers :5057/learning/concepts/idempotency
```

Without cookies, each returns 302 to login and `Cache-Control: private, no-store`.
Use Network → Copy as cURL on a signed-in lesson GET to compare its 200 response.
That copied request includes your session cookie; keep it local.

## 4. Explore URL generation in a Python REPL

From the repo root: `PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python`.

```python
from project import create_app
from project.learning.navigation import workspace_navigation
app = create_app(dict(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite://",
                      LEARNING_PRACTICE_ENABLED=True))
with app.test_request_context():
    links = workspace_navigation("idempotency", mode="learn",
                                 session={"id": "demo-session"})

links["review_url"]
links["build_url"]
```

This creates no tables and reads no progress: the helper builds links from
already-authorized metadata. Try `session=None` and compare the destinations.
For stepping through content projections with `pdb`, use the five-minute
[REPL exercise](learning-checkpoint-1-test-guide.md). For failed saves and receipt
recovery, use the [practice workspace guide](learning-workspace-test-guide.md).
