# Checkpoint 4: the interviewer and its durable replies

Pick one experiment. Predict the result, inspect it, then explain any surprise. Part A covers checkpoint 4a: replies that survive restarts, budgets, and fencing, all driven by a scripted fake interviewer, so nothing here spends money or calls a provider. Part B covers checkpoint 4b, the interviewer itself: what each call may see, hidden requirements and hints, the context allowance, the OpenAI call process, and the evaluation harness. It still spends nothing: the fake answers every call, and the call process runs only against a local stand-in.

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

Expect `'cancelled'`: the reply hadn't started. Now resume with `practice.request_reply(...)`, claim it with `practice.claim_reply(datetime.now(timezone.utc), known_profiles=("interviewer-2",), worker_id="me")`, pause again, and call `practice.begin_call(...)` with the returned ID and token. Why does it raise `CallFenced` even though the reply was already running?

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
- The interviewer itself: part B. Any real AI call: activation.

## Part B — the interviewer

### REPL: what each call sees

Start from part A's REPL setup (a fresh `poetry run python`), which loads the real exercise. Then add:

```python
import json
from project.learning import interviewer
from project.models import SessionMessage

session_id = practice.start_session(user, exercise_id="idempotent-order-api", request_id=str(uuid4()))["session_id"]
sent = practice.send_turn(user, session_id, body="Could two customers share an idempotency key?", expected_sequence=1,
                          artifact_revisions=current, brief_revision=0, request_id=str(uuid4()))
context = practice.reply_context(sent["reply"]["id"])
settings = practice.ai_settings()
selector = interviewer.selector_request(context, settings)
json.loads(selector["input"])
selector["text"]["format"]["schema"]["properties"]
```

The selector sees the learner's message and, for each requirement still hidden, its clarification cues. It never sees a fact: search `json.dumps(selector)` for `2,000 order attempts`. The schema's `enum` lists only the hidden IDs. Why doesn't the selector see the conversation or the reference solution? What could a selector that saw the facts do wrong?

**Build the reply from a selection:**

```python
selection = interviewer.parse_selection({"constraint_ids": ["scope"], "hint_requested": False}, context)
facilitator = practice.reply_facilitator(context, selection)
body = interviewer.reply_request(context, facilitator, settings)
list(json.loads(body["input"]))
json.loads(body["input"])["newly_revealed_facts"]
```

Expect `['exercise', 'transcript', 'revealed_facts', 'newly_revealed_facts', 'learner_brief', 'artifacts', 'latest_message', 'hint']` and only the scope fact. Why does the order matter for the provider's prompt cache? Now try `interviewer.parse_selection({"constraint_ids": ["scope", "made-up"], "hint_requested": False}, context)`: it raises `InvalidOutput`. The schema already has an `enum`, so why check again on the server?

**Reveal it for real:**

```python
provider = practice_worker.FakeProvider(selections=[{"constraint_ids": ["scope"], "hint_requested": False}])
practice_worker.run_once(provider)
practice.session_detail(1, session_id)["revealed_requirements"]
SessionMessage.query.filter_by(practice_session_id=session_id, kind="context").one().data
[(charge.purpose, charge.state) for charge in LearningAICharge.query.order_by(LearningAICharge.id)]
```

The requirement is revealed with the sequence of the reply that revealed it, and a `context` record holds `{"revealed": ["scope"], "turn_sequence": 3, …}`. Both calls were paid for: `select`, then `reply`. Find `complete_reply` in `practice_service.py`: why must the record and the reply commit together?

**Ask for a hint:**

```python
latest = practice.session_detail(1, session_id)["messages"][-1]["sequence"]
practice.send_turn(user, session_id, body="Could I have a hint?", expected_sequence=latest, artifact_revisions=current,
                   brief_revision=0, request_id=str(uuid4()))
hinted = practice_worker.FakeProvider()
practice_worker.run_once(hinted)
json.loads(hinted.reply_calls()[0]["input"])["hint"]
[message["hint"] for message in practice.session_detail(1, session_id)["messages"] if message["role"] == "interviewer"]
```

The fake selector spotted the request, so the reply got the first permitted hint, and that reply is flagged `True`. Ask twice more: the second hint, then none. Where does the server count hints, and why isn't it the model's job?

### REPL: the context allowance

Continue in the same REPL:

```python
for number in range(3):
    latest = practice.session_detail(1, session_id)["messages"][-1]["sequence"]
    practice.send_turn(user, session_id, body=f"Long thought {number}: " + "detail " * 500, expected_sequence=latest,
                       artifact_revisions=current, brief_revision=0, request_id=str(uuid4()))
    practice_worker.run_once(practice_worker.FakeProvider())
app.config["LEARNING_AI_CONTEXT_BYTES"] = 15_000
latest = practice.session_detail(1, session_id)["messages"][-1]["sequence"]
practice.send_turn(user, session_id, body="And now?", expected_sequence=latest, artifact_revisions=current,
                   brief_revision=0, request_id=str(uuid4()))["reply"]
```

