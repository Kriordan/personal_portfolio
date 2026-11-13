# Engineering Learning: Milestone 1 implementation checkpoints

Scope approved October 28, 2026: one complete **idempotency** concept on the existing Flask website. Preserve the Learning APIs, scheduler, progress, and legacy notes. The existing Flask/PostgreSQL architecture remains; Expo is Milestone 2 and needs separate approval. This log records implementation sequencing without replacing the approved architecture or the earlier Learning mobile modernization record.

Read the [approved revised plan](engineering-learning-revised-plan.md) for the agreed architecture and milestone acceptance criteria. For current progress, remaining work, local setup, and implementation gotchas, start with the [engineering handoff](engineering-learning-handoff.md).

After Milestone 1's local acceptance, Keith separately approved checkpoint 6a on
November 7: enrollment, saved reading position, and home continuation. He then
approved 6b with four independent optional ratings and dated check-ins. Both are
recorded below; Expo and content expansion still need separate approval.

| Checkpoint | Deliverable and acceptance gate | Status |
| --- | --- | --- |
| 1. Content foundation | Versioned catalog, draft lesson/four questions/one structured interview; audience projections; atomic import; additive migration verified on PostgreSQL; legacy Learning regression checks. | Committed as `1f344a5`; [REPL guide](learning-checkpoint-1-test-guide.md). |
| 2. Learn and Review on web | Published lesson, retry visualization, safe Markdown, explicit answer reveal, four questions through the existing scheduler; unchanged old API behavior and progress. Human content review precedes publication. | Committed as `3b108bf`; [hands-on guide](learning-checkpoint-2-test-guide.md), refined in `0c2848a`. Production publication remains pending human content review. |
| 3a. Practice sessions and artifacts | Sessions pinned to a published exercise; API/SQL/pseudocode artifacts with immutable revisions; idempotent saves; per-artifact conflicts without data loss; ownership; failure recovery; web workspace; JWT API; feature flag. Migration and concurrency verified on PostgreSQL. No IDE or execution sandbox. | Committed as `fe91fe2` (persistence and service) and `709658b` (web workspace and API); [practice guide](learning-checkpoint-3-test-guide.md), part A. |
| 3b. Discussion record | Learner turns citing exact artifact revisions, editable session brief, pause/resume, delete; resume elsewhere with transcript, brief, and revisions intact. | Committed as `b7ae1e2` (service) and `bcb0f40` (workspace and API); [practice guide](learning-checkpoint-3-test-guide.md), part B. |
| 4a. Durable replies | Replies as tracked PostgreSQL requests, run by a worker thread in the web process against a scripted fake provider: owner-only access, fencing, budgets and reservations, interruption and explicit retry, polling on the website and API. | Committed as `81312c8` (service and worker) and `27af973` (website and API); [checkpoint 4 guide](learning-checkpoint-4-test-guide.md), part A. |
| 4b. The interviewer | The OpenAI call in a child process through Learning's own key, the `interviewer-1` profile, approved disclosure and hints on request, a read-only revealed-requirements list, a context allowance with **Continue with recent messages** and a specific stop (compaction deferred), the 24-turn check-in, and an evaluation harness. | Committed as `216d394` (the interviewer, its service and API) plus the following website commit; [checkpoint 4 guide](learning-checkpoint-4-test-guide.md), part B. |
| 4. Activation | Keith creates Learning's OpenAI project and key; live evaluations choose the model; verified prices recorded. No production enablement. | Done locally October 30: `gpt-6.1-sol` at low reasoning, after three rounds of live evaluations. Production enablement waits for content review. |
| UI follow-up 1. Learning home | Compact home with one continuation action; dedicated reference and personal-flashcard catalogs; preserve existing review and practice behavior. | Implemented November 2; see Learning home checkpoint below. |
| Login boundary | Require login for every Learning website route; retain JWT API authentication and private cache headers. | `e1a90bc`, November 2. |
| UI follow-up 2. Shared concept workspace | Bring Learn and concept Review into the four-mode workspace; maintain session and artifact continuity. | Implemented November 2; see Shared concept workspace below. |
| 5a. Feedback foundation | Content schema 2 and exercise revision 2 with evaluator-only misconception mappings; validate remediation links; preserve v1 sessions and review history. | Implemented November 2; see Checkpoint 5a below. |
| 5b. Submission snapshots and syntax checks | Immutable revision references, saved JSON/YAML results, editable sessions, Checks UI and API, recovery. | Implemented November 2; see Checkpoint 5b below. |
| 5c. Saved design feedback | One complete snapshot per bounded call, evidence validation, saved findings, and recovery. | Implemented November 2; details below. |
| Live evaluator review | Bounded live quality/latency/accounting review with fixed cases. | `88c706b`; complete November 2; report below. |
| 5d. Learner responses and follow-up practice | Saved decisions/notes, authored questions for accepted concerns, explicit scheduler ratings, recovery and exact-session return. | Implemented November 2; details and guide below. |
| 5e. Portable session export | Private JSON/Markdown downloads with complete saved history and consistent concurrent reads. | Implemented November 3; details and guide below. |
| 5f. Complete demonstration and accessibility review | Full Learn → Review → Discuss → Build walkthrough, targeted accessibility fixes, and regression tests. | Complete locally November 3; report below. Human content/evaluator review, screen-reader listening, standalone Safari/Firefox checks, and final milestone approval remain. |
| 5g. Delegated content and AI review | Correct the private concurrency reference in a new exercise revision and verify saved-work/version boundaries. | Complete locally November 6. Codex recommends local pilot acceptance following Keith's delegated review. Publication and browser/screen-reader limits are recorded in the acceptance report. |
| 6a. Enrollment and resumption | Explicit Start learning, saved section, clear home continuation; preserve scheduler and saved work; PostgreSQL and browser verification. | Approved and implemented November 7; [hands-on guide](learning-checkpoint-6a-test-guide.md). |
| 6b. Optional self-assessment | Four independent ratings, dated history, native forms and JWT API, safe conflict/retry/deletion behavior; unchanged review/practice/AI state. | Approved and implemented November 7; [hands-on guide](learning-checkpoint-6b-test-guide.md). |
| 7a. Persistent personal pilot | Dedicated local PostgreSQL, exact labelled drafts, durable $5 total/$1 verification allowance, backups and safe restart. | Implemented in `dfdabbc`; [operating guide](learning-checkpoint-7a-test-guide.md). |
| 7b. Private hosted pilot | Existing hosted account/site/database, exact private drafts, fresh hosted practice, frozen local AI and carried spending, production server and release safeguards. | Prepared November 13; tests complete; **deployment requires approval**. [Rollout and hands-on guide](learning-checkpoint-7b-test-guide.md). |

Each checkpoint should remain independently reviewable. At Milestone 1 completion, stop for approval before Expo or content expansion. Additional personalities, voice, advanced editors, and the remaining concepts are outside these checkpoints.

## Checkpoint 1 implementation

- Adds `CurriculumItem` and `ContentRevision`, with a composite identity/version primary key and publication attestation constraints. The additive migration is `a4b5c6d7e8f9 → b5c6d7e8f9a0`; it contains no content seed, user changes, or review-table changes.
- Adds strict version 1 schemas, canonical content checksums, local Markdown resolution, reference/DAG validation, and explicit learner/facilitator/evaluator projections.
- Adds `validate-curriculum` and `import-curriculum` CLI commands. Imports default to rollback; `--apply` stores drafts; publication requires an explicit human-review attestation. See [the authoring and import contract](../curriculum/README.md).
- Supplies one draft concept, four review questions, and one interviewer exercise with three expected artifacts. Hidden constraints, alternative reasoning, rubric anchors, and remediation remain outside learner projections and web/mobile assets. Public-source access remains possible by design.
- Uses a PostgreSQL advisory transaction lock for rare operator imports. No queue, cache, provider SDK, frontend dependency, or infrastructure service is introduced. Existing review operations do not acquire this lock.

The current published revision is the highest published version. This avoids a separate mutable pointer and a circular foreign key. Publication metadata can be added to an already imported draft; content itself cannot change under the same ID/version through the importer. A future explicit retirement workflow is separate from source-file omission.

## Validation evidence

October 28, 2026 local result: **314 backend tests run, 313 passed, one skipped** (the existing Linux-only Jobwizard parent-death signal test on macOS). All 17 new curriculum tests passed, including eight on real PostgreSQL **18.6**. `git diff --check` passed. The disposable database was used only for fixtures; no production database was accessed.

Tests use deterministic local content and an isolated PostgreSQL 18 database with dotenv and cloud metadata disabled. They cover:

- Schema errors, duplicate keys/IDs, malformed versions, invalid links, prerequisite cycles, escaping Markdown paths, and source text included in checksums.
- Learner projection leakage sentinels, nested future-field exclusion, selective hidden-fact disclosure, explicit answer reveal, and private source URLs returning 404.
- Dry-run rollback, draft invisibility, repeat import/publication, immutable version conflicts, atomic batch rollback, version pinning, retention of omitted items, and no publication downgrade.
- Simultaneous first publication, conflicting concurrent publication, and process death during an import followed by successful retry after lock release.
- Actual Alembic upgrade/downgrade on populated PostgreSQL review fixtures, unchanged stored review values before/after, and ORM/migration schema parity.

Commands for a disposable test database named `library_sync_test` on localhost:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
  LIBRARY_TEST_POSTGRES_URL=postgresql+psycopg://library_test@127.0.0.1:55439/library_sync_test \
  poetry run python -m unittest discover -s tests -p 'test_curriculum*.py' -v

PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
  LIBRARY_TEST_POSTGRES_URL=postgresql+psycopg://library_test@127.0.0.1:55439/library_sync_test \
  poetry run python -m unittest discover -s tests
