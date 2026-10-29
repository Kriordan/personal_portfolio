# Checkpoint 3: save, conflict, and recover practice work

Pick one experiment. Predict the result, inspect it, then explain any surprise. Part A covers checkpoint 3a (sessions and artifacts). Part B will cover checkpoint 3b (discussion turns, brief, pause/resume, delete).

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
first = practice.save_artifacts(user, session_id, edits=[edit], request_id=request_id)
first == practice.save_artifacts(user, session_id, edits=[edit], request_id=request_id)
ArtifactRevision.query.one().body
practice.save_artifacts(user, session_id, edits=[dict(edit, body="changed")], request_id=request_id)
```

Expect `True`, then `'POST /orders\n'`, then `RequestConflictError`. Why did `\r\n` become `\n`? Find `normalize_text`. Then inspect `PracticeReceipt.query.all()[-1].payload_sha256`: the receipt stores a hash of your text, not the text itself.

**Lose a conflict, then keep an untouched artifact:**

```python
try:
    practice.save_artifacts(user, session_id, request_id=str(uuid4()), edits=[
        dict(edit, body="another tab's design"), dict(artifact_id="schema", base_revision=0, language="sql", body="")])
except practice.StaleArtifactError as exc:
    pprint(exc.conflicts)
```

The API edit conflicts because revision 1 now exists. The schema edit is empty and matches what that view loaded, so it does not conflict. Nothing was written: count `ArtifactRevision` rows to confirm.

**Step through the decision:**

```python
import pdb
pdb.runcall(practice.save_artifacts, user, session_id, request_id=str(uuid4()),
            edits=[dict(edit, base_revision=1, body="POST /orders\n")])
```

At `(Pdb)`, set `b _apply_edits` (the debugger starts inside `practice_service`), press `c`, then step with `n`. Inspect `head.revision`, `submitted`, and `_state(head, spec)`. Which branch runs, and why does the result say `"changed": False`?

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

### What this does not cover

- PostgreSQL behaviour (row locks, races, process death, migrations) is in `tests/test_practice_postgres.py` and `tests/test_curriculum_postgres.py`. The fixture uses SQLite.
- If the database is down before the request signs you in, the site's normal error page appears instead of the rescue page. Use the browser's Back button to recover typed text.
- The AI interviewer, discussion turns, the brief, pause/resume, and delete are not part of checkpoint 3a.
