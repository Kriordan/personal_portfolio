# Checkpoint 6b: investigate your self-assessment check-ins

Open <http://127.0.0.1:5067/learning/concepts/idempotency/self-assessment>.
Disposable accounts: `learning1@example.test` or `learning2@example.test` /
`LearningPreview123!`. Account 1 has scripted practice/feedback and an example
reflection from manual verification; account 2 starts fresh. These are fixture
ratings, not an assessment of Keith. To start a fresh preview:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python scripts/learning-preview-fixture.py --concept --feedback-example --port 5067
```

The preview uses temporary data and fake AI. Stopping/restarting removes its data.
Use a free port if another preview is already running. The existing 5066 preview
predates this checkpoint; use 5067 for self-assessment.

## DevTools: follow one save, then reproduce a conflict

1. Open **Network → All → Preserve log**. Open **Self-assessment (optional)**
   from any concept mode. Browsing creates no check-in or enrollment. Choose
   different answers for two areas; leave the others **Not assessed**.
2. **Save check-in** sends a native POST, followed by a **303** and GET. Inspect
   its Form Data: four ratings, `content_version`, `expected_revision`,
   `request_id`, CSRF token, and the selected practice session. The history has
   one dated entry. There should be no AI or review-rating request.
3. Right-click that POST → **Copy as cURL**, or import it into Postman. Replaying
   it unchanged adds no entry. Even after another check-in, the exact old retry
   returns the original result without replacing the latest one. Changing a
   rating while reusing that request ID returns **409**.
4. Open the page in two tabs. Save different choices in the first, then the
   second. The second displays both the latest check-in and your unsaved choices.
   **Save as a new check-in** explicitly adds a new entry; earlier entries stay.
5. Use Tab, arrow keys, and Enter to save. Expand history with the keyboard.
   Switch back to Build: the same session and artifacts should still be there.
   Sign out and try account 2; account 1's check-ins must not appear.

In Console, inspect the current form:

```js
const form = document.querySelector('[data-self-assessment-form]');
Object.fromEntries(new FormData(form));
[...form.querySelectorAll('select')].map(s => [s.labels[0].textContent, s.value]);
```

In **Sources**, set a breakpoint in `learning-self-assessment.js` inside the
`beforeunload` listener. Change a rating and follow a link; compare `initial`
with `value()` and cancel leaving. This script only guards unsaved choices;
the native form owns persistence. In **Performance**, record opening history:
it expands local HTML, with no fetch or AI work.

For deletion, use **Delete self-assessment history** and read the confirmation
before submitting. Ratings are removed; dates/request records remain to protect
retries. Old saves cannot restore deleted ratings, and retrying an old deletion
cannot remove a check-in saved afterward. Other study progress is unaffected.
Keep copied cookies, bearer tokens, and CSRF tokens private.

## HTTPie: inspect the paginated API

Run this block together; the preview's access token lasts ten seconds:

```sh
LEARNING_TOKEN=$(http --body POST :5067/api/v1/auth/login \
  email=learning1@example.test password='LearningPreview123!' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
http GET :5067/api/v1/learning/concepts/idempotency/self-assessments \
  Authorization:"Bearer $LEARNING_TOKEN"
```

Inspect `revision`, `current`, `entries`, and `next_before`. The newest ten
check-ins are returned; use `?before=<next_before>` for older ones. Each entry
pins its lesson version and `scale_version: 1`. POST takes `content_version`,
`ratings` (all four keys), `expected_revision`, and `request_id`. DELETE takes
only `expected_revision` and `request_id`. Cookie-authenticated website forms
use the singular `/self-assessment`; the JWT API uses plural `/self-assessments`.

## Python REPL: explore without touching the preview

This creates an independent in-memory fixture. The automated PostgreSQL suite
checks locking; this exercise is for exploring behavior and stepping into code.

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python
```

```python
from tests.test_practice_web import PracticeWebCase
from tests.test_self_assessment import checkin, clear
from project.services import self_assessment_service as assessment
from project.services import concept_progress_service as progress

fixture = PracticeWebCase()
fixture.setUp()
assessment.history(1, 'idempotency')       # revision 0, no check-ins
payload = checkin(recognition='without_help', application='with_help')
first = assessment.save(1, 'idempotency', **payload)
assessment.save(1, 'idempotency', **payload) == first  # True: exact retry
second = assessment.save(1, 'idempotency', **checkin(1, judgment='not_yet'))
assessment.save(1, 'idempotency', **payload) == first  # Still True
assessment.history(1, 'idempotency')['current'] == second  # True
progress.progress(1, 'idempotency')        # None: reflection did not enroll
assessment.history(2, 'idempotency')['entries']  # []: another account

# Step into the replay: n = next, s = step in, p request_id = inspect, c = continue.
import pdb
pdb.runcall(assessment.save, 1, 'idempotency', **payload)

deletion = clear(2)
assessment.clear_history(1, 'idempotency', **deletion)  # revision 3
assessment.save(1, 'idempotency', **checkin(3, understanding='with_help'))
assessment.clear_history(1, 'idempotency', **deletion)  # old receipt, not a new delete
assessment.history(1, 'idempotency')['current']['revision']  # 4
fixture.tearDown()
```