```

These PostgreSQL tests are destructive fixtures guarded to localhost and that exact database name; use a disposable cluster, never a development or production database with real data. CI already provides the PostgreSQL service and variable; no CI infrastructure change is needed.

The migration has not been applied to production. Its downgrade removes the two new catalog tables and their content, while preserving the pre-existing review tables. Content has not been published. This checkpoint has no new learner UI; the browser walkthrough, AI mocks for compaction/recovery/budget accounting, and cross-device testing belong to the corresponding later checkpoints.

## Checkpoint 2 implementation and verification

Authenticated Learning now lists published concepts alongside the unchanged legacy flashcard notes. The idempotency lesson has expandable explanations, primary references, and a step-through simulation of commit/response failure and key reuse. Safe Markdown uses the existing locked Marked/DOMPurify dependencies with a small allowlist excluding images, embeds, and executable content; if dependencies are unavailable, escaped text remains readable.

Review uses ordinary Flask forms with CSRF protection. The answer is fetched only after **Show answer**. Each form pins its question version, progress revision, and request UUID. Saves reuse the existing user-row lock, scheduler, receipt, and transaction. A duplicate POST returns the original result; stale forms show a recovery link. Save failures retain the same attempt for explicit retry. Committed ratings survive leaving the page or reopening it; the next visit reads the current due queue. There is no browser-side queue or new client storage to reconcile.

Migration `b5c6d7e8f9a0 → c6d7e8f9a0b1` adds nullable `ReviewLog.content_version` with a composite foreign key to the reviewed content snapshot. Legacy rows stay null and retain their values. Downgrading this migration discards the new version linkage, not the rating/scheduling history. Curriculum IDs cannot reuse a legacy note namespace, and legacy incident authoring cannot claim a curriculum namespace.

New concept routes use the existing login boundary and private/no-store responses. Private Learning pages no longer load Google Analytics or Hotjar. The legacy JSON API and its due queue remain unchanged; the curriculum's web adapter feeds the same scheduling logic. No Expo changes, AI calls, practice sessions, or artifacts are part of this checkpoint.

October 28 local validation: **326 backend tests run, 325 passed, one existing Linux-only test skipped on macOS**, with PostgreSQL 18.6 enabled. Twelve additional backend tests cover authenticated/CSRF flows, explicit reveal, independent user progress, suspended cards, version pinning, repeat/stale submissions, rollback, namespace conflicts, and four completed reviews. PostgreSQL tests cover the new schema through actual Alembic upgrade/downgrade and concurrent curriculum review saves. Root Node checks passed (13 tests plus dependency-integrity checks); browser checks passed (23 legacy flashcard, nine extraction, and 27 concept checks). Sass compiled successfully.

The disposable browser preview verified lesson navigation, changing the retry key, answer reveal, and a saved rating leading to the next question. A 390-pixel layout check verified the stacked rating controls and readable question/answer. This is browser layout coverage, not Expo/native or a complete screen-reader audit. The fixture marks content as a demo only; it does not attest human technical review or publish to production.

## Checkpoint 3a implementation and verification

Decided with Keith on October 28, after reviewing the handoff, the approved revised plan, and the original vision against the code:

- Checkpoint 3 is split into 3a (sessions, artifacts) and 3b (turns, brief, pause/resume, delete).
- Learner turns and the brief come in 3b. The brief is stored as versioned snapshots in `SessionMessage`.
- A JWT API ships now.
- Any signed-in user may practise once `LEARNING_PRACTICE_ENABLED` is on.
- Delete ships in 3b; export stays in checkpoint 5.

The handoff records the reasons and the review's other findings.

Migration `c6d7e8f9a0b1 → d7e8f9a0b1c2` adds five practice tables:

- `practice_session` (pinned exercise revision, interaction style, status).
- Immutable `artifact_revision` rows.
- Ordered `session_message` records.
- `session_message_artifact` citations, whose composite foreign keys cannot cross sessions.
- Hash-only `practice_receipt` rows.

Deletes cascade in the database. No catalog, review, or progress table changes. Downgrading drops all practice data.

`practice_service` starts a session on the latest published exercise revision and records the authored opening prompt as the interviewer's first turn (`opening_view` is the one facilitator field a learner sees). It saves artifacts all-or-nothing:

- Text equal to the saved head is unchanged, so no revision is written.
- An edit on the current head becomes the next revision.
- An untouched box keeps a revision saved elsewhere.
- Anything else is a conflict, and nothing is written.

Text is normalized to LF and limited to 64 KiB of UTF-8, with NUL rejected before the database. Every write takes the owner's user-row lock, checks its receipt, then reads owner-scoped rows fresh. SQL parameters are hidden in every environment, and practice logs use `describe_failure`, because PostgreSQL's DETAIL line quotes failing rows.

The website workspace is one Flask-WTF form with a 24-hour CSRF token. Every rejected save re-renders the learner's text:

- **400:** an expired token or invalid input.
- **409:** a conflict, with both versions shown.
- **503:** a database failure, on a standalone page that needs neither the database nor the shared layout. An unknown outcome keeps the request ID, so a retry replays.

The lesson and the Learning index link to sessions only when the flag is on. With the flag off, they make no practice queries. The JWT API under `/api/v1/learning/practice` uses the same service with explicit response fields. The preview fixture enables practice and can simulate failures before or after a save commits.

October 28 local validation: **371 backend tests run, 370 passed, one existing Linux-only test skipped on macOS**, with PostgreSQL 18.6 enabled. The 45 new tests cover:

- **Projections:** `opening_view` leakage and the shared vocabulary.
- **Service (SQLite with foreign keys on):** start/pinning/replay, unchanged saves, normalization, replay and request-ID reuse, stale and untouched artifacts, input limits, ownership, immutable history, hash-only receipts, cross-session citations, and hidden parameters.
- **Web (CSRF on):** the flag, sign-in, start and resume, save/history, replayed POSTs, two-tab conflict, untouched refresh, CSRF and validation re-renders, newline round trips, and the rescue page with every further SQL statement refused, both unknown-outcome and definite errors. Also cross-account 404.
- **API:** exact response fields, replay/unchanged/conflict/receipt, invalid input and 413, cross-account 404, and the website plus API acting as two devices.
- **PostgreSQL:**
  - Same-base and replay races, process death, and resume from a fresh process.
  - Composite-key rejection, log-safe failure summaries, and NUL handling.
  - The existing Alembic test now seeds practice rows before downgrade/upgrade, checks the catalog survives the practice downgrade, and verifies the migrated CHECK constraints by name and value.

Root Node checks passed (13 tests plus dependency integrity). Browser checks passed: 23 legacy flashcard, nine extraction, 27 concept, and 11 practice checks. Sass compiled.

The disposable fixture walkthrough covered:

- starting from the lesson and saving;
- a two-tab conflict (focused error summary, both texts kept);
- a simulated database failure (rescue page, a retry that saved without a duplicate, a log line without learner text);
- the 390-pixel layout.

Not covered: a screen-reader audit; if the database is down before sign-in, the site's error page appears instead of the rescue page; 3b behaviour; anything involving AI. Nothing was pushed, deployed, migrated in production, or published.

## Checkpoint 3b implementation and verification

No migration: 3b uses the tables from 3a. `practice_service` adds:

- **`save_work`:** an all-or-nothing save of artifact edits and/or the learner's brief.
  - A brief edit stores a full snapshot (`kind='brief'`) with the next revision number. It follows the artifact rule: unchanged, next revision, untouched (keep the newer brief), or conflict.
  - Saving resumes a paused session; the website's **Save and pause** saves first, then pauses.
- **`save_and_send`:** the website's Send. One transaction saves every artifact and the brief, then appends the learner turn. The turn cites the current revision of every artifact and records the brief revision.
  - A turn needs an up-to-date view. A conflict, an untouched artifact or brief that changed elsewhere, or a newer turn refuses the whole request.
  - Freshness compares against the latest turn, so brief snapshots never cause false conflicts.
- **`send_turn`:** the API's Send, citing already-saved revisions; each must be current.
- **`set_status`:** pause and resume, with receipts.
- **`delete_session`:** takes the owner lock and deletes the session row; database cascades remove revisions, messages, citations, and receipts. A repeat finds nothing (404). It refuses to run on a SQLite connection without foreign-key enforcement, which would otherwise keep every row.

Limits: 8 KiB per turn; 50 brief entries of 2 KiB each; up to ten sources per entry, each an existing turn or artifact revision of the session. `StaleViewError` replaces `StaleArtifactError` and carries every stale part, with codes `stale_artifact`, `stale_brief`, `stale_transcript`, and (website Send only) `out_of_date`.

The workspace is still one form, now with the brief editor and a message box:

- **Send**, **Save work**, and **Save and pause** (or **Resume**) all submit everything, so no button discards other work. A hidden first button makes Enter in a field save, never send.
- Saving with a typed message re-renders (200) with the message kept, flagging anything that changed elsewhere while it was written; other saves redirect.
- **409** re-renders show the newer work beside yours: conflicting artifacts and brief side by side, untouched parts refreshed, new turns labelled. Your edits and message stay in place.
- The rescue page now holds the message and brief entries too, and retries the same action with the same request ID.
- A confirmation page explains that deletion has no undo and that backups are separate, then returns to the lesson.

The API adds `PUT …/brief`, `POST …/turns`, `POST …/pause`, `POST …/resume`, and `DELETE /sessions/<id>`. The preview fixture turns on SQLite foreign keys, simulates failures for sends as well as saves, and counts turns and brief revisions.

October 29 local validation: **410 backend tests run, 409 passed, one existing Linux-only test skipped on macOS**, with PostgreSQL 18.6 enabled. The 39 new tests cover:

- **Service (SQLite with foreign keys on, 14):** citations, API turns and each stale code, freshness ignoring brief records, out-of-date sends, required message and artifacts, replays, brief snapshots and conflicts, brief validation, pause/resume, delete removing everything and nothing else, the foreign-key guard, ownership, and hash-only receipts.
- **Web (13):** Send with citations, the kept draft and work that changed while it was written, out-of-date and new-turn re-renders, a resent page based on the saved work it matches, brief add/edit/pin/remove, brief conflicts and refresh, message and brief errors, pause/resume, delete with confirmation and replay, cross-account refusal, and the rescue page for a send that failed before or after committing.
- **API (5):** brief, turns, pause/resume/delete, retry advice in each 503, and cross-account 404.
- **Content schema (1):** an exercise expects at most 20 artifacts.
- **PostgreSQL (6):** Send against a save, two Sends, brief lookup by revision on the `json` type, a fresh process resuming a paused session, delete cascades, and delete during a save. Repeated runs saw both orders of each race, with no orphan rows: in 15 runs the Send committed first 7 times and the save 8 times; in 20 runs the delete committed first 5 times and the save 15 times.

An independent review of the diff found no high-severity problems and three real ones, each now fixed with a regression test that fails without the fix:

- **Medium:** after **Save work** with a typed message, the page moved to the latest state silently, so a message written against an older view could then be sent without the learner seeing what changed. The page now flags new turns and updated parts first, as an out-of-date Send does.
- **Low:** after a lost response, a re-render could keep an old base for work that already matched the learner's own saved revision, so a later edit conflicted with their own work. Re-renders now base such parts on the saved head.
- **Low:** an exercise with more than 20 artifacts would publish but crash the workspace. The content schema now caps it at 20, the same shared limit the form and service use.

The API's 503 messages also no longer tell GET and DELETE callers to reuse a request ID.

Two test-fixture fixes came with these tests. The form parser now submits only ticked checkboxes and normalizes textarea line breaks as browsers do. The web suites' `login()` also clears the CSRF token cached on the shared app context. 3a's cross-account save test had been refused for that stale token rather than for ownership; it now reaches the ownership check.

Root Node checks passed (13 tests plus dependency integrity). Browser checks passed: 23 legacy flashcard, nine extraction, 27 concept, and 19 practice checks. Sass compiled.

The disposable fixture walkthrough covered:

- sending with an artifact edit, then the transcript's revision link;
- a send from a stale tab (focused alert, the other tab's turn marked New, draft kept), then sending again;
- **Save and pause**, signing out, the API reading the paused session intact and resuming it, then signing back in;
- a send whose result was lost after commit (rescue page with message and brief, one turn after the retry, a log line with only the error class);
- keyboard order (message box, then Send, then the brief) and Enter on a Pin box saving rather than sending;
- the 390-pixel layout;
- delete, ending with zero rows, receipts included.

Not covered: a screen-reader audit; Firefox and Safari (the walkthrough used Chromium, where Enter on a Pin box submitted the form and the hidden Save button kept the message unsent); AI. A tab open on a session deleted elsewhere gets "not found" on its next save. Sources on brief entries can be added through the API only (the website shows and preserves them). There is no brief history page. Nothing was pushed, deployed, migrated in production, or published.

## Decisions for checkpoints 4 and 5 (October 29)

Keith decided the open questions before checkpoint 4; the handoff's decisions table records the reasons.

- **Worker:** a thread in the web process, using the PostgreSQL job table and leases. Moving it to a `worker:` dyno later is a one-line Procfile change.
- **Provider:** OpenAI, as approved, through Learning's own project and key rather than JobWizard's. The model is chosen during the reviewed live evaluations.
- **Interviewer behaviour:** versioned in code, pinned when a session starts and recorded on every AI request; no content change.
- **Compaction:** deferred out of Milestone 1. Sessions send the whole transcript within a larger configurable allowance and stop with a specific explanation when essential context cannot fit. The long-session acceptance test keeps more than 24 turns, a restart, a revised assumption, and multiple artifact revisions, without forced compactions.
- **Misconceptions:** content schema 2 and exercise version 2 at the start of checkpoint 5, before the human content review. Accepted findings offer their linked questions as an extra, labelled review.
- **Deterministic checks:** JSON/YAML parse errors in API definitions are reported as confirmed findings before AI judgment.

The other three vision-review proposals (milestone order, progress model, richer lesson schema) wait for Milestone 1's completion.

## Checkpoint 4 plan (October 29)

Keith approved the checkpoint 4 plan the same day, choosing:

- three parts: 4a (durable replies against a scripted fake provider), 4b (the interviewer), then activation;
- revealed requirements as a separate read-only list beside the scenario, not entries in the learner's brief;
- no model "interpretation" entries, deferred along with compaction;
- **Continue with recent messages** when a transcript outgrows the context allowance.

Choices in the plan approved with it:

- Pause stops pending replies and a running reply's next paid call. A call already in flight finishes, and its reply is kept.
- Send is refused while a reply is live (409 `reply_pending`, draft kept); saving continues.
- Retries are never automatic: after an interruption the learner asks again.
- `POST …/turns` returns 202 when a reply is queued and 201 otherwise.

## Checkpoint 4a implementation and verification

Migration `e8f9a0b1c2d3` adds:

- `ai_request`: one row per reply attempt, with its status, a content-free error code, claim token and lease, the pinned profile version and models, and the turn it answers. Partial unique indexes allow one live (pending or running) request per session and one completed reply per turn.
- `learning_ai_charge`: the content-free spending ledger in micro-dollars. It has no foreign key to sessions or requests, so it outlives delete.
- `practice_session.profile_version` (existing rows get `interviewer-1`) and the `reply` receipt operation.

The service (`practice_service`, `practice_budget`, `practice_worker`):

- **Send** queues a reply in the same transaction when AI is available: the switch is on, the learner is the one verified account named by `LEARNING_AI_OWNER_EMAIL`, the models are priced, and the reply's worst case fits this month's budget. Otherwise the turn is saved with a reason (`disabled`, `owner_only`, or `budget`).
- A live reply refuses another Send. A stale one reads as interrupted everywhere: pending for more than two minutes or once AI is unavailable, or running past its lease. The next Send, Ask, or pause records it; delete removes it with the session.
- **request_reply** asks again for the latest unanswered turn: a retry, or a turn saved while AI was unavailable. On the website it also saves the page's work. If a reply reached the turn meanwhile, it still saves and reports `answered`.
- **The worker** sweeps stale rows and claims the oldest fresh request by compare-and-swap, skipping profiles it doesn't know. Before each paid call it checks that the request is still running with its token and an unexpired lease, the session is active, and AI is available. It then extends the lease and reserves the worst case under a budget lock.
- After the call, the charge is settled from usage (or at the reservation, without usage), released after a definite refusal, or left reserved when the outcome is unknown. Replies are written under the owner lock and cite the turn's revisions. A database error retries the write, never the call.
- Lock order: owner (`FOR NO KEY UPDATE`), request, session, budget, charge.
- The thread starts only from `run.py`; `flask learning-worker` runs the same loop in the foreground. `FakeProvider` modes: `success`, `slow`, `fail`, `lost`, `hang`, and `invalid`.

The website adds a reply-status region under the conversation: replying; failed or interrupted, with **Retry the reply**; cancelled by pause; not available for this account; or no room in the budget. **Ask for a reply** covers a turn saved without one. Both are workspace-form actions that also save. A script polls `…/reply?after=<sequence>`, inserts newer turns marked New, and updates `expected_sequence`. It retries a dropped connection or server error with growing waits, and stops on sign-out, a 4xx, or six failures in a row, then brings Send back with a note to reload. Without JavaScript, **Check for the reply** saves and reloads. Send is disabled while a reply is live. The owner sees a spending banner from the warning line, or once the month is used up.

The API's `POST …/turns` returns 202 with a pending reply, otherwise 201, plus `reply` and `latest_sequence`. It adds `GET …/sessions/<id>/reply?after=` and `POST …/sessions/<id>/reply` (`{request_id}`; 202 when a reply is queued, 200 with `answered` or `unavailable` otherwise), and 409 `reply_pending`. The session detail adds `reply` and `ai_budget` (the owner's only).

The preview fixture runs the worker with the fake provider and makes `learning1@example.test` the owner. `/fixture/state` accepts `ai` (a fake mode) and `cap_usd`; `/fixture/results` adds reply counts and the month's spend.

October 29 local validation: **454 backend tests run, 453 passed, one existing Linux-only test skipped on macOS**, with PostgreSQL 18.6. The 44 new tests cover:

- **Service and worker (SQLite with foreign keys on, 19):** who gets a reply (switch, provider, priced model, and an owner email matching exactly one verified account in any case); inputs pinned to the turn, including edits made during a reply; hidden material kept out of requests; stale replies never blocking Send; pause cancelling a pending reply and fencing the next call; delete fencing a late reply while the ledger keeps its cost; each failure's status and charge; the budget rule; an expired lease; asking again; unknown profiles; reply text limits; the read-order race; no learner text in requests, ledger, receipts, or logs; the worker's start conditions; and the real thread on file SQLite, including a restart while a call is stuck.
- **PostgreSQL (11):** two releases claiming at once; reservations racing at the cap; completion against delete, pause, and the sweep, each with either side first and racing; the worker's call check held at two points while a delete, a pause, or a stale Send arrives; `kill -9` mid-call and before storing, each recovered by an explicit retry with the ledger right; a fresh process picking up a reply queued before a restart.
- **Web (10) and API (3):** every reply state and its message; polling (`after`, ownership, `no-store`, and the last poll reporting the newest turn); Retry and Ask saving the page, including after the reply already arrived; 409 with the draft kept; the spending banner and the non-owner note; and a `<script>` reply shown as text. On the API, also strict `after` and replaying a send recorded before 4a.
- **Telemetry (1):** reply reports carry fixed codes only.

The migration test also downgrades through `e8f9a0b1c2d3` and checks its CHECK constraints and partial-index predicates. Commit `81312c8` passed on its own in a clean checkout (441 tests).

Repeated natural races never let a completion beat a delete or the sweep, so each pair runs with either side forced first and once racing. The call-check tests hold the worker at a lock with a SQLAlchemy engine event, because natural races almost never land there.

An independent review of the service found four problems. Each is fixed with a regression test that was confirmed to fail without its fix:

- **Medium-high:** a PostgreSQL deadlock. The call check inserts a ledger charge while holding the request row, and that insert's foreign-key check takes `FOR KEY SHARE` on the user row, which the `FOR UPDATE` owner lock blocked. A delete or a stale Send arriving then deadlocked. The owner lock is now `FOR NO KEY UPDATE`, and owner-side writes, delete included, lock the live request row before changing anything else.
- **Medium-low:** a pause, or a Send that found an expired lease, could slip in during the call check. A paid call could then start after a pause had committed, or a reply about to be paid for was marked interrupted and a second one queued. The check now requires an unexpired lease and share-locks the session, and owner-side writes wait for it.
- **Medium-low:** the budget could never read as used up, because reservations never take spending past the cap. Near the cap, every Send queued a reply that then failed, and Retry was offered forever. Now a reply is queued and offered only when its worst case fits, priced from the request body the worker will send. The month reads as used up once even the smallest reply can't fit.
- **Low:** PostgreSQL returned the month's spend as a decimal, which reached the API's JSON as a string.

Two smaller fixes came with them. A worker restarted while its thread was stuck in a call could start a second thread. The spending banner now also appears when the month is used up before the warning line.

The walkthrough found one more bug, also fixed with a regression test. After **Retry the reply**, a reply landing between the page's two reads showed neither the reply nor "replying". The page now reads the reply's state before the transcript.

A second independent review, of the website and API, found eight problems and three documentation errors, all fixed. Each code fix has a regression test that was confirmed to fail without it:

- **Medium:** polling gave up on the first failure, so after a restart the page kept saying "replying" with Send disabled until a reload. It now retries dropped connections and server errors with growing waits, and when it does stop, it brings Send back with a note to reload.
- **Low-medium:** the last poll could say "The interviewer replied." over a newer turn's failed reply, hiding its Retry, and a reply landing between two reads was never announced. "Replied" now means the latest learner turn has its reply.
- **Low-medium:** Retry on a turn whose reply had just arrived (from another tab, or late) failed with a 400, didn't save the page's work, and left the page out of date. It now saves and says the interviewer has already replied.
- **Low:** every poll rewrote the status region, so screen readers could repeat "replying" every few seconds; an out-of-range `after` returned an error page on the website, and the API read `after=abc` as 0; replaying a Send recorded before 4a crashed the API; and Ask with a typed message lost "Asked the interviewer for a reply." when newer work had arrived.

The preview fixture also removes its temporary database when stopped with SIGTERM, as preview tools do; earlier runs had left nine behind.

Root Node checks passed (13 tests plus dependency integrity). Browser checks passed: 23 legacy flashcard, nine extraction, 27 concept, and 42 practice checks (23 new, for polling). Sass compiled.

The disposable fixture walkthrough covered:

- a reply arriving while the page polls: Send disabled meanwhile, the reply marked New, and `expected_sequence` advanced without a reload;
- `fail`, then **Retry the reply**; `hang` (about ten seconds of "replying", then "didn't answer in time"); `lost` (its reservation kept in the month's spend);
- the budget: the spending banner, "used up", a Send saved with "no room for another reply", and **Ask for a reply** once the cap was raised;
- `learning2@example.test`: messages saved, "AI replies aren't available for this account", no spending shown;
- saving an artifact while a reply ran: the reply cites revision 1, and the editor keeps revision 2;
- a second tab sending while a reply was live: 409 with its draft kept, then the reply appearing in that tab;
- pausing mid-reply (the call already running finished and its reply was kept) and deleting mid-reply (the session gone, the call's cost still in the spend);
- the 390-pixel layout;
- server logs with only codes such as `provider` and `timeout`.

Not covered: a screen-reader audit; Firefox and Safari; any real provider call; the interviewer's behaviour (4b). Nothing was pushed, deployed, migrated in production, or published.

## Checkpoint 4b implementation and verification

No migration: `session_message` already allowed `context` and `assistance` records and the `system` role. The interviewer (`project/learning/interviewer.py`, profile `interviewer-1`) makes up to two calls per reply:

- **The selector** sees only the learner's latest message and the clarification cues of the requirements still hidden (`selector_view`). Its strict schema offers only those IDs, and `hint_requested` only while permitted hints remain; with neither, the call is skipped. The server checks its answer again. If it fails or answers badly, the reply fails: its cost settles, nothing is revealed, and asking again reruns both calls.
- **The reply** sees the rules and the exercise's authored instructions, the scenario, the facts revealed before the turn and those just revealed (marked as new), the learner's brief at the turn's revision, the cited artifacts, the transcript, and the next permitted hint only when the learner asked for one. The input puts what stays fixed first, then the append-only transcript, then what changes, for prompt caching. It notes any omitted earlier messages.
- **Records:** the reply, then an interviewer `context` record (the IDs it revealed) and an `assistance` record (the hint index), all in one transaction. What counts as revealed, and which hint comes next, is read from the records before the turn, so retries and late replies can't shift it.

The context allowance (`LEARNING_AI_CONTEXT_BYTES`, a placeholder of 512 KiB until activation) bounds what a reply may read, measured in UTF-8 bytes of its instructions and input. It is checked when a reply would be queued or offered, using the worst case (every hidden fact revealed and a hint given), and again on the actual request before the reply's paid call.

- When the conversation doesn't fit, **Continue with recent messages** records a learner `context` entry. Replies then read from the earliest message that still fits, found by binary search. Nothing is deleted, later replies keep reading from there, and the transcript marks the spot.
- When even the latest message with the brief and artifacts doesn't fit, the reply stops and names the largest part to shorten.

The budget check prices the selector and reply worst cases together.

The OpenAI call runs in a child process: `project/learning_ai_call.py`, run with `python -I`, imports only the standard library and `requests`. `project/services/learning_ai_provider.py` gives it an environment of the key, `PATH`, CA settings, and the trusted interpreter library directory on Linux, and discards its stderr. The Linux path is derived from `sys.base_prefix`, never inherited from arbitrary parent loader settings. The child:

- reads one size-capped request on stdin;
- guards against an orphaned start, with a hard alarm deadline;
- refuses plain HTTP except to `127.0.0.1` or `localhost`, and never follows redirects;
- caps the response size;
- reports usage on every path that read a reply (refusals, cut-off replies, and invalid output included).

Codes map to what the ledger records: 400, 401, 402, 403, 404, and 429 release the reservation; refusals and invalid output settle it from usage; timeouts, 5xx, and connection failures keep it. `provider_for` returns this provider only when `LEARNING_OPENAI_API_KEY` is set, and models stay unpriced until activation, so AI stays off with OpenAI configured. Starting the process took about 66 ms per call locally.

The website shows **Revealed requirements** beside the scenario, each with a link to the reply that revealed it, updated while polling. Turns that gave a hint are labelled **Hint**. A notice appears after 24 learner turns (`LEARNING_AI_CHECK_IN_TURNS`), offering to keep going or pause; it never stops the conversation. **Continue with recent messages** is a workspace action, and a learner whose essentials are too large is told which part to shorten. The API adds `revealed_requirements`, `context_choices`, `learner_turns`, and `check_in_due` to the session detail, `hint` to each turn, and `context: "recent"` to `POST …/reply`.

The evaluation harness (`project/learning/interviewer_eval.py`, `flask learning-eval`) runs 13 reviewed cases from `tests/fixtures/interviewer/cases.json` through the real request builders:

- a paraphrase for each hidden requirement, and two requirements asked at once;
- an unrelated question, an already revealed requirement, "just tell me the answer", and a hint request;
- prompt injection in a message and in an artifact;
- a valid alternative design, and an artifact discrepancy.

Every expectation comes from the case itself, never from the builders being checked. The nine checks:

- the selector is offered exactly the requirements still hidden, sees nothing but their cues, answers validly, and answers as expected;
- the reply request carries only what may be revealed, and everything that was earned (earlier facts, new facts, and a requested hint);
- the reply is valid and repeats no unrevealed fact (five-word runs, or numbers however they're written) and no reference reasoning (eight-word runs).

Against the fake, which answers as each case expects, all 13 cases pass all nine checks; this tests the plumbing and the request checks. Live runs at activation test the model and write `docs/evaluations/learning-interviewer-<date>.json`.

October 29 local validation: **503 backend tests run, 502 passed, one existing Linux-only test skipped on macOS**, with PostgreSQL 18.6. The 49 new tests cover:

- **The interviewer (19):**
  - disclosure: a clarifying question revealing its requirement once; unrelated questions and "just tell me the answer" revealing nothing; hints only when asked, each once; the selector skipped once nothing is left; a failing or badly answering selector failing the reply and revealing nothing;
  - privacy: what each call carries (sentinels for hidden facts, hints, instructions, and evaluator content, and prompt injection kept out of `instructions`), and the input's order;
  - the allowance: Continue with recent messages; work too large to read, naming the part, then shortening and sending again; a message too long to read; no choice recorded when the interviewer can't reply; an unknown profile; a reply that outgrows the allowance before its paid call;
  - the check-in and the long-session recovery case;
  - a reply through the real child process against a local stand-in for the Responses API, and the request builders without a database.
- **The call process (17):** every status, refusal, timeout, and size limit; usage on every path; no redirects; plain HTTP only to localhost; the minimal environment; stderr discarded; and text beyond ASCII intact.
- **The harness (8):** the cases are well formed, all pass against the fake, and each check fails when what it checks is broken.
- **Web (4) and API (1):** revealed requirements and hints, Continue with recent messages from the page, work too large to read, the check-in, and the same over the API.

Existing tests changed with the design: each reply now makes two calls and two charges, the PostgreSQL process-death test's stand-in answers the selector, and the API and service key sets grew. The long-session case covers 26 learner turns, a worker that dies mid-reply, a revised assumption, and six artifact revisions, then the budget and size limits, keeping every turn, revision, and brief snapshot.

My own tests caught the harness taking "what may be revealed" from the builder it was checking, and that is fixed. Two independent reviews followed; the first service review was cut off by a network error and rerun. Each fix below has a test confirmed to fail without it.

- **Website and API, medium:** when the learner's own work was too large to read, the page said to shorten it and ask again. Asking again couldn't help, because a reply reads the work its message was sent with, and no button appeared. The page now says to shorten, save, and send a new message, and names the part; the API names it with the artifact ID. A message that is too long gets its own wording.
- **Website and API, low:** Continue with recent messages crashed for a session pinned to a profile this release doesn't know; it now falls back to a normal request. The fixture can now simulate failures for Ask, Retry, and Continue. A tab already waiting for a reply shows another tab's Continue marker only after reloading (documented).
- **Service:** no correctness or privacy problems in disclosure, pinning, the worst-case bounds, the budget, locking, or the call process.
- **Service, medium:** nothing checked that a reply received what the learner earned, so a disclosure regression could pass the harness. It is now checked.
- **Service, low:**
  - The harness's leak checks searched escaped JSON, missing text with quotes or line breaks.
  - It trusted `selector_view` for what was offered.
  - It accepted a mistyped `--case`, and missed "2000" written without a comma.
  - Continue with recent messages recorded a choice before checking AI was available.
  - A bad `context` was reported as an artifact error.
  - The child's input cap had little headroom; it now has more, and the request travels as UTF-8.
  - A reply the schema allows could exceed the storage limit; any such reply now fits.

Root Node checks passed (13 tests plus dependency integrity). Browser checks passed: 23 legacy flashcard, nine extraction, 27 concept, and 43 practice checks (one new, for the revealed list). Sass compiled.

The disposable fixture walkthrough covered:

- "Who owns the key?" revealing the scope requirement, with the list filling while polling and linking to its reply;
- a hint request labelled **Hint**, and an unrelated question revealing nothing;
- three long messages and a lowered allowance, then **Continue with recent messages**: its marker placed before the first message the interviewer reads, earlier messages kept, and the reply arriving;
- work too large to read, with the new wording;
- the 390-pixel layout.

Not covered: the live model (activation); the check-in in the browser (tests only); a screen-reader audit; Firefox and Safari. Nothing was pushed, deployed, migrated in production, or published.

## Activation (October 29 and 30)

Keith created Learning's OpenAI project and key and set a $50 hard limit on the project. The key lives only in the local `.env` and reaches the call process at call time.

Three rounds of live evaluations, each case three times at low reasoning, cost about $1.73 in all. The handoff's Recommended next checkpoint has the full results, and `docs/evaluations/` holds every reply.

1. **`interviewer-1`, Sol and Terra (October 29).** Every privacy and disclosure check passed, but both models called hidden requirements "unspecified", as that profile's rules told them to.
2. **`interviewer-2`, Sol, Terra, and Astra (October 29).** The revised rules fixed that. Every check passed in all 39 turns for each model. Terra misread a revealed fact in all three runs.
3. **Catching flaws, Sol and Astra (October 30).** Ten scratch cases: nine designs or arguments with one planted flaw each, three of them after earlier turns, and a sound control. A separate grader scored the 60 replies blind. Both models caught all 27 flaws, and neither agreed with a flaw, gave away a fix, or invented one. Their replies were nearly identical; Astra costs five times as much.

Keith chose `gpt-6.1-sol` at low reasoning (October 30). It is now the `openai` provider's default for both calls (`practice_service.DEFAULT_MODELS`), and configuration overrides it.

What changed for activation:

- `interviewer-2` is released and is the profile for new sessions; a test pins each released profile's text by hash.
- Cache writes are priced: `PRICES` has a `cache_write` rate, `cost()` bills cached reads and writes separately, and the worst case prices every input byte as a write.
- Migration `f9a0b1c2d3e4` adds `learning_ai_charge.cache_write_tokens`, so each charge's tokens explain its cost.
- `flask learning-eval --provider openai` refuses to start without `LEARNING_OPENAI_API_KEY`, since a model is always configured now.
- The defaults for deadlines, output caps, and the context allowance were checked against 216 live Sol calls and kept.

Verification: the full suite passed with PostgreSQL (515 tests, one skipped), including the migration round trip and the comparison of the migrated schema with the models. One live session ran through the app on a disposable database: three turns through Send, the worker, the call process, and the ledger, with Sol as the default, for $0.013. No front-end code changed, so the Node and browser suites weren't rerun. Nothing was pushed, deployed, migrated in production, or published.

## Workspace checkpoint: tabs and conversation continuity (November 1)

Keith approved this UI checkpoint after reviewing the practice workspace. It keeps Milestone 1 on web and does not start feedback, Expo, or content expansion.

The practice page now has **Learn / Review / Discuss / Build** navigation. Learn and Review open the existing lesson and review pages. Discuss and Build share one session and one native form: both panes remain visible on desktop, with more room for the selected activity; small screens show the selected pane. **Brief / API / Schema / Pseudocode / Notes** tabs expose one work area at a time. Instructions and session details use disclosure controls, and new note fields appear on demand. The compact header applies only to practice.

The implementation deliberately keeps native POST/redirect behavior instead of adding a second write protocol. Hidden panels retain their enabled form controls, so Save, Send, Pause, and reply recovery actions still submit every artifact and note with the existing CSRF token, request UUID, expected sequence, and revisions. The server's conflict and standalone rescue pages remain authoritative. There are no service, API, schema, migration, review-scheduling, or AI-prompt changes.

The UI restores the selected work tab, transcript position, and editing focus after native navigation. Send returns focus to the composer and the latest exchange. Save restores the editor's selection, identifying notes by their stable entry ID when removing another entry changes their form indices. Incoming replies preserve an unsent message and do not pull a reader away from earlier turns; a New messages button offers a jump, and mobile Build shows a new-reply indicator on Discuss. Error-summary links reveal the relevant hidden panel. Byte-limit warnings, leave-page protection, and all existing recovery controls remain available.

Browser storage contains only view/scroll preferences and temporary focus/caret metadata. It never contains learner text, session content, server revisions, or tokens. This is not draft autosave: unsaved text still needs Save or Send before leaving. If storage is blocked, tabs still work and the URL carries the view. Without JavaScript, all work fields remain visible and native saving works.

Implementation is in `practice.html` and its five extracted partials, `learning-workspace.js`, scoped `learning-workspace.scss`, and small event/save-indicator additions in `learning-practice.js`. `base.html` only adds an overridable container-class block. Generated CSS is committed. No new runtime or test dependency was added.

Verification:

- **516 backend tests run, 515 passed, one existing Linux-only test skipped on macOS**, using an isolated PostgreSQL **18.6** cluster. This includes migration, concurrency, budget, and recovery coverage.
- **41 focused web/browser tests passed after the final UI refinements**, including **97 integrated browser assertions**. The new `tests/test_practice_browser.py` serves actual Flask pages with CSRF and a deterministic fake interviewer; Chrome drives native submissions, redirects, and polling. It exercises hidden-field saves, keyboard tabs, focus/selection and scroll continuity, note reindexing, Pause/Resume, stale conflicts from another tab, lost-response receipt replay, failed writes, mobile 390/320-pixel layouts, blocked storage, and no-JavaScript saves. It also checks that reference/evaluation sentinels and analytics are absent from the page. It runs in normal backend unittest discovery; Chrome is required in CI.
- Existing root checks: **13 Node tests**, dependency integrity, and **102 browser checks** passed; Sass compiled. The full PostgreSQL run preceded the final UI-only refinements; the focused suite was rerun afterward.
- The disposable fixture was inspected on desktop and at 390 pixels. The final pass fixed a clipped Send control and focus restoration when a note's form index changes. Safari, Firefox, and a screen-reader audit remain outstanding.

For the new targeted check:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
  poetry run python -m unittest tests.test_practice_browser
```