Expect `{'id': None, 'status': 'unavailable', 'reason': 'context_too_large'}`: the message is saved, but the conversation no longer fits in 15,000 bytes. The size is measured in bytes, not tokens. Why is that safe? Then continue with recent messages:

```python
recent = practice.request_reply(user, session_id, context="recent", request_id=str(uuid4()))
recent["context_from_sequence"]
after = practice_worker.FakeProvider()
practice_worker.run_once(after)
json.loads(after.reply_calls()[0]["input"])["note"]
```

The reply reads from a later message (9 here), and its input says so. Nothing was deleted: `practice.session_detail(1, session_id)["messages"]` still holds every message. Read `_recent_from`: why can a binary search find the starting point? Finally, save an API contract of `"contract " * 4000`, send a message, and set the allowance to 20,000. The summary now says `essential_too_large`, and `too_large_part` is `“API contract”`. Why offer to drop old messages in one case but not the other?

### DevTools: the interviewer in the browser

Start the fixture as in part A. The fake selector reveals a requirement when a message repeats one of its clarification cues, or shares two distinctive words with one.

1. **Reveal a requirement.** With **Network** open, send "Who owns the key?". When the reply lands, the poll's `revealed_html` changes and **Revealed requirements** fills in beside the scenario without a reload. **Show the reply** jumps to the reply that revealed it. Then send "Should order IDs be UUIDs?": nothing new is revealed.
2. **Hints.** Send "Could I have a hint?": the reply is labelled **Hint**. The exercise permits two. What happens on the third request?
3. **Continue with recent messages.** Send three long messages, a few thousand characters each (paste a paragraph several times). Then in the Console:

   ```javascript
   await fetch('/fixture/state', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({context_bytes: 15000})})
   ```

   Send once more: the status says the conversation is too long, with **Continue with recent messages**. Choose it. A marker shows where the interviewer now reads from. Set `context_bytes` to `524288` when you're done.

### HTTPie or Postman: the interviewer over the API

With part A's `token` and `session`:

1. `GET …/sessions/$session` after a revealing reply: `revealed_requirements` lists `id`, `fact`, and `sequence`; each message has `hint`; `context_choices`, `learner_turns`, and `check_in_due` follow.
2. With the conversation too long (see DevTools step 3), `POST …/sessions/$session/reply` with `request_id` and `context=recent`: **202**, with `context_from_sequence`. Repeat it with the same `request_id`: the same JSON comes back. What does `context=older` return?

### The evaluation harness

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run flask --app project learning-eval
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run flask --app project learning-eval --case hint-request --output /tmp/learning-eval.json
```

Every case passes against the fake, which answers each case as `tests/fixtures/interviewer/cases.json` expects. Open the JSON: each case lists its selection, reply, calls (time and tokens), and checks. A run where the fake always passes proves little, so make a check fail on purpose, in the REPL:

```python
from project.learning import interviewer_eval
cases = interviewer_eval.load_cases()
item = interviewer_eval.exercise(cases["exercise_id"])
case = next(case for case in cases["cases"] if case["id"] == "unrelated")
leaky = practice_worker.FakeProvider(selections=[case["expect"]], replies=["Peak traffic is 2,000 order attempts per second."])
interviewer_eval.run_case(leaky, item, case, dict(settings, model="fake-interviewer"), profile_version="interviewer-2")["checks"]
```

`reply_reveals_nothing_unearned` is now `False`. Read `run_case`: which checks look at the requests, and which at the reply? At activation the same command runs with `--provider openai` and Learning's key, and writes `docs/evaluations/learning-interviewer-<date>.json`.

### The call process by hand

The OpenAI call runs in a child process that imports only the standard library and `requests`. From the repository root, feed it a request with no key in its environment:

```sh
echo '{"parent_pid": '$$', "deadline": 5, "base_url": "https://api.openai.com/v1", "body": {}, "max_response_bytes": 1000}' \
  | env -i PATH="$PATH" "$(poetry env info -p)/bin/python" -I project/learning_ai_call.py
```

Expect `{"error": "provider_auth", "charged": "no", "usage": null, "seconds": 0.0}`. Nothing was sent, so nothing was charged. Change the base URL to `http://example.com`: why is plain HTTP refused except for `127.0.0.1` and `localhost`? `tests/test_learning_ai_call.py` runs the real child against a local stand-in for every status, refusal, timeout, and size limit.

### What part B does not cover

- The live model's behaviour: whether it spots paraphrased questions, declines to give the answer, and gives hints well. That's activation, with `learning-eval --provider openai`.
- The check-in after 24 learner turns. The tests set a smaller count; the fixture keeps the default.
