# Checkpoint 5c: investigate saved feedback

Use the disposable preview at <http://127.0.0.1:5059/learning/>. Login:
`learning1@example.test` / `LearningPreview123!`. To start it yourself:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python scripts/learning-preview-fixture.py --concept --feedback-example --port 5059
```

This preserves older previews on 5057/5058. It seeds one **scripted example**, with
a strength, a race concern, and missing evidence. New feedback requests use an
honestly labelled demo response, not a technical grader. Nothing calls a paid
provider. Data disappears when this process stops.

## DevTools: follow the request, evidence, and recovery

1. Resume the example. **Build → Checks → View this snapshot and request
   feedback** opens its saved result. Follow an evidence link to revision 1.
   Change/save the API in another tab: the old finding must still cite revision 1.
2. Save a **new** snapshot. In Network, enable **Preserve log**, choose **All**,
   then click **Request feedback**. Inspect the document POST: it sends CSRF and
   `request_id`, not a fresh copy of the editors. The 303 leads to the saved
   snapshot; subsequent GETs poll its `/feedback` URL.
3. Inspect the polling response: `{html, live}` contains escaped learner-facing
   feedback. There should be no private rubric, reference solution, or
   misconception mapping. Reload or leave and return: the result persists.
4. In Network, right-click the POST → **Copy as cURL**, then run it unchanged in
   your terminal (or import it into Postman). The same request ID replays the
   original result; it doesn't buy another assessment. A new snapshot is needed
   to assess revised work.

For a recovery experiment, run this from the preview's Console before requesting
feedback on another new snapshot:

```js
await fetch('/fixture/state', {
  method: 'POST', headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({practice: 'lost'})
});
```

Expect an unconfirmed-request page. Change `lost` to `success` in the same command,
then retry the form. Compare `/fixture/results` before/after: one request/result,
not a duplicate. This fixture simulates a committed POST whose response was lost.
`practice: 'failure'` instead fails before saving. `ai: 'slow'` helps inspect the
pending state; `ai: 'lost'` simulates an unknown provider outcome. Each requires an
explicit retry after failure; status polling never automatically submits work.

HTTPie can control and observe this disposable server too:

```sh
http POST :5059/fixture/state ai=slow
http GET :5059/fixture/results
http POST :5059/fixture/state ai=success context_bytes:=100
```

With `context_bytes=100`, request feedback on a new snapshot. Expect “too large to
assess in one call”; no paid call, no partial assessment. Restore `context_bytes`
to `524288` afterward. The authenticated JSON API is
`/api/v1/learning/practice/sessions/<id>/submissions/<sequence>/feedback`:
POST accepts only `request_id`; GET returns structured findings and status.
It uses the existing JWT login flow from the checkpoint 3 guide, not browser cookies.

## Python REPL: inspect why a fabricated quote is rejected

This uses a disposable in-memory fixture for setup, not the running preview or
your application database. You are calling functions interactively, not running
the test suite.

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python
```

```python
from copy import deepcopy
from tests.test_practice_feedback import FeedbackCase
from project.learning import evaluator

fixture = FeedbackCase()
fixture.setUp()
inputs, answer = fixture.inputs_and_output()
checked = evaluator.validate(answer, inputs)
checked['findings'][1]['evidence']   # exact revision, original quote, line number

bad = deepcopy(answer)
bad['findings'][1]['evidence'][0]['quote'] = 'The learner never wrote this.'
evaluator.validate(bad, inputs)     # InvalidFeedback: evidence

breakpoint()                        # try: p inputs['sources']; n; c
fixture.tearDown()                  # clean up even after experimenting
```

`inputs` is **server-only** and includes private assessment material; the public
API never returns it. Exact quotation checks prevent invented citations, but
cannot prove an AI's technical interpretation is right.

For a profiling refresher, record the feedback request in Performance and compare
Network's Timing tab with the rendering work. Provider latency and Python/SQL
execution do not appear as JavaScript CPU time. The fake's latency says nothing
about the live evaluator's speed or grading quality.