The [hands-on workspace guide](learning-workspace-test-guide.md) walks through Elements, Console, Network, HTTPie failure simulation, and a short Performance recording. Use the disposable fake-provider fixture; it does not load paid AI credentials or write to real progress. Nothing was pushed, deployed, or migrated in production.


## Learning home checkpoint (November 2)

The approved preview is now implemented for the Learning home and library
navigation. Engineering learning has the primary card and one Continue practice
link to the user's newest active or paused session. Without an open session, the
card links to the published lesson. A pinned session stays reachable even if its
concept is unpublished; opening it never starts or resumes a session implicitly.
Practice queries still remain entirely disabled when the feature flag is off.

Reference articles and My flashcards have smaller links to dedicated pages:
At this checkpoint, `/learning/references` was public and `/learning/flashcards`
required sign-in; the later login checkpoint below protects both.
The latter uses a native GET search by title, reloadable pagination, and 25 notes
per page. Its due count and Start review always cover the full personal review
queue. Home no longer reads or summarizes all note files. The new compact shell
also wraps the existing article, note, and personal-review pages; Back/Done links
lead to their respective catalogs. The original URLs and article content remain
available. The idempotency Learn and Review layouts were reserved for the shared
workspace checkpoint below.

This is a presentation/read-path change: no model, migration, service/API
contract, scheduler, practice write, budget, context, prompt, or recovery logic
changed. There is no new runtime JavaScript or infrastructure. Existing owner
checks, CSRF/revisions/receipts, analytics exclusion, and private cache headers
remain in force. Reference/evaluation-only material never enters the new pages.
The repository remains public as previously acknowledged.

