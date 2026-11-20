# Checkpoint 2d: respond, recall, and inspect recovery

Implemented locally November 20, 2026; release and an updated signed iPhone
preview await approval. Existing installed previews do not include this yet.

## Five-minute phone walkthrough

1. Open **Learning → Idempotency → Build → Feedback & snapshots**. On a saved
   finding, open **Your response**. Choose Agree/Disagree/Not reviewed and add an
   optional note. Close and reopen the app before saving: the device draft should
   remain. **Save response** shares it with the web; it makes no AI request.
2. For an agreed concern with linked questions, tap **Start focused review**.
   Explain your answer, reveal it, and choose Again/Hard/Good/Easy. Revealing alone
   does not record a rating. Each question completes this extra pass once; its
   next ordinary review still follows the existing scheduler.
3. **Return to your response**, then **Back to saved feedback**. Check that you
   are in the same session and snapshot. Newer drafts never rewrite the original
   AI assessment. Optional responses are not mastery scores.

## A Python REPL experiment

Use disposable data. In the repo's Python environment, start the existing fake-AI
fixture; a local QA phone build must point at it:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
  poetry run python scripts/learning-preview-fixture.py \
  --concept --feedback-example --port 5075
```

Open a separate `poetry run python` REPL:

```python
import requests
from uuid import uuid4
from project.services.feedback_review_service import DECISIONS, NOTE_LIMIT
DECISIONS, NOTE_LIMIT  # inspect the existing service's contract

base = 'http://127.0.0.1:5075'
s = requests.Session()
def login():
    r = s.post(base + '/api/v1/auth/login', json={
        'email': 'learning1@example.test', 'password': 'LearningPreview123!'})
    r.raise_for_status()
    s.headers['Authorization'] = 'Bearer ' + r.json()['access_token']

login()
root = base + '/api/v1/learning/practice'
sid = s.get(root + '/sessions').json()['sessions'][0]['id']
session = root + '/sessions/' + sid
seq = s.get(session).json()['submissions'][0]['sequence']
feedback = s.get(f'{session}/submissions/{seq}/feedback').json()['feedback']
finding = next(f for f in feedback['findings'] if f['kind'] == 'concern')
finding['annotation']
url = f"{session}/submissions/{seq}/feedback/{finding['id']}"
payload = dict(request_id=str(uuid4()), expected_revision=finding['annotation']['revision'],
               decision='agree', note='Trace two simultaneous first requests.')
login()
first = s.put(url + '/response', json=payload)
first.status_code, first.json()
s.put(url + '/response', json=payload).json() == first.json()  # same receipt
s.get(root + '/receipts/' + payload['request_id']).json()      # no note body
s.get(url + '/review').json()['questions']                    # no answers yet
```

The fixture token expires after ten seconds: call `login()` again between
experiments. Never copy tokens into screenshots or committed collections.

## DevTools, Postman, and interruption experiments

- In the fixture's web feedback page, open **DevTools → Network → All**, save a
  response, reveal a linked question, then rate it. Inspect which requests write
  and which only read. Web forms navigate documents, so XHR-only filtering hides
  them. In Postman, use the same JWT routes shown in the REPL above.
- Make a phone note draft, then save a different note through the REPL with a
  fresh UUID. The phone must keep its draft and show the newer saved version.
  Adopting that revision does not itself save; a later Save response does.
- Only in the disposable fixture, POST `{"practice":"lost","reads":"failure"}`
  to `/fixture/state` immediately before saving a response. Restore
  `{"practice":"success","reads":"success"}` and check recovery: one saved
  response, no duplicate mutation. For a focused **rating**, use
  `{"practice":"lost","receipts":"failure"}` instead, close the app, then
  restore both to `"success"`. Learning should offer the exact affected review.
- Inspect `GET /fixture/results` before and after. One explicit rating adds one
  log and receipt. Response saves, reveals, and recovery do not increase its
  simulated AI spending. The existing hosted $5/$1/$50 limits are untouched.

Automated results and remaining accessibility limits are in the
[checkpoint log](engineering-learning-milestone-2.md#checkpoint-2d--responses-and-focused-practice-on-iphone).
