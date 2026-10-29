# Checkpoint 4: durable interviewer replies

Pick one experiment. Predict the result, inspect it, then explain any surprise. Part A covers checkpoint 4a: replies that survive restarts, budgets, and fencing, all driven by a scripted fake interviewer, so nothing here spends money or calls a provider. Part B will cover checkpoint 4b, the interviewer itself.

## Part A — durable replies

### REPL: queue, run, and fence a reply

This uses an in-memory SQLite database that disappears when Python exits. From the repository root:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python
```

```python
from datetime import datetime, timezone
from pprint import pprint
from uuid import uuid4
from sqlalchemy import event
from project import create_app
from project.database import db
from project.learning.content_schema import load_catalog
from project.models import AIRequest, ContentRevision, CurriculumItem, LearningAICharge, User
from project.services import practice_budget, practice_service as practice, practice_worker
from project.services.curriculum_service import content_checksum

app = create_app(dict(TESTING=True, SECRET_KEY="repl", SQLALCHEMY_DATABASE_URI="sqlite://",
    LEARNING_AI_ENABLED=True, LEARNING_AI_PROVIDER="fake", LEARNING_AI_OWNER_EMAIL="repl@example.test"))
app.app_context().push()
db.create_all()
user = User(id=1, username="repl", email="repl@example.test", email_verified=True)
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
current = {"api": 0, "schema": 0, "algorithm": 0}
sent = practice.send_turn(user, session_id, body="Do keys expire?", expected_sequence=1,
                          artifact_revisions=current, brief_revision=0, request_id=str(uuid4()))
sent["reply"]
```

Expect `{'id': '…', 'status': 'pending', 'reason': None}`: the turn and its reply request committed together. Nothing has answered yet, because nothing in this REPL runs the worker.

**Run the worker once:**

```python
provider = practice_worker.FakeProvider()
practice_worker.run_once(provider)
practice.session_detail(1, session_id)["messages"][-1]["body"]
charge = LearningAICharge.query.one()
charge.state, charge.reserved_microusd, charge.cost_microusd
```

The reply is written, and its charge is settled for far less than was reserved. Why reserve so much more? Find `reserve` in `practice_budget.py`. Then check `provider.calls[0]["store"]`, and search `provider.calls[0]["input"]` for `2,000 order attempts` (a hidden requirement) or `reference_reasoning`: neither is there, because hidden material stays on the server until the interviewer may reveal it.

**A reply whose outcome is unknown:**

```python
practice.send_turn(user, session_id, body="And after expiry?", expected_sequence=3,
                   artifact_revisions=current, brief_revision=0, request_id=str(uuid4()))
practice_worker.run_once(practice_worker.FakeProvider("lost"))
[(row.status, row.error_code) for row in AIRequest.query.order_by(AIRequest.created_at)]
[(row.state, row.reserved_microusd, row.cost_microusd) for row in LearningAICharge.query.order_by(LearningAICharge.id)]
practice_budget.committed(practice_budget.period(datetime.now(timezone.utc)))
```

The lost call stays `reserved`, and the month's committed spend includes its whole reservation. Why not refund it? And why is it not retried automatically? Ask again with `practice.request_reply(user, session_id, request_id=str(uuid4()))`, then run the worker.

**Pause before the next paid call:**

```python
practice.send_turn(user, session_id, body="One more question", expected_sequence=5,
                   artifact_revisions=current, brief_revision=0, request_id=str(uuid4()))