Automated coverage adds 12 tests, including a 56-assertion Chrome walkthrough of
real Flask pages. It checks saved-session/tab continuity, public/private
navigation, the legacy rating endpoint and receipt, scheduling after reload,
search and pagination, hostile/long titles, 390/320-pixel layouts, keyboard skip
focus, and navigation with scripts blocked. The review queue's existing
randomness is seeded in the browser fixture. The separate 97-assertion practice
browser regression still covers save conflicts, unconfirmed writes, replay,
failed sends, polling, and recovery. Two old assertions were updated for the
moved destinations and one for the new status layout; their security and
pause/resume expectations remain covered.

For DevTools, HTTPie, and REPL exercises, use the
[Learning home guide](learning-home-test-guide.md). The dedicated flashcard page
still reads all legacy notes to calculate due counts; pagination bounds rendering,
not the underlying filesystem scan. That existing service remains sufficient
for this pilot. Chrome and the in-app browser were inspected; Firefox, Safari,
and a screen-reader audit are not yet covered.

Final verification: **528 backend tests run, 527 passed, one existing Linux-only
JobWizard test skipped on macOS**, with the isolated PostgreSQL **18.6** cluster.
This includes the migrations/schema comparison, concurrency, budget, recovery,
and both integrated browser regressions. The first full run found an old
punctuation-dependent paused-status assertion; after updating it to assert the
status and session link, the entire suite passed. The existing **13 Node tests**,
dependency integrity check, and **102 browser renderer checks** passed; Sass
compiled with its existing deprecation warnings. No production migration or
paid AI call was needed. Nothing was pushed or deployed.


