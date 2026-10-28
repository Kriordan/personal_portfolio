# Engineering Learning Platform Handoff

As of October 28, 2026, **Milestone 1 is partially implemented: Learn and Review work on web; Discuss, Build, saved practice sessions, and AI feedback do not exist yet.** Continue on `feature/learning-content-foundation`. The next implementation checkpoint is the unified practice workspace.

This handoff records the approved architecture and refinements, the implementation at `0c2848a`, and the remaining acceptance work. It complements the [checkpoint log](engineering-learning-milestone-1.md) and [curriculum contract](../curriculum/README.md). The original and refined plans were approved in the Codex chat **Plan engineering learning platform**; their relevant decisions are captured here so implementation does not depend on access to that chat. The refined milestone order and unified session model supersede the original early milestone order and separate Discuss/Build sessions.

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
| 1 | One complete concept on web, including continuity, feedback, privacy, budgets, export/delete, and a runnable demonstration. | Approved; checkpoints 1 and 2 complete locally. |
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
| 3 | Unified session and artifact persistence, simple web editors, ownership, idempotent saves, revision conflicts, save/resume. | Not started. |
| 4 | Interview behavior, PostgreSQL worker, provider adapter, disclosure, durable requests, budgets, context compaction and recovery. | Not started. |
| 5 | Evidence-linked feedback, remediation, export/delete, complete recovery demonstration and milestone acceptance. | Not started. |

No push, PR, deployment, production migration, or production publication was performed for these checkpoints. The working tree was clean at the start of this documentation handoff. Content remains an AI-assisted draft awaiting human technical review; demo publication is not production approval.

## Decisions and reasons

| Decision | Reason and consequence |
| --- | --- |
| Extend Flask/PostgreSQL and existing feature services. | Preserve the working application and minimize operational changes. Website authentication remains Flask-Login plus CSRF; JSON API authentication remains JWT. |
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

## What exists in the repository

### Content and publication

[The idempotency package](../curriculum/idempotency/catalog.json) has six version-1 items: concept `idempotency`; questions `idempotency:timeout`, `idempotency:race`, `idempotency:scope`, and `idempotency:external-effect`; exercise `idempotent-order-api`. The three lesson sections are `overview`, `retries`, and `design`. Its prerequisites include descriptive prior knowledge; it does not fabricate prerequisite concept records for content not yet authored.

The exercise expects `api`, `schema`, and `algorithm` artifacts. Its schema separates `brief`, `facilitator`, and `assessment`. The brief contains scenario, objectives, functional/nonfunctional requirements, prerequisites, artifact expectations, and public assessment dimensions. Server-side content contains disclosure cues/facts, interviewer instructions, allowed hints, alternative approaches, anchored rubrics, and remediation links. Do not copy those private packets into future UI fixtures, HTML, bundles, or session exports.

`schema_version: 1` versions the catalog; exercise `spec_version: 1` versions the simulation contract; each item's integer `version` versions its content. Strict schemas reject unknown fields, invalid or duplicate IDs, duplicate JSON keys, invalid references, prerequisite cycles, and invalid versions, including booleans masquerading as integers. Markdown paths cannot escape the package, including through symlinks. Resolved Markdown text participates in the checksum.

`CurriculumItem` stores stable ID and kind. `ContentRevision` uses `(item_id, version)` as its primary key and stores schema version, checksum, resolved JSON payload, import timestamp, and publication attestation. Content immutability is enforced by application import paths; it is not a database permission boundary against administrators.

`validate-curriculum` validates files without accessing database tables. `import-curriculum` requires PostgreSQL and defaults to rollback. `--apply` saves drafts. Publication additionally requires `--publish`, a real `--reviewed-by`, and actual `--reviewed-on` date. The importer owns a separate transaction, uses a PostgreSQL advisory transaction lock to serialize rare catalog writes, and atomically imports/publishes the batch. Ordinary review operations do not acquire that lock.

