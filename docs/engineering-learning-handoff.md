# Engineering Learning Platform Handoff

As of October 29, 2026, **Milestone 1 is partially implemented: Learn and Review work on web, and practice sessions hold Build artifacts with history, conflicts, and recovery (checkpoint 3a) plus the discussion record: learner turns citing exact revisions, an editable brief, pause/resume, and delete (checkpoint 3b). The AI interviewer, feedback, and export do not exist yet.** Continue on `feature/learning-content-foundation`. The next implementation checkpoint is 4, the interviewer. Keith made its decisions on October 29 (see Decisions); it needs a detailed plan before building.

This handoff records the approved architecture and refinements, the implementation through checkpoint 3b, and the remaining acceptance work. It complements the [approved revised plan](engineering-learning-revised-plan.md), [checkpoint log](engineering-learning-milestone-1.md), and [curriculum contract](../curriculum/README.md). The original and refined plans were approved in the Codex chat **Plan engineering learning platform**; the revised plan is now preserved in the repository, with relevant baseline decisions captured here. The refined milestone order and unified session model supersede the original early milestone order and separate Discuss/Build sessions.

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

Only **Milestone 1** is authorized. Do not start Expo implementation, expand to the other concepts, or add other AI personalities without further approval. No executable sandbox, full IDE, voice, recording, vector database, CMS, or agent framework is needed for this milestone. Important architectural decisions not covered below must go back to Keith.

Work in small, cohesive checkpoints with separate commits. Report changes, meaningful verification, and unresolved limitations. Keith's requested testing guides are hands-on engineering practice: Python REPL and debugger experiments, DevTools Network/Console/Sources/Performance, and HTTPie/Postman requests. Keep those separate from automated test evidence.

## Delivery plan and current status

| Milestone | Scope and gate | Status |
| --- | --- | --- |
| 1 | One complete concept on web, including continuity, feedback, privacy, budgets, export/delete, and a runnable demonstration. | Approved; checkpoints 1, 2, 3a, and 3b complete locally. |
| 2 | Same experience in Expo; resume across web/mobile without losing or overwriting confirmed work. | Requires approval after Milestone 1. |
| 3 | Fourteen production-systems concepts, about 42 questions, representative Build work, remaining discussion styles, and a short diagnostic. | Requires separate approval; content breadth must not delay the first experience. |
| 4 | Four-week personal trial with unaided baseline and delayed transfer probes, including roughly 7- and 21-day checks. Evaluate usefulness, misleading feedback, usability, and cost. | Later. |

The longer-term direction remains a reviewed curriculum of roughly 200–300 concepts, deeper practice, possible FSRS evaluation, isolated code execution, and eventually voice/personalization. These are planning estimates and later choices, not current deliverables.

Within Milestone 1:

| Checkpoint | Deliverable | Status |
| --- | --- | --- |
| 1 | Versioned content, validation, projections, importer, draft idempotency material, additive migration. | `1f344a5` — complete locally. |
| 2 | Web lesson, visualization, answer reveal, shared review scheduling, version-pinned logs, privacy treatment. | `3b108bf` — complete locally. |
| Documentation follow-up | Replace test-suite instructions with interactive investigation guides. | `0c2848a`. |
| 3a | Practice sessions pinned to a published exercise, immutable artifact revisions, idempotent saves, per-artifact conflicts, ownership, failure recovery, web workspace, JWT API, feature flag. | `fe91fe2` (persistence and service) and `709658b` (web workspace and JSON API) — complete locally. |
| 3b | Discussion turns citing exact artifact revisions, editable session brief, pause/resume, delete. | `b7ae1e2` (service) plus the following "workspace and API" commit — complete locally. |
| 4 | Interview behavior, PostgreSQL worker, provider adapter, disclosure, durable requests, budgets, context compaction and recovery. | Not started. |
| 5 | Evidence-linked feedback, remediation, export/delete, complete recovery demonstration and milestone acceptance. | Not started. |

No push, PR, deployment, production migration, or production publication was performed for these checkpoints. Content remains an AI-assisted draft awaiting human technical review; demo publication is not production approval.