## Learning login boundary (November 2)

At Keith's request, every route in the Learning website now requires an existing
login, including home, the reference catalog, and the long-form article. The
blueprint checks authentication before route/feature logic, so future Learning
pages inherit the same rule. Login retains the requested destination. Every
Learning response, including a sign-in redirect, uses `private, no-store`.
The portfolio's Learning navigation link is also shown only after sign-in.
The separate JSON APIs retain their existing JWT authentication. Static assets
and the public source repository are unchanged; this is application access
control, not repository confidentiality.

Verification: 63 focused route/API tests passed, including a test that enumerates
every registered Learning route and rejects unauthenticated reads and writes.
The real-browser hub regression passed all 60 checks, including signed-out
redirects for home, references, flashcards, and the article. No schema, scheduler,
AI, budget, or recovery operation changed. This is a separate commit before the
shared concept-workspace checkpoint.

Navigation follow-up: moved Learning into the existing signed-in portfolio
navigation group. All five Learning web tests pass, including authenticated and
anonymous header checks and the existing route-wide login checks.


## Shared concept workspace (November 2)

Learn, Review, Discuss, and Build now share the same compact concept heading and
mode navigation. The lesson shows one section at a time, with section links on
desktop and a native picker on mobile. The existing retry simulation sits inside
the retry explanation and retains its state when sections change. Supporting
goals, prerequisites, references, and session options use disclosure controls.
Without JavaScript, the whole lesson remains readable. Review presents one
question, the existing explicit answer reveal, and the existing rating/retry
flow. Its completion screen leads back to the same conversation.

`practice_session` carries the selected session through Learn/Review links,
hidden reveal/rating fields, remediation, and completion. An explicit UUID must
be owned and match the concept; otherwise the server returns 404. Without one,
navigation selects the newest open session for the concept's exercises. A new
read-only `session_summary` projection avoids loading the transcript/artifacts.
The practice renderer builds navigation from its existing data, keeping extra
reads out of recovery paths. A first-time Discuss/Build click opens a start page;
the existing CSRF-protected POST alone creates a session. Opening a paused
session leaves it paused. Disabling practice still disables all practice queries.

Saving remains explicit. Discuss/Build keep their shared native form and unsaved
text warning; leaving for Learn/Review requires Save or Send to preserve edits.
No new storage model, dependency, infrastructure, migration, write protocol,
review scheduler, AI prompt, budget, or context behavior was introduced. Hidden
constraints and evaluator/reference material remain outside learner responses
and bundles; the repository remains public.

Verification:

- **538 backend tests run, 537 passed, one existing Linux-only JobWizard test
  skipped on macOS**, with isolated PostgreSQL **18.6**, including migration/schema,
  concurrency, budget, and recovery coverage.
- Eight new route tests cover exact older-session selection, ownership, read-only
  navigation, CSRF/start replay, stale/failed review recovery, rating receipts, and
  feature-off behavior. A new **70-check browser walkthrough** follows saved work
  and a conversation through all four modes, all four reviews, remediation,
  completion, mobile 390/320-pixel layouts, and no-JavaScript reading.
- The **60-check hub** and **97-check practice** browser regressions passed,
  including conflicts, lost-response replay, failed sends, and composer geometry.
  Existing **13 Node tests**, dependency integrity, **102 renderer checks**, and
  Sass compilation passed. Desktop and 390-pixel screens were inspected manually.

The browser tests caught a clipped Send button caused by shared line-height/flex
rules; practice now retains its line height and a nonshrinking composer. The
fixture CSP was also being overwritten by Talisman's response hook: both browser
fixtures now apply their local-only policy last and assert it. GET form actions
discard their query string, so the selected session must be a hidden input during
answer reveal. These cases have regression coverage.

Use the [hands-on concept guide](learning-concept-workspace-test-guide.md) to
inspect links, requests, forms, and the navigation helper. Safari, Firefox, and
a screen-reader audit remain outstanding. Feedback/export and Milestone 2 have
not started. No paid AI call, push, deployment, or production migration occurred.


## Checkpoint 5a: feedback content foundation (November 2)

Keith approved the feedback foundation as a separate checkpoint. The new
`curriculum/idempotency/catalog-v2.json` contains the same concept, four questions,
and exercise, with four evaluator-only misconception mappings. Each connects a
mistaken reasoning pattern to an assessment dimension, evidence guidance, a
lesson section, existing review questions, and a suggested next step. The
guidance distinguishes demonstrated errors from missing evidence and valid
alternatives. The material remains a draft requiring human technical review.

Catalog/spec pairs 1/1 and 2/2 are validated explicitly. Version 2 requires
1–100 mappings and 1–100 unique review targets per mapping; unknown fields,
duplicate IDs, missing or wrong-kind references, invalid sections/dimensions,
and questions from the wrong remediation concept are rejected. The evaluator
projection selects the contract for the pinned spec. Other audience projections
remain unchanged and exclude all mappings.

The original catalog and Markdown are preserved. All six v2 item revisions
advance because the existing checksum includes the catalog schema version.
Their stable IDs and all prior lesson, question, brief, facilitator, and
assessment content remain unchanged. The importer, storage schema, scheduler,
practice writes, prompts, budgets, and recovery behavior need no changes. Drafts
do not replace published content; older sessions and review attempts stay pinned
after v2 publication. No content was published in the application database.

Sixteen new tests cover:

- Ten content-contract tests: strict versions/fields, bounds/duplicates,
  reference closure, valid remediation to another concept, immutable checksums,
  unchanged v1 content, projection copies/privacy, CLI validation without tables,
  and blocked source URLs.
- Three integration tests: old/new session rendering, existing JWT API saves,
  and both versions completing real worker flows with a scripted fake provider.
  Private sentinels are present in the evaluator snapshot but absent from HTML,
  learner DTOs, and selector/interviewer requests.
- Three PostgreSQL tests: dry run/drafts/publication/replay, unchanged saved
  sessions and review rows, a pinned old review finishing after publication,
  immutable mapping conflicts with full-batch rollback, and conflicting
  concurrent v2 publishers producing one consistent snapshot.

The 36-test focused suite passed on PostgreSQL 18.6, including the existing
migration round trip and schema comparison. The [5a REPL guide](learning-checkpoint-5a-test-guide.md)
provides hands-on inspection, reference failures, and debugger stepping.

Final verification: **554 backend tests run, 553 passed, one existing Linux-only
JobWizard test skipped on macOS**, with PostgreSQL **18.6**. The complete run
includes migration/schema, concurrency, budget, recovery, and the 70 concept,
60 hub, and 97 practice browser checks. Front-end files did not change; the
separate Node/renderer suite was not repeated. `git diff --check` passed.

The preview still uses v1; there is no new UI in this checkpoint. Submission
snapshots, deterministic artifact checks, generated feedback, learner acceptance,
targeted review, and export remain for subsequent checkpoints. No new dependency,
infrastructure, migration, paid AI call, push, or deployment was introduced.


## Checkpoint 5b: immutable snapshots and saved syntax checks (November 2)