Repeating identical content is safe. Changing a payload under the same ID/version fails. Publishing behind a newer published revision fails. Omitting items does not delete or retire them. There is no startup/migration content seed, retirement workflow, or content administration UI.

### Web Learn and Review

Authenticated `/learning/` lists published concepts alongside legacy notes. `/learning/concepts/idempotency` renders expandable lesson sections and the retry simulation. The simulation is reviewed application JavaScript; curriculum files cannot inject executable code. Markdown uses the existing Marked/DOMPurify dependencies with a restrictive allowlist. If they fail to load, escaped source text remains readable.

`GET /learning/concepts/idempotency/review` selects a due question. **Show answer** performs another GET carrying `card_id`, `content_version`, `expected_revision`, and `request_id`. The initial learner response omits the answer and explanation. Ratings are `Again=0`, `Hard=3`, `Good=4`, `Easy=5`.

POSTing the CSRF-protected form calls the existing `rate_card_for_user`. On PostgreSQL, a user-row lock serializes saves; progress, review log, and durable receipt commit together. A replay with the same UUID/payload returns the recorded result; reusing the UUID with a different payload or submitting stale progress produces a conflict. Successful saves return 303 then a fresh queue GET. Save failures preserve the attempt for explicit retry. Version pinning allows an already-open question to finish against its original content revision.

Committed reviews survive navigation and reopening because the queue derives from database progress. This is not yet recovery for a practice conversation or unsaved artifact. There is no new browser-side review queue or client storage.

The JSON API under `/api/v1/learning` remains the legacy notes/review/rating/receipt surface. It does not yet expose concepts, artifacts, or sessions. The concept web adapter feeds the shared scheduler without changing that API's due queue. Curriculum and legacy note namespaces are checked to prevent accidental sharing of progress identities.

Personal Learning responses use `Cache-Control: private, no-store`. The shared base template omits Google Analytics and Hotjar on authenticated Learning pages. Future session routes, logs, provider errors, and telemetry still need their own content-leakage checks.

### Migrations

| Revision | Change | Downgrade consequence |
| --- | --- | --- |
| `a4b5c6d7e8f9` → `b5c6d7e8f9a0` | Adds `curriculum_item` and `content_revision`; no user/progress seed or rewrite. | Removes catalog tables and their content. |
| `b5c6d7e8f9a0` → `c6d7e8f9a0b1` | Adds nullable `review_log.content_version` and composite FK to the exact content revision. Existing logs stay null. | Removes version linkage while retaining rating/scheduling history. |

These migrations were exercised on populated disposable PostgreSQL fixtures, including downgrade and ORM/schema parity. Do not downgrade real content as a routine feature rollback. The planned rollout strategy disables new features while retaining saved data.

## Remaining architecture to implement

Everything in this section is approved direction, not an existing subsystem.

### Unified session and artifacts

Use `PracticeSession` for owner, pinned exercise revision, lifecycle, interaction style, and assistance history. Use the existing schema's style values (`interviewer`, `coach`, `collaborative`, `reviewer`) consistently; only interviewer behavior is required for Milestone 1.

`SessionMessage` retains ordered turns, modality/timestamps, assistance events, and references to the artifact revisions associated with a turn. Versioned context checkpoints are structured system records in this same message model, not a separate memory service.

Each `ArtifactRevision` holds session ID, stable artifact ID, revision number, title, format/language, text, and timestamp. Support text, Markdown, pseudocode, SQL, Python, TypeScript, and API definitions as text/JSON/YAML. Simple textareas are sufficient. A submission/checkpoint captures revision IDs rather than duplicating bodies or creating a separate Submission entity.

Saves need owner checks, optimistic expected revisions, request deduplication, and no new revision for unchanged content. Show conflicts rather than silently merging. Before a discussion turn is sent, confirm relevant edits are saved; capture those exact revisions in the AI request. Later edits may proceed while generation runs. Responses/feedback must identify which revision they reviewed. AI suggestions never overwrite learner artifacts automatically.