practice.set_status(user, session_id, status="paused", request_id=str(uuid4()))
AIRequest.query.order_by(AIRequest.created_at.desc()).first().status
```

Expect `'cancelled'`: the reply hadn't started. Now resume with `practice.request_reply(...)`, claim it with `practice.claim_reply(datetime.now(timezone.utc), known_profiles=("interviewer-1",), worker_id="me")`, pause again, and call `practice.begin_call(...)` with the returned ID and token. Why does it raise `CallFenced` even though the reply was already running?

**Step through a whole reply:**

```python
import pdb
practice.request_reply(user, session_id, request_id=str(uuid4()))
pdb.runcall(practice_worker.run_once, practice_worker.FakeProvider())
```

At `(Pdb)`, set `b practice_service.begin_call` and `b practice_service.complete_reply`, then press `c`. In `begin_call`, inspect `held.rowcount`, `session.status`, and `lease`. Which rows has it locked by the time it calls `practice_budget.reserve`, and in what order? In `complete_reply`, which checks decide between `"written"` and `"fenced"`?

**A reply that can't fit:**

```python
now = datetime.now(timezone.utc)
spent = practice_budget.committed(practice_budget.period(now))
app.config["LEARNING_AI_MONTHLY_CAP_USD"] = (spent + 12_000) / 1_000_000
latest = practice.session_detail(1, session_id)["messages"][-1]["sequence"]
sent = practice.send_turn(user, session_id, body="Does a key cover a retry from another device?",
                          expected_sequence=latest, artifact_revisions=current, brief_revision=0,
                          request_id=str(uuid4()))
sent["reply"], practice.ai_budget(1, now)["exhausted"]
```

Expect `({'id': None, 'status': 'unavailable', 'reason': 'budget'}, False)`. The turn is saved, but no reply was queued, although $0.012 is left. Find `_reply_fits` in `practice_service.py`: what does it price, and why check before queueing rather than let the worker's reservation refuse? Then set the cap to `(spent + 9_000) / 1_000_000` and call `practice.ai_budget(1, now)` again. Why does the month now read as used up? Compare `_month`.

### psql: watch the compare-and-swap claim

Two releases of the app can run at once during a deploy, and each runs a worker. This needs the disposable PostgreSQL test database (see the handoff) holding one pending reply. Create it from a REPL connected there (`SQLALCHEMY_DATABASE_URI=<the test URL>` in the setup above, with `db.create_all()`), then open two `psql` sessions on that database:

```sql
-- both sessions
SELECT id, status, claim_token FROM ai_request WHERE status = 'pending';
-- session 1
BEGIN;
UPDATE ai_request SET status = 'running', claim_token = 'one' WHERE id = '<id>' AND status = 'pending';
-- session 2: this waits
UPDATE ai_request SET status = 'running', claim_token = 'two' WHERE id = '<id>' AND status = 'pending';
-- session 1
COMMIT;
```

Session 2 then reports `UPDATE 0`. PostgreSQL re-checked `status = 'pending'` after the lock was released, so only one worker claims the reply. Compare `claim_reply` in `practice_service.py`, which checks the row count.

### psql: why the owner lock is FOR NO KEY UPDATE

Every practice write first locks the learner's `user` row. The worker never takes that lock, but when it inserts a ledger charge, PostgreSQL checks the charge's foreign key by taking `FOR KEY SHARE` on that same row. With the setup above, in two `psql` sessions:

```sql
-- session 1
BEGIN;
SELECT id FROM "user" WHERE id = 1 FOR UPDATE;
-- session 2: this waits
SELECT id FROM "user" WHERE id = 1 FOR KEY SHARE;
-- session 1
ROLLBACK;
```

Repeat with `FOR NO KEY UPDATE` in session 1: session 2 returns at once. The worker inserts the charge while holding a reply's request row, and a Send or delete holding the user lock may be waiting for that row. With `FOR UPDATE`, each waited for the other until PostgreSQL ended one with a deadlock error. Find `_lock_owner` in `practice_service.py`, and `during_call_check` in `tests/test_practice_replies_postgres.py`, which holds the worker at that moment.

### DevTools: follow a reply in the browser

Start the disposable app, sign in as `learning1@example.test` (the configured owner), and start a practice session:

```sh
poetry run python scripts/learning-preview-fixture.py --concept
```

1. **Follow a reply.** The fake answers in well under a second, so first slow it down from the Console (the `fetch` in step 2, with `{ai: 'slow'}`): each reply then takes three seconds. Open **Network** with **Fetch/XHR** selected, then send a message.
   - The page polls `…/reply?after=<n>` about every 1.5 seconds. Open one response: `turns` holds every turn after `n`, already rendered, and `latest_sequence` updates the page's `expected_sequence`.
   - When the reply arrives, polling stops and Send is enabled again. Check **Elements**: the hidden `expected_sequence` changed without a reload.
2. **Failure modes.** In the Console, set a mode, then send:

   ```javascript
   await fetch('/fixture/state', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ai: 'fail'})})
   ```

   - `fail`: "The interviewer couldn't reply", with **Retry the reply**.
   - `lost`: "didn't answer in time". Compare `/fixture/results` before and after: `ai_spend_microusd` keeps the reservation.
   - `slow`: three seconds of "replying". Edit and save an artifact meanwhile: the reply still cites the earlier revision. Why?
   - `hang`: about ten seconds, then a timeout.
   - Set `ai` back to `success` when you're done.
3. **Budget.** Restart the fixture, set `{cap_usd: 0.015}`, and send: the message is saved with "no room for another reply", although nothing has been spent. Why? Then set `{cap_usd: 0.002}` and reload: the banner says the month is used up. Set `{cap_usd: 50}` to bring **Ask for a reply** back.
4. **Another account.** Sign in as `learning2@example.test`: its messages are saved, with "AI replies aren't available for this account".
5. **Send while replying.** In `slow` mode, send twice quickly from two tabs: the second gets **409** "The interviewer is still replying", with its draft kept.
6. **Lose the connection.** In `hang` mode, send, then right-click a `reply?after=` request in **Network** and choose **Block request URL**. Each poll now fails. Watch the gaps between attempts grow (5, 10, 20, then 30 seconds). After the sixth failure, about a minute and a half in, the page says "Couldn't check for the reply" and Send comes back. Why retry a dropped connection or a server error, but stop at once on a redirect to sign-in? Unblock the URL and reload to see where the reply ended up.

The fixture keeps its database only while it runs, so a restart there starts fresh. Restart recovery is covered by the PostgreSQL tests.

### HTTPie or Postman: replies over the API

Get `token` and `session` with checkpoint 3's part A commands, then within ten seconds:

```sh
http --ignore-stdin POST :5057/api/v1/learning/practice/sessions/$session/turns "Authorization:Bearer $token" \
  request_id=$(uuidgen | tr A-Z a-z) body='Do keys expire?' expected_sequence:=1 brief_revision:=0 \
  artifact_revisions:='{"api": 0, "schema": 0, "algorithm": 0}'
