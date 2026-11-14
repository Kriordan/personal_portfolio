# Engineering Learning Platform Handoff

As of November 7, 2026, **Milestone 1 and checkpoints 6a/6b are complete locally; checkpoint 7a provides the persistent personal pilot on port 5068.** Its approved $5 total allowance includes up to $1 for verification, which used $0.037859. Explicitly approved drafts are labelled and isolated; normal publication remains gated. Existing scheduling and practice recovery are preserved. See the [7a operating/exploration guide](learning-checkpoint-7a-test-guide.md), [6b guide](learning-checkpoint-6b-test-guide.md), and [Milestone 1 acceptance report](learning-milestone-1-acceptance.md). Production publication still needs an actual human-review attestation and rollout approval. VoiceOver/NVDA and standalone Safari/Firefox checks remain unverified. Continue on `feature/learning-content-foundation`.

**November 13 update:** Keith approved deployment and checkpoint 7b is **live** at
[Learning](https://www.keithriordan.com/learning/), using his existing verified
account. Heroku release **v171**, source `93a24a2`, is in private `pilot` mode.
Local paid AI is frozen; local work remains readable. Combined spending and
reservations are **$0.076025**, leaving **$4.923975** of the original $5 allowance.
Access, live interviewer/feedback, saved artifacts, restart/resumption and
accounting checks passed. See the [7b rollout and hands-on guide](learning-checkpoint-7b-test-guide.md).

**November 13 mobile update:** Keith subsequently prioritized his iPhone and
approved **Milestone 2a: Learn and Review**. Its implementation reuses the hosted
curriculum, enrollment/bookmark, and scheduler services through small JWT
adapters. No new progress model, migration, dependency, or paid AI calls are
needed. See the [Milestone 2 log](engineering-learning-milestone-2.md) and
[phone/testing guide](learning-checkpoint-2a-iphone-guide.md). Keith then approved
release: **Heroku v173** and [standalone iPhone build 9](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/eb7be266-9a98-484d-b4fa-8bdc4f75e836)
use application source `eee8b9e`. Downloaded-bundle and read-only hosted checks
passed; the unchanged shared allowance has **$4.923975** remaining at verification.
Keith subsequently reported that Learn/Review look good on his iPhone and approved
**2b: native Discuss and conversation continuity**. Its implementation,
draft-persistence decision, verification, and approved release are recorded in the
[Milestone 2 log](engineering-learning-milestone-2.md#checkpoint-2b--discuss-and-conversation-continuity).
Keith explicitly approved deploying `a905098`: **Heroku v175** and
[standalone iPhone build 10](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/45ce8b80-8d63-415f-a0d7-887d77b09aef)
are now released. Hosted recovery/privacy checks and downloaded-archive checks
passed, with no paid AI usage or spending-limit changes. The allowance still had
**$4.923975** remaining at release verification. Build 10 physical-device acceptance
is pending; 2c and additional concepts remain unapproved.

This handoff records the approved architecture and refinements, the implementation through checkpoint 7b and mobile checkpoint 2b, the Learning UI/login follow-ups, and the remaining learning-trial work. It complements the [approved revised plan](engineering-learning-revised-plan.md), [checkpoint log](engineering-learning-milestone-1.md), and [curriculum contract](../curriculum/README.md). The original and refined plans were approved in the Codex chat **Plan engineering learning platform**; the revised plan is now preserved in the repository, with relevant baseline decisions captured here. The refined milestone order and unified session model supersede the original early milestone order and separate Discuss/Build sessions.

The [original project vision](engineering-learning-original-vision.md) preserves Keith's opening request verbatim. Its planning-only instructions describe the initial request; subsequent approval authorizes the Milestone 1 scope recorded here.

## Goal and scope

Keith wants to rebuild fundamentals and develop senior/staff engineering judgment through explanations, retrieval practice, implementation, and realistic technical conversations. Success means better unaided explanations and solutions, including the ability to defend trade-offs. Reading completion and AI scores are not measures of mastery.

The immediate deliverable is one complete **idempotency** experience on the existing Flask website:

1. Learn from a lesson and retry visualization.
2. Review four questions using the existing scheduler.
3. Discuss an order API with an interviewer who reveals hidden requirements after appropriate clarification.
4. Build an API outline, SQL schema, and pseudocode inside that same session.
5. Revise work after challenges, pause, close the app, and resume with confirmed work intact.
6. Receive feedback citing original conversation and exact artifact revisions, follow remediation, and revisit/export/delete saved work.

**Milestone 1 and checkpoints 6a/6b/7a/7b** are authorized and implemented; 7b is privately hosted. The $5 shared allowance and labelled exact drafts remain unchanged. Keith chose four separate optional ratings and dated check-in history for 6b. **Milestone 2a is released and 2b is authorized**, limited to native Discuss, shared sessions/recovery, and read-only work references. Keith approved device-persistent drafts scoped to account/session and cleared on sign-out. Do not start 2c, expand to other concepts, or add other AI personalities without further approval. No executable sandbox, full IDE, voice, recording, vector database, CMS, or agent framework is needed. Important architectural decisions not covered below must go back to Keith.

Work in small, cohesive checkpoints with separate commits. Report changes, meaningful verification, and unresolved limitations. Keith's requested testing guides are hands-on engineering practice: Python REPL and debugger experiments, DevTools Network/Console/Sources/Performance, and HTTPie/Postman requests. Keep those separate from automated test evidence.

## Delivery plan and current status

| Milestone | Scope and gate | Status |
| --- | --- | --- |
| 1 | One complete concept on web, including continuity, feedback, privacy, budgets, export/delete, and a runnable demonstration. | Local implementation and delegated technical review complete through 5g. Codex recommends local pilot acceptance. Production publication remains separately gated. |
| 2 | Same experience in Expo; resume across web/mobile without losing or overwriting confirmed work. | 2a Learn/Review and 2b Discuss released as iPhone build 10; physical-device 2b acceptance pending. 2c still requires approval; see the Milestone 2 log. |
| 3 | Fourteen production-systems concepts, about 42 questions, representative Build work, remaining discussion styles, and a short diagnostic. | Requires separate approval; content breadth must not delay the first experience. |
| 4 | Four-week personal trial with unaided baseline and delayed transfer probes, including roughly 7- and 21-day checks. Evaluate usefulness, misleading feedback, usability, and cost. | Later. |

The longer-term direction remains a reviewed curriculum of roughly 200–300 concepts, deeper practice, possible FSRS evaluation, isolated code execution, and eventually voice/personalization. These are planning estimates and later choices, not current deliverables.

Milestone 1 and the separately approved progress follow-up:

| Checkpoint | Deliverable | Status |
| --- | --- | --- |
| 1 | Versioned content, validation, projections, importer, draft idempotency material, additive migration. | `1f344a5` — complete locally. |
| 2 | Web lesson, visualization, answer reveal, shared review scheduling, version-pinned logs, privacy treatment. | `3b108bf` — complete locally. |
| Documentation follow-up | Replace test-suite instructions with interactive investigation guides. | `0c2848a`. |
| 3a | Practice sessions pinned to a published exercise, immutable artifact revisions, idempotent saves, per-artifact conflicts, ownership, failure recovery, web workspace, JWT API, feature flag. | `fe91fe2` (persistence and service) and `709658b` (web workspace and JSON API) — complete locally. |
| 3b | Discussion turns citing exact artifact revisions, editable session brief, pause/resume, delete. | `b7ae1e2` (service) and `bcb0f40` (workspace and API) — complete locally. |
| 4a | Durable replies: tracked requests, a worker thread, owner-only access, fencing, budgets and reservations, interruption and explicit retry, and polling, all against a scripted fake provider. | `81312c8` (service and worker) and `27af973` (website and API) — complete locally. |
| 4b | The interviewer: the OpenAI call process, the `interviewer-1` profile, disclosure and hints, revealed requirements, the context allowance, the check-in, and an evaluation harness. | `216d394` (the interviewer, its service and API) plus the following website commit — complete locally. |
| 4 activation | Learning's OpenAI project and key (Keith), live evaluations, model choice, verified prices. No production enablement. | Done locally October 30: `gpt-6.1-sol` at low reasoning. Production enablement waits for content review. |
| Workspace follow-up | Compact practice shell, shared Discuss/Build views, artifact/reference tabs, native POST continuity, and integrated browser recovery checks. | Implemented locally November 1; separate checkpoint commit. |
| Learning UI/login follow-ups | Compact home and library catalogs; all Learning behind login; shared four-mode concept workspace with exact-session continuity. | Implemented locally November 2. Home: `30aea19`; login: `e1a90bc`; shared workspace in a separate checkpoint commit. |
| 5a | Feedback content foundation: v2 misconception mappings and backward compatibility. | Implemented locally November 2; separate checkpoint commit. |
| 5b | Immutable submission snapshots and persisted JSON/YAML syntax checks; editable sessions and Checks tab. | Implemented locally November 2; separate checkpoint commit. |
| 5c | Evidence-linked snapshot feedback, exact citations, bounded generation, persistence and recovery. | Implemented November 2; see below and the [hands-on guide](learning-checkpoint-5c-test-guide.md). |
| Live evaluator review | Twelve fixed cases, two live repetitions, technical review, and cost/latency accounting. | Complete November 2; [report and REPL walkthrough](evaluations/learning-feedback-2026-11-02-review.md). Keith delegated the remaining review on November 6; see 5g. |
| 5d | Saved agree/disagree responses and notes; optional authored review questions; recovery and return to the same session. | Implemented locally November 2; [hands-on guide](learning-checkpoint-5d-test-guide.md). |
| 5e | Consistent, learner-safe JSON/Markdown session downloads, full history, ownership and concurrent-write checks. | Implemented locally November 3; [hands-on guide](learning-checkpoint-5e-test-guide.md). |
| 5f | Full local demonstration and targeted accessibility review; fixes and regression tests. | Complete locally November 3; [report and hands-on guide](learning-milestone-1-acceptance.md). Later content/evaluator review recorded in 5g. |
| 5g | Delegated content/AI review and a versioned private reference correction. | Complete locally November 6; 678 tests passed, one platform skip. Local pilot recommended; publication and browser/screen-reader limits remain in the acceptance report. |
| 6a | Explicit enrollment, saved reading position, and home continuation. | Approved and implemented locally November 7; PostgreSQL and browser verification; [hands-on guide](learning-checkpoint-6a-test-guide.md). |
| 6b | Optional recognition/understanding/application/judgment check-ins with dated history and safe retry/deletion. | Approved and implemented locally November 7; PostgreSQL and browser verification; [hands-on guide](learning-checkpoint-6b-test-guide.md). |
| 7a | Persistent personal local pilot, exact labelled drafts, bounded live AI, restart and backup recovery. | Complete locally November 7; $0.037859 verification cost; [operating guide](learning-checkpoint-7a-test-guide.md). |
| 7b | Private hosted pilot on the existing site, with local spending carried forward. | Deployed November 13; v171 / `93a24a2`; live feedback and restart verified; [operating guide](learning-checkpoint-7b-test-guide.md). |

Before checkpoint 7b, no push, PR, deployment, production migration, or production publication was performed for these checkpoints. Content remains an AI-assisted draft awaiting human technical review; demo publication is not production approval.

**Deploying this branch migrates production.** Since checkpoint 7b, the `Procfile`
runs `scripts/release.py` before serving through Gunicorn. A failed release check
prevents promotion; web startup independently checks readiness. This replaced
the former `flask db upgrade; python run.py` command, which could start after a
failed migration. The hosted pilot derives practice access from its validated
owner policy. Leave that policy enabled when switching AI off.

## Decisions and reasons

Keith settled the feedback lifecycle on November 2: **save an immutable snapshot and keep the session editable**. Checking work resumes a paused session, as Save does; it never marks the session completed. Later feedback will refer to one of these snapshots. An explicit Finish/lock action is not part of 5b.

| Decision | Reason and consequence |
| --- | --- |
| Extend Flask/PostgreSQL and existing feature services. | Preserve the working application and minimize operational changes. Website authentication remains Flask-Login plus CSRF, which is enforced only through Flask-WTF forms: there is no global `CSRFProtect`, so a cookie-authenticated JSON endpoint would have none. JSON API authentication remains JWT. |
| Keep existing SM-2/custom half-life scheduling and review history. | Changing learning modes and the scheduler simultaneously would obscure results and risk progress. The half-life implementation uses fixed multipliers, not a fitted regression model. Evaluate FSRS separately later. |
| Git-authored JSON and Markdown; immutable resolved snapshots in PostgreSQL. | Content stays reviewable in Git, while historical sessions and reviews can refer to the exact material used. No CMS is needed. |
| Select the highest published revision instead of maintaining a mutable publication pointer. | Avoids another mutable field and circular foreign key. A newer draft does not hide an older published version. |
| Human review before publication. | Schema checks cannot establish educational accuracy. Architecture approval does not attest review of lesson content, hidden constraints, alternatives, or rubrics. |
| Explicit learner/facilitator/evaluator projections. | Prevent answer/reference leakage through accidental serialization or overly broad prompts. Application privacy does not make the public Git repository secret. |
| One practice session with conversation and multiple evolving artifacts. | Discuss and Build are complementary views of the same work. Avoid duplicated sessions and disconnected feedback. |
| Carry `practice_session` through lesson/review navigation. | Keep the exact selected session rather than silently substituting a newer one. Validate ownership and concept on the server; use a read-only summary, without loading work or starting/resuming a session. No new persistence model is needed. |
| Progressive enhancement for the tabbed workspace. | Keep native Flask form POSTs and their existing CSRF, receipt, conflict, and rescue behavior. Tabs hide panels without removing fields. Local storage holds only per-session view/scroll preferences; session storage temporarily holds focus/caret metadata across a submission. No learner text or server revisions are cached. Without JavaScript, every field remains visible and native saving still works. |
| Immutable artifact revisions without a separate artifact identity table. | Group revisions by stable artifact ID; this supports history, conflicts, and evidence references with a small model. |
| One PostgreSQL-backed worker and foreground polling. | Save work before generation, survive web-request timeouts/restarts, and avoid Redis/Celery or streaming infrastructure for the pilot. |
| Soft check-in at 24 learner turns, not a hard ending. | Substantial scoping/design conversations need continuation without losing decisions, requirements, or artifacts. Context and spending still have hard bounds. |
| Owner-only paid AI and a separate Learning budget. | Limit exposure while validating usefulness. Exhausting the AI budget must not block saving or reading work. |
| Retention and applied evidence remain separate. | Self-rated recall, assisted reasoning, and independently verified implementation are different kinds of evidence. AI findings must not silently change review ratings or schedules. |
| Enrollment, saved reading position, and self-assessment are separate checkpoints before content expansion. Keith, November 3; 6a/6b implementation approved November 7. | Keep Milestone 1 validation focused. Enrollment and reading position are delivered in 6a; optional self-assessment is delivered in 6b. |
| Four independent optional ratings and dated check-ins, chosen by Keith November 7. | Recognition, understanding, application, and judgment can differ. Version-one choices are Not assessed, Not yet, With help, Without help. Preserve history for the trial; do not infer an overall level, demonstrated mastery, scheduler changes, or AI feedback from these reflections. |
| Keith delegated the remaining content/AI review to Codex on November 6 after reviewing the four-mode experience. | Complete the local technical review and make routine corrections. Record Codex's judgment, keep actual human publication attestation separate, and preserve the approval gates for Expo and content expansion. |
| Split checkpoint 3 into 3a (sessions, artifacts) and 3b (turns, brief, pause/resume, delete). Keith, October 28. | Smaller reviewable steps; deletion ships with the first discussion data. |
| Learner turns persist in 3b, before the AI interviewer exists. Keith, October 28. | Checkpoint 4 then adds only the AI request inside the same transaction. A turn without a reply is also the lasting state for non-owner accounts and at the budget cap. |
| The editable session brief is versioned snapshots in `SessionMessage` (`kind='brief'`), from 3b. Keith, October 28. | Matches "no separate memory service"; compaction checkpoints can reference a brief version. Demo step "resume with requirements and decisions intact" needs it. |
| Any signed-in user may practise once `LEARNING_PRACTICE_ENABLED` is on; paid AI stays owner-only. Keith, October 28. | Practice without AI costs nothing; the flag is the rollout and withdrawal switch. |
| A JWT practice API ships with 3a; delete ships in 3b; export stays in checkpoint 5. Keith, October 28. | One service behind web and API, an HTTPie target, and the contract Expo will reuse; saved work becomes removable as soon as discussion data exists. |
| The AI worker is a thread in the web process for Milestone 1. Keith, October 29. | No new infrastructure for one owner's low volume. It uses the planned PostgreSQL job table and leases, so a Procfile `worker:` dyno later is a one-line change. Deploys and Heroku's daily restarts interrupt an in-flight reply, which becomes interrupted with an explicit retry. The thread starts only from the web entry point, never from the app factory, CLI commands, or tests. |
| Learning uses OpenAI through its own project and key, separate from JobWizard's `OPENAI_API_KEY`. Keith, October 29. | The provider's spending limit and usage reports then cover Learning alone, behind the app's $50 cap. The model is chosen during the reviewed live evaluations; development uses mocked responses. |
| Interviewer behaviour is versioned in code, pinned when a session starts, and recorded on every AI request. Keith, October 29. | Prompts and profiles change independently of reviewed content, with no content version bump; exercises keep naming their interaction style. This departs from the revised plan's table, which put the behaviour profile/version in the exercise's facilitator section. |
| Context compaction is deferred out of Milestone 1. Keith, October 29. | It was Milestone 1's riskiest piece (it can promote assumptions or revive superseded decisions), and the learner's brief now holds decisions and assumptions durably. One exercise fits a larger configurable allowance; the 24-turn check-in and a specific stop when essential context cannot fit remain. Revisit after trial sessions show real lengths. |
| Misconception mappings and a follow-up review arrive with checkpoint 5. Keith, October 29. | Content schema 2 and exercise version 2 come first in checkpoint 5, before the human content review, so the reviewer sees the whole exercise once. A finding the learner accepts offers its linked questions as an extra, labelled review; ratings still go through the scheduler, and nothing changes silently. |
| Feedback reports deterministic checks before AI judgment. Keith, October 29. | When an API definition is written as JSON or YAML, a parse error is a confirmed finding (Python's `json`; PyYAML's safe loader with aliases refused). Nothing executes. SQL parsing would need a new dependency and approval. |
| Checkpoint 4 splits into 4a (durable replies against a scripted fake provider), 4b (the interviewer), and activation. Keith, October 29. | Claims, leases, fencing, budgets, and recovery are proven before any prompt or paid call, and each part can be reviewed on its own. |
| Revealed requirements are a separate read-only list beside the scenario, computed from disclosure records; the interviewer adds nothing to the learner's brief. Keith, October 29. | The brief stays the learner's own, and scenario facts never mix with their assumptions. Model "interpretation" entries are deferred along with compaction. |
| When a transcript outgrows the context allowance, the learner can choose **Continue with recent messages**. Keith, October 29. | Nothing is truncated silently or deleted: the choice is a recorded entry in the transcript that later requests honour. |
| Approved with the checkpoint 4 plan, October 29: pause stops pending replies and a running reply's next paid call, but a call already in flight finishes and its reply is kept; Send is refused while a reply is live (409 `reply_pending`, draft kept) while saving continues; retries are never automatic; `POST …/turns` returns 202 when a reply is queued and 201 otherwise. | A paid reply isn't thrown away. One live reply per session keeps the transcript in order. A call with an unknown outcome may already have been charged, so it is repeated only when the learner asks. |

## What exists in the repository

### Content and publication

[The idempotency package](../curriculum/idempotency/catalog.json) has six version-1 items: concept `idempotency`; questions `idempotency:timeout`, `idempotency:race`, `idempotency:scope`, and `idempotency:external-effect`; exercise `idempotent-order-api`. The three lesson sections are `overview`, `retries`, and `design`. Its prerequisites include descriptive prior knowledge; it does not fabricate prerequisite concept records for content not yet authored.

The exercise expects `api`, `schema`, and `algorithm` artifacts; an exercise may expect at most 20, so they fit one practice form and one save. Its schema separates `brief`, `facilitator`, and `assessment`. The brief contains scenario, objectives, functional/nonfunctional requirements, prerequisites, artifact expectations, and public assessment dimensions. Server-side content contains disclosure cues/facts, interviewer instructions, allowed hints, alternative approaches, anchored rubrics, and remediation links. Do not copy those private packets into future UI fixtures, HTML, bundles, or session exports.

`schema_version` versions the catalog; exercise `spec_version` versions the simulation contract; each item's integer `version` versions its content. Supported catalog/spec pairs are 1/1 and 2/2. Strict schemas reject unknown fields, invalid or duplicate IDs, duplicate JSON keys, invalid references, prerequisite cycles, and invalid versions, including booleans masquerading as integers. Markdown paths cannot escape the package, including through symlinks. Resolved Markdown text participates in the checksum.

`CurriculumItem` stores stable ID and kind. `ContentRevision` uses `(item_id, version)` as its primary key and stores schema version, checksum, resolved JSON payload, import timestamp, and publication attestation. Content immutability is enforced by application import paths; it is not a database permission boundary against administrators.

`validate-curriculum` validates files without accessing database tables. `import-curriculum` requires PostgreSQL and defaults to rollback. `--apply` saves drafts. Publication additionally requires `--publish`, a real `--reviewed-by`, and actual `--reviewed-on` date. The importer owns a separate transaction, uses a PostgreSQL advisory transaction lock to serialize rare catalog writes, and atomically imports/publishes the batch. Ordinary review operations do not acquire that lock.

Repeating identical content is safe. Changing a payload under the same ID/version fails. Publishing behind a newer published revision fails. Omitting items does not delete or retire them. There is no startup/migration content seed, retirement workflow, or content administration UI.

### Feedback content foundation (checkpoint 5a)

[The version-2 draft](../curriculum/idempotency/catalog-v2.json) retains the same
six stable IDs and adds four `assessment.misconceptions` mappings: uncertain
outcomes, simultaneous absence checks, operation identity, and remote effects.
Each has a stable ID within the exercise, rubric dimension, description,
evidence guidance, remediation concept/section, review question IDs, and a
suggested next step. Guidance requires evidence and allows valid alternatives;
the mappings themselves are not diagnoses or executable checks.

The validator checks dimensions and the full reference closure. Linked questions
must belong to the remediation concept. Duplicate mapping/question IDs, unknown
fields, empty or oversized collections, unsupported versions, and invalid
targets fail closed. `evaluator_view` dispatches by the pinned exercise's spec
version; v1 keeps its old projection. No mapping reaches learner HTML/API DTOs,
opening prompts, disclosure selectors, or interviewer calls. The public source
repository remains inspectable.

The original catalog and Markdown are unchanged. All six v2 item revisions
advance because the existing immutable checksum includes the catalog schema
version. Lesson/question content, stable review IDs, the learner brief,
facilitator, and prior assessment text are unchanged. No importer/checksum
rewrite, database migration, automatic publication, progress reset, or session
backfill was needed. Draft v2 does not hide published v1; after explicit
publication, new sessions use v2 while older sessions and open review attempts
stay pinned. Publication and review coexistence are tested on PostgreSQL.

This checkpoint does not add submission messages, feedback generation/storage,
deterministic artifact checks, accepted findings, or follow-up review. The
disposable preview still loads v1. Use the [5a REPL guide](learning-checkpoint-5a-test-guide.md)
and [curriculum contract](../curriculum/README.md) to inspect the new content.

### Web Learn and Review

All Learning website routes require Flask-Login through the blueprint's `before_request` guard, including home, references, and the long-form article. The separate JSON APIs retain JWT authentication. `/learning/` prioritizes continuation; references and personal flashcards have dedicated catalogs. `/learning/concepts/idempotency` shows one lesson section at a time, with native hash links, a mobile section picker, and the retry simulation beside the retry explanation. Without JavaScript, every section is readable. The simulation is reviewed application JavaScript; curriculum files cannot inject executable code. Markdown uses Marked and DOMPurify at the locked versions, loaded from jsDelivr, with a restrictive allowlist; only the DOMPurify tag carries a checked SRI hash. If they fail to load, escaped source text remains readable.

Learn, Review, Discuss, and Build share `concept_shell.html` and `_concept_workspace_header.html`. `navigation.py` carries an optional `practice_session` UUID through lesson/review URLs, reveal/rating forms, remediation links, and completion links. An explicit session must belong to the current user and concept or returns 404; otherwise navigation chooses the newest open session for the concept's exercises. `practice_service.session_summary` reads only owned, pinned metadata. Practice rendering builds links from its existing session data, without another database query on recovery paths. When practice is disabled, Learn/Review make no practice queries. A first-use mode opens a read-only start page; only the existing CSRF-protected POST creates a session.

`GET /learning/concepts/idempotency/review` selects a due question. **Show answer** performs another GET carrying `card_id`, `content_version`, `expected_revision`, and `request_id`. The initial learner response omits the answer and explanation. Ratings are `Again=0`, `Hard=3`, `Good=4`, `Easy=5`.

POSTing the CSRF-protected form calls the existing `rate_card_for_user`. On PostgreSQL, a user-row lock serializes saves; progress, review log, and durable receipt commit together. A replay with the same UUID/payload returns the recorded result; reusing the UUID with a different payload or submitting stale progress produces a conflict. Successful saves return 303 then a fresh queue GET. Save failures preserve the attempt for explicit retry. Version pinning allows an already-open question to finish against its original content revision.

Committed reviews survive navigation and reopening because the queue derives from database progress. Navigation preserves the practice session and its confirmed work, not unsaved drafts or an unfinished review attempt across arbitrary mode changes. The pinned reveal URL still restores its original attempt. There is no new browser-side review queue or client storage; Save/Send and the existing leave-page warning protect unsaved practice text.

The JSON API under `/api/v1/learning` remains the legacy notes/review/rating/receipt surface and does not expose concepts; practice sessions have their own API (below). The concept web adapter feeds the shared scheduler without changing that API's due queue. Curriculum and legacy note namespaces are checked to prevent accidental sharing of progress identities.

All Learning responses, including login redirects, use `Cache-Control: private, no-store`. The shared base template omits Google Analytics and Hotjar on authenticated Learning pages. Sentry reporting is strictly allowlisted in `project/monitoring.py`. Practice routes and AI replies have their own leakage checks (below); provider errors get theirs with the provider call in 4b. Static assets and the source repository remain public.

### Practice sessions (checkpoints 3a and 3b)

`LEARNING_PRACTICE_ENABLED` (default off) gates every practice route and query. With it on, a concept page's **Apply it** section starts a session for a published exercise (`POST /learning/practice`), and the Learning home features the newest open session under **Continue practice**. Opening that link is read-only; a paused session stays paused until an explicit workspace action. The concept page still provides its existing session list.

A `PracticeSession` pins the exercise's `(item_id, version)` and records the interviewer's authored `opening_prompt` as turn 1. That comes from `opening_view`, the only facilitator field a learner ever receives. `ArtifactRevision` rows are immutable: each changed save adds revision N+1 with title, format, notation (`language`), text, and SHA-256. `SessionMessage` is the ordered record of turns and brief snapshots, `SessionMessageArtifact` holds each turn's citations, and `PracticeReceipt` holds mutation results. Composite foreign keys keep citations inside one session, and receipts store a payload hash, never text. Deletes cascade from the session in the database.

`practice_service` is the only writer. Every mutation takes the owner's user-row lock, checks its receipt, then reads owner-scoped rows fresh. A save is all-or-nothing across artifacts:

- Text equal to the saved head is unchanged, and no revision is written.
- An edit made on the current head writes the next revision.
- A box left untouched whose artifact changed elsewhere keeps the newer revision.
- Anything else is a conflict, and nothing is written.

Line endings are normalized to LF, and revision 0 counts as an empty body. Limits: 64 KiB of UTF-8 per artifact, NUL characters rejected before the database, and 2 MiB per request.

Checkpoint 3b adds the discussion record:

- **Brief.** The learner's entries are assumptions, open questions, decisions, and a next step. Each has a stable ID, basis `learner`, text, a pin flag, and optional sources: up to ten turns or artifact revisions of the same session. Every edit stores a full snapshot (`kind='brief'`, role `learner`) with the next revision number, using the same four-way rule as artifacts. Limits: 50 entries of 2 KiB each. Initial requirements come from the exercise brief and are not copied in.
- **Turns.** A learner turn cites the current revision of every artifact (`SessionMessageArtifact`) and records the brief revision in its `data`. On the website, Send saves the artifacts and brief and appends the turn in one transaction. API clients save first, then cite. A turn needs an up-to-date view: a conflict, an untouched artifact or brief that changed elsewhere, or a turn newer than `expected_sequence` refuses the whole request. Only turns count for `expected_sequence`, so brief and later system records never cause false conflicts. Turns are limited to 8 KiB.
- **Pause and resume.** Each is an idempotent status change with a receipt. Any learner save or turn resumes a paused session. Since 4a, pausing also cancels a pending reply and stops a running one before its next paid call. Nothing pauses, resumes, or reopens a `completed` session; checkpoint 5 decides what completion allows.
- **Delete.** It takes the owner lock and deletes the session row; database cascades remove its revisions, messages, citations, and receipts. There is no receipt to replay, so a repeat reports not found. It refuses to run on a SQLite connection without foreign-key enforcement, because SQLite would otherwise skip the cascades and keep every row.

The workspace (`/learning/practice/<id>`) is one Flask-WTF form whose CSRF token lasts 24 hours, with Discuss (scenario, conversation, message box, brief editor) and Build side by side on wide screens. **Send message**, **Save work**, and **Save and pause** (or **Resume**) all submit the whole form, so no button discards other work; a hidden first button makes Enter in a field save, never send. Saving with a typed message re-renders the page with the message kept, flagging anything that changed elsewhere while it was written. Every rejected request re-renders the learner's text and message:

- **400:** an expired CSRF token or invalid input, shown beside the artifact, brief, or message.
- **409:** a conflict or an out-of-date Send. Saved versions appear beside the learner's text, untouched parts refresh, and new turns are marked; saving or sending again is an informed choice.
- **503:** a database failure. A standalone page that needs neither the database nor the shared layout holds the artifacts, brief entries, and message, and retries the same action. An unknown outcome keeps the request ID, so a retry replays rather than duplicates.

`/learning/practice/<id>/delete` is a confirmation page that says there is no undo and that backups are separate. Deleting returns to the lesson; repeating it, or targeting another account's session, lands on Learning with "doesn't exist or was already deleted".

Logs carry only exception class, SQLSTATE, and constraint name (`describe_failure`), and SQL parameters are hidden in every environment. History pages are addressed by artifact ID and revision number. A small script adds an unsaved-changes prompt and a UTF-8 byte counter; nothing depends on it.

The JWT API under `/api/v1/learning/practice` uses the same service: list, start, read, and delete sessions; `PUT …/artifacts/<artifact_id>` and `PUT …/brief`; `POST …/turns`, `POST …/pause`, and `POST …/resume`; revision history; and receipts. In the session detail, `brief` is the exercise's authored brief and `session_brief` is the learner's; `PUT …/brief` replaces the latter. Responses are explicit field lists. The 409 codes are `stale_artifact` (with the saved bodies), `stale_brief` (with the saved brief), `stale_transcript` (with `latest_sequence`), `request_conflict`, and (from 4a) `reply_pending`; validation errors name a `part` (`artifact`, `brief`, or `turn`) and a `field`. Each 503 says whether to retry with the same request ID.

### Durable replies (checkpoint 4a)

Replies are tracked requests in PostgreSQL, run by a worker thread and, in 4a, answered by a scripted fake provider. AI stays off until `LEARNING_AI_ENABLED` is set, and `PRICES` holds only the models evaluated at activation.

**Access.** `LEARNING_AI_ENABLED` (default off) turns replies on. `LEARNING_AI_OWNER_EMAIL` names the one account that gets them; it must match exactly one verified user, ignoring case, or AI is off. `LEARNING_AI_PROVIDER` is `openai` (the 4b call process, the default) or `fake`. With `openai`, both calls default to `gpt-6.1-sol` at low reasoning, chosen at activation (`practice_service.DEFAULT_MODELS` and `DEFAULT_REASONING_EFFORT`); `LEARNING_AI_MODEL`, `LEARNING_AI_SELECTOR_MODEL`, and `LEARNING_AI_REASONING_EFFORT` override them. Models must be priced for `LEARNING_AI_SERVICE_TIER`. The key, `LEARNING_OPENAI_API_KEY`, is read from the environment at call time, never from config. Anyone may practise; other accounts' turns are saved without a reply.

**Requests.** Send commits the turn and, when AI is available, a `pending` `ai_request`, together. A claimed request is `running`; it ends `completed`, `failed`, `interrupted`, or `cancelled`, with a content-free error code. Partial unique indexes allow one live request per session and one completed reply per turn.

- A live request refuses another Send with 409 `reply_pending`; saving continues.
- A stale request reads as `interrupted` everywhere, so nothing waits on it. Stale means pending for more than two minutes (`LEARNING_AI_START_SECONDS`) or once AI is unavailable, or running past its lease. Send, Ask, and pause record that state; delete removes the request with the session; the worker's sweep also tidies rows.
- **Ask for a reply** (shown as **Retry the reply** after a failure) is one action for the latest learner turn, when nothing is live. If a reply reached that turn meanwhile, asking still saves the page and reports `answered`.
- Pause cancels a pending reply; delete cascades. The ledger keeps the cost.

**Worker.** The thread `learning-ai-worker` starts only from `run.py`'s `main()`, when the switch is on and a provider is available (once under the debug reloader). It never starts from `create_app`, CLI commands, or tests. `flask learning-worker` runs the same loop in the foreground, for a future `worker:` dyno.

1. Each pass sweeps stale rows, then claims the oldest fresh request by compare-and-swap, skipping profile versions this release doesn't know (deploy overlap).
2. Before each paid call, one transaction checks that the request is still running with its claim token and an unexpired lease, the session is active, and AI is still available. It extends the lease to the call's deadline (`LEARNING_AI_CALL_SECONDS`, 60) plus a margin (30), and reserves the worst case.
3. After the call, its charge settles in a transaction of its own.
4. The reply is written under the owner lock, fenced on status and token only, so a late reply that nothing has marked interrupted is kept. A database error retries the write, never the call.

Lock order everywhere: owner (`FOR NO KEY UPDATE`), request, session, budget, charge. Owner-side writes lock the live request row before changing the session; the worker's checks never take the owner lock.

**Inputs** are pinned to the turn: its cited revisions, the brief revision it was sent with, and the transcript up to it. Edits made while a reply runs never leak in, and the reply cites the same revisions. `interviewer_view` passes only the authored instructions, revealed facts, and a supplied hint. Cues, unrevealed facts, other hints, and evaluator material never reach a request. The `interviewer-1` rules in `project/learning/interviewer.py` are placeholders until 4b; a profile version never changes once released.

**Budget.** `LEARNING_AI_MONTHLY_CAP_USD` (50) and `LEARNING_AI_WARN_USD` (40) apply per UTC month.

- Committed spend is settled cost plus every unsettled reservation, including uncertain ones.
- A reservation is a strict upper bound: the request body's UTF-8 bytes (a token is at least one byte) plus `LEARNING_AI_MAX_OUTPUT_TOKENS` (1,200), at the model's and tier's rates, including any long-context tier. An advisory lock serializes reservations, which never take the month past the cap.
- A reply is queued, or offered again, only when its worst case fits. That is priced from the same request body the worker will send, with every input byte priced as a cache write, the dearest input rate. The month reads as used up once even the smallest reply (its output alone) can't fit.
- A charge settles from usage (or at the reservation, without usage), is released after a definite refusal, or stays reserved when the outcome is unknown.
- The ledger holds no learner text and no foreign key to sessions, so it outlives delete. `PRICES` and `PRICING_VERSION` are filled at activation, with input, cached-input, cache-write, and output rates; the fake provider has its own `FAKE_PRICES`. A settled charge records its input, cached, cache-write, and output tokens, so they explain its cost.

**Website.** A status region under the conversation says whether a reply is coming or arrived, failed or was interrupted (with **Retry the reply**), was cancelled by pause, isn't available for this account, or has no room in the budget. Retry, Ask, and the no-JavaScript **Check for the reply** are workspace-form actions that also save. A script polls `GET /learning/practice/<id>/reply?after=<sequence>` every 1.5 seconds, then every 5 after 30 seconds. It inserts each newer turn marked New, advances `expected_sequence`, and rewrites the status region only when its words change, so screen readers don't repeat them. A dropped connection or server error, such as a restart, is retried after 5, 10, 20, then 30 seconds. A sign-out redirect, a 4xx, a non-JSON answer, or a sixth failure in a row stops polling: Send comes back (the server still refuses it while a reply is live) with a note to reload. The script never touches a field. Send is disabled while a reply is live. The owner sees a spending banner from the warning line, or once the month is used up.

**API.** `POST …/turns` returns 202 with a pending reply, otherwise 201, plus `reply` and `latest_sequence`. `GET …/sessions/<id>/reply?after=` returns the reply's state and newer turns; `after` must be a whole number and defaults to 0. `POST …/sessions/<id>/reply` takes exactly `{request_id}` and returns 202 when a reply is queued. It returns 200 when none is: the turn already has one (`answered`), or AI can't reply now (`unavailable`, with a reason). The session detail adds `reply` and `ai_budget` (the owner's only).

**Privacy and telemetry.** Requests, the ledger, receipts, logs, and Sentry hold no learner text or model output; sentinel tests check each. The worker logs a fixed code per failure. Sentry gets `operation=learning.reply` with codes from a fixed list, reported explicitly because threads aren't captured automatically.

### The interviewer (checkpoint 4b)

The interviewer (`project/learning/interviewer.py`, profile `interviewer-2` for new sessions) answers with up to two calls, both through the 4a worker, fencing, and ledger.

**The selector** sees only the learner's latest message and the clarification cues of the requirements still hidden (`content_schema.selector_view`): no facts, hints, conversation, or reference. Its strict schema offers only the hidden IDs, and `hint_requested` only while permitted hints remain; with neither left, the call is skipped. The server checks the answer again (`parse_selection`). If the selector fails, so does the reply: its cost settles, nothing is revealed, and asking again reruns both calls.

**The reply** sees the rules, the exercise's authored instructions, and the scenario. It also gets the facts revealed before the turn and those just revealed (marked as new), the learner's brief at the turn's revision, the cited artifacts, the transcript, and the next permitted hint only when asked (`interviewer.facilitator`). Its input is ordered for prompt caching: fixed parts, then the append-only transcript, then what changes. Learner text travels only in `input`, never in `instructions`. A profile is released with its first live evaluation and never edited after; a test pins each released version's text by hash, and sessions keep the version they started with. `interviewer-1` told the reply to call anything outside the revealed facts unspecified, which covered hidden requirements too. `interviewer-2` fixes that: the reply never calls a detail unspecified or says no other requirements exist, answers a direct question about the learner's approach, asks the learner to make design choices, and keeps hint bookkeeping out of replies; its selector doesn't count "what next?" as a hint request.

**Records.** The reply turn is followed by an interviewer `context` record (`revealed`, `turn_sequence`) and an `assistance` record (`hint_index`), in one transaction. What counts as revealed, and which hint comes next, is read from the records before the turn, so retries and late replies can't shift it. Revealed requirements appear in a read-only list beside the scenario (`revealed_requirements` in the API), each linked to its reply, and hinted turns are labelled **Hint**.

**The context allowance.** `LEARNING_AI_CONTEXT_BYTES` (a 512 KiB placeholder) bounds what a reply reads, in UTF-8 bytes of its instructions and input; a token is at least one byte. It is checked when a reply would be queued or offered, against the worst case (every hidden fact revealed and a hint given), and again on the real request before the reply's paid call (`failed`/`context_too_large`).

- When the conversation doesn't fit, **Continue with recent messages** records a learner `context` entry. Replies then read from the earliest message that fits, found by binary search, and keep doing so. Nothing is deleted, and the transcript marks the spot. It is `request_reply(context="recent")`: the `recent` workspace action, or `context: "recent"` on the API.
- When even the latest message with the brief and artifacts doesn't fit (`essential_too_large`), the learner is told the largest part to shorten.

The budget check prices the selector's and reply's worst cases together.

**The check-in.** After `LEARNING_AI_CHECK_IN_TURNS` (24) learner turns, a notice offers to keep going or pause; nothing stops. The API detail adds `learner_turns` and `check_in_due`.

**The OpenAI call** runs in a child process: `project/learning_ai_call.py`, started with `python -I` by `project/services/learning_ai_provider.py`. It imports only the standard library and `requests`, and gets an environment of the key, `PATH`, CA settings, and the trusted interpreter library directory on Linux; its stderr is discarded. It reads one size-capped request on stdin, guards against an orphaned start, and enforces a hard alarm deadline. It refuses plain HTTP except to `127.0.0.1` or `localhost` and never follows a redirect. It caps the response size and reports usage on every path that read a reply. Codes map to the ledger:

- 400, 401, 402, 403, 404, and 429 release the reservation;
- refusals, cut-off replies, and invalid output settle it from usage;
- timeouts, 5xx, and connection failures keep it.

`provider_for` uses this provider only when `LEARNING_OPENAI_API_KEY` is set; `LEARNING_AI_BASE_URL` points it at a local stand-in in tests. Starting the process took about 66 ms per call locally. The fake provider answers selector calls from a script, or by spotting a message that repeats a cue (`fake_selection`).

**Evaluation.** `flask learning-eval` runs the reviewed cases in `tests/fixtures/interviewer/cases.json` through the real request builders. It checks the selector's answers, that each request carries only what it may and everything the learner earned, and the replies for leaks, taking every expectation from the case rather than from the builders (`project/learning/interviewer_eval.py`; `project/learning/evaluation.py` is the review scheduler's, unrelated). Against the fake it tests the plumbing; with `--provider openai` at activation it tests the model and writes `docs/evaluations/learning-interviewer-<date>.json`.

### Migrations

| Revision | Change | Downgrade consequence |
| --- | --- | --- |
| `a4b5c6d7e8f9` → `b5c6d7e8f9a0` | Adds `curriculum_item` and `content_revision`; no user/progress seed or rewrite. | Removes catalog tables and their content. |
| `b5c6d7e8f9a0` → `c6d7e8f9a0b1` | Adds nullable `review_log.content_version` and composite FK to the exact content revision. Existing logs stay null. | Removes version linkage while retaining rating/scheduling history. |
| `c6d7e8f9a0b1` → `d7e8f9a0b1c2` | Adds `practice_session`, `artifact_revision`, `session_message`, `session_message_artifact`, and `practice_receipt`, with named constraints and database cascades. | Removes every practice session and its revisions, messages, citations, and receipts; catalog and review data stay. |
| `d7e8f9a0b1c2` → `e8f9a0b1c2d3` | Adds `ai_request` and `learning_ai_charge`, `practice_session.profile_version` (existing rows get `interviewer-1`), and the `reply` receipt operation. | Removes every reply request, the spending ledger, profile versions, and reply receipts. Interviewer turns already written stay. |
| `e8f9a0b1c2d3` → `f9a0b1c2d3e4` | Adds nullable `learning_ai_charge.cache_write_tokens` (October 30); earlier charges keep null. | Drops the column; every charge keeps its cost. |
| `f9a0b1c2d3e4` → `a0b1c2d3e4f5` | Allows `submit` receipts; no new table or copied artifacts. | Removes submit receipts to restore the old constraint; preserves snapshots, artifacts, turns, and review history. |
| `a0b1c2d3e4f5` → `b1c2d3e4f5a6` | Adds `practice_feedback`, same-session request/snapshot FKs, the request composite unique key, and `feedback` receipts. | Removes derived feedback, feedback requests/receipts; retains snapshots, artifacts, conversation, review history, and billing metadata. |

These migrations were exercised on populated disposable PostgreSQL fixtures, including downgrade and ORM/schema parity. CHECK constraints are verified separately, because Alembic's comparison ignores them. Do not downgrade real content as a routine feature rollback. To withdraw practice while keeping saved work, turn `LEARNING_PRACTICE_ENABLED` off.

## Session and feedback architecture

This section distinguishes the implemented snapshot boundary from the remaining feedback work.

### Session record: what later checkpoints add

Checkpoints 3a through 4b implemented sessions, artifacts, turns, the brief, pause/resume, delete, interviewer replies, and the records 4b adds to the same ordered `SessionMessage` table (above): interviewer `context` records for revealed requirements, `assistance` records for hints, and learner `context` entries for Continue with recent messages. The interviewer adds nothing to the learner's brief, which keeps only `learner` entries; model "interpretation" entries are deferred with compaction (Keith, October 29). Explicit style changes would be `assistance` records too. What remains:

- **Submission snapshots are implemented in 5b**, using `SessionMessage(kind="submission")` and `SessionMessageArtifact` references. See the snapshot contract below. Sessions stay editable; an explicit completion/lock action remains outside this checkpoint.

Responses and feedback must identify which revisions they reviewed. AI suggestions never overwrite learner artifacts automatically. Persisting foreign IDs, reading another user's history, and replaying another user's request must keep failing; tests for each exist for 3a and 3b.

### Interview behavior and disclosure

The interviewer challenges reasoning and asks focused follow-ups without prematurely teaching a reference solution. Coaching gives graduated help; collaborative scoping negotiates requirements and dependencies; design review critiques alternatives. Changing from interview to coaching must be explicit and recorded. Do not implement the additional profiles merely because their schema values exist.

For hidden constraints, a bounded selector receives the learner turn and authored clarification cues and returns eligible IDs. Validate IDs server-side; provide only approved facts to the conversational call. The selector does not receive reference solutions, and the conversational call does not receive all unrevealed facts. Commit successful disclosure with the response and visible requirements record. Unspecified facts remain unknown; learner assumptions do not become scenario facts.

4b built this (above): `selector_view` gives the selector cues only, `interviewer_view` gives the reply revealed facts and a requested hint, and disclosure commits with the reply. Profiles live in code with their own version, pinned when a session starts. The live evaluations at activation measured the model's behaviour (October 29 and 30; see Recommended next checkpoint).

### Durable AI requests and spending

Checkpoint 4a implemented the request lifecycle, the worker thread, owner-only access, the $50/$40 budget with reservations, and recovery (above). Database deduplication cannot guarantee exactly one provider charge after an uncertain network outcome, which is why uncertain reservations keep counting and retries wait for the learner.

4b added the OpenAI call process (above); the selector's charge settles before the reply's reservation.

- **Activation** (done locally, October 30): Keith created the Learning OpenAI project and key and set a $50 hard limit. Three rounds of live evaluations chose `gpt-6.1-sol` with low reasoning for turns, and the model, service tier, prices, `pricing_version`, p95 latency, and cost per session are recorded under Recommended next checkpoint. Checkpoint 5c defaults feedback to the configured model at medium reasoning. The November 2 bounded review supports keeping Sol/medium: 24 saved results, median 20.759 seconds, observed p95 25.203 seconds, $0.519980 total. See the evaluator report for scope and limitations. Verify access and current pricing again before production enablement. Do not silently switch models after failures, or couple Learning to JobWizard's extraction workflow. Before a paid call on a new deploy target, verify the isolated child starts using a fake provider. Heroku's Python requires its own shared-library directory: on Linux the child derives `LD_LIBRARY_PATH` from `sys.base_prefix / "lib"`. It never inherits arbitrary loader paths, `LD_PRELOAD`, Python paths, or other application credentials. The November 13 deployment caught this startup failure before an API call; 79 targeted local tests and all 18 provider tests on Heroku passed after the fix. The failed request's $0.007315 reservation remains counted conservatively, and paid recovery requires an explicit new request. `requests` verifies TLS with certifi, so only `REQUESTS_CA_BUNDLE` changes the trust store.

Disclosure, evaluation passes, and synthesis all consume this budget, as would compaction if it returns. Hosting is separate. At the cap, paid generation stops while reading, review, editing, saving, export, and later resumption continue.

### Continuity and context

24 learner turns is a configurable progress check-in (4b). Continuation stays in the same session. Suggested duration, input allowance, output limits, and deadlines are server policy. The defaults were checked against Sol's live calls at activation and kept: a 60-second call deadline (the slowest of 216 calls took 7.1 s), 1,200 reply and 200 selector output tokens (the most any call used was 175 and 47), and a 512 KiB context allowance (Sol's window is 1,050,000 tokens and a token is at least one byte, so a full allowance always fits).

Compaction is deferred out of Milestone 1 (Keith, October 29). Each call includes pinned instructions and disclosed facts, the current session brief, the current artifact revisions, and the whole transcript, within a configurable input allowance larger than the original 32,000 tokens. Keep prompts append-only so provider caching applies.

The learner-visible, editable brief preserves requirements, disclosed constraints, assumptions, open questions, decisions/rationale/alternatives, current artifact references, assistance, and next step. Distinguish authoritative facts, learner decisions, and unconfirmed model interpretations. Support pinned/corrected entries with links to original evidence.

If the transcript cannot fit, the reply fails with `context_too_large`, explains why, and offers **Continue with recent messages** (Keith, October 29). If even the essential context cannot fit, stop with a specific explanation naming the largest part; do not truncate silently or complete the session automatically. If compaction returns later, it must not delete transcript or artifacts, promote assumptions to facts, revive superseded decisions, or substitute an obsolete artifact summary for the selected current revision.

Required deterministic recovery case: more than 24 learner turns, a worker restart, a revised assumption, and multiple artifact revisions, with the correct current state preserved. Also cover exhausted budget and oversized essential context without data loss. Forced and failed compactions are no longer required.

### Submission snapshot contract (checkpoint 5b)

- `save_and_submit` atomically saves the complete artifact/brief view, checks syntax, appends a submission record, and records a `submit` receipt. It uses the existing owner → live request → session lock order. Stale artifacts (including untouched ones), brief revisions, or conversation turns refuse the entire write. An in-flight interviewer reply blocks submission; reread after it arrives.
- The record pins exercise ID/version (therefore rubric), exercise spec/profile versions, **all-record `through_sequence`**, latest conversation `turn_sequence`, brief revision, and each artifact revision (including virtual empty revision 0). Existing citation rows reference saved artifacts; bodies are not copied. Future evaluators must read original records only through that boundary, including disclosures, assistance, and continuation choices.
- Results store `checker_version="syntax-1"`, notation, status/code, static message, and optional one-based line/column. Reads and receipt replays never rerun checks. Snapshot timestamps serialize in UTC regardless of PostgreSQL connection timezone. Changing checker behavior requires a version bump; preserve previous results.
- Python `json` rejects non-JSON NaN/Infinity. YAML uses a bounded `SafeLoader`, never unsafe construction. Aliases, duplicate keys, unsupported YAML tags/keys/values, and multiple documents are `not_checked`, not design errors. Checks allow up to 64 KiB and nesting 64; YAML additionally allows 10,000 nodes. SQL/Python/TypeScript/pseudocode/plain text are not executed or parsed. No dependency was added. Parser exceptions are never returned or logged.
- JSON API: `POST /api/v1/learning/practice/sessions/<id>/submissions` takes exactly `{request_id, expected_sequence, edits, brief}`. Each edit is `{artifact_id, base_revision, language, body}` and every authored artifact is required. Brief is `{base_revision, entries}`. The sequence is the last **turn**, as with Send. It returns 201 with `{session_id, submission, artifacts, brief, status}`; the original request replays identically. Existing conflict/503/receipt recovery semantics apply.
- Session detail gains `submissions` in newest-first order. `GET .../submissions/<sequence>` returns `{session, submission, session_brief, artifacts}` with saved notes and current artifact numbers for comparison. Web detail is `/learning/practice/<id>/submissions/<sequence>`. Both require ownership and are private/no-store. DTOs use explicit allowlists, never evaluator packets. Private source remains readable in the public repository.
- **Build → Checks** uses the native CSRF form, preserves an unsent message, opens the results after success, and retains standalone rescue/retry behavior. Older checks link to exact saved revisions and label newer saved work. Save/check works with JavaScript unavailable. Deletion cascades through snapshots/citations/receipts. Budget exhaustion does not prevent checks; no AI request, charge, score, review rating, or progress update is created.
- Reference parser behavior: [Python JSON](https://docs.python.org/3.13/library/json.html), [PyYAML](https://pyyaml.org/wiki/PyYAMLDocumentation). This is syntax evidence only, not OpenAPI/schema validation or assessment of engineering correctness.

### Generated feedback (checkpoint 5c)

**Approved decision, November 2:** assess one complete snapshot in one bounded call.
If it is too large, explain that no assessment happened; never truncate it or start
multiple calls silently. The original revised plan remains the historical approval
record; this is a sequencing refinement for 5c. Session editing remains allowed.

- `project/learning/evaluator.py` defines `evaluator-1`: a strict structured result
  with a summary and findings (`strength`, `concern`, `tradeoff`, `not_observed`).
  Every public assessment dimension must be covered. Findings give concrete next
  steps; concerns are judgments for review, not confirmed errors. Syntax checks
  remain separate, deterministic, and unchanged. There is no score or grade.
- `project/services/feedback_service.py` builds private inputs from the pinned
  exercise/assessment, all original conversation turns through the submission,
  the snapshot's artifact revisions, historical revisions cited by those turns,
  and the snapshot's notes. Empty revision 0 is explicit. It includes revealed
  versus unrevealed requirements, recorded hint counts and continuation choices.
  **Continue with recent messages never truncates evaluation.** Later changes
  never enter these inputs; coverage records exactly which snapshot was assessed.
- Evidence must be an exact substring of an original learner turn, artifact body,
  or saved note. The server supplies source IDs and resolves locations; model URLs,
  fabricated quotes, interviewer quotes presented as learner evidence, unknown
  dimensions/mapping IDs, extra fields, and incomplete dimension coverage fail.
  Misconception IDs require an evidenced concern in their authored dimension.
  Remediation resolves to authored concepts/sections, preferring a matched
  misconception's target. Private descriptions, guidance and mapping IDs are not
  included in learner responses. A verbatim-copy backstop rejects complete private
  passages of at least 20 characters absent from learner-visible inputs; this is
  **not** a guarantee against semantic disclosure or technical misjudgment.
- `PracticeFeedback` holds validated findings/coverage, with a request PK and a
  unique submission FK. Same-session composite FKs prevent cross-session links.
  `AIRequest.kind='feedback'` uses the existing `turn_message_id` as its input
  **submission** ID; completed feedback never appends an interviewer turn.
  The worker claims known interviewer/evaluator profiles and dispatches by kind.
  Completion and next-call checks reject cross-kind operations.
- One completed feedback result per snapshot. Repeated request IDs replay the
  receipt; different IDs for the same live/completed snapshot reuse the request.
  Failure needs an explicit new request; revised work needs a new snapshot.
  Receipts/requests/charges never contain learner text. Sequential attempt creation
  times are monotonic even with a frozen clock, so reads identify the latest retry.
- The shared live-request index allows only one interviewer or evaluator request
  per session. Saving works during evaluation; send/reply/new submission returns
  `feedback_pending` until it finishes. A workspace notice links to that snapshot.
  Requesting from a paused session resumes it. Pausing cancels pending generation;
  an already running call may still save its result, matching interviewer behavior.
  Deletion fences completion and cascades feedback; the content-free charge remains.
- The worker makes exactly one `purpose='feedback'` call, through the existing
  process-isolated provider and budget reservations. It retries only transient
  database completion writes, never paid calls. Unknown outcomes keep the reserved
  amount; invalid generated output is charged but not stored as usable feedback.
  Existing owner, lease, start/call deadlines, monthly cap, pricing and lock order
  remain in force. Full serialized request bytes are checked before queueing and
  again before calling; exceeding the shared context allowance reports
  `context_too_large` without charge or partial feedback.
- Defaults: the configured interview model (`gpt-6.1-sol` in the current OpenAI
  configuration), **medium** reasoning and **4,000** output tokens. Optional env
  overrides: `LEARNING_AI_FEEDBACK_MODEL`, `LEARNING_AI_FEEDBACK_REASONING_EFFORT`,
  `LEARNING_AI_FEEDBACK_MAX_OUTPUT_TOKENS`. Deadlines, tier, context allowance and
  monthly budget remain shared. The existing Sol pricing was verified against
  [official model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
  on November 2 and needed no change. The subsequent bounded live review supports
  retaining this configuration for the next local checkpoint; see the report below.
- API: GET/POST `/api/v1/learning/practice/sessions/<id>/submissions/<sequence>/feedback`.
  POST accepts only `request_id`; 202 for pending/running, 200 for completed reuse
  or unavailable, 409 for a different live request. GET returns request status,
  validated learner findings/coverage, availability and `can_request`. Receipts
  use the existing endpoint. JWT ownership, feature flag and no-store apply.
- Web: **Build → Checks → View this snapshot and request feedback**. The separate
  CSRF form acts only on saved work. Results link to original turns/revisions/notes
  and keep the compact Learning navigation. Status polling is GET-only, stops
  after six failures, and has a native Refresh fallback. A standalone recovery
  page keeps the request UUID after an unconfirmed POST. No raw model Markdown or
  HTML is rendered. The plain form and saved feedback work without JavaScript.

Development used deterministic fixtures only; **no paid calls were made in 5c**.
The optional preview `--feedback-example` seeds a clearly labelled scripted result;
ordinary fake-provider feedback explicitly does not grade the work. These fixtures
test mechanisms, not live model quality. The subsequent [live review](evaluations/learning-feedback-2026-11-02-review.md)
ran those cases twice through the real worker: 24 saved outputs, no critical
misgrading found by Codex, $0.519980 total, and median provider wall time 20.759
seconds. It supports retaining Sol/medium, with no prompt or content change.
Keith’s review and real learner trials remain. The public repository still
contains authored reference material; server-side projection is not source secrecy.

### Feedback and privacy

`PracticeFeedback` now references the immutable submission, which pins the transcript boundary, exercise/rubric version, brief revision, and artifact revisions evaluated. Findings cite original messages or artifact excerpts; summaries cannot stand in as learner quotes. Validate structure, IDs, quotations, rubric dimensions, and remediation links deterministically. Keith approved one complete snapshot per call for 5c (November 2). Oversized snapshots explicitly stop before generation. Multiple passes/synthesis remain deferred; do not imply omitted material was assessed.

Distinguish confirmed errors, concerns requiring review, defensible trade-offs, and “not observed.” Accept valid alternatives. Record assistance, allow feedback annotations/disputes, and suggest remediation from accepted gaps without modifying review history. Avoid authoritative ability scores. Milestone 1 must demonstrate a meaningful strength, an evidenced concern when present, and a useful next step.

Two additions, decided October 29: deterministic checks come first, so a JSON or YAML API definition that fails to parse is a confirmed finding; and a finding the learner accepts can offer its linked questions as an extra, labelled review. Checkpoint 5a supplies the versioned misconception mappings. Checkpoint 5b implements syntax checks and snapshots; 5c implements generated feedback; 5d implements learner responses and follow-up review.

Use reviewed, versioned evaluation fixtures for correct alternatives, clear errors, missing evidence, assisted answers, and adversarial instructions embedded in learner work. Reject fabricated evidence; require no critical technical misgrading in the reviewed release set. The original pilot targets are conversational p95 completion under 15 seconds and final-feedback p95 under 45 seconds. Measure these with the chosen configuration; they are acceptance targets, not achieved performance.

Retain work until the owner deletes it. Export portable JSON and readable Markdown using learner-safe fields. Delete session content, derived feedback, and learner responses together while retaining content-free billing metadata required for accounting. Explicit recall ratings remain in the existing review history and scheduler when a practice session is deleted; the confirmation page explains this. Backup expiry/provider retention are separate from app deletion. Keep transcripts, code, feedback, and response notes out of logs and analytics; `store: false` alone is not a zero-retention guarantee.

### Learner responses and follow-up practice (checkpoint 5d)

Keith approved this checkpoint after the live evaluator review. It closes the
accepted-gap loop without changing evaluation, content, or scheduling algorithms.

- `PracticeFeedbackAnnotation` is keyed by feedback request and finding ID. It
  stores the latest `unreviewed` / `agree` / `disagree` decision, an optional plain
  text note (2,000 characters), revision, and timestamp. Absence means revision 0.
  Original `PracticeFeedback.data` and submission evidence remain untouched;
  annotations are not fed to the interviewer or evaluator.
- Migration `c2d3e4f5a6b7` follows `b1c2d3e4f5a6`. It adds that table with a
  cascading FK and extends practice receipts with `annotate`. Receipts contain
  metadata, never the note. Downgrade drops annotations and their receipts only;
  feedback, work, existing ratings, and billing history survive.
- Annotation writes acquire the existing owner lock, require the current revision,
  and reuse the practice request UUID protocol. A replay returns the original
  metadata; stale notes get a 409 with the current response. The web page preserves
  the draft and shows both versions before an explicit replacement. Unknown commit
  outcomes retain the original UUID in a standalone recovery form with no DB reads.
- Only **agreed concerns** with authored misconception links offer **Practise this**.
  Private mappings remain server-side. Strengths, missing evidence, unmapped concerns,
  and v1 feedback can still receive responses; no questions are invented for them.
- Extra practice is **one pass per finding**, derived from existing `ReviewLog`
  rows tagged `feedback:<feedback-request-uuid>:<finding-id>`. There is no new queue
  or run table. It offers linked published questions even when not due, skips
  suspended/unavailable questions, and pins question version/progress revision at
  reveal. A subsequently published version does not replace the revealed version.
- Only an explicit Again/Hard/Good/Easy rating calls `rate_card_for_user` and its
  existing scheduler/receipt transaction. Even Again completes that question's
  extra-practice pass; the scheduler determines its next ordinary review. Agreement,
  disagreement, notes, navigation, and answer reveal change no progress or AI budget.
- Rating holds the owner lock through authorization and the scheduler transaction.
  Concurrent withdrawal/deletion is serialized. Withdrawal blocks new ratings;
  an already committed same-UUID rating replays even after withdrawal. Deletion
  removes the finding, so its URL returns 404, while explicit review history remains.
- JWT API base: `/api/v1/learning/practice/sessions/<id>/submissions/<sequence>/feedback/<finding-id>`.
  `PUT /response` accepts exactly `request_id`, `expected_revision`, `decision`,
  `note`. `GET /review` returns the remaining questions without answers. Supplying
  exactly `card_id`, `content_version`, `expected_revision`, `request_id` reveals
  a pinned answer; `POST /review` accepts those fields plus `rating`. Existing
  ownership, feature flag, no-store headers, and validation boundaries apply.
- Native CSRF forms work without JavaScript. Response controls are collapsed
  beneath each finding; unsaved notes get a navigation warning but are never
  copied to browser storage. The review page uses the shared tabs and returns to
  the exact original session. The lesson remediation link now carries the correct
  `practice_session` parameter too.

Preview: port **5062**, `--concept --feedback-example`; draft v2 is seeded only in
the disposable fixture. `practice=failure|lost` also exercises annotation and
follow-up rating recovery. No paid calls, dependencies, or infrastructure were added.

### Portable session exports (checkpoint 5e)

Keith approved JSON/Markdown exports after 5d. Both formats are read-only downloads
under **Session details**, also available before deleting a session. Links open
separately to preserve unsaved editor text and clearly say that only saved work is
included. There is no automatic save, generation, export job, archive table, or
server-side retained copy. Import/restore is outside this checkpoint.

- Service: `project/services/practice_export_service.py`. JSON has
  `format='engineering-learning.practice-session'` and `schema_version=1`.
  Top-level fields: `exported_at`, `session`, learner-facing pinned `exercise`,
  `artifacts` with `current_revision` and every saved revision, `brief_revisions`,
  `transcript`, `revealed_requirements`, `context_choices`, `submissions` with
  saved checks/feedback/latest annotations, and `followup_ratings` scoped to these
  findings. Empty revision 0 is explicit. Notes and artifact bodies referenced
  by old feedback remain available; Continue with recent messages never removes
  old conversation from an export.
- Full current and historical work is included, but annotations have only their
  latest saved version because the model does not store annotation history.
  Follow-up rating records contain the source snapshot/finding, card/version,
  explicit rating, and timestamp. Account-wide review history/progress is excluded.
  No unfinished AI output is implied to have been included.
- The export uses a separate SQLAlchemy connection with **REPEATABLE READ, READ
  ONLY** on PostgreSQL. Authorization establishes the snapshot before the contents
  are collected. Saves, ratings, and deletion can commit concurrently without
  producing mixed revisions or waiting on an export's owner lock. A download
  already reading when deletion commits can finish its prior consistent snapshot;
  subsequent requests return 404. Export doesn't commit/rollback the caller's
  transaction, and the connection's isolation settings reset when returned to the pool.
- SQLite uses an explicit read transaction for deterministic fixtures, but the
  concurrency guarantees above were tested on PostgreSQL. In-memory SQLite's
  shared connection cannot isolate an export from uncommitted caller writes;
  the exporter refuses that case before borrowing the connection, preserving
  the writes for an explicit commit or rollback in the REPL. Do not replace this
  with several independent calls to normal detail/history services: their reads
  are separate snapshots under the default READ COMMITTED isolation.
- Exercise, record, evidence, coverage, remediation, and annotation fields are
  explicitly projected. Facilitator instructions, hidden requirements not yet
  revealed, rubric/reference reasoning, misconception mappings, request receipts,
  leases, credentials, and billing data are excluded. Learner text itself is not
  censored. Public source remains inspectable; export filtering is not source secrecy.
- Markdown quotes prose literally, escapes HTML/link/image syntax, and uses
  artifact fences longer than any backtick run inside the artifact. It cites
  turn numbers, artifact revisions, and note IDs/revisions within the same file.
  JSON preserves the exact saved text and structured source coordinates.
- `GET /learning/practice/<id>/export/json` (or `/md`) uses existing login;
  `GET /api/v1/learning/practice/sessions/<id>/export/json` (or `/md`) uses JWT.
  Existing practice feature gating applies. Successful responses have a fixed
  UUID-based attachment filename, UTF-8 content type, `private, no-store`, and
  `nosniff`. The body is prepared before headers are sent. A retry is a fresh
  read, not a replay receipt; its timestamp and contents may reflect later saves.
- `LEARNING_EXPORT_MAX_BYTES` defaults to **32 MiB**, bounding accumulated records
  and the final encoded file. Database rows are read in batches. Oversized exports
  fail explicitly with 413; database failures with 503, without an attachment or
  silent truncation. The web error page avoids further DB reads and logs only the
  safe failure class. Increasing the allowance is an operator configuration change.

There is no migration or new dependency/infrastructure. Preview **5063** preserves
the 5062 process and data. Both JSON and Markdown were downloaded through the
in-app browser and their files inspected. The [5e guide](learning-checkpoint-5e-test-guide.md)
covers DevTools, cURL/Postman, HTTPie, and direct Python calls.

## Where to work

| File or directory | Responsibility |
| --- | --- |
| [Content schema](../project/learning/content_schema.py) | Strict validation, Markdown resolution, audience projections. |
| [Curriculum service](../project/services/curriculum_service.py) | Checksums, atomic PostgreSQL import/publication, published reads, review adapter. |
| [V2 catalog](../curriculum/idempotency/catalog-v2.json), [v2 contract tests](../tests/test_curriculum_v2.py), [boundary tests](../tests/test_feedback_foundation_boundaries.py) | Misconception mappings, strict reference checks, v1 compatibility, and learner/interviewer privacy. Publication/progress/concurrency coverage is in `test_curriculum_postgres.py`. |
| [Learning service](../project/services/learning_service.py) | Existing queues, scheduler integration, revision checks, user lock, rating/receipt transaction. Preserve these guarantees. |
| [Models](../project/models.py) and [migrations](../migrations/versions/) | Catalog, review, and practice persistence. |
| [Practice service](../project/services/practice_service.py) | Core practice writes: sessions, artifact saves and conflicts, turns, the brief, replies (queueing, the call check, completion), receipts, owner-scoped reads, log-safe failure summaries. |
| [Feedback response service](../project/services/feedback_review_service.py), [web routes](../project/learning/feedback_views.py) | Revisable responses, authored follow-up question resolution, owner-lock serialization, existing scheduler delegation, native conflict/recovery forms. Tests: `test_feedback_review.py`, `test_feedback_review_routes.py`, `test_feedback_review_postgres.py`. |
| [Session exporter](../project/services/practice_export_service.py), [export inspection guide](learning-checkpoint-5e-test-guide.md) | Versioned JSON, readable Markdown, allowlisted snapshot collection and bounded encoding. Tests: `test_practice_export.py`, `test_practice_export_routes.py`, `test_practice_export_postgres.py`. |
| [Interviewer profiles](../project/learning/interviewer.py) | Versioned interviewer rules; the selector and reply requests; what each call may see; size helpers. |
| [OpenAI call process](../project/learning_ai_call.py), [provider](../project/services/learning_ai_provider.py) | The child script (standard library and `requests` only) and the parent that runs it with a minimal environment. |
| [Interviewer evaluation](../project/learning/interviewer_eval.py), [cases](../tests/fixtures/interviewer/cases.json) | `flask learning-eval` and its reviewed cases. Not [`evaluation.py`](../project/learning/evaluation.py), which evaluates the review scheduler. |
| [Practice budget](../project/services/practice_budget.py), [reply worker](../project/services/practice_worker.py), [wake-up signal](../project/services/practice_signals.py) | The spending ledger and reservations; the worker thread, fake provider, and `learning-worker` command; the event a commit sets to wake the worker. |
| [Learning views](../project/learning/views.py), [practice routes](../project/learning/practice_views.py), [forms](../project/learning/forms.py), [templates](../project/learning/templates/learning/) | Website authentication, CSRF, lesson/review flow, practice workspace, re-render and rescue paths. |
| [Practice API](../project/api/learning_practice.py) | JWT endpoints over the practice service. |
| [Legacy JSON API](../project/api/learning.py) | Compatibility surface; no concept API. |
| [Shared terms](../project/curriculum_terms.py), [learning errors](../project/services/learning_errors.py) | Constants and exceptions kept free of imports, to avoid the cycle described under gotchas. |
| [Lesson JavaScript](../project/static/js/learning-concept.js) and [SCSS](../project/static/scss/learning-concept.scss); [practice script](../project/static/js/learning-practice.js) and [SCSS](../project/static/scss/learning-practice.scss) | Rendering and retry simulation; unsaved-change prompt and byte counter. Rebuild generated `main.css` after style changes. |
| [Workspace UI](../project/static/js/learning-workspace.js), [styles](../project/static/scss/learning-workspace.scss) | Accessible view/work tabs, focus and scroll continuity, hidden-error reveal, and presentation-only browser storage. Native form writes remain unchanged. |
| [Concept navigation](../project/learning/navigation.py), [shared shell](../project/learning/templates/learning/concept_shell.html), [concept styles](../project/static/scss/learning-concept-workspace.scss) | Four-mode identity, owned-session selection, focused lesson/review presentation. Lesson section enhancement is in `learning-concept.js`. |
| [Concept navigation tests](../tests/test_concept_workspace.py), [browser walkthrough](../tests/browser/concept-workspace-checks.js) | Exact older-session continuity, ownership, read-only navigation, rating retries/replays, feature-off behavior, mobile and no-JS access. Runs through `test_learning_hub_browser.py`. |
| [Integrated practice browser test](../tests/test_practice_browser.py), [browser assertions](../tests/browser/practice-workspace-checks.js) | Real templates, CSRF forms, redirects, polling, conflict/rescue/retry paths, responsive layout, and no-JS saves with a fake provider. Included in backend unittest discovery; requires Chrome (or CHROME_BIN), including in CI. |
| [Base template](../project/templates/base.html) | Private Learning analytics exclusion and a container-class override for the compact practice shell. |
| [JobWizard provider integration](../project/services/jobwizard_extraction.py) | Existing bounded-call/validation patterns to study, not the Learning worker. |
| [Content tests](../tests/test_curriculum.py), [PostgreSQL import tests](../tests/test_curriculum_postgres.py) | Schemas, leakage, imports, process death, migrations. |
| [Web concept tests](../tests/test_concept_web.py), [PostgreSQL review tests](../tests/test_learning_postgres.py) | Auth/CSRF, reveal/version pinning, rollback/replay, scheduling and concurrency. |
| Practice tests: service ([3a](../tests/test_practice_service.py), [3b](../tests/test_practice_discussion.py)), web ([3a](../tests/test_practice_web.py), [3b](../tests/test_practice_web_discussion.py)), API ([3a](../tests/test_practice_api.py), [3b](../tests/test_practice_api_discussion.py)), [PostgreSQL](../tests/test_practice_postgres.py) | Saves, sends, citations, brief snapshots, replays, conflicts, normalization, limits, leakage, ownership, pause/resume, delete, rescue page, two-device behaviour, races, process death, cross-session citations, log safety. |
| Reply tests (4a): [service and worker](../tests/test_practice_replies.py), [web](../tests/test_practice_web_replies.py), [API](../tests/test_practice_api_replies.py), [PostgreSQL](../tests/test_practice_replies_postgres.py) | Access, pinned inputs, staleness, fencing, budgets and the ledger, each fake failure mode, polling, claims across releases, forced lock interleavings, process death, restart pickup, worker start conditions. |
| Interviewer tests (4b): [service](../tests/test_practice_interviewer.py), [call process](../tests/test_learning_ai_call.py), [evaluation](../tests/test_interviewer_eval.py) | Disclosure, hints, what each call sees, selector failures, the allowance and Continue with recent messages, the check-in, the long-session recovery case, a reply through the real child process, every status and failure of the child, and checks that the harness's checks can fail. |
| [Browser checks](../tests/browser/README.md) | Actual renderer/simulation and legacy browser regression checks. |
| [Preview fixture](../scripts/learning-preview-fixture.py) | Disposable local demo and inspection endpoints. |

## Run and inspect the completed slice

Use the repository's `.python-version` (**3.13.18**) and `.nvmrc` (**24.22.1**). Check `poetry run python --version`; an existing Poetry environment can retain an older interpreter even after the shell changes. Dependencies are locked. From the repository root:

```sh
poetry install
nvm use
npm ci --ignore-scripts
poetry run python scripts/learning-preview-fixture.py --concept
```

Open `http://127.0.0.1:5057/login`. Sign in with `learning1@example.test` / `LearningPreview123!`; the second independent account is `learning2@example.test` with the same password. These are disposable fixture credentials. Open Learning → Idempotency and uncertain outcomes, step through retries, and complete a review. Stop with Ctrl+C; restarting resets the fixture.

The fixture disables dotenv, uses temporary SQLite, and directly inserts demo-published content. It does not exercise the real PostgreSQL importer or migrations and must not be pointed at real data. The actual importer intentionally rejects SQLite. `/fixture/results` exposes review counts for inspection only in this fixture. Its access JWTs expire after ten seconds, so delayed HTTPie/Postman calls may need a fresh login or refresh token.

With `--concept`, practice is enabled: Learning → Idempotency → **Apply it** starts a session. `POST /fixture/state` with `practice=failure` or `practice=lost` simulates database failures before or after a save or send commits, and `/fixture/results` also reports practice counts. The fixture turns on SQLite foreign keys so deletes cascade.

It also runs the reply worker with the fake provider, and `learning1@example.test` is the AI owner. `POST /fixture/state` accepts `ai` (`success`, `slow`, `fail`, `lost`, `hang`, or `invalid`) `cap_usd`, which lowers the monthly budget and moves the warning line to 80% of it, and `context_bytes`, which shrinks what the interviewer may read. `/fixture/results` adds reply counts and the month's spend. The fake reveals a requirement when a message repeats one of its clarification cues, and gives a hint when asked. The fixture sets `TEMPLATES_AUTO_RELOAD=True`; templates reload on the next request. Python changes require a restart, which resets its temporary data.

Use the [REPL guide](learning-checkpoint-1-test-guide.md) to inspect projections, provoke validation failures, and step through functions. Use the [running-system guide](learning-checkpoint-2-test-guide.md) for Network request replay, Console/Sources inspection, HTTPie/Postman, and profiling. Use the [practice guide](learning-checkpoint-3-test-guide.md) for saves, sends, the brief, conflicts, recovery pages, pause/resume, delete, and the practice API (parts A and B), and the [checkpoint 4 guide](learning-checkpoint-4-test-guide.md) for replies, the fake failure modes, the budget, locks, and the reply API (part A), and for what each interviewer call sees, disclosure, hints, the context allowance, the call process, and the evaluation harness (part B). Form navigations appear under Network All/Doc, not a Fetch/XHR-only filter. The simulation performs local DOM work without application requests.

## Verification evidence and commands

Latest verification, November 7, for checkpoint 6b:

- **721 tests run: 720 passed, one existing Linux-only skip**, with isolated
  PostgreSQL 18.6. Twenty-four new tests cover history, ownership, version pins,
  strict payloads, rollback/replay, deletion, concurrency, migration and browser flow.
- **55 self-assessment browser checks**, plus **225 practice / 70 concept / 60
  hub / 40 progress** checks. This includes native/no-script saves, stale tabs,
  lost responses, retry, keyboard controls, 320-pixel layout, and account isolation.
- PostgreSQL first-write races, concurrent bookmark saves, save-versus-clear
  races, process death before commit, upgrade/downgrade, DB constraints, and
  metadata comparison passed. Other progress tables remain unchanged.
- 13 Node tests, dependency integrity, Sass compilation, and `git diff --check`
  passed. Final response copy received a focused route/browser rerun. Additional
  paid AI cost: **$0**. No production changes.

Earlier verification, November 7, for checkpoint 6a:

- **697 tests run: 696 passed, one existing Linux-only skip**, including the
  isolated PostgreSQL 18.6 migration/concurrency/recovery suites. Eighteen added
  tests include 40 new browser checks; existing practice/concept/hub checks pass.
- Concurrent first enrollment, exact retries, conflicting bookmarks, enrollment
  during a save, and process death before commit were verified against PostgreSQL.
  The additive migration/downgrade preserve existing review and practice data.
- 13 Node tests, dependency-integrity checks, 29 standalone lesson browser checks,
  and the Sass build passed. The final home action was rechecked with the route
  and browser suites. No new infrastructure or paid AI calls (**$0**).


Earlier verification, November 6, for checkpoint 5g:

- **679 tests run: 678 passed, one existing Linux-only skip**, with isolated
  PostgreSQL 18.6. Five added tests cover the private revision, projections,
  source-route exclusion, import/replay, old saved work and ratings, and evaluator
  inputs pinned independently to exercise versions 2 and 3.
- The full run includes **225 practice, 70 concept, and 60 hub browser checks**,
  the migration/concurrency/recovery suites, and the SERIALIZABLE interleaving
  regression. `git diff --check` passed.
- The revision-3 manifest replays the five existing concept/question revisions
  and adds one exercise revision. The feedback preview selects this manifest on
  its next start. Existing running previews retain their temporary data.
- Saved live feedback was rechecked; added paid cost was **$0**. Historical live
  outputs assess revisions 1/2. Revision 3 was verified with deterministic
  integration tests and technical review, without a fresh paid evaluation.

Earlier verification, November 3, for checkpoint 5f:

- **674 tests run: 673 passed, one existing Linux-only skip**, with isolated
  PostgreSQL 18.6, including migration, ownership, budget, concurrency, and recovery
  regressions. No migration or backend/service change.
- **225 practice browser checks** (20 added), **70 concept**, and **60 hub** checks
  passed. **104 renderer/security checks** (two added), **13 Node tests**, dependency
  integrity, and `git diff --check` passed. Thirteen discussion/web tests passed
  again after the final deletion-shell adjustment.
- Native keyboard/320-pixel walkthrough covered Learn, Review, disclosure, saved
  artifacts/notes, evidence/response/follow-up practice, revision, pause/reopen,
  JSON export, and deletion confirmation/cancel. Actual deletion/cascades remain
  covered by automated route and PostgreSQL tests. Scripted providers, **$0 paid
  AI cost**. No new dependency or stylesheet rebuild.
- See the [report](learning-milestone-1-acceptance.md) for fixes and a short DevTools
  walkthrough. VoiceOver/NVDA listening and standalone Safari/Firefox remain
  unverified; this is not a WCAG conformance audit or human content approval.

Earlier verification, November 3, for checkpoint 5e:

- **674 backend tests run: 673 passed, one existing Linux-only skip**, with isolated
  PostgreSQL 18.6. Adds 21 export service, web/API, and PostgreSQL tests.
- Five PostgreSQL cases prove consistent reads during saves, annotation/rating,
  feedback completion, and deletion, plus caller-transaction/isolation preservation.
  Existing migration and concurrency regressions passed; no new migration is needed.
- **205 practice browser checks** (21 added), **70 concept** and **60 hub** checks,
  plus **102 renderer/security checks**, passed. Draft preservation, exact-session
  links, private downloads, errors/retry, narrow layouts and no-JS controls are covered.
- Native JSON/Markdown downloads were inspected. Scripted fixtures only, no paid
  calls. `git diff --check` passed. No style or dependency change required a rebuild.

Earlier verification, November 2, for checkpoint 5d:

- **653 backend tests run: 652 passed, one existing Linux-only skip**, using
  isolated PostgreSQL 18.6. Adds 28 service/API/web/PostgreSQL cases, including
  simultaneous notes/ratings and forced ordering against withdrawal/deletion.
  Populated upgrade/downgrade and metadata parity tests include the new migration.
- **182 integrated practice browser checks** passed in the full run. Two further
  checks were then added for cancelling a save with two unsaved notes; the focused
  browser run passed **184 checks**. Existing concept/hub checks remain 70/60.
- **13 Node tests**, dependency integrity, **102 renderer checks**, Sass and
  `git diff --check` passed. New preview visually inspected on 5062; no paid calls.

Earlier verification, November 2, for the [live evaluator review](evaluations/learning-feedback-2026-11-02-review.md):

- **24 live calls / 24 validated saved results**, covering 12 fixed cases twice. Codex reviewed every output; no critical misgrading or undisclosed requirement/reference disclosure was observed. This is not independent human content approval.
- **$0.519980** total against a $2 ceiling; all 24 charges settled and were recomputed from usage. Median provider wall time **20.759 seconds**, observed p95 **25.203 seconds**.
- **55 focused tests passed**, including eight new harness tests and existing feedback/API/web/PostgreSQL recovery cases. No production runtime, migration, UI, model, profile, or content change.

Earlier verification, November 2, for checkpoint 5c:

- **617 backend tests run: 616 passed, one existing Linux-only skip on macOS**, including isolated PostgreSQL 18.6 migration, shared budget, concurrency, foreign-key and deletion/recovery checks. The checkpoint adds 31 tests; populated migration coverage was extended.
- **145 practice browser assertions** (26 new), plus the existing 70 concept and 60 hub checks. After response/display refinements, 39 focused feedback/API/web/browser tests passed again.
- **13 Node tests**, dependency integrity, **102 renderer checks**, Sass compilation and `git diff --check` passed. Desktop/mobile feedback was inspected in the disposable preview; this is not a screen-reader or cross-browser audit.
- Scripted provider only: no paid calls, production migration, publication, push or deployment. Live technical quality, semantic privacy, latency and final milestone acceptance remain unverified.

Earlier verification, November 2, for checkpoint 5b:

- **586 backend tests run: 585 passed, one existing Linux-only JobWizard test skipped on macOS**, with disposable **PostgreSQL 18.6**. This includes populated migration downgrade/upgrade/schema parity, simultaneous submissions/edits/deletion, forced worker lock windows, process death, and fresh-process recovery.
- **32 new tests** cover parser safety/limits, immutable results, ownership/CSRF/privacy, v1/v2 snapshots, stale views, receipt replay, failure recovery, AI-off/exhausted-budget operation, and PostgreSQL races. Integrated Chrome walkthroughs: **70 concept**, **60 hub**, **119 practice** assertions (22 new practice assertions).
- Node 24: **13 tests passed**, dependency asset verification passed, and **102 browser renderer/recovery checks passed** (23 + 9 + 27 + 43). `git diff --check` passed. A visual walkthrough verified the compact Checks panel in a separate disposable preview on 5058; 5057 was preserved.
- No paid calls, application content publication, production migration, push, or deployment. No dependencies or infrastructure were added. The local preview still uses draft v1; version-2 privacy and compatibility run in tests. The [5b guide](learning-checkpoint-5b-test-guide.md) covers REPL stepping, native request inspection/replay, stale tabs, and lost confirmations.

Earlier verification, November 2, for checkpoint 5a:

- **554 backend tests run: 553 passed, one existing Linux-only JobWizard test skipped on macOS**, using isolated **PostgreSQL 18.6**. The full run includes migrations/schema comparison, publication concurrency, budget, failure recovery, and all three browser walkthroughs (70 concept, 60 hub, 97 practice checks).
- **16 new tests** cover versioned content/validation, learner and interviewer boundaries with a scripted provider, immutable v2 publication/conflicts, unchanged v1 sessions and progress, and an old review completing after v2 publication. The 36-test focused suite also passed against PostgreSQL.
- No front-end files changed, so the separate Node/renderer suite was not repeated. No paid provider, preview reset, application publication, migration, push, or deployment was performed. The new content remains a draft.

Earlier verification, November 2, for the login and shared concept workspace:

- **538 backend tests run: 537 passed, one existing Linux-only JobWizard test skipped on macOS**, using isolated **PostgreSQL 18.6**. Migration/schema, concurrency, budget, and recovery tests ran against PostgreSQL.
- Included browser walkthroughs: **70 shared concept checks**, **60 Learning hub checks**, and **97 practice recovery checks**. New route tests cover selected-session ownership, no navigation writes, CSRF, review receipt replay, stale/failed ratings, and the practice flag. All use disposable data and deterministic providers.
- **13 Node tests**, dependency integrity, **102 browser renderer checks**, and Sass compilation passed. Desktop and 390-pixel screens were inspected; browser assertions also cover 320 pixels.
- No migration or write protocol changed; the added service operation is a read-only session summary. No paid AI, production mutation, push, or deployment. Safari, Firefox, and screen-reader validation remain outstanding.

Earlier verification, November 1, for the tabbed workspace checkpoint:

- **516 backend tests run: 515 passed, one existing Linux-only JobWizard signal test skipped on macOS**, with an isolated **PostgreSQL 18.6** cluster. Migration, concurrency, budget, and recovery coverage ran against PostgreSQL.
- After the final UI refinements, **41 focused web/browser tests passed**, including **97 integrated browser assertions** against real Flask forms and a deterministic fake interviewer. These cover native saves/sends, focus and scroll continuity, note reindexing, conflicts, lost-response replay, failed-send recovery, mobile layouts, blocked browser storage, and saving without JavaScript.
- The existing **102 browser checks**, **13 root Node tests**, dependency integrity checks, and Sass build passed. Desktop and 390-pixel views were inspected in the disposable fixture.
- No service, API, model, migration, review scheduling, or AI behavior changed. The full PostgreSQL run preceded the last UI-only refinements; the focused checks were rerun afterward. This is not a Safari/Firefox or screen-reader audit.

Earlier verification, recorded October 29 after checkpoint 4b:

- **503 backend tests run: 502 passed, one existing Linux-only JobWizard signal test skipped on macOS**, with PostgreSQL **18.6** enabled.
  - 4b added 49: 19 interviewer, 17 call-process, 8 harness, 4 web, and 1 API test.
  - The tests include the long-session recovery case and a reply through the real child process against a local stand-in for the Responses API.
  - My tests and two independent reviews found problems, all fixed with regression tests, each confirmed to fail with its fix removed (see the checkpoint log).
- The evaluation harness passes all 13 cases on all nine checks against the fake.
- **102 browser checks**: 23 legacy flashcard, nine extraction, 27 concept, and 43 practice checks.
- **13 root Node tests**, dependency integrity checks, Sass build, and `git diff --check` passed.
- A live walkthrough in the disposable fixture covered disclosure, hints, Continue with recent messages, work too large to read, and the 390-pixel layout (details in the checkpoint log). This is not a screen-reader audit.

Checkpoint 4a's results (454 tests, 101 browser checks; its first commit passed alone with 441) are in the checkpoint log.

Earlier results (3b: 410 tests, 78 browser checks; 3a: 371, 70; 2: 326, 59) and the checkpoint-by-checkpoint coverage are there too.

These are historical local results, not a claim that CI or AI evaluations have passed for unimplemented work. Detailed coverage is in the [checkpoint log](engineering-learning-milestone-1.md).

For targeted file/web checks:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
  poetry run python -m unittest discover -s tests -p 'test_curriculum.py' -v
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
  poetry run python -m unittest discover -s tests -p 'test_concept_web.py' -v
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
  poetry run python -m unittest discover -s tests -p 'test_practice*.py' -v
npm test
npm run test:browser
```

Browser checks need Chrome; use `CHROME_BIN` when its executable is not in the expected location. The npm checks exercise JavaScript with local dependencies. `poetry run python -m unittest tests.test_practice_browser` additionally drives actual Flask pages and native HTTP submissions using a temporary localhost database and fake AI; it is also included in backend discovery. Use `npm run sass` after SCSS changes and commit the generated CSS.

For migrations/concurrency, provision an **isolated PostgreSQL 18 database named `library_sync_test` on localhost**. The previous local cluster used role `library_test` and port `55439`; it is not a service dependency. The [backend CI workflow](../.github/workflows/backend.yml) documents equivalent PostgreSQL provisioning on port 5432. Adjust only the disposable test connection below:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
  LIBRARY_TEST_POSTGRES_URL=postgresql+psycopg://library_test@127.0.0.1:55439/library_sync_test \
  poetry run python -m unittest discover -s tests
```

These fixtures drop tables and reset migration state. Never use a database containing useful data, and do not run independent suites concurrently against the same fixture database. Without `LIBRARY_TEST_POSTGRES_URL`, PostgreSQL tests skip: a green SQLite-only run is not migration/concurrency acceptance. Preserve the environment guards so tests do not load real `.env` credentials or probe cloud metadata. The older general [verification runbook](verification-runbook.md) is useful for app setup, but its historical test counts and SQLite-only description predate this work.

## Gotchas encountered

- **A download needs one database snapshot.** Chaining existing detail/history
  reads under READ COMMITTED can mix a new artifact head with older feedback or
  notes. Export owns a separate read-only REPEATABLE READ connection and buffers
  the file before responding; tests force concurrent changes between its queries.
- **Local previews reload templates without reloading Python.** New download
  links render only when the current route passes `export_available`, so older
  preview processes do not try to resolve routes they haven't loaded.
- **WTForms renders submitted integer `raw_data` before `.data`.** Updating only
  the expected revision after a conflict still submitted the stale value. Rebuild
  the recovery form from the preserved draft with no submitted formdata.
- **Cancelling navigation must not mark a draft saved.** The response script
  exempts the submitted form for just that navigation. Another dirty finding may
  cause the learner to cancel; both drafts then still need protection.
- **Browsers reserve ports 5060/5061.** The new preview uses 5062; there is no need
  to bypass browser protections. Older preview processes were left alone.
- **Hidden panels must remain recoverable.** Errors and conflict links reveal their work panel before focus moves. Form fields remain enabled and in the original form, including inactive artifacts and notes. Background replies only follow when the learner is already at the newest exchange.
- **View persistence is not draft persistence.** Browser storage contains only view/scroll preferences and temporary focus metadata. Unsaved text still depends on the form and leave-page warning; confirmed text remains on the server. See the [workspace inspection guide](learning-workspace-test-guide.md).
- **GET form submission replaces the action's query.** Keep `practice_session` as a hidden input on Show answer as well as in navigation URLs; otherwise an older session can be lost during reveal. Rating/retry forms carry it too. Review receipts remain independent of this navigation parameter.
- **Shared styles can clip practice controls.** The lesson's taller line height and flex shrinking initially clipped Send. Practice keeps its previous line height and a nonshrinking composer; retain the browser geometry assertion when changing the header.
- **Test CSP must run after Talisman.** Flask runs response hooks in reverse registration order. Both integrated browser fixtures explicitly put their local-only policy last and assert the resulting header; otherwise Talisman silently replaces it and external scripts can load during tests.

- **Alembic logging leaked across tests.** Its logging configuration disabled unrelated application loggers, causing later log assertions to fail. The curriculum migration test patches `logging.config.fileConfig` around the actual PostgreSQL upgrade/downgrade; it does not mock the migration itself.
- **Authentication leaked inside a test fixture.** Two initial web-test failures came from retaining a login across requests. Use deliberately isolated clients/session state when asserting anonymous versus authenticated behavior.
- **Small screens exposed a header overlap.** Keep checking narrow layouts as the workspace adds controls; desktop/browser tests alone did not reveal it.
- **Public source and learner privacy are different.** Reference material is intentionally outside Flask static/templates and Expo assets, but remains inspectable in Git. Never describe it as secret from repository readers.
- **A successful demo is not publication.** The fixture bypasses the importer for its disposable database. Real publication needs human review and explicit attestation. A new source edit needs a new content version even if only a Markdown body changed.
- **Identifiers and versions serve different purposes.** Preserve existing card IDs and progress; use a new ID if the learning objective materially changes. Historical logs can legitimately have null content versions. Future sessions must pin exact revisions rather than repeatedly reading the newest item.
- **Local tool permissions can resemble app failures.** The Codex sandbox required elevated local permissions for binding/accessing localhost and writing Git commits. An `Operation not permitted` at that boundary was not an application defect. Temporary preview servers were stopped after checks.
- **The `project.learning` package imports its views on load.** `learning_service` imports a `project.learning` submodule, so anything those views import must not import names from the half-loaded `learning_service`. Shared constants live in `project/curriculum_terms.py`, and learning exceptions in `project/services/learning_errors.py`, which `learning_service` re-exports unchanged.
- **PostgreSQL error messages quote rows.** A CHECK or NOT NULL violation's DETAIL line contains the failing row's values even with SQL parameters hidden. Log `practice_service.describe_failure(exc)`, never `str(exc)` or `logger.exception`.
- **Flask-WTF CSRF tokens expire after an hour,** and `Meta.csrf_time_limit = None` falls back to that hour. The workspace form uses 24 hours, and every CSRF rejection re-renders the learner's text.
- **Textareas change what is submitted.** Browsers send CRLF line breaks and drop one newline directly after `<textarea>`. The service normalizes to LF, and templates render through WTForms `TextAreaField`, which writes the guard newline.
- **Error pages read the database.** `_header.html` and `500.html` use `current_user.username`, which needs a query after a rollback, so with the database down both fail. The practice rescue page avoids the shared layout. The concept review 503 path still has this latent issue (it is tested only with injected errors).
- **SQLite enforces foreign keys only with `PRAGMA foreign_keys=ON`.** The practice tests and the preview fixture enable it per connection. Deleting a session relies on it for the cascades, so `delete_session` refuses to run on a SQLite connection without it rather than leave the rows behind; PostgreSQL always enforces foreign keys. In-memory SQLite uses one connection, so races are only meaningful on PostgreSQL. The practice tables' `user_id` foreign keys don't cascade, so any future account deletion must delete practice sessions first.
- **The shared test app context also caches the CSRF token.** Suites that keep one app context pushed share `g` across requests. The test login leak above recurred: `login()` must clear `g._login_user`, and also `g.csrf_token`, or the next POST fails with "The CSRF session token is missing". 3a's cross-account save test had passed only because of that rejection; it now reaches the ownership check.
- **A WTForms field named `type` is unreachable through a `FormField`:** the enclosing field's own `type` attribute shadows it. The brief row's field is `kind`.
- **Enter submits with the form's first button, even from a checkbox.** Chromium did this from a brief entry's Pin box. With Discuss before Build, that first button was Send, so Enter would have sent a half-written message. A hidden Save button now comes first: the same keypress saves and keeps the message in the box.
- **Replays return the recorded response.** A replayed pause still says `"changed": true`. Clients should read a replay as history, not as current state.
- **A `FOR UPDATE` lock deadlocks with foreign-key checks.** Inserting a row that references another takes `FOR KEY SHARE` on the referenced row, which `FOR UPDATE` blocks. The worker inserts ledger charges, which reference the user, while holding a request row. So the owner lock is `FOR NO KEY UPDATE`: it still serializes owner writes but lets those checks through.
- **Lock the live request before the session row.** The worker's call check holds the request row, then share-locks the session. Send, Ask, pause, and delete lock the live request first, so they wait for a running check instead of deadlocking or overwriting the lease it just extended.
- **Read the reply state before the transcript.** A page's reads are not one snapshot. The workspace once read the turns and then the reply state, so a reply landing in between showed neither. Reading the state first can at worst say "replying" for a reply already on the page, and the next poll settles it.
- **Spending never reaches the cap.** Reservations refuse anything that would exceed it, so "spent ≥ cap" never fired and the month never read as used up. A reply's worst case is now checked when it would be queued or offered.
- **PostgreSQL sums `bigint` as `numeric`.** Python receives a `Decimal`, which Flask serializes as a string. Convert sums to `int`.
- **Natural races rarely land in narrow windows.** Repeated runs never let a completion beat a delete, so the race tests force each order, and the call-check tests hold the worker at a lock with a SQLAlchemy `before_cursor_execute` event. When polling `pg_stat_activity` for a waiting lock, start a new transaction each time: the view is a per-transaction snapshot.
- **CSS `:empty` doesn't match an element holding only whitespace,** which Jinja leaves behind. The reply region uses `:has(p)` instead.
- **SIGTERM skips `with` cleanup.** By default it ends Python without unwinding, so the preview fixture left its temporary database behind whenever a tool stopped it that way. The fixture now turns SIGTERM into a normal exit.
- **A check must not trust what it checks.** The evaluation harness first took "what the reply may reveal" from the facilitator it was checking, so a facilitator that revealed everything looked consistent. It now derives that from the selection. `tests/test_interviewer_eval.py` breaks each check on purpose.
- **Bytes bound tokens, but escaping inflates bytes.** Reservations price the whole request as sent, where the material is JSON inside JSON and a newline costs three bytes. The allowance measures only what the model reads (instructions and input). Both are safe upper bounds.
- **Template text isn't escaped; values are.** A literal apostrophe in a template stays `'`, while one inside an inserted value becomes `&#39;`. Tests asserting page text must match which it is.
- **Schema version participates in content identity.** Do not put unchanged v1 item versions into a schema-2 catalog and expect import to replay: the checksum changes. The v2 draft explicitly advances all six revisions while preserving stable IDs. Keep the old catalog/Markdown intact; future lesson edits need their own source revision too.

## Checkpoint 6a: enrollment and reading position

Approved November 7, after Milestone 1 local acceptance. `UserConceptProgress`
uses `(user_id, concept_id)` as its primary key, with enrollment/update timestamps,
a revision counter, and a nullable versioned section bookmark. It stores no
mastery score. Migration `d3e4f5a6b7c8` follows `c2d3e4f5a6b7`; apply it before
running this code against a persistent database. It creates one table and does
not backfill enrollments or modify existing review/practice rows.

`concept_progress_service` owns the shared web/JWT contract. Enrollment serializes
on the existing user row, like rating saves, so simultaneous first requests create
one record. Repeating enrollment never resets a bookmark. Reading saves use that
same lock, refresh any cached ORM row, and require `expected_revision`. The row
retains the last request ID: an exact immediate retry returns the same response;
a retry after another write conflicts without changing the newer bookmark. This
is a bookmark, so there is no additional receipt journal. Timestamps are returned
in UTC, including replay after a PostgreSQL connection returns local-offset dates.

The web uses CSRF-protected POST forms; JWT clients get/add/update progress through
`GET /api/v1/learning/concepts/<id>/progress`, `POST .../enrollment` (empty JSON
object), and `PUT .../reading-position` (content_version, section_id,
expected_revision, request_id). Authentication and private/no-store responses
match existing Learning endpoints. Responses contain only the caller's progress.

Browsing before enrollment writes nothing. Enrollment allows new authored
questions into that concept's due queue, without creating review rows. Previously
started cards keep their existing scheduling, even without enrollment. Explicit
one-off ratings/remediation still work. The legacy notes/review API is unchanged.

Reading records sections, not scroll offsets or completion. Ordinary return
restores a surviving section ID; an explicit fragment takes precedence, and
non-lesson fragments do not overwrite the bookmark. A removed section falls back
to the lesson's beginning without a GET-side database rewrite. With JavaScript,
confirmed section changes are serialized and rapid navigation saves the latest
requested section. Unconfirmed writes offer an exact retry; a 409 requires reload.
The page moves focus to the status only on an explicit keyboard retry. Without
scripts, the native selector/form saves the chosen section and the home link
returns to that anchor. A failed review rating renders recovery from data loaded
before the attempted write, without another progress query during the failure.

Home features the most recently updated enrolled concept and its latest open
practice session; when there is no enrollment it retains the existing newest
practice/fallback-concept selection. Existing unpublished practice remains
reachable. There is no enrollment withdrawal UI or self-assessment in 6a.

The disposable preview is at <http://127.0.0.1:5066/learning/>. Account 1 has a
scripted session and a saved reading position from manual verification; account 2
can demonstrate first enrollment. Both use the fixture credentials in the guide.
Earlier previews were not migrated/restarted; their Python processes predate 6a
and may be incompatible with auto-reloaded templates. Use the new preview.

## Checkpoint 6b: optional self-assessment

Keith approved this checkpoint and chose **four independent ratings** and
**dated check-ins** on November 7. The scale is a learner's reflection, never an
overall mastery score or an AI judgment. It is available before enrollment as an
optional baseline. Visiting, skipping, or changing an unsaved selection writes
nothing. Only Save check-in writes a new entry, even when its choices match the
previous entry. Each dimension may remain `not_assessed`; the other values are
`not_yet`, `with_help`, and `without_help`. No notes, charts, prompts from AI,
required completion steps, or new learning mode were added.

`ConceptSelfAssessment` is the one new table. Migration `e4f5a6b7c8d9` follows
`d3e4f5a6b7c8`; apply it before running the updated app on persistent data. No
backfill occurs. The primary key is `(user_id, concept_id, revision)`; each row
pins lesson `content_version` and `scale_version=1`, four ratings, UTC creation
time, and a UUID request ID unique per user. The lesson version has a composite
foreign key. Database checks enforce the scale and active/deleted row shapes.
Do not change version-one meanings in place when evolving this scale.

`self_assessment_service` shares the existing user-row lock pattern, with its own
revision sequence so bookmark autosaves cannot make a reflection stale. It
refreshes cached ORM state after locking. Exact request replay returns the
original dated snapshot even after later check-ins; reusing the ID with different
content conflicts. A different stale request returns 409 with the current
revision and latest snapshot. The website keeps the submitted choices, shows the
latest check-in, and offers an explicit Save as a new check-in. It never silently
overwrites. An unconfirmed write renders a standalone recovery page without
further DB reads, retaining the original request for a safe retry.

Explicit history deletion nulls the four rating columns in old entries and adds
a clear marker with the next revision. Dates, lesson versions, and request
identities remain, with no ratings; they fence old forms and prevent deleted data
from reappearing on a lost-response retry. Replaying a clear request returns its
original receipt and cannot delete entries created afterward. A stale deletion
requires fresh confirmation. These records belong only to that learner; deleting
a practice session does not delete concept-level reflection. User deletion uses
the table's existing-style cascading user FK.

The quiet Self-assessment (optional) link is in the concept header, outside the
four core mode tabs. Native selects and POST forms work without JavaScript;
the only new script guards unsaved choices and expands history anchor links.
There is no local/session storage. The latest choices prefill the form, and
history is collapsed until opened, with ten entries per page. Older history
pages still prefill the latest choices. Dates are explicitly UTC. A selected
practice session passes through owner/concept validation and round-trips to the
same Discuss/Build session; entering reflection never resumes or creates one.

Web routes are `/learning/concepts/<id>/self-assessment` (GET/POST) and its
`/delete` confirmation (GET/POST), with login, CSRF, and private/no-store headers.
The JWT API is `/api/v1/learning/concepts/<id>/self-assessments`:

- GET returns `revision`, `current`, `entries`, `next_before`, and `concept_id`.
  Use `?before=<next_before>` for older entries; pagination remains bounded as
  new entries are saved.
- POST accepts exactly `content_version`, `ratings` (all four keys),
  `expected_revision`, and `request_id`; it returns an allowlisted `checkin`.
- DELETE accepts exactly `expected_revision` and `request_id`; it returns
  `revision` and `cleared_through` for that deletion, including historical replay.

Owned history remains readable/removable if lesson publication is withdrawn,
without exposing draft content or allowing a new check-in against it. No private
reference/evaluation material, enrollment, reading position, review schedule,
practice/artifacts, feedback, AI request, or budget record is changed. No new
infrastructure was required. Four ratings are data, not an ordered promotion
system; self-assessment must not become a shortcut for demonstrated capability.

The new disposable preview uses port **5067**, with the same fixture credentials
as the [hands-on guide](learning-checkpoint-6b-test-guide.md). Account 1 has one
example reflection from manual verification, not a rating of Keith. Account 2
is fresh. Previous previews were left running with their data; use 5067 for this
checkpoint because their Python code/schema predates it. Tests used a separate
temporary PostgreSQL 18.6 cluster, removed after verification. No production
migration or content publication was performed.

## Open items and decisions to revisit

1. **Publication review and rollout owner:** Codex completed the delegated technical review in 5g and recommends the local pilot. `catalog-v3.json` is the current draft, with exercise revision 3 and concept/question revisions 2. General publication still requires an actual human reviewer and review date for that exact packet. No publication attestation was created by the delegated review. The approved and deployed 7b exception allows only exact labelled drafts behind the verified owner gate. It does not authorize general publication.
2. **Concept progress:** separately approved 6a/6b are implemented (November 7). `UserConceptProgress` contains enrollment/bookmark state; `ConceptSelfAssessment` independently records optional recognition/understanding/application/judgment check-ins. Existing rated cards remain eligible without enrollment; new questions enter a concept queue only after enrollment. The legacy API queue remains unchanged. Trial observations should guide future presentation; no overall mastery score or inferred promotion is implemented.
3. **Exact session schema and lifecycle:** decided and built through 3b (schema, constraints, payloads, replay, conflicts, limits, brief snapshots, turn freshness, pause/resume, delete). Choices made while building 3b that Keith may want to revisit: **Save and pause** saves before pausing; brief sources can be added only through the API (the website shows and preserves them); there is no brief history page; delete refuses SQLite without foreign keys. Ask Keith if a substantial departure is necessary.
4. **Provider and worker activation:** decided October 29: a worker thread in the web process, and Learning's own OpenAI project and key. The worker thread, request table, and content-free budget ledger exist (4a), and so does the OpenAI call process (4b). Activation (October 29 and 30): Keith created the project and key with a $50 hard limit, and live evaluations chose `gpt-6.1-sol` at low reasoning, with access and prices verified, and confirmed the deadlines, output caps, and context allowance. Checkpoint 7b moves production to a release phase plus one threaded Gunicorn web process; its post-initialization hook starts the existing worker only after readiness checks. `run.py` remains a development entry point. The separately approved 7a personal pilot instead uses `scripts/learning-pilot.py serve --live`; ordinary app-factory/CLI reads never start a worker.
5. **Profile versioning and evaluator contract:** profiles are versioned in code and pinned per session (decided October 29). The `evaluator-1` contract, strict structured outputs, and evidence/coverage validation are implemented in 5c; annotations and follow-up practice in 5d. Keith delegated the remaining live-results review on November 6. Codex's 5g assessment supports the current profile/model for local use, with feedback density to observe during the trial. Historical paid results remain pinned to exercise revisions 1/2.
6. **Content lifecycle and mobile representation:** explicit retirement, richer presentation blocks/visualization metadata, and the full taxonomy manifest remain future work. Today the importer stores resolved Markdown text, not precompiled portable presentation blocks. Agree any necessary schema evolution before Expo; do not silently invalidate version-1 content.
7. **Remaining validation and rollout:** local end-to-end, keyboard/accessibility-tree, recovery, budget, concurrency, and delegated content/AI review are complete through 5g. VoiceOver/NVDA listening and standalone Safari/Firefox remain unverified. Human attestation for general publication and approval to deploy the prepared private hosted pilot remain outstanding. Full snapshot coverage and explicit oversized rejection are implemented; multipass feedback is deferred by Keith's 5c decision. The broader multi-style AI evaluation set belongs to pilot expansion.
8. **Content-schema gaps against the approved plan:** the misconception mapping gap is closed in 5a through catalog/spec version 2 and exercise revision 2. The behaviour profile/version remains in code (item 5); the facilitator schema is unchanged. Feedback evidence/coverage is implemented in 5c; learner responses and follow-up review in 5d.
9. **Third-party scripts on private pages:** Marked (no SRI) and Alpine (no SRI, in the base template) load from jsDelivr, and the CSP allows `ws:`/`wss:` to any host. The practice workspace loads no Markdown library. Site-wide SRI and a narrower CSP are follow-ups.
10. **Proposals from the October 28 vision review.** Keith accepted three on October 29 (see Decisions): defer compaction out of Milestone 1, close the misconception loop, and report deterministic JSON/YAML checks first. Three wait for Milestone 1's completion:
    - After Milestone 1, expand content on web and give Expo concept Learn/Review before porting Discuss/Build.
    - Shape the progress model (item 2) around the vision's four levels, keeping retention and applied evidence separate. The optional reflection portion is now approved and delivered in 6b; a combined evidence/mastery dashboard remains outside that scope.
    - Agree a richer lesson schema before writing more concepts.
11. **Choices made while building 4a that Keith may want to revisit:**
    - A reply is queued only when its worst case fits this month's budget, priced from the full request body. Near the cap, Send therefore saves the turn without a reply, rather than queueing one that would fail at the worker.
    - The month reads as used up, and the owner sees that banner, once even the smallest reply (its output alone) can't fit, even before spending reaches the warning line.
    - After a pause, a reply whose call was already in flight still appears in the paused session (approved with the plan).
    - Asking for a reply to a turn that already has one still saves the page and reports `answered` (200 on the API), rather than failing with a 400.
    - The page stops checking for a reply after six failures in a row (about a minute and a half) and asks the learner to reload.
12. **Choices made while building 4b that Keith may want to revisit:**
    - Continue with recent messages picks the longest recent stretch that fits, so a long conversation may need it again a few messages later.
    - The selector sees only the latest message, as planned, so a question split over two messages may not reveal anything until it is asked in one.
    - Revealed requirements are listed in the order they were revealed, each linked to its reply; hinted replies are labelled, and the hint text appears only inside the reply.
    - The check-in notice stays from the 24th message on, rather than appearing once.
    - A tab that is waiting for a reply while another tab chooses Continue with recent messages shows the marker (and any new check-in notice) only after it reloads; polling brings the new turns but not those.
    - A connection that fails before anything is sent still keeps the reservation ("unknown"), which is conservative; it could be released.
    - The fake selector, used by the fixture, reveals a requirement only when a message repeats a cue or shares two distinctive words with one. Paraphrases are the live model's job.

## Recommended next checkpoint

Keith's approved Learning UI sequence is complete locally: a compact home,
dedicated reference/flashcard catalogs, and a shared Learn / Review / Discuss /
Build workspace. The selected practice session survives lesson navigation,
answer reveal, rating, remediation, and return to practice. Reading or opening
a mode never starts/resumes a session. Every Learning website route requires
login, and the portfolio navigation shows Learning only to signed-in users.
The original approved planning snapshot remains unchanged.

The [concept workspace guide](learning-concept-workspace-test-guide.md) provides
a short DevTools, HTTPie, and REPL walkthrough. The [home guide](learning-home-test-guide.md)
covers the library; the [practice guide](learning-workspace-test-guide.md) covers
unsaved work and recovery. `tests/test_learning_hub_browser.py` now runs separate
60-check hub and 70-check concept walkthroughs. See the checkpoint log for all
verification. Safari, Firefox, and screen-reader validation are still pending.

**Next:** use the [live private pilot](https://www.keithriordan.com/learning/)
for a short idempotency learning trial, following its
[hands-on guide](learning-checkpoint-7b-test-guide.md), with an
optional baseline and later check-in. New concepts, personalities, lesson-schema
changes, and Expo still require separate approval.

### Checkpoint 7b: private hosted pilot deployed — November 13

**Hosting audit.** Heroku app `keithriordan` runs on `heroku-24` in the US,
with one Basic `web.1` process, an existing Essential 0 PostgreSQL database,
and Heroku Scheduler. The pre-deployment release v164 used source `c5edc1b2`.
That commit was not
an ancestor of this branch, despite the initial audit note: its entire tree
matched the common ancestor. History-only merge `cd5555e` preserved deployed
ancestry without changing the reviewed `1142806` tree or force-pushing.
A database connection restricted to read-only transactions confirmed PostgreSQL
**16.14**, Alembic revision
`a4b5c6d7e8f9`, one verified administrator account (ID 1), and none of the new
curriculum/practice/AI-ledger tables. No Learning feature flags or dedicated
Learning provider key were configured on Heroku at that baseline. Existing secrets
were filtered in memory and were not copied into this document or tool output.

**Decisions approved by Keith.** Reuse this site/database and verified owner ID 1;
allow the exact labelled `catalog-v3.json` draft packet privately; start fresh
hosted practice. Keep local work readable, carry prior spending forward, and
disable local paid AI before hosted activation. The **same $5 total and $1
verification allowance** applies. No new service, database, worker dyno, or
publication attestation is needed. Keith subsequently explicitly approved deployment.

The local read-only check found one enrollment, the Codex verification session,
no review ratings or self-assessments, no pending/running AI requests, and five
settled charges totaling **$0.037859**. Cutover rechecked the same amounts and
froze local paid AI before hosted activation. The private cutover file carries
identity, exact draft fingerprints, ledger checksum/count and amounts by month,
never session content.

**Access and configuration.** `project/learning/hosted_pilot.py` validates the
operator's exact `LEARNING_HOSTED_APPROVAL` JSON and derives the owner ID/email,
draft allowlist, pinned models, context/output limits, secure cookies and verified
hostnames. Invalid configuration fails startup. Both Learning API blueprints,
every Learning website route and navigation require that verified owner; another
administrator cannot bypass it. Web cookies never authorize the JWT API.
Learning responses are private/no-store/noindex and labelled
`X-Learning-Content-Status: private-draft-pilot`. Owner pages show a draft banner;
Learning and account pages omit analytics. Learner projections still exclude
private references/rubrics; the source repository remains public.

**Spending and cutover.** `handoff-hosted` in the local launcher requires its
operator lock, original approval, current schema and no pending/running requests.
It atomically disables local paid AI before writing the private portable record.
A failed second write is safely replayable for the same target. Local reads and
edits remain possible; reauthorization and live restart are refused. Hosted
budget checks add carried costs to the existing ledger under its existing lock.
Uncertain reservations still count; released charges do not. The total never
resets across months, restarts or deletion. `LEARNING_HOSTED_AI_MODE` is `off`
by default, `verification` for the shared $1 cap, or `pilot` for the shared $5 cap.
Configured lower caps remain effective. Only Learning's dedicated key is accepted.

PostgreSQL migrations now take transaction-scoped advisory lock `(1427870284, 3)`
before reading the migration revision, with a 30-second lock wait limit. DDL and
the version-table update share that transaction. The new PostgreSQL rehearsal
starts at the deployed revision, preserves account/review/Grocery fixtures,
repeats the upgrade, restores its pre-upgrade backup, runs two competing release
processes, and verifies that a deliberate failure after DDL rolls back the whole
pending chain. No new table or migration is introduced by 7b.

**Runtime.** `Procfile` now has a release step (`scripts/release.py`) that migrates,
imports the exact unpublished packet idempotently and checks readiness without
starting AI. Heroku's [release phase](https://devcenter.heroku.com/articles/release-phase)
keeps the prior release serving if it fails, but does not undo committed database
or configuration changes. Web startup independently checks readiness before
starting the existing worker. Gunicorn **27.0.1**, one gthread worker/eight threads,
replaces the development server; preload/reload/multiple workers are refused.
This follows the [threaded Socket.IO deployment](https://flask-socketio.readthedocs.io/en/latest/deployment.html)
and needs no Redis or queue service. Production requires HTTPS through the Heroku
router; only the two observed domains are trusted. Local `run.py` is unchanged.

**Verification.** The suite ran **759 tests: 758 passed, one existing Linux-only
skip** on PostgreSQL 16, including 450 browser assertions. Nineteen added tests
cover every route's owner boundary, policy parsing, cutover failure recovery,
cross-month/concurrent budget accounting, release rollback/serialization, native
WebSocket upgrades with cookie/JWT auth, HTTPS login and real Gunicorn restart.
The existing 13 Node tests and dependency integrity checks pass. Dependency
audit findings required small existing-library updates to OAuthLib 4.0.1 and
pyasn1 0.6.5; Gunicorn is the only new runtime dependency. These pre-deployment
AI tests used scripted responses. The later runtime fix passed 79 targeted local
tests and all 18 provider tests against a fake endpoint on Heroku's Linux runtime.

**Actual backup rehearsal.** A consistent, read-only production snapshot restored
to a newly marked local database. Two release runs upgraded `a4b5c6d7e8f9` to
`e4f5a6b7c8d9`, preserved all **11,324 rows across 28 existing application tables**,
and imported six unpublished revisions with no sessions/charges. The fresh
private deployment backup/report is under
`.local/learning-pilot/hosted-rehearsals/20261113T184616Z/`; its dump SHA-256 is
`dd6d6649b0eca086105f8ef024dacbd176c858a5fb5c839374797baa96d33d33`.
The temporary clone was removed. Heroku backup **b011** preceded deployment;
**b012** completed after verification and includes the new work and ledger.
The stopped local pilot was backed up before its paid-AI freeze.

**Gotchas.** Use matching PostgreSQL 16 clients: the Mac defaults to version 18.
Heroku's public-schema ownership makes its dump explicitly recreate `public`;
restore now cleans only its exclusively created fresh target before loading.
The automated fixture exercises that ownership difference. Compare timestamps
in UTC and exclude Heroku's monitoring views when fingerprinting application
rows. CI now uses PostgreSQL 16 and matching clients on Ubuntu 24.04.

**Hosted verification and activation.** Release v166 deployed `cd5555e` with AI
off and migrated to `e4f5a6b7c8d9`. Owner-only pages/API, anonymous and non-owner
denial, draft labels, private headers, omitted analytics and reference fields,
public portfolio, existing lists and an authenticated native WebSocket handshake
passed. Five deployed workspace assets matched the reviewed source hashes.

The first live selector failed before Python could start: Heroku's shared Python
requires its interpreter library directory. AI was turned off, the narrow
runtime fix was committed as **`93a24a2`**, and fake-provider tests passed on
Heroku before redeployment. One explicit retry used the original saved turn and
artifact revisions. The initial **$0.007315** uncertain reservation still counts;
there was no automatic paid retry and no budget reset.

The recovered interviewer disclosed only the requested retention constraint,
referenced saved drafts and asked the learner to choose expiry behavior. Feedback
assessed the complete snapshot, validated eight exact citations, distinguished
missing evidence from errors and acknowledged Codex assistance. No review rating,
enrollment or self-assessment was recorded on Keith's behalf. The clearly labelled
setup example is session `d0739690-1e7b-485f-842a-e36257a6976d`, snapshot 5;
it is paused and is not evidence of Keith's unaided ability.

A real web restart preserved the session export, feedback, login cookie and
ledger; explicit resume/pause worked. Final **v171 / `93a24a2`** is in `pilot`
mode with the original $5 cap, one Basic web dyno, and no active AI requests.
Spending at activation: **$0.037859 carried**, **$0.030851 new settled calls**,
**$0.007315 reserved** = **$0.076025 counted**, leaving **$4.923975**. All
verification remains within the shared $1 allowance. Content-free activation
records and private response snapshots are under
`.local/learning-pilot/hosted-deployment/`; temporary operator credentials were
removed after verification. No passwords or existing signing keys were changed.

**Remaining:** a short personal learning trial and the already recorded
Safari/Firefox/screen-reader checks. Content expansion, new personalities and
Expo remain unapproved. Unrelated mobile interval-timer changes and its
`.gitignore` edit remain outside these commits. Keep the owner gate enabled
when turning AI off, and never reactivate a restored hosted database until its
missing spending has been reconciled; see the rollout guide. Only Heroku was
pushed; no GitHub push or PR was created for activation.

### Checkpoint 7a: personal local pilot — November 7

Keith explicitly approved $5 total for this pilot, including at most $1 for
Codex verification, and labelled draft content in the isolated local database.
The current draft has delegated technical review, not a human publication
attestation. No publication or production deployment occurred.

**Entry point and storage.** `scripts/learning-pilot.py` disables dotenv before
imports. `scripts/learning_pilot.py` supplies explicit settings to the existing
Flask factory and starts the existing worker only for `serve --live`. It binds
127.0.0.1, permits Learning/auth/static routes, retains CSRF/account ownership,
uses instance-specific cookies, excludes login/Learning analytics, and reads
only Learning's dedicated provider key. Startup never seeds or migrates. It
checks the schema against the checkout's Alembic head. `status` is read-only and
works while the server runs. Backup/upgrade require the operator lock and a
stopped server. A port collision is detected before any worker starts.

The actual database is `learning_personal_pilot` on the existing Postgres.app
server, loopback port 5432; the website is on 5068. It is migrated through
`e4f5a6b7c8d9`. State, login, approval, logs, and backups live under the
Git-ignored `.local/learning-pilot/`. Settings/credentials are private files;
a UUID database comment binds them to the correct database. Remote URLs,
connection-option redirects, existing databases, and mismatched identities are
refused. No existing portfolio database or preview was changed.

The existing Poetry environment used Python 3.13.11 despite the repository pin.
A separate locked environment using **3.13.18** is under
`.local/learning-pilot/venvs/`; commands use `POETRY_VIRTUALENVS_PATH` to select
it. Existing previews keep their original environment. Node checks/Sass use
**24.22.1**. On a fresh checkout, select the pinned interpreter, install locked
dependencies, run `init` once, and then `authorize --total-usd …
--verification-usd … --allow-idempotency-draft` only for an explicitly agreed
allowance. `resume-init` can complete interrupted initialization using its
original identity/login without resetting existing users or progress.

**Visibility and spend.** `approval.json` records the explicit allowance and
exact `(item_id, version, checksum)` tuples from `catalog-v3.json`. The importer
writes six unpublished immutable snapshots (lesson/questions v2, exercise v3),
with no reviewer/date attestation. The guarded local factory supplies the
allowlist to `curriculum_service.learner_visibility`; normal readers remain
published-only. Learner projections are unchanged, with a `local_draft` marker
on locally visible items and an HTTP draft-pilot header. Private reference,
facilitator, and evaluation fields do not enter learner responses or bundles.
The authored source still exists in the public repository.

`LEARNING_AI_TOTAL_CAP_USD` adds an optional all-month limit to the existing
content-free ledger and advisory budget lock. Monthly/per-call/context limits
remain enforced, and normal behavior is unchanged when the total cap is absent.
Settled costs plus outstanding/uncertain reservations count. Deleting sessions,
restarting, or crossing months cannot refund/reset the allowance. `serve --live
--verification` applies $1 to the same total ledger, so repeated verification
runs do not receive another $1. `serve --live` uses the approved $5. Defaults
remain AI-off; an absent/zero approval cannot enable calls. There is no automatic
retry or automatic cap increase. Model and prompt choices are unchanged:
`gpt-6.1-sol`, low interviewer reasoning, medium feedback reasoning, standard
service tier. Published rates were checked again on November 7 against the
[official model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol).

**Recovery.** `scripts/learning_pilot_storage.py` handles exclusive database
creation, private files, operator locking, `pg_dump`, checksum verification,
and `pg_restore` into a new database. Backups contain the dump, settings,
approval, and login, but do not automatically capture the provider key. Restore
rotates signing secrets and retains draft access/passwords. Restored instances
are permanently AI-off in this checkpoint: an older ledger can omit later
charges, so reactivation requires spending reconciliation and a new reviewed
approval/path. There is no force-live flag or automatic restoration of live
spending authorization. This limitation preserves the total allowance.

The actual verified backup is `backups/verified-7a`, restored independently to
`learning_pilot_restored_7a` with state in `restored/checkpoint-7a`. Original and
restored conversation/artifact/feedback exports matched after excluding only
the export timestamp; all five settled charges and their total matched too.
The real web process was restarted, and the same browser login, paused session,
artifacts, snapshot, feedback and budget remained available. The restored copy
stays offline. Files are local backups, not off-computer disaster recovery.

**Verification.** The final full run passed **739 tests, with one existing
Linux-only skip (740 run)** on isolated PostgreSQL 18.6, Python 3.13.18 and Node
24.22.1. It includes 450 browser assertions (225 practice / 70 concept / 60 hub /
40 progress / 55 reflection), fresh full migrations/metadata comparison, actual
CLI process restarts, backup restoration, approval/key isolation, draft privacy,
and concurrent/cross-month/deletion-safe budget reservations. Thirteen Node
tests, dependency integrity, Sass, and `git diff --check` pass. Final local-only
pause copy received a focused route/PostgreSQL rerun.

Live verification used session `31806d3b-7e95-4b39-b78a-04736a0dbb48`, snapshot 7:
two interviewer turns referenced the three saved artifacts; one complete-snapshot
feedback request produced three evidenced strengths, an appropriate expiry-contract
concern, and a trade-off. It accepted the new READ COMMITTED statement after a
conflicting insert, and did not claim the external effect was atomic. It correctly
recognized the Codex authorship and missing final unaided trace. This is a bounded
integration check, not a new broad evaluator benchmark or proof of learning.

All five calls settled: select 1,044 + reply 4,086 + select 782 + reply 6,546 +
feedback 25,401 = **37,859 micro-dollars ($0.037859)**. There are no outstanding
requests or uncertain reservations from verification. **$4.962141 remains**.
The session is paused and explicitly marked as setup verification in its first
message. Enrollment, review ratings and self-assessment remain empty for Keith
to begin his own trial. Private report/export files are beside `settings.json`.

**Gotchas fixed.** Talisman was re-enabling secure-only cookies over loopback
HTTP; actual HTTP clients exposed the issue that Flask's test client missed.
Only the local entry point disables that override, retaining HttpOnly/SameSite
and CSRF; production HTTPS is unchanged. PostgreSQL can return timestamps with
its local UTC offset; the practice timestamp renderer now converts to UTC before
printing a UTC label. Stored times were already correct; no data rewrite was
needed. Local-only navigation excludes unavailable portfolio/password-reset
routes and pause text correctly refers to this computer.

### Activation record

Activation (see Durable AI requests and spending), done locally on October 30 apart from production enablement:

1. Keith creates the Learning OpenAI project and key, and sets its spending limit. The project and key exist (October 29), and the key is in the local `.env`. OpenAI sets spending limits per organization or project, not per key. Set the project's monthly limit with **Enforce a hard limit** on; without that, a limit only alerts. One full evaluation run makes 26 calls, with about 21,000 input tokens (estimated from request bytes) and at most 18,200 output tokens under the current caps.
2. Run `flask learning-eval --provider openai` on candidate models, within a small evaluation budget. Fill `PRICES` for each candidate first, so the results show cost. These calls don't go through the ledger or the monthly cap: the project's spending limit bounds them, and the results file records each call's cost. Keith set a $50 hard limit on the Learning project.
   - **Done October 29.** Three runs each of `gpt-6.1-sol` and `gpt-6.1-terra` at low reasoning; `LEARNING_AI_REASONING_EFFORT` is now read from the environment.
   - Both models passed every privacy and disclosure check. Sol's selector differed from the case once in 39 turns: it read "What should I look at next?" as a hint request. Terra's matched every case.
   - Median turn time was 4.2 s (Sol) and 3.9 s (Terra), with p95 of 5.4 s and 4.4 s. Each 26-call run cost $0.043 and $0.023.
   - Both models call hidden requirements "unspecified", because `interviewer-1`'s rules tell them to call anything outside the revealed facts unspecified. Fixed in `interviewer-2` (second round, below).
   - Results are in `docs/evaluations/learning-interviewer-2026-10-29-*-run1..3.json`.
   - **Second round, October 29.** `interviewer-2` with Sol, Terra, and `gpt-6-astra` (OpenAI's flagship, five times Sol's prices), three runs each at low reasoning. Every check passed in all 39 turns for all three models, every selection matched, and no reply called anything unspecified.
   - Terra said, in all three runs, that the revealed delivery fact doesn't cover whether delivery must finish before the API responds, though the fact says delivery is asynchronous. Sol and Astra replied almost identically; Astra asked what an ambiguous question meant where Sol answered both readings.
   - Median turn time was 4.9 s (Sol), 3.7 s (Terra), and 4.2 s (Astra), with p95 of 6.2, 5.1, and 5.5 s. Each 26-call run cost $0.045, $0.022, and $0.226. A synthetic 24-turn session with caching is estimated at $0.13, $0.07, and $0.70.
   - Prompt caching is on by default: the one prompt over 1,024 tokens was written to the cache in run 1 and read back in runs 2 and 3, and the results record both. Results files now also record `reasoning_effort`.
   - Results are in `docs/evaluations/learning-interviewer-2026-10-29-interviewer-2-*-run1..3.json`.
   - **Third round, October 30: catching flaws.** Ten scratch cases test what the reviewed cases don't. Nine are learner designs or arguments with one planted flaw each, such as check-then-insert with no unique constraint, an order committed before its receipt, keys shared across customers, and a warehouse publish after the commit. The tenth is a sound design as a control. Three follow earlier turns: a fix that doesn't work, a wrong argument from the learner, and a fix that adds a bug. Sol and Astra ran each case three times at low reasoning with `interviewer-2`. A separate grader scored the 60 replies blind, against rules written before the runs.
   - Both models caught all 27 planted flaws and passed all 3 control runs. Neither agreed with a flawed design, gave away a fix, stated a hidden requirement, or invented a flaw. Their replies are nearly word for word the same; the grader preferred Astra's in 7 of 10 cases, over small differences in wording. Both sometimes asked two questions where the rules say one: Sol in 8 of 30 replies, Astra in 7. The control turned out to have one small real gap, which every reply found: its contract forgets keys after 72 hours, but nothing checks a receipt's age before cleanup.
   - Median turn time was 6.5 s (Sol) and 5.9 s (Astra), with p95 of 8.8 and 8.1 s, at about 1,500 input tokens per reply. The three runs cost $0.10 and $0.55.
   - Recommended: Sol for the interviewer. Astra didn't catch more or teach better in this role; a stronger model is more likely to matter for feedback (checkpoint 5).
   - Results are in `docs/evaluations/learning-interviewer-2026-10-30-flaws-interviewer-2-*-run1..3.json`; each case carries its inputs and grading rule. The cases aren't yet reviewed into `tests/fixtures/interviewer/`.
3. Keith reviews the outputs, including each case's `reply_should`, and picks the model. **Done October 30: `gpt-6.1-sol` at low reasoning**, for the selector and the reply. It is the `openai` provider's default; `LEARNING_AI_MODEL`, `LEARNING_AI_SELECTOR_MODEL`, and `LEARNING_AI_REASONING_EFFORT` override it, and any model in `PRICES` can replace it with no code change.
4. Record the verified prices, the tier, `pricing_version`, the measured p95 latency, and the cost per session. Size `LEARNING_AI_CONTEXT_BYTES` and the output caps to the model. `interviewer-2` is released; a test pins its text. **Done October 30:**
   - Prices for the `default` tier, `pricing_version` `openai-2026-10-29`, checked against OpenAI's pricing page on October 29, per million tokens: $2.00 input, $0.10 cached input, $2.50 cache write (30-minute lifetime), and $10.00 output. Above 272K input tokens: $4.00, $0.20, $5.00, and $15.00.
   - Latency: the p95 turn (selector and reply together) was 6.2 s over the reviewed cases and 8.8 s over the larger flaw cases. The slowest of 216 calls took 7.1 s.
   - Cost: a synthetic 24-turn session is about $0.13 with caching and $0.22 without. Critiques run longer than round two's replies (about 120 output tokens against 70) and add about a cent. Three sessions a day comes to about $12 a month, inside the $50 cap.
   - Limits kept, from the measurements: the 512 KiB context allowance, 1,200 reply and 200 selector output tokens, and the 60-second call deadline (see Continuity and context).
   - One live session through the app: three turns on a disposable PostgreSQL database with the defaults, through Send, the worker, the call process, and the ledger. Both requirements asked about were revealed, all six charges settled with their write tokens, and the session cost $0.013. The first turns' prompts shared too short a prefix to read from the cache; longer sessions do.
   - Cache writes are priced (October 29). GPT-6 and GPT-6.1 models bill tokens written to the prompt cache at 1.25 times the input rate, in place of it (2.5 times for the 12-hour lifetime, which the app doesn't request). `PRICES` has a `cache_write` rate; the call process and its parent read `input_tokens_details.cache_write_tokens`; `cost()` bills cached reads, writes, and the rest separately; and `worst_case` prices every input byte as a write. The ledger records them too: `learning_ai_charge.cache_write_tokens` (migration `f9a0b1c2d3e4`, October 30).

For general production publication, content review and a separate approval remain required. Checkpoint 7b instead has explicit approval to use exact labelled drafts privately and transfer the existing dedicated Learning allowance/key after local AI is frozen. Its private deployment was approved and completed November 13. A later general rollout should use its own key, which Keith creates. The recommendation is a separate OpenAI project with a hard limit a little above the app's monthly cap, so development and evaluation spending can't use up production's limit. That key goes in the production config, never in a `.env` file. Checkpoint 5 can be planned meanwhile.

Checkpoints 5a–5e implement content mappings, submission snapshots, deterministic syntax checks, evidence-linked generated feedback, learner responses, optional follow-up practice, and session export. Checkpoints 5f/5g complete the local demonstration, targeted accessibility review, delegated content/AI review, and private reference correction. Separately approved 6a/6b add enrollment, saved reading position, and optional dated self-assessment. Checkpoint 7a supplies the persistent local pilot with an approved total allowance, exact labelled drafts, live verification, and backup/restart recovery. Production publication and remaining browser/screen-reader validation are recorded follow-ups. The remaining vision-review proposals (open item 10) and Milestone 2 beyond 2a still need Keith's explicit approval.