**Deploying this branch migrates production.** The `Procfile` runs `flask db upgrade; python run.py`, so every deploy applies pending migrations, and the `;` starts the app even if the upgrade fails. Practice stays hidden unless `LEARNING_PRACTICE_ENABLED=1`; with the flag off, no page queries the practice tables, so Learn and Review keep working even if that migration failed.

## Decisions and reasons

| Decision | Reason and consequence |
| --- | --- |
| Extend Flask/PostgreSQL and existing feature services. | Preserve the working application and minimize operational changes. Website authentication remains Flask-Login plus CSRF, which is enforced only through Flask-WTF forms: there is no global `CSRFProtect`, so a cookie-authenticated JSON endpoint would have none. JSON API authentication remains JWT. |
| Keep existing SM-2/custom half-life scheduling and review history. | Changing learning modes and the scheduler simultaneously would obscure results and risk progress. The half-life implementation uses fixed multipliers, not a fitted regression model. Evaluate FSRS separately later. |
| Git-authored JSON and Markdown; immutable resolved snapshots in PostgreSQL. | Content stays reviewable in Git, while historical sessions and reviews can refer to the exact material used. No CMS is needed. |
| Select the highest published revision instead of maintaining a mutable publication pointer. | Avoids another mutable field and circular foreign key. A newer draft does not hide an older published version. |
| Human review before publication. | Schema checks cannot establish educational accuracy. Architecture approval does not attest review of lesson content, hidden constraints, alternatives, or rubrics. |
| Explicit learner/facilitator/evaluator projections. | Prevent answer/reference leakage through accidental serialization or overly broad prompts. Application privacy does not make the public Git repository secret. |
| One practice session with conversation and multiple evolving artifacts. | Discuss and Build are complementary views of the same work. Avoid duplicated sessions and disconnected feedback. |
| Immutable artifact revisions without a separate artifact identity table. | Group revisions by stable artifact ID; this supports history, conflicts, and evidence references with a small model. |
| One PostgreSQL-backed worker and foreground polling. | Save work before generation, survive web-request timeouts/restarts, and avoid Redis/Celery or streaming infrastructure for the pilot. |
| Soft check-in at 24 learner turns, not a hard ending. | Substantial scoping/design conversations need continuation without losing decisions, requirements, or artifacts. Context and spending still have hard bounds. |
| Owner-only paid AI and a separate Learning budget. | Limit exposure while validating usefulness. Exhausting the AI budget must not block saving or reading work. |
| Retention and applied evidence remain separate. | Self-rated recall, assisted reasoning, and independently verified implementation are different kinds of evidence. AI findings must not silently change review ratings or schedules. |
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

## What exists in the repository

### Content and publication

[The idempotency package](../curriculum/idempotency/catalog.json) has six version-1 items: concept `idempotency`; questions `idempotency:timeout`, `idempotency:race`, `idempotency:scope`, and `idempotency:external-effect`; exercise `idempotent-order-api`. The three lesson sections are `overview`, `retries`, and `design`. Its prerequisites include descriptive prior knowledge; it does not fabricate prerequisite concept records for content not yet authored.

The exercise expects `api`, `schema`, and `algorithm` artifacts; an exercise may expect at most 20, so they fit one practice form and one save. Its schema separates `brief`, `facilitator`, and `assessment`. The brief contains scenario, objectives, functional/nonfunctional requirements, prerequisites, artifact expectations, and public assessment dimensions. Server-side content contains disclosure cues/facts, interviewer instructions, allowed hints, alternative approaches, anchored rubrics, and remediation links. Do not copy those private packets into future UI fixtures, HTML, bundles, or session exports.

`schema_version: 1` versions the catalog; exercise `spec_version: 1` versions the simulation contract; each item's integer `version` versions its content. Strict schemas reject unknown fields, invalid or duplicate IDs, duplicate JSON keys, invalid references, prerequisite cycles, and invalid versions, including booleans masquerading as integers. Markdown paths cannot escape the package, including through symlinks. Resolved Markdown text participates in the checksum.