Add session create/list/detail/pause/resume, message, artifact save/history, and checkpoint operations through shared services. New API resources belong beneath `/api/v1/learning`; website mutations use CSRF. Persisting foreign IDs, reading another user's history, and replaying another user's request must fail. Session APIs and exact schemas are still to be written.

### Interview behavior and disclosure

The interviewer challenges reasoning and asks focused follow-ups without prematurely teaching a reference solution. Coaching gives graduated help; collaborative scoping negotiates requirements and dependencies; design review critiques alternatives. Changing from interview to coaching must be explicit and recorded. Do not implement the additional profiles merely because their schema values exist.

For hidden constraints, a bounded selector receives the learner turn and authored clarification cues and returns eligible IDs. Validate IDs server-side; provide only approved facts to the conversational call. The selector does not receive reference solutions, and the conversational call does not receive all unrevealed facts. Commit successful disclosure with the response and visible requirements record. Unspecified facts remain unknown; learner assumptions do not become scenario facts.

The existing `facilitator_view` can project approved IDs, but there is no selector, disclosure persistence, provider call, prompt suite, or behavior evaluation yet. Separately version prompts/profiles and pin all inputs used for a result.

### Durable AI requests and spending

Start with one configurable OpenAI adapter using application-owned context, structured outputs, and `store: false`. The original candidate was GPT-6.1 Sol with low reasoning for turns and medium for feedback; it has not passed Learning evaluations. Verify model access and current pricing before activation. Do not silently switch models after failures or couple Learning to JobWizard's extraction workflow.

`AIRequest` owns job identity, status, lease, selected exercise/context/artifact revisions, transcript boundary, provider/model/prompt versions, usage, and cost reservation. Commit user input and its request atomically, then return 202. The worker claims under a short transaction, releases database locks before network calls, enforces a provider deadline, and commits only if its lease/session state still permits completion. Allow one active generation per session. Foreground clients poll and recover results after reconnect.

Expired running jobs become interrupted with explicit retry. Deletion must cancel pending work and fence late responses. Database deduplication cannot guarantee exactly one provider charge after an uncertain network outcome; keep conservative reservations for such calls rather than blindly refunding/retrying.

Only Keith's configured account may initiate paid Learning requests. Enforce **$50/month**, warn at **$40**, and count actual usage plus in-flight/uncertain reservations in PostgreSQL. Track the pricing version and keep Learning accounting separate from JobWizard. Disclosure, compaction, evaluation passes, and synthesis all consume this budget. Hosting is separate. At the cap, block new paid generation while preserving reading, review, editing, saving, export, and later resumption.

### Continuity and context

Keep 24 learner turns as a configurable progress check-in. Continuation stays in the same session. Suggested duration, input allowance, output limits, and deadlines are server policy; no numeric output limit or deadline has been finalized in code.

Start with a configurable **32,000-token input allowance** and compaction around **75%** utilization. Each call includes pinned instructions and disclosed facts, the current session brief, relevant artifact revisions, recent turns, and bounded older-context summary with source references.

The learner-visible, editable brief preserves requirements, disclosed constraints, assumptions, open questions, decisions/rationale/alternatives, current artifact references, assistance, and next step. Distinguish authoritative facts, learner decisions, and unconfirmed model interpretations. Support pinned/corrected entries with links to original evidence.

Compaction does not delete transcript or artifacts. It must not promote assumptions to facts, revive superseded decisions, or substitute an obsolete artifact summary for the selected current revision. Failure retains the last valid checkpoint and original work. If essential context cannot fit, stop generation with a specific explanation and focused-selection/context-adjustment options; do not truncate silently or complete the session automatically.

Required deterministic recovery case: more than 24 learner turns, at least two forced compactions, a worker restart, a revised assumption, and multiple artifact revisions. Also cover failed compaction, exhausted budget, and oversized essential context without data loss.

### Feedback and privacy

