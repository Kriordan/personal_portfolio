# Checkpoint 3: save, conflict, and recover practice work

Pick one experiment. Predict the result, inspect it, then explain any surprise. Part A covers checkpoint 3a (sessions and artifacts). Part B covers checkpoint 3b (discussion turns, the brief, pause/resume, delete).

## Part A — sessions and artifacts

### REPL: call the service directly

This uses an in-memory SQLite database that disappears when Python exits. From the repository root:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python
```

```python
from datetime import datetime, timezone
from pprint import pprint
from uuid import uuid4
from project import create_app
from project.database import db
from project.learning.content_schema import load_catalog
from project.models import ArtifactRevision, ContentRevision, CurriculumItem, PracticeReceipt, User
from project.services import practice_service as practice
from project.services.curriculum_service import content_checksum

app = create_app(dict(TESTING=True, SECRET_KEY="repl", SQLALCHEMY_DATABASE_URI="sqlite://"))
app.app_context().push()
db.create_all()
user = User(id=1, username="repl", email="repl@example.test")
db.session.add(user)
now = datetime.now(timezone.utc)
for item in load_catalog("curriculum/idempotency/catalog.json")["items"]:
    db.session.add(CurriculumItem(id=item["id"], kind=item["kind"]))
    db.session.flush()
    db.session.add(ContentRevision(item_id=item["id"], version=item["version"], schema_version=1, payload=item,
        checksum=content_checksum(item), imported_at=now, published_at=now, reviewed_by="REPL demo",
        reviewed_on=now.date()))
db.session.commit()

session_id = practice.start_session(user, exercise_id="idempotent-order-api", request_id=str(uuid4()))["session_id"]
pprint(practice.session_detail(1, session_id)["messages"])
```

The first message is the interviewer's authored opening line. Search the detail for `hidden_constraints` or `reference_reasoning`: neither appears.

**Replay and reuse a request ID:**

```python
edit = dict(artifact_id="api", base_revision=0, language="text", body="POST /orders\r\n")
request_id = str(uuid4())
first = practice.save_work(user, session_id, edits=[edit], request_id=request_id)
first == practice.save_work(user, session_id, edits=[edit], request_id=request_id)
ArtifactRevision.query.one().body
practice.save_work(user, session_id, edits=[dict(edit, body="changed")], request_id=request_id)
```

Expect `True`, then `'POST /orders\n'`, then `RequestConflictError`. Why did `\r\n` become `\n`? Find `normalize_text`. Then inspect `PracticeReceipt.query.all()[-1].payload_sha256`: the receipt stores a hash of your text, not the text itself.

**Lose a conflict, then keep an untouched artifact:**

```python
try:
    practice.save_work(user, session_id, request_id=str(uuid4()), edits=[
        dict(edit, body="another tab's design"), dict(artifact_id="schema", base_revision=0, language="sql", body="")])
except practice.StaleViewError as exc:
    pprint(exc.conflicts)
```

The API edit conflicts because revision 1 now exists. The schema edit is empty and matches what that view loaded, so it does not conflict. Nothing was written: count `ArtifactRevision` rows to confirm.

**Step through the decision:**

```python
import pdb
pdb.runcall(practice.save_work, user, session_id, request_id=str(uuid4()),
            edits=[dict(edit, base_revision=1, body="POST /orders\n")])
```

At `(Pdb)`, set `b _decide_edits` (the debugger starts inside `practice_service`), press `c`, then step with `n`. Inspect `head.revision`, `submitted`, and `_state(head, spec)`. Which branch runs, and why does the result say `"changed": False`?

### DevTools: follow a save in the browser

Start the disposable app, sign in as `learning1@example.test` / `LearningPreview123!`, and open **Learning → Idempotency and uncertain outcomes → Apply it → Start a new practice session**:

```sh
poetry run python scripts/learning-preview-fixture.py --concept
```

1. **Follow a save.** Open **Network**, enable **Preserve log**, and select **All** or **Doc**. Type in **API contract** and select **Save work**.
   - Expect a **POST**, then a **303**, then a **GET**.
   - Inspect the form fields: `request_id`, each `artifacts-N-base_revision`, and the CSRF token.
   - The textarea's line breaks are sent as `%0D%0A` (CRLF).
2. **Replay it.** Right-click the POST → **Copy as cURL** and run it unchanged. It replays the receipt, so no new revision appears. In the Console, compare `await fetch('/fixture/results').then(r => r.json())` before and after.
3. **Two tabs.** Open the workspace in two tabs. Save an edit in the second tab, then save a different edit in the first.
   - Expect **409**, with your text still in the box and the other version under "Saved elsewhere".
   - Find `artifacts-0-base_revision` in Elements: it now names the newer revision.
   - Save again: your text becomes the next revision, and history keeps both.
4. **Unknown outcome.** In the Console, run:

   ```javascript
   await fetch('/fixture/state', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({practice: 'lost'})})
   ```

   Then save. The fixture commits and reports a failure, so you get **503** on a standalone page with your text.
   - Compare its `request_id` with the original POST: it is unchanged.
   - Set `practice` back to `success` and select **Try saving again**. The retry replays the saved result instead of creating a second revision.
   - Repeat with `practice: 'failure'`, which fails before saving.
5. **Leave with unsaved text.** Edit a box, then select **History**: the browser asks before leaving. **Sources** → `learning-practice.js` shows why: `dirty()` compares each field with its loaded value.

These are HTML form navigations, so a Fetch/XHR-only filter hides them.

### HTTPie or Postman: the JSON API

Fixture access tokens expire after ten seconds, so run each block in one go. `uuidgen` prints uppercase; request IDs must be lowercase.

```sh
token=$(http --ignore-stdin --body POST :5057/api/v1/auth/login email=learning1@example.test \
  password='LearningPreview123!' | poetry run python -c 'import json, sys; print(json.load(sys.stdin)["access_token"])')