`CurriculumItem` stores stable ID and kind. `ContentRevision` uses `(item_id, version)` as its primary key and stores schema version, checksum, resolved JSON payload, import timestamp, and publication attestation. Content immutability is enforced by application import paths; it is not a database permission boundary against administrators.

`validate-curriculum` validates files without accessing database tables. `import-curriculum` requires PostgreSQL and defaults to rollback. `--apply` saves drafts. Publication additionally requires `--publish`, a real `--reviewed-by`, and actual `--reviewed-on` date. The importer owns a separate transaction, uses a PostgreSQL advisory transaction lock to serialize rare catalog writes, and atomically imports/publishes the batch. Ordinary review operations do not acquire that lock.

Repeating identical content is safe. Changing a payload under the same ID/version fails. Publishing behind a newer published revision fails. Omitting items does not delete or retire them. There is no startup/migration content seed, retirement workflow, or content administration UI.

### Web Learn and Review

Authenticated `/learning/` lists published concepts alongside legacy notes. `/learning/concepts/idempotency` renders expandable lesson sections and the retry simulation. The simulation is reviewed application JavaScript; curriculum files cannot inject executable code. Markdown uses Marked and DOMPurify at the locked versions, loaded from jsDelivr, with a restrictive allowlist; only the DOMPurify tag carries a checked SRI hash. If they fail to load, escaped source text remains readable.

`GET /learning/concepts/idempotency/review` selects a due question. **Show answer** performs another GET carrying `card_id`, `content_version`, `expected_revision`, and `request_id`. The initial learner response omits the answer and explanation. Ratings are `Again=0`, `Hard=3`, `Good=4`, `Easy=5`.

POSTing the CSRF-protected form calls the existing `rate_card_for_user`. On PostgreSQL, a user-row lock serializes saves; progress, review log, and durable receipt commit together. A replay with the same UUID/payload returns the recorded result; reusing the UUID with a different payload or submitting stale progress produces a conflict. Successful saves return 303 then a fresh queue GET. Save failures preserve the attempt for explicit retry. Version pinning allows an already-open question to finish against its original content revision.

Committed reviews survive navigation and reopening because the queue derives from database progress. This is not yet recovery for a practice conversation or unsaved artifact. There is no new browser-side review queue or client storage.

The JSON API under `/api/v1/learning` remains the legacy notes/review/rating/receipt surface and does not expose concepts; practice sessions have their own API (below). The concept web adapter feeds the shared scheduler without changing that API's due queue. Curriculum and legacy note namespaces are checked to prevent accidental sharing of progress identities.

Personal Learning responses use `Cache-Control: private, no-store`. The shared base template omits Google Analytics and Hotjar on authenticated Learning pages. Sentry reporting is strictly allowlisted in `project/monitoring.py`. Practice routes have their own leakage checks (below); provider errors and AI telemetry will need theirs.

### Practice sessions (checkpoints 3a and 3b)

`LEARNING_PRACTICE_ENABLED` (default off) gates every practice route and query. With it on, a concept page's **Apply it** section starts a session for a published exercise (`POST /learning/practice`), and the Learning index lists open sessions under **Continue practising**.

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
- **Pause and resume.** Each is an idempotent status change with a receipt. Any learner save or turn resumes a paused session. Fencing pending generation arrives with checkpoint 4. Nothing pauses, resumes, or reopens a `completed` session; checkpoint 5 decides what completion allows.
- **Delete.** It takes the owner lock and deletes the session row; database cascades remove its revisions, messages, citations, and receipts. There is no receipt to replay, so a repeat reports not found. It refuses to run on a SQLite connection without foreign-key enforcement, because SQLite would otherwise skip the cascades and keep every row.

The workspace (`/learning/practice/<id>`) is one Flask-WTF form whose CSRF token lasts 24 hours, with Discuss (scenario, conversation, message box, brief editor) and Build side by side on wide screens. **Send message**, **Save work**, and **Save and pause** (or **Resume**) all submit the whole form, so no button discards other work; a hidden first button makes Enter in a field save, never send. Saving with a typed message re-renders the page with the message kept, flagging anything that changed elsewhere while it was written. Every rejected request re-renders the learner's text and message:

