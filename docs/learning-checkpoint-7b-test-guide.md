# Checkpoint 7b: private hosted pilot

Deployed November 13, 2026 with Keith's explicit approval. **The private pilot
is live** at [Learning](https://www.keithriordan.com/learning/), using the existing
verified account. Heroku **v171 / `93a24a2`** is in `pilot` mode; the existing
site, PostgreSQL database and single Basic web dyno are reused.

Keith approved one-account access, exact labelled idempotency drafts and fresh
hosted practice. Local sessions remain readable and local paid AI is frozen.
The original **$5 total** and **$1 verification portion** carry forward. At
activation, $0.076025 was counted ($0.037859 carried, $0.030851 new settled calls,
$0.007315 reserved), leaving **$4.923975**. The on-screen allowance is the current
source of truth as you use the pilot.

## A short hands-on check

1. In a private browser window, open Learning. Expect a login redirect and no
   Learning link in the public navigation. Sign in with your existing account;
   expect **Private Learning pilot · Draft idempotency content**. Another signed-in
   account cannot enter Learning, even if it is an administrator.
2. Open **DevTools → Network → All**, enable **Preserve log**, and reload Learn.
   Inspect `Cache-Control: private, no-store`, `X-Robots-Tag: noindex, nofollow`,
   and `X-Learning-Content-Status: private-draft-pilot`. Under **Application →
   Cookies**, the session/remember cookies should be Secure, HttpOnly and Lax.
   Learning and login pages should load neither Google Analytics nor Hotjar.
3. Start learning, reveal/rate one Review answer, then start a fresh Discuss
   session. Write a small API outline in Build and send a clarification about it.
   Inspect the form POST in Network: the turn cites the saved artifact revision.
   Fetch/XHR shows reply polling. Reload after saving; the same work remains.
4. Use **Checks → Save and check → View this snapshot → Request feedback**.
   Follow a citation and edit the artifact afterward. The old snapshot should
   remain unchanged. This step and conversation replies use the shared allowance.
5. Save and pause. Close/reopen the browser and resume from Learning. A later
   hosted process restart should also retain work, feedback, login and spending.
   A reply interrupted during a restart offers explicit recovery; it is never
   automatically charged again.

You can also inspect the paused [Codex setup example](https://www.keithriordan.com/learning/practice/d0739690-1e7b-485f-842a-e36257a6976d?view=build&work=artifact-api).
Its artifacts and feedback are labelled as assisted verification, not your
unaided work. Start a new session for your own practice. The hosted restart
check already confirmed that its work, login and accounting survive restarts.

For an API check without changing progress, use Postman to POST your credentials
as JSON (`email`, `password`) to `/api/v1/auth/login`. Keep its access token in a
private local variable and GET `/api/v1/learning/practice/sessions` with Bearer
authentication. A browser cookie alone should return 401. Use **Copy as cURL**
on an existing request to inspect it in a terminal or import it into Postman.
Replaying a saved request ID is a retry; a new ID represents another action.
Do not share captured credentials, cookies or tokens.

These HTTPie reads require no credentials and create no work:

```sh
http --headers GET https://www.keithriordan.com/learning/
http --headers GET https://www.keithriordan.com/api/v1/learning/practice/sessions
```

Expect 302 and 401 respectively. The [7a guide](learning-checkpoint-7a-test-guide.md)
has a local Python REPL exploration. It continues to work after cutover when
`app_for` is used without live mode. Do not use production credentials in a local
REPL or point a disposable preview at the hosted database.

## Deployment procedure — completed for this rollout

1. Confirm the exact checkpoint commit, current Heroku release/source, schema,
   verified owner ID **1**, domain list and one Basic web dyno. The inspected
   baseline was v164/source `c5edc1b2`, schema `a4b5c6d7e8f9`, PostgreSQL 16.14.
   Stop if those assumptions have materially changed. The branch includes the
   previously approved Learning checkpoints that are not on production yet.
2. Take a fresh private production backup and record its checksum/release.
   Restore it to a new local database and verify the upgrade. Use PostgreSQL 16
   client tools; never restore into the live database or the local pilot. The
   November 13 rehearsal is evidence, not a substitute for a current backup.
3. Let local paid work finish, stop the local server and back it up. Resolve any
   pending/running requests explicitly before proceeding. With the prepared
   Python environment selected, run:

   ```sh
   poetry run python scripts/learning-pilot.py handoff-hosted \
     --owner-id 1 --owner-email keith.riordan@gmail.com
   ```

   This writes `.local/learning-pilot/hosted-handoff.json` privately, only after
   freezing local paid AI. Retrying after a partial write is safe for the same
   target/ledger. `serve --live` and reauthorization are then refused. Plain
   `serve` retains local reading/editing. Do not remove the freeze marker or
   re-enable an old copy of the source settings.
4. Read that file and Learning's existing dedicated key privately in memory.
   Patch only the intended Heroku configuration values using a structured API
   request; never put the key, approval JSON or database URL in shell arguments,
   shared logs or Git. Preserve existing site/authentication configuration.

   | Setting | Initial value |
   | --- | --- |
   | `LEARNING_HOSTED_PILOT` | `1` |
   | `LEARNING_HOSTED_APPROVAL` | Exact contents of the private cutover file |
   | `LEARNING_HOSTED_AI_MODE` | `off` |
   | `LEARNING_OPENAI_API_KEY` | Existing dedicated Learning key; never the generic provider key |

   Owner, content fingerprints, model settings and limits are derived from the
   validated approval. `LEARNING_AI_TOTAL_CAP_USD`, if set, can only lower the
   approved cap. Verification mode caps the same combined lifetime spending at
   $1; pilot mode caps it at $5. Existing monthly limits also apply. Never clear
   the hosted flag as an AI kill switch: that removes the one-account boundary.
5. Deploy the **reviewed commit SHA**, not uncommitted files, and wait for the
   release task and web readiness checks. The release task migrates to
   `e4f5a6b7c8d9`, imports the six exact unpublished draft revisions and verifies
   the owner/content. It starts no worker or paid request. Repeated releases do
   not reset data or spending. Keep one Gunicorn process and one web dyno so
   existing Socket.IO rooms remain local to that process.
6. With AI off, verify public portfolio/login and existing list behavior, owner
   access, non-owner denial, draft labels, saved artifacts and private responses.
   Reference solutions/rubrics must remain absent from learner payloads. Their
   authored source remains in this public repository; this is not source secrecy.
7. Set `LEARNING_HOSTED_AI_MODE=verification` and wait for its release. Use a
   clearly identified setup-verification session for one clarification, saved
   artifacts and one feedback snapshot. Do not rate reviews or record a learner
   self-assessment on Keith's behalf. Inspect settled/uncertain charges, pause
   and restart, and verify recovery. Stop on a failure instead of retrying paid
   calls automatically. Earlier verification costs count against the same $1.
8. After those checks, set mode `pilot` within the same approved $5 allowance.
   Record release/commit, schema, frozen carryover, new verification spending,
   remaining total and any interrupted requests. Provide the live link to Keith.
   Keep raw backup/config/key material private and retain a secure off-computer
   backup for recovery.

## Stopping and recovering

Set **`LEARNING_HOSTED_AI_MODE=off`**, leaving the owner guard and exact approval
intact, and wait for the release. A call already in flight may finish; if its
outcome is lost, its reservation continues to count. Saving, reading and explicit
recovery remain available. No new paid work should start after the switch.

A failed release leaves the previous release serving. Heroku configuration
changes can persist despite release failure, and a code rollback does not undo
database migrations. Inspect both before retrying. The migrations here are
additive and were tested from the deployed schema; do not run destructive
downgrades to remove Learning tables. See Heroku's
[release-phase behavior](https://devcenter.heroku.com/articles/release-phase).

Prefer a forward fix or an inspected compatible prior release. Keep hosted AI
off during rollback/recovery and preserve the current full ledger. If restoring
an older database becomes necessary, first take a backup of the current state,
stop active workers and restore into a **new database** for inspection. The old
backup may lack charges made afterward. Reconcile those amounts, including
uncertain reservations, before approving any reactivation. **An arbitrary
hosted database restore is not automatically detected by this configuration.**
Never run two active databases against the same allowance or reactivate local
AI as a fallback. Obtain approval for a restore/reactivation plan that could
lose newer work or alter accounting.

## Automated evidence

The 759-test suite includes 19 hosted-specific tests: exhaustive route isolation,
strict approval/cap parsing, local cutover crash recovery, real PostgreSQL races,
cross-month/restart accounting, transactional/concurrent migrations, backup
restore, native WebSocket cookie/JWT authentication and real Gunicorn recovery.
Existing browser tests cover 450 assertions; 13 Node tests pass. The sole skip
is an existing Linux-only check on macOS. All pre-deployment AI was mocked;
those tests spent **$0**. The separate production-copy rehearsal preserved all
11,324 pre-existing rows across 28 application tables with no production writes.

Hosted verification found that isolated Python needed its own Linux shared-library
path. Fix `93a24a2` derives only that trusted directory; it does not inherit arbitrary
loader/Python settings or other credentials. It passed 79 targeted local tests
and all 18 provider tests on Heroku using a fake endpoint before paid recovery.
The first failed request's reservation remains counted conservatively.

The recovered live interviewer referenced saved artifacts and challenged the
open expiry decision. Feedback covered the complete snapshot and validated eight
exact citations. Private fields and analytics remained absent; anonymous and
non-owner access stayed denied. Public portfolio/list pages and an authenticated
WebSocket upgrade passed. Restart/resume preserved the work, feedback, login and
ledger. Final activation had no pending AI requests. Heroku backups **b011**
(before deployment) and **b012** (after verification) completed; private records
are under `.local/learning-pilot/hosted-deployment/`.

The backend workflow now matches hosted PostgreSQL 16 and installs matching
backup clients. Gunicorn 27.0.1 is pinned; OAuthLib 4.0.1 and pyasn1 0.6.5 are
the existing-library security updates identified during this review. Safari,
Firefox and screen-reader listening remain the previously recorded follow-ups.