session=$(http --ignore-stdin --body POST :5057/api/v1/learning/practice/sessions "Authorization:Bearer $token" \
  exercise_id=idempotent-order-api concept_id=idempotency request_id=$(uuidgen | tr A-Z a-z) \
  | poetry run python -c 'import json, sys; print(json.load(sys.stdin)["session_id"])')
request=$(uuidgen | tr A-Z a-z); echo "session=$session request=$request"
http --ignore-stdin PUT :5057/api/v1/learning/practice/sessions/$session/artifacts/api \
  "Authorization:Bearer $token" request_id=$request base_revision:=0 language=text body='POST /orders'
```

Then, with a fresh token and the same `session` and `request` values:

1. Repeat the PUT unchanged: the same JSON comes back.
2. Change only `body` with the same `request_id`: **409** `request_conflict`.
3. Use a new request ID with `base_revision:=0` and a different body: **409** `stale_artifact`, including the saved body.
4. Run `GET :5057/api/v1/learning/practice/receipts/$request`: the recorded result.
5. Run `GET …/sessions/$session/artifacts/api/revisions`: the history.
6. Sign in as `learning2@example.test` and `GET …/sessions/$session`: **404**. Another account's sessions are indistinguishable from missing ones.

`:=` sends a JSON number, while `=` sends a string. Try `base_revision=0` and read the 400.

The website and the API are two devices for the same session. Save from HTTPie while a browser tab is open, then save from the tab: it gets the same 409 as two tabs.

## Part B — turns, the brief, pause/resume, and delete

### REPL: a turn and the record around it

Continue in part A's REPL session.

```python
from project.models import SessionMessage
detail = practice.session_detail(1, session_id)
edits = [dict(artifact_id=a["artifact_id"], base_revision=a["revision"], language=a["language"], body=a["body"])
         for a in detail["artifacts"]]
brief = dict(base_revision=0, entries=[dict(id="e1", type="decision", text="Replays return the stored 201", pinned=True)])
sent = practice.save_and_send(user, session_id, edits=edits, brief=brief, body="Is the stored 201 enough?",
                              expected_sequence=1, request_id=str(uuid4()))
pprint(sent)
[(m.sequence, m.role, m.kind) for m in SessionMessage.query.order_by(SessionMessage.sequence)]
```

The turn cites API contract revision 1, the revision on screen when it was sent. The record reads `[(1, 'interviewer', 'turn'), (2, 'learner', 'brief'), (3, 'learner', 'turn')]`. Why is the turn number 3, not 2?

**Send from an out-of-date view:**

```python
try:
    practice.save_and_send(user, session_id, edits=edits, brief=brief, body="From a second device",
                           expected_sequence=1, request_id=str(uuid4()))
except practice.StaleViewError as exc:
    print(exc.code, exc.latest_turn)
```

Expect `stale_transcript 3`. The brief at record 2 didn't count: find `_latest_turn`. The brief isn't stale either, even though its base is still 0. Why not?

**Step through the brief decision:**

```python
pdb.runcall(practice.save_and_send, user, session_id, edits=edits, brief=brief, body="From a second device",
            expected_sequence=3, request_id=str(uuid4()))
```

At `(Pdb)`, set `b _decide_brief`, press `c`, then step with `n`. Which `return` runs? Then change `brief["entries"][0]["text"]`, keep `base_revision=0`, and send again with `expected_sequence=4`. What do you get, and why?

**Pause, then save:**

```python
practice.set_status(user, session_id, status="paused", request_id=str(uuid4()))
practice.save_work(user, session_id, request_id=str(uuid4()),
                   edits=[dict(edits[0], base_revision=1, body="POST /orders\nIdempotency-Key: required\n")])["status"]