- **400:** an expired CSRF token or invalid input, shown beside the artifact, brief, or message.
- **409:** a conflict or an out-of-date Send. Saved versions appear beside the learner's text, untouched parts refresh, and new turns are marked; saving or sending again is an informed choice.
- **503:** a database failure. A standalone page that needs neither the database nor the shared layout holds the artifacts, brief entries, and message, and retries the same action. An unknown outcome keeps the request ID, so a retry replays rather than duplicates.

`/learning/practice/<id>/delete` is a confirmation page that says there is no undo and that backups are separate. Deleting returns to the lesson; repeating it, or targeting another account's session, lands on Learning with "doesn't exist or was already deleted".

Logs carry only exception class, SQLSTATE, and constraint name (`describe_failure`), and SQL parameters are hidden in every environment. History pages are addressed by artifact ID and revision number. A small script adds an unsaved-changes prompt and a UTF-8 byte counter; nothing depends on it.

The JWT API under `/api/v1/learning/practice` uses the same service: list, start, read, and delete sessions; `PUT …/artifacts/<artifact_id>` and `PUT …/brief`; `POST …/turns`, `POST …/pause`, and `POST …/resume`; revision history; and receipts. In the session detail, `brief` is the exercise's authored brief and `session_brief` is the learner's; `PUT …/brief` replaces the latter. Responses are explicit field lists. The 409 codes are `stale_artifact` (with the saved bodies), `stale_brief` (with the saved brief), `stale_transcript` (with `latest_sequence`), and `request_conflict`; validation errors name a `part` (`artifact`, `brief`, or `turn`) and a `field`. Each 503 says whether to retry with the same request ID.

### Migrations

| Revision | Change | Downgrade consequence |
| --- | --- | --- |
| `a4b5c6d7e8f9` → `b5c6d7e8f9a0` | Adds `curriculum_item` and `content_revision`; no user/progress seed or rewrite. | Removes catalog tables and their content. |
| `b5c6d7e8f9a0` → `c6d7e8f9a0b1` | Adds nullable `review_log.content_version` and composite FK to the exact content revision. Existing logs stay null. | Removes version linkage while retaining rating/scheduling history. |
| `c6d7e8f9a0b1` → `d7e8f9a0b1c2` | Adds `practice_session`, `artifact_revision`, `session_message`, `session_message_artifact`, and `practice_receipt`, with named constraints and database cascades. | Removes every practice session and its revisions, messages, citations, and receipts; catalog and review data stay. |

These migrations were exercised on populated disposable PostgreSQL fixtures, including downgrade and ORM/schema parity. CHECK constraints are verified separately, because Alembic's comparison ignores them. Do not downgrade real content as a routine feature rollback. To withdraw practice while keeping saved work, turn `LEARNING_PRACTICE_ENABLED` off.

## Remaining architecture to implement

Everything in this section is approved direction, not an existing subsystem.

### Session record: what later checkpoints add

Checkpoints 3a and 3b implemented sessions, artifacts, turns, the brief, pause/resume, and delete (above). Later records reuse the same ordered `SessionMessage` table:

- **Interviewer replies (checkpoint 4)** are `interviewer` turns. The `AIRequest` is created inside Send's transaction and pins the brief record and the turn's cited revisions. Pause fences pending generation; delete must cancel pending work and fence late responses.
- **Brief entries from the interviewer (checkpoint 4)** use the bases `scenario_fact` (disclosed constraints) and `interpretation` (unconfirmed model readings). The website's brief editor must then round-trip their basis, and the rules for learner edits of those entries need deciding. Today only `learner` entries exist.
- **Assistance history** (permitted hints, explicit style changes) is recorded as `assistance` messages once checkpoint 4 introduces assistance.
- **A submission checkpoint** (the set of revisions feedback evaluates) is a `submission` message in checkpoint 5, which also decides what a `completed` session allows.

Responses and feedback must identify which revisions they reviewed. AI suggestions never overwrite learner artifacts automatically. Persisting foreign IDs, reading another user's history, and replaying another user's request must keep failing; tests for each exist for 3a and 3b.

### Interview behavior and disclosure