`Feedback` references the exact transcript boundary, exercise/rubric version, context checkpoint, and artifact revisions evaluated. Findings cite original messages or artifact excerpts; summaries cannot stand in as learner quotes. Validate structure, IDs, quotations, rubric dimensions, and remediation links deterministically. Long sessions may need bounded evaluation passes plus synthesis; record coverage and do not imply omitted material was assessed.

Distinguish confirmed errors, concerns requiring review, defensible trade-offs, and “not observed.” Accept valid alternatives. Record assistance, allow feedback annotations/disputes, and suggest remediation from accepted gaps without modifying review history. Avoid authoritative ability scores. Milestone 1 must demonstrate a meaningful strength, an evidenced concern when present, and a useful next step.

Use reviewed, versioned evaluation fixtures for correct alternatives, clear errors, missing evidence, assisted answers, and adversarial instructions embedded in learner work. Reject fabricated evidence; require no critical technical misgrading in the reviewed release set. The original pilot targets are conversational p95 completion under 15 seconds and final-feedback p95 under 45 seconds. Measure these with the chosen configuration; they are acceptance targets, not achieved performance.

Retain work until the owner deletes it. Export portable JSON and readable Markdown using learner-safe fields. Delete session content and derived feedback together while retaining only content-free billing metadata required for accounting. Backup expiry/provider retention are separate from app deletion. Keep transcripts, code, and feedback out of logs and analytics; `store: false` alone is not a zero-retention guarantee.

## Where to work

| File or directory | Responsibility |
| --- | --- |
| [Content schema](../project/learning/content_schema.py) | Strict validation, Markdown resolution, audience projections. |
| [Curriculum service](../project/services/curriculum_service.py) | Checksums, atomic PostgreSQL import/publication, published reads, review adapter. |
| [Learning service](../project/services/learning_service.py) | Existing queues, scheduler integration, revision checks, user lock, rating/receipt transaction. Preserve these guarantees. |
| [Models](../project/models.py) and [migrations](../migrations/versions/) | Catalog/review persistence and future additive session models. |
| [Learning views](../project/learning/views.py), [forms](../project/learning/forms.py), [templates](../project/learning/templates/learning/) | Website authentication, CSRF, lesson/review flow. |
| [Legacy JSON API](../project/api/learning.py) | Compatibility surface; no concept/session API yet. |
| [Lesson JavaScript](../project/static/js/learning-concept.js) and [SCSS](../project/static/scss/learning-concept.scss) | Rendering and retry simulation; rebuild generated `main.css` after style changes. |
| [Base template](../project/templates/base.html) | Private Learning analytics exclusion. |
| [JobWizard provider integration](../project/services/jobwizard_extraction.py) | Existing bounded-call/validation patterns to study, not the Learning worker. |
| [Content tests](../tests/test_curriculum.py), [PostgreSQL import tests](../tests/test_curriculum_postgres.py) | Schemas, leakage, imports, process death, migrations. |
| [Web concept tests](../tests/test_concept_web.py), [PostgreSQL review tests](../tests/test_learning_postgres.py) | Auth/CSRF, reveal/version pinning, rollback/replay, scheduling and concurrency. |
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

Use the [REPL guide](learning-checkpoint-1-test-guide.md) to inspect projections, provoke validation failures, and step through functions. Use the [running-system guide](learning-checkpoint-2-test-guide.md) for Network request replay, Console/Sources inspection, HTTPie/Postman, and profiling. Form navigations appear under Network All/Doc, not a Fetch/XHR-only filter. The simulation performs local DOM work without application requests.

## Verification evidence and commands

Latest full application verification recorded October 28, before the documentation follow-up:

