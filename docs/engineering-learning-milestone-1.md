# Engineering Learning: Milestone 1 implementation checkpoints

Scope approved October 28, 2026: one complete **idempotency** concept on the existing Flask website. Preserve the Learning APIs, scheduler, progress, and legacy notes. The existing Flask/PostgreSQL architecture remains; Expo is Milestone 2 and needs separate approval. This log records implementation sequencing without replacing the approved architecture or the earlier Learning mobile modernization record.

| Checkpoint | Deliverable and acceptance gate | Status |
| --- | --- | --- |
| 1. Content foundation | Versioned catalog, draft lesson/four questions/one structured interview; audience projections; atomic import; additive migration verified on PostgreSQL; legacy Learning regression checks. | Implemented locally; validation evidence below. |
| 2. Learn and Review on web | Published lesson, retry visualization, safe Markdown, explicit answer reveal, four questions through the existing scheduler; unchanged old API behavior and progress. Human content review precedes publication. | Not started. |
| 3. Unified practice workspace | One session spanning Discuss/Build, API/SQL/pseudocode artifacts, immutable revisions, authorization, concurrent-edit conflict handling, save/resume. No IDE or execution sandbox. | Not started. |
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