Keith approved the lifecycle choice before implementation: **save a snapshot and
keep the session editable**. `Save and check` follows Save's resume behavior;
it does not finish or lock a session. This checkpoint stops at deterministic
checks; generated assessment, accepted findings, and targeted review remain later work.

Snapshots use the existing `SessionMessage(kind="submission")` and
`SessionMessageArtifact` tables. They pin the exercise/rubric version, spec and
profile versions, all-record boundary, latest conversation turn, notes revision,
and exact artifact revisions. Artifact bodies are not copied. Parser results
are stored with `syntax-1` and never recomputed during reads or retries. The only
migration, `a0b1c2d3e4f5`, extends the receipt operation constraint with `submit`.
Downgrade removes these receipts but preserves snapshots and all saved work.

JSON and YAML syntax checks use existing Python/PyYAML dependencies. The YAML
loader is safe and rejects aliases before construction. Checks bound bytes,
nesting, and YAML nodes. Unsupported/ambiguous syntax features (including
aliases, duplicate keys, unknown tags, and multi-document YAML) are labelled
**Not checked**; they are not engineering mistakes. Confirmed parse errors have
static messages and optional one-based locations. No code executes, raw parser
exceptions escape, provider call runs, or review progress changes.

**Build → Checks** adds native save/check, saved results, and earlier snapshot
links to the existing workspace. The snapshot detail shows exact artifact
revision links, notes, and conversation boundary; older work is labelled when a
newer artifact exists. Unsent conversation text survives checking. The JWT API
adds submission POST/detail GET and an additive `submissions` list on session
GET, using explicit learner-safe projections. Reference solutions remain
server-only in runtime responses, though the repository is public.

Recovery uses the existing owner lock, freshness checks, CSRF/JWT boundaries,
request hashes, receipt replay, and standalone rescue form. A check cannot race
past a pending reply or silently include edits from another tab. Snapshotting
works with AI disabled or its budget exhausted. Sessions and snapshot results
survive process restarts; owner deletion cascades through all snapshot records.

Verification:

- **32 new automated tests**: parser safety/resource limits; immutable evidence
  and results; both content versions and private sentinels; no budget charge;
  CSRF/ownership/strict input; stale work, lost responses, and retries; seven
  PostgreSQL concurrency/process tests. The existing populated migration test
  now also verifies submit receipt rollback and retained snapshot reads.
- **586 backend tests: 585 passed, one pre-existing Linux-only test skipped on
  macOS**, against disposable PostgreSQL **18.6**. Full migration/schema,
  scheduling, budget, and recovery coverage passed.
- Integrated Chrome: **70 concept + 60 hub + 119 practice assertions**. The 22
  new practice assertions cover checks without JavaScript, revision history,
  unsent messages, syntax locations, failed/lost confirmations, exact retry,
  and a 320px layout.
- Node **24.22.1**: **13 tests**, dependency asset verification, and **102 browser
  renderer/recovery assertions** passed. `git diff --check` passed.
- Visual inspection shortened the initial explanation so the first syntax
  finding is visible sooner. A separate disposable preview on **5058** preserves
  the existing **5057** demo. The fixture accepts `--port`, reloads templates,
  includes check failure simulation, and reports snapshot counts.

PostgreSQL exposed one recovery gotcha: `timestamptz` reads use the connection's
timezone, while the newly created receipt held UTC. Snapshot DTOs now normalize
timestamps to UTC so fresh-process reads match the original receipt exactly.

The [hands-on guide](learning-checkpoint-5b-test-guide.md) covers REPL/debugger,
DevTools, copied request replay, and recovery experiments. No paid calls, new
dependencies, production migration/publication, push, or deployment occurred.
Next, after approval: evidence-linked AI feedback on these snapshots. Expo and
content expansion remain outside scope.

## Checkpoint 5c: evidence-linked saved feedback (November 2)

Keith approved **one complete snapshot per bounded evaluation call**, with an
explicit oversized response instead of silent truncation or multiple passes.
The editable snapshot lifecycle from 5b remains. The historical revised plan
is preserved; this decision sequences multipass evaluation beyond 5c.

Implemented:

- Versioned `evaluator-1` instructions and a strict structured-output contract.
  Original conversation, selected/cited artifact revisions and saved notes are
  evaluated together; later edits and interviewer context truncation cannot alter
  the snapshot. Server-owned coverage and assistance records accompany findings.
- Strengths, evidenced concerns, trade-offs and missing-evidence findings, with
  next steps and authored remediation links. Exact source quotations, known
  dimensions, compatible misconception IDs, full dimension coverage and a direct
  private-copy backstop are validated before persistence. No ability scores,
  generated URLs, replacement artifacts or automatic review ratings.
- `PracticeFeedback` and migration `b1c2d3e4f5a6`, down from `a0b1c2d3e4f5`.
  Same-session request/snapshot FKs, one saved result per submission, and feedback
  receipts. A downgrade removes derived feedback/requests/receipts while retaining
  work and billing metadata. No production migration or curriculum publication.
- Existing worker/leases/process boundary/budget ledger reused; no new SDK or
  infrastructure. One paid call at most per attempt, with conservative reservations,
  fenced completion, explicit retry, and idempotent database-write recovery.
  Interviewer and evaluator share one live slot; editing remains available.
- Owner-only JWT and CSRF endpoints, readable saved results, source links, polling,
  no-JavaScript support and a standalone same-UUID recovery form. A new snapshot
  is needed to assess revised work. The page uses the compact Learning shell.