- **326 backend tests run: 325 passed, one existing Linux-only JobWizard signal test skipped on macOS**, with PostgreSQL **18.6** enabled.
- **59 browser checks**: 23 legacy flashcard, nine extraction, 27 concept renderer/simulation checks.
- **13 root Node tests**, dependency integrity checks, Sass build, and `git diff --check` passed.
- A disposable live browser walkthrough covered navigation, changing the retry key, answer reveal, saving, and the next question. A 390-pixel layout check found and fixed a header overlap. This is not Expo or full screen-reader acceptance.
- The subsequent guide rewrite verified the Python examples and live HTTPie 200/400/401 cases. It did not require rerunning the application suite.

These are historical local results, not a claim that CI or AI evaluations have passed for unimplemented work. Detailed coverage is in the [checkpoint log](engineering-learning-milestone-1.md).

For targeted file/web checks:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
  poetry run python -m unittest discover -s tests -p 'test_curriculum.py' -v
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
  poetry run python -m unittest discover -s tests -p 'test_concept_web.py' -v
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

## Open items and decisions to revisit

1. **Human content review and rollout owner:** the exact lesson/questions/exercise/reference packet still need review. Confirm the reviewer and actual review date before publication. Migration/deployment and paid-provider activation have not happened.
2. **Enrollment and reading progress:** the original plan includes explicit concept enrollment, reading position, self-assessment, and avoiding automatic due-queue expansion. `UserConceptProgress` does not exist. Currently, visiting a concept's review route offers its four eligible questions, while the legacy API queue is unchanged. Carry this forward as unfinished product work; do not claim enrollment is delivered. Settle its placement before Milestone 1 acceptance, and implement it before content expansion.
3. **Exact session schema and lifecycle:** the entity responsibilities above are approved; table constraints, lifecycle transitions, save payloads, request replay behavior, brief-edit conflicts, and editor byte limits still need concrete implementation. Resolve routine details in checkpoint 3; ask Keith if a substantial departure is necessary.
4. **Provider and worker activation:** identify the authorized account, verify provider/model availability and current price accounting, and confirm worker compatibility with existing hosting. Finalize output caps, deadlines, reservation reconciliation, and configurable context policy with deterministic tests. No Learning provider key, worker process, or budget ledger has been configured by these checkpoints.
5. **Profile versioning and evaluator contract:** catalog item versions pin today's interviewer configuration, but independent prompt/profile versions, structured AI outputs, feedback annotations, and evidence/coverage validation still need implementation and evaluation. Do not invent a hidden solution-disclosure path when adding these.
6. **Content lifecycle and mobile representation:** explicit retirement, richer presentation blocks/visualization metadata, and the full taxonomy manifest remain future work. Today the importer stores resolved Markdown text, not precompiled portable presentation blocks. Agree any necessary schema evolution before Expo; do not silently invalidate version-1 content.
7. **Remaining acceptance:** export/delete with late-response fencing, owner-only AI access, telemetry exclusions, worker outage/restart, budget races, failed/oversized compaction, long-session feedback coverage, keyboard/accessibility checks, and the complete end-to-end demonstration are still outstanding. The broader multi-style AI evaluation set belongs to pilot expansion; Milestone 1 still needs reviewed interviewer-specific fixtures including valid alternatives and adversarial learner text.

## Recommended next checkpoint

Start checkpoint 3 by defining the minimal session/message/artifact schema and state transitions, then implement persistence and a simple web workspace. Make save/resume useful before connecting a paid model. Preserve shared service boundaries so Expo can reuse them later.

Its reviewable acceptance gate should show one owned session with three saved artifacts, immutable history, duplicate-save replay, unchanged-save handling, stale-edit conflict without data loss, cross-account rejection, and resumption after reopening. Exercise migrations and concurrent writes on real PostgreSQL. Add a short REPL/HTTPie/DevTools exploration guide and commit the checkpoint separately.

Then implement the interviewer/continuity and feedback checkpoints with mocked provider responses and deterministic accounting/recovery fixtures, followed by reviewed live AI evaluations. At Milestone 1 completion, demonstrate all six steps under Goal and scope, present test evidence, limitations, and incurred costs, and stop for Keith's approval before Milestone 2.