```

Expect `'active'`: saving resumes a paused session. Find where `save_work` does that.

**Delete:**

```python
practice.delete_session(user, session_id)
```

Expect a `RuntimeError`. This REPL's SQLite connection doesn't enforce foreign keys, so the database cascades wouldn't run and the "deleted" session's rows would stay behind. Turn enforcement on, then delete and count:

```python
from sqlalchemy import text
db.session.execute(text("PRAGMA foreign_keys=ON"))
practice.delete_session(user, session_id)
[model.query.count() for model in (ArtifactRevision, SessionMessage, PracticeReceipt)]
```

Expect `[0, 0, 0]`. PostgreSQL always enforces foreign keys; the tests and the preview fixture turn SQLite's on for every connection.

### DevTools: Send, conflicts, and recovery

Start the fixture and a practice session as in part A, with **Network** open (**Preserve log**, **All** or **Doc**).

1. **Send.** Edit **API contract**, add a brief entry, write a message, and select **Send message**.
   - Expect **POST**, **303**, then **GET**.
   - The payload carries `action=send`, `expected_sequence`, `brief_revision`, and the `brief-N-…` rows.
   - The conversation shows "Sent with API contract revision 1". Follow the link.
2. **New turns elsewhere.** Open the workspace in two tabs. Send from the second, then from the first.
   - Expect **409**, the other tab's turn marked **New**, and your message still in the box.
   - In Elements, `expected_sequence` has moved to the new turn. Send again.
3. **Untouched but out of date.** In two tabs, save a schema edit in one. In the other, edit only the API contract and select **Send message**.
   - Expect **409** "this page was out of date"; the schema box now shows the other tab's text.
   - **Save work** from the same stale page would have succeeded. Why does Send refuse it?
4. **Brief conflict.** Edit the same brief entry in two tabs and save both. The second gets **409**, "Saved elsewhere: brief revision N", with the other version listed.
5. **Save with a typed message.** Type a message, then select **Save work**. Expect **200** rather than a redirect, with the message still in the box. Why no redirect? Now send from a second tab, then type and save in the first again: the page flags the new turn before you can send.
6. **Pause, then resume elsewhere.** Select **Save and pause**. Learning lists the session as Paused. Sign out, then resume from HTTPie (below) or a second browser profile: the transcript, brief, and revisions are intact.
7. **A lost Send.** Set `practice: 'lost'` from the Console as in part A, then send.
   - Expect **503** "Your message wasn't confirmed", holding your message and brief entries.
   - Set `practice` back to `success` and select **Try sending again**. The message appears once, and `/fixture/results` counts it once.
8. **Delete.** Select **Delete this practice session**, then **Delete permanently**: **303** to the lesson, which says the session was deleted.
   - Replay that POST with **Copy as cURL**: it now answers **303** to `/learning/`, where a browser would say the session "doesn't exist or was already deleted". The same answer goes to another account, so it reveals nothing.
   - `/fixture/results` shows zero sessions, revisions, turns, and receipts.

### HTTPie or Postman: brief, turns, pause, delete

Get `token` and `session` with part A's first two commands, then within ten seconds:

```sh
http --ignore-stdin PUT :5057/api/v1/learning/practice/sessions/$session/brief "Authorization:Bearer $token" \
  request_id=$(uuidgen | tr A-Z a-z) base_revision:=0 \
  entries:='[{"id": "e1", "type": "assumption", "text": "Keys expire after 24 hours", "pinned": true}]'
http --ignore-stdin POST :5057/api/v1/learning/practice/sessions/$session/turns "Authorization:Bearer $token" \
  request_id=$(uuidgen | tr A-Z a-z) body='Do keys expire?' expected_sequence:=1 brief_revision:=1 \
  artifact_revisions:='{"api": 0, "schema": 0, "algorithm": 0}'
```

Expect brief revision 1, then **201** with `"sequence": 3`. Then, with a fresh token:

1. Send the turn again with a new request ID and `expected_sequence:=1`: **409** `stale_transcript` with `"latest_sequence": 3`.
2. PUT the brief from `base_revision:=0` with different text: **409** `stale_brief`, with the saved brief.
3. Cite `"api": 1` in a turn before saving any API contract: **400**, not 409. Why?
4. `POST …/sessions/$session/pause` with `request_id=$request` twice, reusing the same ID: identical JSON, `"changed": true` both times. With a new ID: `"changed": false`. Why the difference?
5. `DELETE :5057/api/v1/learning/practice/sessions/$session`: **204**. Repeat it: **404**. Then `GET …/receipts/$request`: `null`, because receipts go with the session.

Responses from the API and the website are the same session: pause in HTTPie, then reload the workspace.

### What this does not cover

- PostgreSQL behaviour (row locks, races, process death, migrations, cascades) is in `tests/test_practice_postgres.py` and `tests/test_curriculum_postgres.py`. That includes Send against a save, two Sends from one view, delete during a save, and a fresh process resuming a paused session. The fixture uses SQLite.
- If the database is down before the request signs you in, the site's normal error page appears instead of the rescue page. Use the browser's Back button to recover typed text.
- A tab still open on a session deleted elsewhere gets "not found" on its next save. Use Back to recover typed text.
- The AI interviewer, feedback, and export arrive in later checkpoints.
