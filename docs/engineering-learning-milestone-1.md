# Engineering Learning: Milestone 1 implementation checkpoints

Scope approved October 28, 2026: one complete **idempotency** concept on the existing Flask website. Preserve the Learning APIs, scheduler, progress, and legacy notes. The existing Flask/PostgreSQL architecture remains; Expo is Milestone 2 and needs separate approval. This log records implementation sequencing without replacing the approved architecture or the earlier Learning mobile modernization record.

Read the [approved revised plan](engineering-learning-revised-plan.md) for the agreed architecture and milestone acceptance criteria. For current progress, remaining work, local setup, and implementation gotchas, start with the [engineering handoff](engineering-learning-handoff.md).

| Checkpoint | Deliverable and acceptance gate | Status |
| --- | --- | --- |
| 1. Content foundation | Versioned catalog, draft lesson/four questions/one structured interview; audience projections; atomic import; additive migration verified on PostgreSQL; legacy Learning regression checks. | Committed as `1f344a5`; [REPL guide](learning-checkpoint-1-test-guide.md). |
| 2. Learn and Review on web | Published lesson, retry visualization, safe Markdown, explicit answer reveal, four questions through the existing scheduler; unchanged old API behavior and progress. Human content review precedes publication. | Committed as `3b108bf`; [hands-on guide](learning-checkpoint-2-test-guide.md), refined in `0c2848a`. Production publication remains pending human content review. |
| 3a. Practice sessions and artifacts | Sessions pinned to a published exercise; API/SQL/pseudocode artifacts with immutable revisions; idempotent saves; per-artifact conflicts without data loss; ownership; failure recovery; web workspace; JWT API; feature flag. Migration and concurrency verified on PostgreSQL. No IDE or execution sandbox. | Committed as `fe91fe2` (persistence and service) and `709658b` (web workspace and API); [practice guide](learning-checkpoint-3-test-guide.md), part A. |
| 3b. Discussion record | Learner turns citing exact artifact revisions, editable session brief, pause/resume, delete; resume elsewhere with transcript, brief, and revisions intact. | Committed as `b7ae1e2` (service) and `bcb0f40` (workspace and API); [practice guide](learning-checkpoint-3-test-guide.md), part B. |
| 4a. Durable replies | Replies as tracked PostgreSQL requests, run by a worker thread in the web process against a scripted fake provider: owner-only access, fencing, budgets and reservations, interruption and explicit retry, polling on the website and API. | Committed as `81312c8` (service and worker) and `27af973` (website and API); [checkpoint 4 guide](learning-checkpoint-4-test-guide.md), part A. |
| 4b. The interviewer | The OpenAI call in a child process through Learning's own key, the `interviewer-1` profile, approved disclosure and hints on request, a read-only revealed-requirements list, a context allowance with **Continue with recent messages** and a specific stop (compaction deferred), the 24-turn check-in, and an evaluation harness. | Committed as `216d394` (the interviewer, its service and API) plus the following website commit; [checkpoint 4 guide](learning-checkpoint-4-test-guide.md), part B. |
| 4. Activation | Keith creates Learning's OpenAI project and key; live evaluations choose the model; verified prices recorded. No production enablement. | Needs Keith. |
| 5. Feedback and complete demonstration | Content schema 2 with misconception mappings; deterministic JSON/YAML checks, then evidence-linked transcript/artifact feedback; remediation and a follow-up review from accepted findings; export; pause/reopen/recover; one full Learn → Review → Discuss → Build walkthrough. | Not started. |

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

The OpenAI call runs in a child process: `project/learning_ai_call.py`, run with `python -I`, imports only the standard library and `requests`. `project/services/learning_ai_provider.py` gives it an environment of just the key, `PATH`, and CA settings, and discards its stderr. The child:

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
