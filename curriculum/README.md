# Versioned curriculum source

The first catalog is `idempotency/catalog.json`: one concept, four review questions, and one interview exercise. Its Markdown files are part of the content snapshot. This is an **AI-assisted draft awaiting human technical review**, not published curriculum. No reviewer approval is implied by approval of the application architecture.

The canonical source is Git. PostgreSQL stores resolved, immutable revisions and separate publication attestations. These files deliberately live outside Flask static/templates and the Expo project. The repository remains public: the exercise's facilitator and evaluator material is private **inside the application**, not secret from someone reading GitHub.

## Contract

`schema_version: 1` versions the catalog format. Each item has `id`, positive integer `version`, `kind`, `title`, and `content`. Exercise `spec_version: 1` versions its simulation contract independently. Stable IDs survive revisions; never reuse an ID for a different learning objective. Review question IDs already fit the existing `note:card` convention and 128-character storage limit; the adapter to the legacy review service belongs to checkpoint 2.

| Kind | Content |
| --- | --- |
| `concept` | Domain/topic identifiers, objectives, prerequisite concept IDs and prior knowledge, Markdown sections, linked questions/exercises, primary references. |
| `question` | Parent concept, question type, prompt, self-review answer/explanation, remediation section. Answers require an explicit reveal in the learner projection. |
| `exercise` | A learner `brief`, server-only `facilitator`, and evaluator-only `assessment`. The public brief includes assessment dimensions, not rubric anchors or reference reasoning. |

The exercise brief describes scenario, objectives, initial functional/nonfunctional requirements, prerequisites, and expected artifacts. Facilitator content contains an interaction style, instructions, hidden facts with clarification cues, and permitted hints. Assessment content contains reference reasoning, defensible alternatives/trade-offs, anchored rubrics, and remediation links. The single authored profile is an interviewer. Actual AI behavior and disclosure classification are checkpoint 4 work.

Schemas reject unknown fields recursively, unsupported versions, duplicate IDs/JSON keys, missing or mismatched references, missing rubric dimensions, and prerequisite cycles. A manifest must include the full reference closure of its items; it need not include unrelated catalog items. Markdown paths must resolve inside the manifest directory, including through symlinks. Only Markdown text is snapshotted; path names are not part of runtime content. HTML safety is a rendering responsibility for checkpoint 2: do not render this raw text as trusted HTML.

`learner_view` is the only learner DTO. `facilitator_view` includes only server-approved disclosed facts and excludes evaluation material. `evaluator_view` is server-only. Future route handlers must use these projections, never serialize `ContentRevision.payload` directly. Session and feedback records will pin `(item_id, version)` and artifact revisions in later checkpoints.

## Validation and import

Use the existing Flask application environment. Validation does not access database tables:

```sh
poetry run flask --app project:create_app validate-curriculum curriculum/idempotency/catalog.json
```

On an explicitly selected, migrated PostgreSQL database, the default import is a dry run. It exercises the same transaction and constraints, then rolls back:

```sh
poetry run flask --app project:create_app import-curriculum curriculum/idempotency/catalog.json
poetry run flask --app project:create_app import-curriculum curriculum/idempotency/catalog.json --apply
```

The second command saves drafts. They remain absent from `published_learner_item`. Publication additionally requires `--publish --reviewed-by 'Human reviewer name' --reviewed-on YYYY-MM-DD`. Supply the real reviewer and actual review date only after that person reviews the exact lesson, questions, hidden constraints, alternatives, and rubric. The CLI is an operator attestation, not an identity verification or editorial approval service. No content is imported automatically on application startup or migration.

Imports own a transaction separate from the caller's ORM session. A PostgreSQL advisory transaction lock serializes catalog writers, including the first insert; review and ordinary catalog reads do not take that lock. Each identity/version can have only one SHA-256 checksum over canonical, fully resolved JSON. A changed snapshot requires a new version. Application import paths never update or delete snapshot bodies; database administrators retain normal database privileges.

Publication is atomic across the batch. Repeating an identical import/publication is a no-op. The first publication records the reviewer/date and publication time. New drafts do not hide the latest published version; old published versions remain readable by explicit version for history. Publishing behind a newer published version is rejected. Missing source items are retained, not implicitly retired or deleted. Explicit retirement and content administration are later work; do not manually remove rows to simulate retirement.

## Technical review before publication

Check the primary references in the concept, particularly HTTP intended-effect semantics, PostgreSQL uniqueness and statement visibility, and the distinction between durable delivery intent and idempotent external processing. The warehouse requirement is a fictional scenario assumption, not a claim about an existing service. The numeric load and retention constraints are also exercise inputs.

Review whether the questions require explanation instead of terminology alone; whether clarification cues admit equivalent natural-language questions; and whether the rubric gives credit to defensible alternatives. Automated schema and projection tests cannot establish educational accuracy or the quality of an AI interview.