The interviewer challenges reasoning and asks focused follow-ups without prematurely teaching a reference solution. Coaching gives graduated help; collaborative scoping negotiates requirements and dependencies; design review critiques alternatives. Changing from interview to coaching must be explicit and recorded. Do not implement the additional profiles merely because their schema values exist.

For hidden constraints, a bounded selector receives the learner turn and authored clarification cues and returns eligible IDs. Validate IDs server-side; provide only approved facts to the conversational call. The selector does not receive reference solutions, and the conversational call does not receive all unrevealed facts. Commit successful disclosure with the response and visible requirements record. Unspecified facts remain unknown; learner assumptions do not become scenario facts.

The existing `facilitator_view` can project approved IDs, but there is no selector, disclosure persistence, provider call, prompt suite, or behavior evaluation yet. Separately version prompts/profiles and pin all inputs used for a result. Profiles live in code with their own version, pinned when a session starts.

### Durable AI requests and spending

Start with one configurable OpenAI adapter using application-owned context, structured outputs, and `store: false`. Learning has its own OpenAI project and key, separate from JobWizard's. The original candidate was GPT-6.1 Sol with low reasoning for turns and medium for feedback; it has not passed Learning evaluations. Verify model access and current pricing before activation. Do not silently switch models after failures or couple Learning to JobWizard's extraction workflow.

`AIRequest` owns job identity, status, lease, selected exercise/context/artifact revisions, transcript boundary, provider/model/prompt versions, usage, and cost reservation. Commit user input and its request atomically, then return 202. The worker (for Milestone 1, a thread in the web process, started only by the web entry point) claims under a short transaction, releases database locks before network calls, enforces a provider deadline, and commits only if its lease/session state still permits completion. Allow one active generation per session. Foreground clients poll and recover results after reconnect.

Expired running jobs become interrupted with explicit retry. Deletion must cancel pending work and fence late responses. Database deduplication cannot guarantee exactly one provider charge after an uncertain network outcome; keep conservative reservations for such calls rather than blindly refunding/retrying.

Only Keith's account, named by an explicit setting, may initiate paid Learning requests; with the setting unset, paid AI is off. Enforce **$50/month**, warn at **$40**, and count actual usage plus in-flight/uncertain reservations in PostgreSQL. Track the pricing version and keep Learning accounting separate from JobWizard. Disclosure, evaluation passes, and synthesis all consume this budget, as would compaction if it returns. Hosting is separate. At the cap, block new paid generation while preserving reading, review, editing, saving, export, and later resumption.

### Continuity and context

Keep 24 learner turns as a configurable progress check-in. Continuation stays in the same session. Suggested duration, input allowance, output limits, and deadlines are server policy; no numeric output limit or deadline has been finalized in code.

Compaction is deferred out of Milestone 1 (Keith, October 29). Each call includes pinned instructions and disclosed facts, the current session brief, the current artifact revisions, and the whole transcript, within a configurable input allowance larger than the original 32,000 tokens. Keep prompts append-only so provider caching applies.

The learner-visible, editable brief preserves requirements, disclosed constraints, assumptions, open questions, decisions/rationale/alternatives, current artifact references, assistance, and next step. Distinguish authoritative facts, learner decisions, and unconfirmed model interpretations. Support pinned/corrected entries with links to original evidence.

If essential context cannot fit, stop generation with a specific explanation and focused-selection/context-adjustment options; do not truncate silently or complete the session automatically. If compaction returns later, it must not delete transcript or artifacts, promote assumptions to facts, revive superseded decisions, or substitute an obsolete artifact summary for the selected current revision.

Required deterministic recovery case: more than 24 learner turns, a worker restart, a revised assumption, and multiple artifact revisions, with the correct current state preserved. Also cover exhausted budget and oversized essential context without data loss. Forced and failed compactions are no longer required.

### Feedback and privacy

`Feedback` references the exact transcript boundary, exercise/rubric version, brief revision, and artifact revisions evaluated. Findings cite original messages or artifact excerpts; summaries cannot stand in as learner quotes. Validate structure, IDs, quotations, rubric dimensions, and remediation links deterministically. Long sessions may need bounded evaluation passes plus synthesis; record coverage and do not imply omitted material was assessed.

