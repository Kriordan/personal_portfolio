# Engineering Learning: Milestone 1 implementation checkpoints

Scope approved October 28, 2026: one complete **idempotency** concept on the existing Flask website. Preserve the Learning APIs, scheduler, progress, and legacy notes. The existing Flask/PostgreSQL architecture remains; Expo is Milestone 2 and needs separate approval. This log records implementation sequencing without replacing the approved architecture or the earlier Learning mobile modernization record.

Read the [approved revised plan](engineering-learning-revised-plan.md) for the agreed architecture and milestone acceptance criteria. For current progress, remaining work, local setup, and implementation gotchas, start with the [engineering handoff](engineering-learning-handoff.md).

| Checkpoint | Deliverable and acceptance gate | Status |
| --- | --- | --- |
| 1. Content foundation | Versioned catalog, draft lesson/four questions/one structured interview; audience projections; atomic import; additive migration verified on PostgreSQL; legacy Learning regression checks. | Committed as `1f344a5`; [REPL guide](learning-checkpoint-1-test-guide.md). |
| 2. Learn and Review on web | Published lesson, retry visualization, safe Markdown, explicit answer reveal, four questions through the existing scheduler; unchanged old API behavior and progress. Human content review precedes publication. | Committed as `3b108bf`; [hands-on guide](learning-checkpoint-2-test-guide.md), refined in `0c2848a`. Production publication remains pending human content review. |
| 3a. Practice sessions and artifacts | Sessions pinned to a published exercise; API/SQL/pseudocode artifacts with immutable revisions; idempotent saves; per-artifact conflicts without data loss; ownership; failure recovery; web workspace; JWT API; feature flag. Migration and concurrency verified on PostgreSQL. No IDE or execution sandbox. | Committed as `fe91fe2` (persistence and service) and `709658b` (web workspace and API); [practice guide](learning-checkpoint-3-test-guide.md), part A. |
| 3b. Discussion record | Learner turns citing exact artifact revisions, editable session brief, pause/resume, delete; resume elsewhere with transcript, brief, and revisions intact. | Committed as `b7ae1e2` (service) plus the following workspace/API commit; [practice guide](learning-checkpoint-3-test-guide.md), part B. |
| 4. Interview and continuity | Postgres-backed worker, owner-only AI use, approved disclosure, idempotent requests, budgets/reservations, configurable soft turn check-in, context compaction, durable recovery. | Not started. |
| 5. Feedback and complete demonstration | Evidence-linked transcript/artifact feedback, remediation, pause/reopen/recover, one full Learn → Review → Discuss → Build walkthrough. | Not started. |

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
