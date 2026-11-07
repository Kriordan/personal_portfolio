# Checkpoint 6a: investigate enrollment and reading recovery

Open <http://127.0.0.1:5066/learning/>. Disposable accounts:
`learning1@example.test` or `learning2@example.test` / `LearningPreview123!`.
Account 1 has scripted practice/feedback; use account 2 for a fresh enrollment.
To start a fresh preview yourself:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python scripts/learning-preview-fixture.py --concept --feedback-example --port 5066
```

This uses temporary data and fake AI. Restarting removes the preview's data.

## DevTools and Postman: follow a save

1. Open **Network → All → Preserve log**. Explore the lesson before choosing
   **Start learning**: there should be no enrollment or reading-position POST.
   Start learning sends a CSRF-protected `/enrollment` POST and a 303 redirect.
2. Choose another lesson section. Inspect `/reading-position`: `section_id`,
   `content_version`, `expected_revision`, and `request_id` go to the server.
   Its JSON response confirms the saved section and increments `revision`.
   Reading creates no rating or practice-session request.
3. Right-click the save → **Copy as cURL**, run it unchanged, or import it into
   Postman. The exact retry returns the same revision. After a newer save,
   replaying that old request returns **409**, preserving the newer bookmark.
4. Open the same lesson in two tabs. Move to another section in one, then in
   the other. The stale tab explains the conflict and offers **Reload saved
   position**. It does not silently overwrite the other tab.
5. In DevTools, choose **Offline**, change sections, and watch the unconfirmed
   status. Restore **No throttling** and choose **Retry saving position**.
   A normal return restores the saved section; an explicit `#design` link wins
   over the bookmark. Sign out/in and check the Learning home's continuation.

In Console, inspect the current form without changing it:

```js
const form = document.querySelector('[data-reading-position]');
Object.fromEntries(new FormData(form));
document.querySelector('[data-position-status]').textContent;
```

In **Sources**, put a breakpoint inside `save` in `learning-position.js`.
Step through how `pending` retains a failed request and `desired` tracks a newer
section. Keep the form's CSRF token and copied authentication headers private.

## HTTPie: inspect the authenticated API

Run this block together; the disposable preview's access token lasts ten seconds:

```sh
LEARNING_TOKEN=$(http --body POST :5066/api/v1/auth/login \
  email=learning1@example.test password='LearningPreview123!' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
http GET :5066/api/v1/learning/concepts/idempotency/progress \
  Authorization:"Bearer $LEARNING_TOKEN"
```

Before enrollment, `progress` is null. The new JWT write endpoints are POST
`/enrollment` with `{}` and PUT `/reading-position` with the four fields above.
The existing review API remains unchanged.

## Python REPL: inspect the service yourself

This creates an independent in-memory fixture, separate from the preview and
your configured database. The PostgreSQL concurrency checks are automated;
this REPL exercise is for exploring the service contract.

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python
```

```python
from uuid import uuid4
from tests.test_concept_progress import ConceptProgressTests
from project.services import concept_progress_service as progress
from project.models import ReviewProgress

fixture = ConceptProgressTests()
fixture.setUp()
progress.progress(1, 'idempotency')          # None
progress.enroll(1, 'idempotency')            # revision 1
change = dict(content_version=1, section_id='retries',
              expected_revision=1, request_id=str(uuid4()))
progress.save_position(1, 'idempotency', **change)  # revision 2
progress.save_position(1, 'idempotency', **change)  # still 2
progress.progress(2, 'idempotency')          # None: another account
ReviewProgress.query.count()                # 0: no ratings created
# Try: import pdb; pdb.runcall(progress.save_position, 1, 'idempotency', **change)
# In pdb: n (next), s (step into), p request_id (inspect), c (continue).
fixture.tearDown()
```
