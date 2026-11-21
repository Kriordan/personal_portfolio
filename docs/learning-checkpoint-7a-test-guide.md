# Checkpoint 7a: use and inspect your personal pilot

Open <http://127.0.0.1:5068/learning/>. This pilot keeps data across restarts and
uses the real interviewer/evaluator. Your generated login is in
`.local/learning-pilot/login.txt`; keep it private. The 5067 disposable preview
remains unchanged.

Keith approved **$5 total**, including **at most $1 for Codex verification**.
Verification used **$0.037859** for two replies and one evaluation (five provider
calls including requirement selection). All charges settled; **$4.962141 remains**.
The total persists across restarts and months; existing monthly, context,
deadline, and output limits still apply.

The draft banner is intentional: only the approved idempotency versions/checksums
are available locally. No human publication attestation was created. Private
reference/evaluation material stays out of learner responses and static assets;
its authored source remains in the public repository, as previously acknowledged.

## Start, stop, and inspect spending

From the repository root, select the prepared Python 3.13.18 environment in this
terminal. This leaves the older previews' environment intact:

```sh
export POETRY_VIRTUALENVS_PATH="$PWD/.local/learning-pilot/venvs"
poetry run python --version
poetry run python scripts/learning-pilot.py status
poetry run python scripts/learning-pilot.py serve --live
```

Postgres.app must be running. Ctrl-C stops the web process; the same `serve`
command reopens it without migrating, importing, or resetting data. Stop this
chat's server first if port 5068 is occupied. `status` works while the app runs
and makes no paid calls. Omit `--live` to read/edit without AI.

Live startup requires recorded approval and Learning's dedicated key, read from
`LEARNING_OPENAI_API_KEY` or that one entry in `.env`. No other dotenv settings
are loaded. Stop after a reply finishes when possible; an uncertain call keeps
its reservation and is never retried automatically. `--live --verification`
applies the smaller $1 cap to the same entire ledger, not $1 per run.

## Try the loop and investigate it

1. Choose **Start learning**, read a section, then use **Review** to reveal an
   answer and rate your recall. Optional self-assessment records confidence
   separately. In **DevTools → Network → All → Preserve log**, follow the POST
   and redirect; opening a page should not create a review rating.
2. Start a **new Discuss session**, clarify requirements, and draft an API or
   algorithm in **Build**. Send a message about it. Inspect artifact revisions
   in the submitted form and the interviewer's links to the revisions it read.
3. Use **Checks → Save and check → View this snapshot → Request feedback**.
   Follow an evidence link and judge whether the concern is supported. Edit the
   artifact afterward; the old snapshot must remain unchanged. Polling appears
   under Fetch/XHR; native form submissions appear under All/Doc.
4. Save and pause, restart, and return from Learning. The same login, work, and
   feedback should remain. **Application → Cookies** shows an instance-specific
   `learning_pilot_…` cookie. Responses are `private, no-store`, with
   `X-Learning-Content-Status: local-draft-pilot`.

There is one paused **Codex setup-verification session**, explicitly identified
in its first message. Its [saved feedback](http://127.0.0.1:5068/learning/practice/31806d3b-7e95-4b39-b78a-04736a0dbb48/submissions/7)
is an example, not an assessment of Keith. Verification created no enrollment,
review ratings, or self-assessment. Start a new session for your own trial.

In Network, copy a save request as cURL or import it into Postman. Replaying the
same request UUID should not create another artifact/snapshot/paid request.
A fresh UUID represents a new action; avoid changing one on a paid request
unless you intend another call. Keep captured cookies/tokens private.

For HTTPie, `http GET :5068/pilot/health` reports health and whether AI is enabled.
In Postman, POST your local `email` and `password` as JSON to `/api/v1/auth/login`,
then use its bearer token for `/api/v1/auth/me` or the Learning APIs.

For a read-only Python exploration, retain the environment selection above:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python
```

```python
from scripts import learning_pilot as pilot
from project.database import db
from project.services import curriculum_service, practice_budget

settings = pilot.load_settings(pilot.DEFAULT_STATE)  # contains secrets: don't print
approval = pilot.load_approval(pilot.DEFAULT_STATE, settings)
app = pilot.app_for(settings, approval=approval)  # no worker; AI disabled
with app.app_context():
    lesson = curriculum_service.published_learner_item("idempotency")
    print(lesson["version"], lesson["local_draft"])
    print("committed USD:", practice_budget.committed() / 1_000_000)
    db.session.remove()
    db.engine.dispose()
```

Use `breakpoint()` before the content lookup to follow visibility and learner
projection code. These reads do not enroll, rate, or call AI. Never run
`db.drop_all()`, `db.create_all()`, or the disposable preview on this database.

## Back up and recover

Stop the server first. Choose a new directory for each backup:

```sh
poetry run python scripts/learning-pilot.py backup .local/learning-pilot/backups/my-first-session
```

The private backup contains a PostgreSQL dump/checksum, settings, approval, and
login. It does not automatically include the provider key. Keep it out of Git
and shared folders; a secure off-computer copy is needed against disk loss.

Restore always creates a new database and state directory. Substitute your local
PostgreSQL role and a fresh name:

```sh
poetry run python scripts/learning-pilot.py \
  --state-dir .local/learning-pilot/restored/check \
  restore .local/learning-pilot/backups/my-first-session \
  --database-url postgresql+psycopg://YOUR_LOCAL_ROLE@127.0.0.1:5432/learning_pilot_restored_check
```

Restores retain your password/draft access, rotate session/JWT secrets, and
**block live AI**. An older ledger may omit spending after the backup; reconcile
that spending and obtain a reviewed new approval before adding a reactivation
path. There is no force-live bypass. To inspect a restore, stop the original and
use `--state-dir … serve` without `--live`; both default to port 5068.

The checked backup is `backups/verified-7a`, with an offline restore at
`restored/checkpoint-7a`. Conversation/artifact/feedback exports matched the
original checksum; all five charge records and their total also matched.
Private reports and the export are beside `settings.json`.

For future schema changes: stop, back up, run `upgrade`, then `serve`. Keep the
checkout revision with the backup. Fresh setup and policy details are in the
[handoff](engineering-learning-handoff.md#checkpoint-7a-personal-local-pilot--november-7).