Distinguish confirmed errors, concerns requiring review, defensible trade-offs, and “not observed.” Accept valid alternatives. Record assistance, allow feedback annotations/disputes, and suggest remediation from accepted gaps without modifying review history. Avoid authoritative ability scores. Milestone 1 must demonstrate a meaningful strength, an evidenced concern when present, and a useful next step.

Two additions, decided October 29: deterministic checks come first, so a JSON or YAML API definition that fails to parse is a confirmed finding; and content schema 2 adds misconception mappings, so a finding the learner accepts can offer its linked questions as an extra, labelled review.

Use reviewed, versioned evaluation fixtures for correct alternatives, clear errors, missing evidence, assisted answers, and adversarial instructions embedded in learner work. Reject fabricated evidence; require no critical technical misgrading in the reviewed release set. The original pilot targets are conversational p95 completion under 15 seconds and final-feedback p95 under 45 seconds. Measure these with the chosen configuration; they are acceptance targets, not achieved performance.

Retain work until the owner deletes it. Export portable JSON and readable Markdown using learner-safe fields. Delete session content and derived feedback together while retaining only content-free billing metadata required for accounting. Backup expiry/provider retention are separate from app deletion. Keep transcripts, code, and feedback out of logs and analytics; `store: false` alone is not a zero-retention guarantee.

## Where to work

| File or directory | Responsibility |
| --- | --- |
| [Content schema](../project/learning/content_schema.py) | Strict validation, Markdown resolution, audience projections. |
| [Curriculum service](../project/services/curriculum_service.py) | Checksums, atomic PostgreSQL import/publication, published reads, review adapter. |
| [Learning service](../project/services/learning_service.py) | Existing queues, scheduler integration, revision checks, user lock, rating/receipt transaction. Preserve these guarantees. |
| [Models](../project/models.py) and [migrations](../migrations/versions/) | Catalog, review, and practice persistence. |
| [Practice service](../project/services/practice_service.py) | The only practice writer: sessions, artifact saves and conflicts, receipts, owner-scoped reads, log-safe failure summaries. |
| [Learning views](../project/learning/views.py), [practice routes](../project/learning/practice_views.py), [forms](../project/learning/forms.py), [templates](../project/learning/templates/learning/) | Website authentication, CSRF, lesson/review flow, practice workspace, re-render and rescue paths. |
| [Practice API](../project/api/learning_practice.py) | JWT endpoints over the practice service. |
| [Legacy JSON API](../project/api/learning.py) | Compatibility surface; no concept API. |
| [Shared terms](../project/curriculum_terms.py), [learning errors](../project/services/learning_errors.py) | Constants and exceptions kept free of imports, to avoid the cycle described under gotchas. |
| [Lesson JavaScript](../project/static/js/learning-concept.js) and [SCSS](../project/static/scss/learning-concept.scss); [practice script](../project/static/js/learning-practice.js) and [SCSS](../project/static/scss/learning-practice.scss) | Rendering and retry simulation; unsaved-change prompt and byte counter. Rebuild generated `main.css` after style changes. |
| [Base template](../project/templates/base.html) | Private Learning analytics exclusion. |
| [JobWizard provider integration](../project/services/jobwizard_extraction.py) | Existing bounded-call/validation patterns to study, not the Learning worker. |
| [Content tests](../tests/test_curriculum.py), [PostgreSQL import tests](../tests/test_curriculum_postgres.py) | Schemas, leakage, imports, process death, migrations. |
| [Web concept tests](../tests/test_concept_web.py), [PostgreSQL review tests](../tests/test_learning_postgres.py) | Auth/CSRF, reveal/version pinning, rollback/replay, scheduling and concurrency. |
| Practice tests: service ([3a](../tests/test_practice_service.py), [3b](../tests/test_practice_discussion.py)), web ([3a](../tests/test_practice_web.py), [3b](../tests/test_practice_web_discussion.py)), API ([3a](../tests/test_practice_api.py), [3b](../tests/test_practice_api_discussion.py)), [PostgreSQL](../tests/test_practice_postgres.py) | Saves, sends, citations, brief snapshots, replays, conflicts, normalization, limits, leakage, ownership, pause/resume, delete, rescue page, two-device behaviour, races, process death, cross-session citations, log safety. |
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