http --ignore-stdin GET ":5057/api/v1/learning/practice/sessions/$session/reply?after=2" "Authorization:Bearer $token"
```

Expect **202** with `"reply": {"status": "pending", …}`, then a status that turns `completed` with the interviewer's turn in `turns` once the fixture's worker answers. Then, with a fresh token:

1. Set `ai: 'slow'` (the fake otherwise answers in well under a second), send a turn, and send another before the reply arrives: **409** `reply_pending`.
2. After a failure (`ai: 'fail'`), `POST …/sessions/$session/reply` with a new `request_id`: **202**, a new reply ID.
3. Repeat that POST with the same `request_id`: the same JSON comes back.
4. Ask again once it has a reply: **200**, with `"status": "answered"`. Nothing is queued. Why is that a success rather than an error?
5. Try `GET …/reply?after=abc`: **400**. Leaving `after` out means 0.

### What this does not cover

- PostgreSQL behaviour: two releases claiming at once; budget races at the cap; completion against delete, pause, and the sweep in both orders; the worker's call check held while a delete, a pause, or a stale Send arrives; `kill -9` during a call and before storing; and restart recovery. All are in `tests/test_practice_replies_postgres.py`.
- The interviewer itself (its prompts, hidden-requirement disclosure, hints, and the context allowance) and any real AI call: checkpoint 4b and activation.