- Defaults: configured model (currently Sol), medium reasoning, 4,000 output tokens;
  the existing deadline, context allowance, tier and monthly budget apply. Current
  [Sol documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
  and [strict output contract](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
  were verified November 2. Existing prices remain unchanged. No paid calls were
  made and live grading quality/latency remain unverified.

Verification:

- **617 backend tests run: 616 passed, one existing Linux-only test skipped on
  macOS**, with isolated **PostgreSQL 18.6**. This adds **31 tests**: 18 feedback
  service/contract cases, seven API/web cases, and six PostgreSQL concurrency/FK
  cases. The populated migration round trip and metadata parity checks were also
  extended. Original review history survives the migration sequence.
- Real PostgreSQL covers duplicate requests/claims/completions, the shared live
  slot, competing interviewer/evaluator reservations, forced lock windows during
  deletion, late completion/deletion ordering, and cross-session foreign keys.
- Browser integration passes **145 practice checks** (26 added), plus the existing
  **70 concept** and **60 hub** checks. Feedback cases include lost POST recovery,
  polling, exact evidence links, immutable reload, shared workspace status,
  learner-facing privacy, 320-pixel layout, and native forms without JavaScript.
- **39 focused tests** including the browser walkthrough passed again after final
  response/display refinements. **13 Node tests**, dependency integrity, **102
  renderer checks**, Sass compilation and `git diff --check` passed.
- Deterministic fixtures cover correct alternatives, actual race evidence, absent
  evidence, assistance coverage, hostile input as data, fabricated citations,
  unknown/private IDs, oversized contexts, lost provider outcomes and charged
  invalid output. These are contract/recovery checks, not a live grading benchmark.

Gotchas: a freshly initialized local cluster without an explicit encoding chose
SQL_ASCII and psycopg returned bytes for the server version. Recreating only the
disposable test database with UTF-8 fixed the fixture; no application change was
needed. A frozen-clock retry also exposed the need to order feedback attempts
monotonically rather than by random UUID. Saved pages now use Learning's typography
and header instead of the portfolio layout.

The [hands-on guide](learning-checkpoint-5c-test-guide.md) covers DevTools, cURL/
Postman, HTTPie, REPL inspection, and failure experiments. Preview port 5059 keeps
5057/5058 intact; `--feedback-example` seeds a labelled scripted result. No push,
deployment, production publication, Expo work, or content expansion occurred.

Next approval: live evaluator release review, then learner acceptance/targeted
review and export as separate checkpoints. Milestone 1 acceptance is still open.

## Live evaluator quality review (November 2)

Keith approved a bounded live review and asked to settle important decisions
before making changes. The review used the existing Sol/medium configuration
and `evaluator-1`, with a **$2 total ceiling** announced before paid calls.

- Twelve fixed synthetic cases were run twice through real saved snapshots,
  the worker, output validation, persistence, and the PostgreSQL ledger. Cases
  cover three defensible designs, four actual errors, absent evidence, recorded
  assistance, hostile instructions, a corrected earlier draft, and exercise v1.
- **24/24 calls produced validated saved results.** Codex reviewed every output
  against the expectations authored before the runs. No critical misgrading or
  undisclosed requirement/reference leakage was found in this set. All eight
  planted-error repetitions received the expected misconception mapping.
- **$0.519980** spent; all charges settled, with no uncertain balance. Costs were
  recomputed from usage. Peak committed spending while a call was reserved was
  $0.578016. The review stayed in one disposable database across rounds.
- Provider wall time: **20.759 seconds median**, **25.203 seconds observed p95**,
  25.755 seconds maximum. These are small-sample measurements for compact design
  snapshots, not a guarantee for long sessions.
- Added a guarded CLI, frozen fixtures, raw results, and an accounting/input
  audit. PostgreSQL run exclusion and an all-time review cap supplement the
  existing monthly reservation ledger. No automatic paid retries occur.
- **55 focused tests passed:** eight new harness cases plus 47 existing
  feedback/API/web/PostgreSQL recovery tests. The SERIALIZABLE alternative's
  overlapping absence reads were independently checked on PostgreSQL 18.6.

One fixture-only issue was corrected: the seeder initially used schema-1
metadata/checksums for both catalogs. The payloads were correct. A real importer
replay test now enforces catalog identity; six disposable metadata rows were
repaired and all 24 model request hashes remained identical. No content or case
expectations changed and no additional paid call was required for the correction.

Recommendation: retain the current model/profile and proceed to learner
acceptance/targeted follow-up review after Keith approves that checkpoint.
Human content review, export, accessibility checks, the full demonstration, and
milestone acceptance remain. The report also records a future content wording
clarification and the need to assess feedback focus with real learners.

See the [review report and REPL walkthrough](evaluations/learning-feedback-2026-11-02-review.md)
for per-case judgments, exact costs, limitations, and reproduction instructions.
The disposable cluster was stopped; existing previews were preserved. No
production runtime/UI change, model switch, migration, publication, deployment,
Expo work, or content expansion occurred.

## Checkpoint 5d: learner responses and optional practice (November 2)

Keith approved saved agree/disagree responses, optional notes, authored follow-up
questions, and a return to the same design session. The original feedback stays
immutable. This checkpoint uses no AI calls and changes no scheduling algorithm.

- Added `PracticeFeedbackAnnotation` and migration `c2d3e4f5a6b7`, following
  `b1c2d3e4f5a6`. A response has a decision, optional 2,000-character note,
  revision, and timestamp. Existing content-free practice receipts handle safe
  retries; the owner lock and expected revision prevent stale overwrites.
- Added compact response forms beneath findings and optional **Practise this**
  for agreed concerns with authored question mappings. No question generation or
  automatic progress changes. Legacy v1/unmapped findings retain lesson links.
- Reused existing review questions, explicit answer reveal, rating receipts, and
  scheduler. One pass per finding is derived from review logs, with no new queue.
  Suspended questions are respected; revealed content versions remain pinned.
  Extra practice survives reload and returns to the original practice session.
- Native web/CSRF and JWT endpoints preserve ownership, private responses, and
  server-only evaluation material. Stale-note recovery shows the saved note and
  draft; unknown commit recovery retains the same request ID. Unsaved notes stay
  in the form, with navigation protection and no browser-storage copy.
- Deletion cascades responses with feedback; explicit recall ratings remain in
  existing review history, as explained on the confirmation page. Withdrawal of
  agreement blocks new follow-up ratings but permits committed receipt replays.

Verification:

- **653 backend tests run: 652 passed and one existing Linux-only test skipped**
  on macOS. The **28 new tests** cover service behavior, API/web boundaries,
  immutable feedback, stale notes, lost commits, suspended/versioned questions,
  explicit scheduling, and PostgreSQL concurrency/deletion ordering.
- Real **PostgreSQL 18.6** verifies ten new concurrency cases, populated migration
  upgrade/downgrade, constraints, and metadata parity. Existing feedback, work,
  and review history survive the new migration's round trip.
- The full run passed **182 practice browser assertions**, plus **70 concept**
  and **60 hub** checks. A subsequent two-draft navigation fix passed a focused
  **184-check browser run**, covering retries, stale notes, answer reveal/rating,
  exact-session return, 320-pixel layouts, and use without JavaScript.
- **13 Node tests**, dependency integrity, **102 renderer checks**, Sass
  compilation, and `git diff --check` passed. The disposable preview was also
  visually inspected. No live AI call was needed.

Gotchas: WTForms integer fields render submitted `raw_data` before a changed
`.data`, so conflict recovery must rebuild the form against the displayed revision.
Also, a cancelled navigation must keep both annotation drafts dirty; a submit event
alone is not confirmation. Both now have regressions. Browsers reserve 5060/5061,
so the new demo uses **5062** and leaves older preview processes alone.

The [hands-on guide](learning-checkpoint-5d-test-guide.md) covers DevTools request
inspection, cURL/Postman replay, HTTPie failure simulation, and direct REPL calls.
`--feedback-example` now seeds draft v2 in the disposable database so the authored
race question is available. No new dependencies, infrastructure, content, paid
calls, production migrations, publication, push, or deployment occurred.

Next checkpoint to approve: learner-safe JSON/Markdown export. Human content
review, accessibility checks, the complete demonstration, and milestone sign-off
remain. Expo and additional concepts remain out of scope.

## Checkpoint 5e: portable session exports (November 3)

Keith approved JSON/Markdown exports as the next checkpoint. The download includes
the pinned learner-facing exercise, complete saved conversation, all artifact and
note revisions, revealed requirements, continuation choices, saved checks/feedback,
latest learner responses, and explicit follow-up ratings associated with the session.

- Versioned JSON (`engineering-learning.practice-session`, schema 1) preserves
  exact text and structured citations. Readable Markdown preserves work and source
  coordinates, escapes untrusted prose, and safely fences arbitrary saved code.
- Historical revisions are included so old feedback can be understood offline.
  Private rubrics/reference reasoning, hidden constraints not yet disclosed,
  misconception mappings, receipts, provider state, account data, billing, and
  unrelated review history are excluded through explicit field projections.
- The exporter reads on a separate PostgreSQL **REPEATABLE READ, READ ONLY**
  connection. Concurrent changes can't mix versions, and exporting takes no
  owner lock or caller-transaction ownership. There is no progress change or AI call.
- The complete response is prepared before sending download headers. Database
  batches and a configurable **32 MiB** allowance bound preparation; errors return
  413/503 without an attachment or silent truncation. The error page performs no
  further DB reads. No persistent export copy, job, dependency, or migration was added.
- Website and JWT download routes preserve existing ownership, feature gating,
  private cache headers and `nosniff`. UUID filenames exclude user-controlled
  titles. **Session details** and the delete confirmation have download links;
  they open separately and leave unsaved editor text intact. Copy explains that
  saved work is exported. Import/restore is outside this checkpoint.

Verification:

- **674 backend tests run: 673 passed, one existing Linux-only skip** on macOS.
  Adds **21 tests**: ten service/projection cases, six web/API cases, and five
  real PostgreSQL cases. Existing migration and Learning regressions pass.
- **PostgreSQL 18.6** tests force saves, annotation/rating, feedback completion,
  and deletion between export reads. Writers finish while the export holds its
  snapshot; the next export sees new state. Caller changes remain uncommitted,
  and connection settings return to READ COMMITTED/read-write afterward.
- **205 integrated practice browser checks** (21 added), plus **70 concept**,
  **60 hub**, and **102 renderer/security checks** pass. Coverage includes exact
  session links, private responses, drafts, failures/retry, 320-pixel layout,
  and controls without JavaScript. `git diff --check` passes.
- Both native browser downloads were opened as files and checked. Preview **5063**
  uses disposable data and fake AI; the earlier 5062 preview was left running.
  No paid calls, production publication/migration, push, or deployment occurred.

The main gotcha is that authentication may already have opened the request's ORM
transaction. A separate export connection establishes snapshot isolation without
rolling back or committing that caller transaction. In-memory SQLite shares one
physical connection; a regression test showed that borrowing it could roll back
uncommitted REPL writes. The exporter now refuses that case before borrowing the
connection, leaving an explicit commit/rollback to the caller. Older preview processes also
reload templates without Python; new links are gated by the updated render context
so an old process doesn't try resolving routes it hasn't loaded.

The [hands-on guide](learning-checkpoint-5e-test-guide.md) covers DevTools download
inspection, cURL/Postman, HTTPie failure simulation, and direct Python REPL calls.
The [handoff](engineering-learning-handoff.md) documents the export contract and limits.

Next checkpoint to approve: the full Milestone 1 acceptance and accessibility
walkthrough. Human content review and the placement of enrollment/reading progress
remain open before milestone sign-off. Expo and content expansion remain out of scope.

## Checkpoint 5f: walkthrough and accessibility review (November 3)

Keith approved the complete Milestone 1 walkthrough, accessibility fixes, tests,
and a separate commit. He also settled the prior entry's placement question:
**enrollment, saved reading position, and self-assessment are a separate checkpoint
before content expansion**, not required for Milestone 1 sign-off. They remain
unimplemented. No new architectural choice was necessary for this review.

The native walkthrough followed Learn → Review → Discuss → Build, clarification
and disclosure, saved artifacts/notes, old-revision feedback, an agreed finding,
optional follow-up practice, a revised snapshot, pause/resume, closing/reopening,
JSON export, and deletion confirmation/cancel. The demo session was retained.
The [review report](learning-milestone-1-acceptance.md) records each result and
provides a short keyboard/DevTools guide. The preview uses scripted AI; its newly
generated feedback is not evidence of technical grading quality.

Fixes:

- Keep keyboard focus on Start again when the retry simulation ends; keep the
  edited pane visible when the workspace narrows; preserve focus when feedback
  replaces its Refresh control, when following note evidence, and after saving
  a response. Leave unrelated focus alone.
- Put tabpanel semantics on wrappers so artifact/note fieldsets retain native
  groups and legends. Associate inline errors/conflict instructions with fields
  and make saved code/revision text keyboard scrollable.
- Use Learning's compact navigation and skip link on artifact history and deletion
  confirmation. Their native forms and ownership boundaries remain unchanged.

Verification:

- **674 tests run: 673 passed, one existing Linux-only skip**, with isolated
  **PostgreSQL 18.6**. Includes the existing migration, concurrency, budget,
  privacy, and recovery suites. No database/service/API/scheduler change.
- **225 integrated practice browser checks** (20 added), plus **70 concept** and
  **60 hub** checks, passed. **104 renderer/security checks** (two added), **13 Node
  tests**, dependency integrity, and `git diff --check` passed. Thirteen
  discussion/web tests passed again after the final deletion-shell fix.
- Native keyboard/accessibility-tree and 320-pixel walkthrough passed. A downloaded
  JSON file confirmed the saved history; actual deletion/cascades are covered in
  automated route/PostgreSQL tests. No paid calls; **$0 AI cost** for 5f.

The responsive-focus regression initially exposed browser event-order differences:
a pane may blur before resize is dispatched, and requestAnimationFrame callbacks
were throttled in the headless fixture. The final fix uses a guarded microtask
plus resize handling. Tests check both editing directions and that feedback
completion does not steal focus from outside its replaced region.

Remaining limits: VoiceOver/NVDA spoken output and standalone Safari/Firefox were
not tested; this is not a WCAG conformance audit. Human technical content review,
Keith's review of the live evaluator report, and final milestone approval remain.
No production change, Expo work, or content expansion was performed or authorized.

## Checkpoint 5g: delegated content and AI review (November 6)

Keith reported that Learn/Review and Discuss/Build looked good, then delegated the
remaining content and AI feedback judgment to Codex. The local technical review
is complete and supports starting the local pilot. The
[acceptance addendum](learning-milestone-1-acceptance.md#november-6-delegated-content-and-feedback-review)
records the judgment, supporting sources, and remaining limitations.

`curriculum/idempotency/catalog-v3.json` corrects one private reference passage.
It now distinguishes an uncoordinated READ COMMITTED lookup/insert from valid
uniqueness, locking, and SERIALIZABLE protocols and asks how competing callers
recover after commit or rollback. Catalog/spec format stays 2. Only the exercise
advances to revision 3, while the five lesson/question items replay revision 2.
The preview fixture's `--feedback-example` option selects this manifest on its
next start. Existing sessions continue using their pinned revisions.

The saved live evaluation summaries and concerns were rechecked in both runs,
including alternative designs, corrections, incomplete work, and assistance.
Those results support the existing interviewer/evaluator profiles for local use.
Feedback density remains an observation for the pilot. Additional paid cost was
**$0**. The historical paid results assess revisions 1/2; the reference correction
has technical review and deterministic integration coverage, without a fresh live
revision-3 evaluation.

Five regression tests were added. They verify that the correction only changes
private exercise identity, stays out of learner/interviewer projections and public
source routes, inserts one new revision on PostgreSQL, preserves work/ratings and
replayed start receipts, and reaches the evaluator only for sessions pinned to
revision 3. **679 tests ran: 678 passed, one existing Linux-only skip**, with
isolated PostgreSQL 18.6. The full run includes **225 practice, 70 concept, and
60 hub browser checks**, migration/concurrency/recovery tests, and the PostgreSQL
SERIALIZABLE interleaving regression. `git diff --check` passed.

Codex's delegated review is recorded as the local technical assessment. Actual
human publication attestation, production rollout approval, VoiceOver/NVDA
listening, and standalone Safari/Firefox remain outstanding. The next proposed
implementation checkpoint is enrollment, reading position, and self-assessment,
subject to separate approval before content expansion. Expo also requires
explicit approval.

## Checkpoint 6a: enrollment and continue learning (November 7)

Keith approved enrollment, reading position, and a clear continuation point as a
small follow-up after Milestone 1. Optional self-assessment is proposed as 6b;
Expo and content expansion remain separately gated.

Implemented one `UserConceptProgress` row per user/concept, with an explicit
Start learning operation and a versioned section bookmark. Migration
`d3e4f5a6b7c8` is additive, with no enrollment backfill or review/practice changes.
The service serializes first enrollment and reading writes using the existing
user-row lock pattern. Exact immediate reading retries replay; stale revisions
return 409, including an old retry after a newer save. UTC-normalized timestamps
keep replay responses identical across database connection time zones.

Home offers Start learning for an unenrolled concept, or Continue lesson at its
saved section, alongside review and existing practice. New concept questions are
eligible after enrollment; already-started questions keep their schedules even
without it. Browsing does not enroll or rate. The legacy review API is unchanged.
Explicit section links take precedence over stored reading position, and unrelated
anchors do not erase it. Native forms work without scripts. The enhanced saver
serializes rapid navigation, retains an unconfirmed request for exact retry,
handles stale tabs without overwriting, and preserves focus when retrying by
keyboard. This records reading location, not mastery or completion.

Web writes use CSRF; the shared JWT progress endpoints use the existing Learning
API and private cache policy. No new infrastructure or changes to the practice,
AI worker, budget, feedback, or artifact contracts were needed. The existing
rating failure path uses preloaded progress so it does not query the database
again while rendering recovery from a failed write.

Verification:

- **697 tests run, 696 passed, one existing Linux-only skip**, with isolated
  **PostgreSQL 18.6**. Eighteen new tests cover the service, web/JWT boundaries,
  migration, concurrency, process-death rollback, and browser flow.
- **40 new progress browser checks**, plus the existing **225 practice / 70
  concept / 60 hub** checks. They cover opt-in behavior, saved/deep-link
  navigation, sign-out/account isolation, stale tabs, lost responses, offline
  retry, rapid navigation, native forms, keyboard retry, and 320-pixel layout.
- **13 Node tests**, dependency integrity, **29 standalone lesson browser
  checks**, Sass compilation, and `git diff --check` passed. The final home
  enrollment action received a focused route/browser rerun.
- Manual preview verified Start learning, saving a different section, and a home
  continuation link to that exact section. Additional paid AI cost: **$0**.

The [hands-on guide](learning-checkpoint-6a-test-guide.md) uses DevTools,
Postman/HTTPie, and a Python REPL. The updated disposable preview is on port 5066;
older previews retain their data but their running Python code predates these
changes. Use the new preview. Persistent environments require the new migration
before starting the updated app. No production migration/publication/deployment
was performed. Optional self-assessment remains the proposed next checkpoint.

## Checkpoint 6b: optional self-assessment (November 7)

Keith approved four separate optional ratings and dated check-ins. A quiet
Self-assessment link in the concept header leads to native selects for
recognition, understanding, application, and judgment. Choices are Not assessed,
Not yet, With help, and Without help. Reflection is available before enrollment,
never required, and never interpreted as demonstrated mastery. The main four-mode
workspace remains unchanged, including the selected practice session.

Migration `e4f5a6b7c8d9` adds `ConceptSelfAssessment`, with owner/concept/revision
identity, per-user request UUIDs, lesson/scale version pins, UTC dates, and four
independent ratings. No backfill or existing-table mutation occurs. The service
uses the existing user-row lock pattern and a revision sequence independent of
bookmarks. Exact retries return the original snapshot even after later check-ins.
Stale new requests show the latest entry alongside unsaved choices; an explicit
Save as a new check-in appends rather than overwrites. Lost-response recovery
retains the original request and renders without further DB reads.

History uses ten-entry pages. Deletion requires confirmation and removes the
rating values while retaining dates/request identities and a clear marker for
retry fencing. Old forms cannot resurrect deleted ratings, and a repeated deletion
cannot erase a check-in saved afterward. Owned history remains readable/removable
if the lesson is withdrawn, with no draft/reference exposure. Website routes use
login/CSRF; GET/POST/DELETE `/api/v1/learning/concepts/<id>/self-assessments` use
JWT and private/no-store responses. There is no AI call, overall score, promotion,
local storage, or change to enrollment, bookmarks, reviews, feedback, or budgets.

Verification:

- **721 tests run, 720 passed, one existing Linux-only skip**, using isolated
  **PostgreSQL 18.6**. Twenty-four new tests cover the service, web/JWT adapters,
  DDL, constraints, first-write/concurrent-save/deletion races, process-death
  rollback, pagination, publication withdrawal, and browser behavior.
- **55 new self-assessment browser checks**, plus **225 practice / 70 concept /
  60 hub / 40 progress**. Native and no-script forms, stale tabs, lost responses,
  failure before commit, keyboard controls, 320-pixel layout, account isolation,
  and exact-session/artifact continuity passed.
- **13 Node tests**, dependency integrity, Sass, and `git diff --check` passed.
  Final response copy received a focused route/browser rerun.
- Manual preview verified independent choices, Tab/Enter saving, and keyboard
  history disclosure with labeled controls in the accessibility tree. Additional
  paid AI cost: **$0**. VoiceOver/NVDA listening and standalone Safari/Firefox
  remain unverified.

Gotchas: WTForms integer fields prefer submitted raw data, so conflict recovery
rebuilds the form with the new expected revision; an uncertain save must instead
retain its original UUID/revision. Reading autosaves and reflection have separate
revision streams. A copied POST is a retry, not a fresh tab's request; browser
fixtures must use distinct UUIDs to exercise stale-tab conflicts. The base layout
uses a `scripts` block for progressive enhancement. Older previews do not reload
Python or gain new schema from template reloads.

The [hands-on guide](learning-checkpoint-6b-test-guide.md) covers DevTools,
Postman/HTTPie, and a Python REPL. The new disposable preview is on **5067** with
one example check-in for account 1; earlier previews retain their data. Apply the
migration before updating persistent environments. No production migration,
publication, push, or deployment was performed. Further implementation, Expo,
additional personalities, and content expansion require separate approval.

## Checkpoint 7a: persistent personal local pilot (November 7)

Keith approved **$5 total**, with **at most $1 of it for verification**, and
clearly labelled drafts in the isolated local pilot. The new operator entry
point uses the existing Flask app, PostgreSQL server, request worker, and ledger.
It adds no service or schema migration. Fresh setup applies the existing full
migration chain; normal startup preserves data, credentials and progress.

Private instance settings bind to a dedicated local database. Startup is
loopback-only, uses normal login/CSRF/ownership, and requires explicit `--live`
plus recorded approval for AI. The exact approved draft IDs, versions, and
checksums become visible only through the guarded local factory. Normal content
readers still require publication, and learner projections still exclude private
reference/evaluation material. No human attestation was fabricated.

The optional total allowance uses the existing ledger and PostgreSQL budget
lock alongside monthly limits. It counts unresolved reservations and persists
across restarts, month changes, and session deletion. Verification mode applies
the smaller cap to that same ledger. Backup requires a stopped server; restore
uses a new database, rotates signing keys, and blocks paid AI until spending can
be reconciled and a new activation decision reviewed.

Verification:

- **740 tests run, 739 passed, one existing Linux-only skip**, on PostgreSQL
  18.6 and the pinned Python 3.13.18/Node 24.22.1 runtimes. Nineteen added tests
  cover setup, policy/key isolation, draft privacy, real process restart,
  migration/metadata comparison, backup restoration, budget concurrency and
  cross-month/deletion accounting, and UTC timestamp rendering.
- The full run includes **450 browser assertions** across practice, concept,
  home, enrollment/bookmark, and self-assessment flows. Thirteen Node tests,
  dependency integrity, Sass, and diff checks pass. Final local-only pause copy
  received a targeted route/PostgreSQL rerun.
- The real local pilot completed two interviewer turns with saved API/SQL/
  pseudocode artifacts and one complete-snapshot evaluation. Feedback cited
  exact evidence, accepted the concurrency/outbox design, identified the open
  expiry contract, and acknowledged Codex authorship/insufficient unaided evidence.
- **Actual paid cost: $0.037859**, all five calls settled; **$4.962141 remains**.
  There are no pending requests from verification. The paused example is clearly
  identified in its first message; enrollment, review ratings, and self-assessment
  remain untouched for Keith to begin his own trial.
- A real web-process restart retained the browser login, work, feedback and
  budget. The independent backup restore reproduced the session export checksum
  (excluding export time) and all five charge records, and refused live activation.

The walkthrough exposed two fixes: Talisman re-enabled secure-only cookies on
local HTTP despite the factory config, and the timestamp renderer printed local
offsets with a UTC label. The local entry point now uses the intended cookie
policy; timestamps are converted to UTC for display. Production HTTPS and stored
dates are unchanged. Local navigation also omits unavailable portfolio/reset
routes and uses accurate local-only pause wording.

The persistent pilot is at **5068**, with private settings/login/approval/backups
under `.local/learning-pilot/`. The [operating and exploration guide](learning-checkpoint-7a-test-guide.md)
covers daily use, DevTools, HTTPie/Postman, Python REPL, backup, and recovery.
The prior disposable previews and portfolio database were preserved. The next
step is a short personal learning trial; Expo, new concepts/personalities, and
production publication/deployment still require approval.

## Checkpoint 7b: private hosted pilot preparation (November 13)

Keith approved reusing the existing Heroku site/database/account, exact labelled
drafts behind a verified-owner gate, and fresh hosted practice. Local work stays
readable; its spending carries forward and local paid AI is frozen before hosted
activation. The same $5 lifetime/$1 verification allowance applies. **Deployment
still requires explicit approval.**

The hosting audit found one Basic web dyno, PostgreSQL 16.14, and the existing
verified owner. The new hosted policy validates a private cutover record and
pins that owner, the six approved draft fingerprints, models, limits and HTTPS
cookie/host settings. Every Learning route and navigation uses the owner gate.
Drafts remain unpublished; evaluation references stay out of learner responses.
The local handoff is recoverable after a partial write and refuses live restart.
Hosted budget reservations include carried settled/uncertain costs under the
existing PostgreSQL lock, across restarts and calendar months.

The release phase applies the existing migration chain, imports the exact
unpublished packet and checks readiness without AI. PostgreSQL advisory locking
serializes concurrent migrations; failed DDL rolls the pending chain back.
Gunicorn 27.0.1 runs one threaded process, starts the existing AI worker after
readiness and preserves existing Socket.IO behavior. This replaces the deployed
development server and its migration command that continued after failure.
No new database schema, queue, service or worker dyno was added.

Validation on the final dependency set:

- **759 tests run, 758 passed, one existing Linux-only skip**, including the
  existing 450 browser assertions and 19 new hosted-policy/access/migration/
  handoff/budget/server tests. Real server tests exercise HTTPS router headers,
  secure login, WebSocket cookie/JWT authentication, saved replies and restart.
- The read-only production-copy rehearsal preserved **11,324 rows across 28
  application tables** through two release runs, moving from `a4b5c6d7e8f9` to
  `e4f5a6b7c8d9` and importing six unpublished revisions. The clone was removed;
  the private backup/report is retained locally. Production was not changed.
- Thirteen Node tests, dependency integrity, Poetry lock/install consistency,
  and the Python dependency audit pass. The audit prompted existing-library
  patches to [OAuthLib 4.0.1](https://github.com/oauthlib/oauthlib/releases/tag/v4.0.1)
  and [pyasn1 0.6.5](https://github.com/pyasn1/pyasn1/releases/tag/v0.6.5).
- All AI responses were deterministic fixtures; **$0 spent**. Real local AI is
  not frozen yet. No production configuration, migration, push or deployment
  occurred. Unrelated mobile changes stay outside this commit.

The rehearsal caught a restore issue caused by Heroku's explicit `public`
schema ownership. Restore now cleans only a freshly created target; a regression
test reproduces that ownership. PostgreSQL backup clients must match version 16;
CI now uses that version and matching clients. Row comparisons normalize UTC
and exclude hosting-system monitoring views.

Next: ask for deployment approval against this commit, then follow the
[rollout and hands-on guide](learning-checkpoint-7b-test-guide.md). Activation
starts with AI off, then bounded verification and finally private use. Restore
or rollback must preserve accounting; older hosted backups need spending
reconciliation before AI can resume. Content expansion and Expo remain unapproved.