Use the [REPL guide](learning-checkpoint-1-test-guide.md) to inspect projections, provoke validation failures, and step through functions. Use the [running-system guide](learning-checkpoint-2-test-guide.md) for Network request replay, Console/Sources inspection, HTTPie/Postman, and profiling. Use the [practice guide](learning-checkpoint-3-test-guide.md) for saves, sends, the brief, conflicts, recovery pages, pause/resume, delete, and the practice API (parts A and B). Form navigations appear under Network All/Doc, not a Fetch/XHR-only filter. The simulation performs local DOM work without application requests.

## Verification evidence and commands

Latest full application verification, recorded October 29 after checkpoint 3b:

- **410 backend tests run: 409 passed, one existing Linux-only JobWizard signal test skipped on macOS**, with PostgreSQL **18.6** enabled.
  - 3b added 39: 14 service, 13 web, 5 API, 6 PostgreSQL, and 1 content-schema test.
  - An independent review of the diff found three issues, all fixed with regression tests (see the checkpoint log).
  - Repeated PostgreSQL race runs saw both commit orders for Send against a save and for delete against a save, with no orphan rows.
- **78 browser checks**: 23 legacy flashcard, nine extraction, 27 concept, and 19 practice checks.
- **13 root Node tests**, dependency integrity checks, Sass build, and `git diff --check` passed.
- A live walkthrough in the disposable fixture covered:
  - sending with an artifact edit, then following the turn's revision link;
  - a send from a stale tab (focused alert, the new turn marked, draft kept);
  - Save and pause, signing out, the API reading and resuming the paused session, then signing back in to find everything intact;
  - a send whose result was lost after commit (rescue page, one turn after the retry, a log line without learner text);
  - the 390-pixel layout, and delete (zero rows left, receipts included).

  This is not a screen-reader audit.

Checkpoint 3a's results (371 tests, 70 browser checks), checkpoint 2's (326 tests, 59 browser checks), and the checkpoint-by-checkpoint coverage are in the checkpoint log.

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

Browser checks need Chrome; use `CHROME_BIN` when its executable is not in the expected location. They test the real JavaScript with local dependencies but are not a complete HTTP application walkthrough. Use `npm run sass` after SCSS changes and commit the generated CSS.

For migrations/concurrency, provision an **isolated PostgreSQL 18 database named `library_sync_test` on localhost**. The previous local cluster used role `library_test` and port `55439`; it is not a service dependency. The [backend CI workflow](../.github/workflows/backend.yml) documents equivalent PostgreSQL provisioning on port 5432. Adjust only the disposable test connection below:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
  LIBRARY_TEST_POSTGRES_URL=postgresql+psycopg://library_test@127.0.0.1:55439/library_sync_test \
  poetry run python -m unittest discover -s tests
