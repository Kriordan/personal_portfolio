# Checkpoint 5d: investigate feedback responses and follow-up practice

Open <http://127.0.0.1:5062/learning/>. Disposable login:
`learning1@example.test` / `LearningPreview123!`. If the preview isn't running:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python scripts/learning-preview-fixture.py --concept --feedback-example --port 5062
```

Use the scripted example under **Resume → Build → Checks → View this snapshot**.
This uses fake AI and temporary data. The example publishes draft v2 only inside
the disposable database, so its race concern has a linked review question.

## DevTools: inspect the save and its effect

1. Open **Network → All → Preserve log**. Expand **Your response** on the race
   concern. Choose **Agree**, add a note, and **Save response**. Inspect the
   document POST ending in `/feedback/f2/response`: CSRF, decision, note,
   `expected_revision`, and `request_id` have the `annotation-f2-` prefix.
   The 303 returns to the same finding. The original AI feedback stays unchanged.
2. Right-click that POST → **Copy as cURL**. Run it unchanged, or import it into
   Postman. Reusing the attempt returns its original receipt without saving twice.
   Open the feedback page in two tabs; save different notes from each. The stale
   tab should show both the latest note and your draft before you choose to replace it.
3. Click **Practise this → Show answer**. Both requests are GETs. Only pressing
   **Again / Hard / Good / Easy** sends a rating POST through the existing scheduler.
   Reload: the completed question stays completed for this finding. **Revise your
   work** returns to the original session ID, even if you have started another session.

Observe counts and simulate a lost confirmation with HTTPie:

```sh
http GET :5062/fixture/results
http POST :5062/fixture/state practice=lost
# Save a response or explicitly rate a revealed follow-up question in the browser.
http GET :5062/fixture/results
http POST :5062/fixture/state practice=success
# Retry the recovery form, then inspect the counts again.
http GET :5062/fixture/results
```

`feedback_annotations` counts saved responses; `logs` counts explicit ratings.
A retry should add neither a second response nor a second rating. Agreement alone
adds no rating. `practice=failure` fails before saving instead. The recovery form
retains the same request ID and submitted note/rating. Restore `success` afterward.

For a browser-only version, use Console:

```js
await fetch('/fixture/state', {
  method: 'POST', headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({practice: 'lost'})
}); // Repeat with 'success' before retrying.
```

## Python REPL: compare immutable feedback with your editable response

This creates an independent in-memory fixture; it doesn't connect to the preview
or your application database. Importing a fixture is just setup, not running tests.

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python
```

```python
from copy import deepcopy
from uuid import uuid4
from tests.test_feedback_review import FeedbackReviewTests
from project.models import PracticeFeedback, PracticeFeedbackAnnotation, ReviewLog
from project.services import feedback_review_service as review

fixture = FeedbackReviewTests()
fixture.setUp()
original = deepcopy(PracticeFeedback.query.one().data)
location = (fixture.user, fixture.sid, fixture.seq, 'f2')
change = dict(decision='agree', note='Trace two first attempts.',
              expected_revision=0, request_id=str(uuid4()))
review.annotate(*location, **change)
review.annotate(*location, **change)       # identical receipt, no second change
PracticeFeedbackAnnotation.query.one().revision  # 1
PracticeFeedback.query.one().data == original    # True
ReviewLog.query.count()                   # 0: agreement isn't a rating

queue = review.review_detail(fixture.user.id, fixture.sid, fixture.seq, 'f2')
queue['questions'][0]['card_id']           # idempotency:race
queue['questions'][0].keys()               # answer is absent before reveal
# Try: breakpoint(); then p queue, n, c. No AI call is made here.
fixture.tearDown()                        # always clean up your fixture
```

Only authored questions linked to an accepted concern appear. Legacy v1 and
unmapped findings can still receive responses and keep their lesson links.
Suspended questions stay suspended; withdrawing agreement prevents new ratings,
while a retry of an already committed rating recovers its original result.
