# Versioned curriculum source

The original catalog is `idempotency/catalog.json`: one concept, four review questions, and one interview exercise. `idempotency/catalog-v2.json` adds four evaluator-only misconception mappings. The current draft is `idempotency/catalog-v3.json`, which qualifies one private concurrency reference. It uses catalog/spec format 2, exercise revision 3, and the existing concept/question revisions 2. Their Markdown files are part of the content snapshots.

Codex completed a delegated technical review on November 6, recorded in the [Milestone 1 acceptance report](../docs/learning-milestone-1-acceptance.md#november-6-delegated-content-and-feedback-review). These remain AI-assisted drafts. Production publication requires an actual human review and its reviewer/date attestation.

The canonical source is Git. PostgreSQL stores resolved, immutable revisions and separate publication attestations. These files deliberately live outside Flask static/templates and the Expo project. The repository remains public: the exercise's facilitator and evaluator material is private **inside the application**, not secret from someone reading GitHub.

## Contract

`schema_version` versions the catalog format. Each item has `id`, positive integer `version`, `kind`, `title`, and `content`. Exercise `spec_version` identifies its simulation contract independently of the item's content revision. The supported catalog/spec pairs are **1/1** and **2/2**; unsupported or mismatched versions fail validation. Concepts and questions have the same field contracts in both catalog versions. Stable IDs survive revisions; never reuse an ID for a different learning objective. Question IDs retain the existing `note:card` convention and 128-character limit; the web adapter uses the shared scheduler.

| Kind | Content |
| --- | --- |
| `concept` | Domain/topic identifiers, objectives, prerequisite concept IDs and prior knowledge, Markdown sections, linked questions/exercises, primary references. |
| `question` | Parent concept, question type, prompt, self-review answer/explanation, remediation section. Answers require an explicit reveal in the learner projection. |
| `exercise` | A learner `brief`, server-only `facilitator`, and evaluator-only `assessment`. The public brief includes assessment dimensions, not rubric anchors or reference reasoning. |

The exercise brief describes scenario, objectives, initial functional/nonfunctional requirements, prerequisites, and expected artifacts (at most 20, so they fit one practice workspace). Facilitator content contains an interaction style, instructions, hidden facts with clarification cues, and permitted hints. Assessment content contains reference reasoning, defensible alternatives/trade-offs, anchored rubrics, and remediation links. Version 2 also requires `assessment.misconceptions`. The single authored profile remains an interviewer; adding evaluator content does not change its behavior.

Schemas reject unknown fields recursively, unsupported versions, duplicate IDs/JSON keys, missing or mismatched references, missing rubric dimensions, and prerequisite cycles. A manifest must include the full reference closure of its items; it need not include unrelated catalog items. Markdown paths must resolve inside the manifest directory, including through symlinks. Only Markdown text is snapshotted; path names are not part of runtime content. HTML safety is a rendering responsibility for checkpoint 2: do not render this raw text as trusted HTML.

`learner_view` is the learner DTO for catalog items. `opening_view` is the one deliberate exception: it gives the learner exactly one facilitator field, the exercise's authored `opening_prompt` (with its `interaction_style`), which a practice session shows as the interviewer's first turn. **Review the opening prompt as learner-facing text.** `facilitator_view` includes only server-approved disclosed facts and excludes evaluation material. `selector_view` and `interviewer_view` also exclude the assessment. `evaluator_view` is server-only and selects the assessment contract from the pinned exercise's `spec_version`; v1 does not acquire v2 mappings implicitly. Route handlers must use these projections, never serialize `ContentRevision.payload` directly. Practice sessions pin the exercise's `(item_id, version)`; feedback records will also pin the artifact revisions they evaluate.

### Version 2 misconception mappings

Each of the 1–100 mappings contains:

| Field | Meaning |
| --- | --- |
| `id` | Stable identifier within this exercise; unique within the revision. |
| `dimension_id` | One of the exercise's public assessment dimensions, already covered by its rubric. |
| `description` | The mistaken belief or reasoning pattern to investigate. |
| `evidence_guidance` | What original evidence would support a finding, and how to avoid confusing missing evidence or valid alternatives with an error. |
| `concept_id`, `section_id` | An existing concept and explanation section to revisit. |
| `review_question_ids` | 1–100 distinct existing questions belonging to the remediation concept. |
| `suggestion` | An authored next step for a later accepted finding. |

The full reference closure is validated from the manifest: dimensions, concept,
section, question kind, and question parent must match. Remediation may target a
prerequisite concept. These mappings are evaluator-only; none of their text or
IDs is added to learner responses or interviewer prompts. A mapping is not a
diagnosis, an executable detector, or permission to alter progress. Feedback
generation, evidence validation, learner acceptance, and extra review are later
checkpoints. Targets use stable content IDs; ordinary reviews still pin the
question revision when offered.

### Keeping version 1 intact

Keep `catalog.json` and its Markdown sources unchanged. The new catalog uses the
same stable IDs and advances **all six item revisions to 2** because the existing
checksum includes the catalog schema version, even for otherwise unchanged
lesson/question content. This preserves the immutable-import contract without
rewriting checksums or adding per-item schema overrides. The lesson, questions,
learner brief, facilitator configuration, and existing assessment text are
unchanged; only the v2 exercise adds mappings.

Importing v2 as a draft does not hide v1. Once explicitly published after human
review, new sessions pin exercise revision 2; old sessions and open review
attempts keep their original revisions. Stable question IDs preserve review
history and scheduling. Nothing is automatically published, migrated, or
backfilled, and no database migration is needed for this format change.

### Exercise reference correction in revision 3

The new manifest includes the complete reference closure and changes one
`assessment.reference_reasoning` entry. It distinguishes an uncoordinated
READ COMMITTED lookup/insert from valid coordination through uniqueness, an
appropriately scoped lock, or SERIALIZABLE with whole-transaction retry. The
reference also asks how competing callers recover after commit or rollback.

Only exercise `idempotent-order-api` advances to revision 3. The concept and four
questions replay their existing revision-2 checksums. Existing sessions retain
their pinned reference, saved work, feedback, and review history. The preview's
`--feedback-example` option uses this current manifest. The saved live evaluation
files remain evidence for revisions 1 and 2; revision 3 has deterministic
projection/import/feedback tests and a technical source review.

## Validation and import

Use the existing Flask application environment. Validation does not access database tables:

```sh
poetry run flask --app project:create_app validate-curriculum curriculum/idempotency/catalog-v3.json
```

On an explicitly selected, migrated PostgreSQL database, the default import is a dry run. It exercises the same transaction and constraints, then rolls back:

```sh
poetry run flask --app project:create_app import-curriculum curriculum/idempotency/catalog-v3.json
poetry run flask --app project:create_app import-curriculum curriculum/idempotency/catalog-v3.json --apply
```

The second command saves drafts. They remain absent from `published_learner_item`. Publication additionally requires `--publish --reviewed-by 'Human reviewer name' --reviewed-on YYYY-MM-DD`. Supply the real reviewer and actual review date only after that person reviews the exact lesson, questions, hidden constraints, alternatives, and rubric. The CLI is an operator attestation, not an identity verification or editorial approval service. No content is imported automatically on application startup or migration.

Imports own a transaction separate from the caller's ORM session. A PostgreSQL advisory transaction lock serializes catalog writers, including the first insert; review and ordinary catalog reads do not take that lock. Each identity/version can have only one SHA-256 checksum over canonical, fully resolved JSON. A changed snapshot requires a new version. Application import paths never update or delete snapshot bodies; database administrators retain normal database privileges.

Publication is atomic across the batch. Repeating an identical import/publication is a no-op. The first publication records the reviewer/date and publication time. New drafts do not hide the latest published version; old published versions remain readable by explicit version for history. Publishing behind a newer published version is rejected. Missing source items are retained, not implicitly retired or deleted. Explicit retirement and content administration are later work; do not manually remove rows to simulate retirement.

## Technical review before publication

Check the primary references in the concept, particularly HTTP intended-effect semantics, PostgreSQL uniqueness and statement visibility, and the distinction between durable delivery intent and idempotent external processing. The warehouse requirement is a fictional scenario assumption, not a claim about an existing service. The numeric load and retention constraints are also exercise inputs.

Review whether the questions require explanation instead of terminology alone; whether clarification cues admit equivalent natural-language questions; and whether the rubric gives credit to defensible alternatives. Automated schema and projection tests cannot establish educational accuracy or the quality of an AI interview.

For v2, review all four misconception mappings against the existing
[HTTP semantics](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2),
[PostgreSQL constraints](https://www.postgresql.org/docs/18/ddl-constraints.html#DDL-CONSTRAINTS-UNIQUE-CONSTRAINTS),
and [delivery-intent reference](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html).
Check that each evidence rule distinguishes an actual contradiction from an
unfinished explanation, credits valid coordination/delivery designs, and points
to a useful existing question. The [checkpoint 5a REPL guide](../docs/learning-checkpoint-5a-test-guide.md)
shows how to inspect mappings and provoke validation errors without a database.