```

These fixtures drop tables and reset migration state. Never use a database containing useful data, and do not run independent suites concurrently against the same fixture database. Without `LIBRARY_TEST_POSTGRES_URL`, PostgreSQL tests skip: a green SQLite-only run is not migration/concurrency acceptance. Preserve the environment guards so tests do not load real `.env` credentials or probe cloud metadata. The older general [verification runbook](verification-runbook.md) is useful for app setup, but its historical test counts and SQLite-only description predate this work.

## Gotchas encountered

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

## Open items and decisions to revisit

1. **Human content review and rollout owner:** the exact lesson/questions/exercise/reference packet still need review. Confirm the reviewer and actual review date before publication; schedule the review after exercise version 2 (the start of checkpoint 5), so the reviewer sees the whole exercise once. Migration/deployment and paid-provider activation have not happened.
2. **Enrollment and reading progress:** the original plan includes explicit concept enrollment, reading position, self-assessment, and avoiding automatic due-queue expansion. `UserConceptProgress` does not exist. Currently, visiting a concept's review route offers its four eligible questions, while the legacy API queue is unchanged. Carry this forward as unfinished product work; do not claim enrollment is delivered. Settle its placement before Milestone 1 acceptance, and implement it before content expansion.
3. **Exact session schema and lifecycle:** decided and built through 3b (schema, constraints, payloads, replay, conflicts, limits, brief snapshots, turn freshness, pause/resume, delete). Choices made while building 3b that Keith may want to revisit: **Save and pause** saves before pausing; brief sources can be added only through the API (the website shows and preserves them); there is no brief history page; delete refuses SQLite without foreign keys. Ask Keith if a substantial departure is necessary.
4. **Provider and worker activation:** decided October 29: a worker thread in the web process, and Learning's own OpenAI project and key. Still to do: Keith creates that project and key and sets its spending limit; the model is chosen, with access and current prices verified, during the live evaluations; output caps, deadlines, reservation reconciliation, and the context allowance get finalized with deterministic tests. The `Procfile` runs only `web`, and `run.py` uses Flask's built-in server, so the worker thread starts there and nowhere else. No Learning provider key, worker, or budget ledger exists yet. The budget ledger must stay content-free and must not cascade from session deletion.
5. **Profile versioning and evaluator contract:** profiles are versioned in code and pinned per session (decided October 29). Structured AI outputs, feedback annotations, and evidence/coverage validation still need implementation and evaluation. Do not invent a hidden solution-disclosure path when adding these.
6. **Content lifecycle and mobile representation:** explicit retirement, richer presentation blocks/visualization metadata, and the full taxonomy manifest remain future work. Today the importer stores resolved Markdown text, not precompiled portable presentation blocks. Agree any necessary schema evolution before Expo; do not silently invalidate version-1 content.
7. **Remaining acceptance:** export, fencing late AI responses after pause or delete, owner-only AI access, telemetry exclusions, worker outage/restart, budget races, oversized essential context, long-session feedback coverage, a full keyboard/screen-reader pass, and the complete end-to-end demonstration are still outstanding. The workspace has labelled controls, a focused error summary, status/alert regions, text labels for new turns and pins, and no colour-only cues, but has had no screen-reader audit. The broader multi-style AI evaluation set belongs to pilot expansion; Milestone 1 still needs reviewed interviewer-specific fixtures including valid alternatives and adversarial learner text.
8. **Content-schema gaps against the approved plan:** decided October 29. The behaviour profile/version lives in code (item 5), so the facilitator schema stays as it is. Misconception mappings arrive with content schema 2 and exercise version 2 at the start of checkpoint 5.
9. **Third-party scripts on private pages:** Marked (no SRI) and Alpine (no SRI, in the base template) load from jsDelivr, and the CSP allows `ws:`/`wss:` to any host. The practice workspace loads no Markdown library. Site-wide SRI and a narrower CSP are follow-ups.
10. **Proposals from the October 28 vision review.** Keith accepted three on October 29 (see Decisions): defer compaction out of Milestone 1, close the misconception loop, and report deterministic JSON/YAML checks first. Three wait for Milestone 1's completion:
    - After Milestone 1, expand content on web and give Expo concept Learn/Review before porting Discuss/Build.
    - Shape the progress model (item 2) around the vision's four levels, keeping retention and applied evidence separate.
    - Agree a richer lesson schema before writing more concepts.

## Recommended next checkpoint

Checkpoint 4, the interviewer and continuity, with Keith's October 29 decisions: a worker thread in the web process, Learning's own OpenAI project and key, profiles versioned in code, and no compaction. Plan it in detail and get approval before building. The plan covers the `AIRequest` table and lease loop, the provider adapter, owner-only access, the disclosure selector, budgets and reservations, the context allowance and its stop, pause and delete fencing, and recovery. Build it with mocked provider responses and deterministic accounting and recovery fixtures, then run reviewed live AI evaluations, which is where the model gets chosen. Keith creates the Learning OpenAI project and key before the live evaluations.

Then checkpoint 5: content schema 2 with misconception mappings, feedback with deterministic checks first, the follow-up review, export, and the full demonstration. At Milestone 1 completion, decide the remaining vision-review proposals (open item 10), demonstrate all six steps under Goal and scope, present test evidence, limitations, and incurred costs, and stop for Keith's approval before Milestone 2.
