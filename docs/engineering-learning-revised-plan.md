# Engineering Learning & Mastery Platform — refined implementation plan

> Approved planning snapshot, preserved from the revision discussion before implementation began. Statements about implementation being unstarted describe that point in time. For current progress, see the [engineering handoff](engineering-learning-handoff.md) and [Milestone 1 checkpoint log](engineering-learning-milestone-1.md). Only Milestone 1 is currently authorized.

The accepted architecture remains: Flask, PostgreSQL, Expo, versioned curriculum content, the existing review engine, one AI worker, owner-only paid AI access, a $50 monthly AI cap, and saved work retained until deletion. The curriculum, content-quality requirements, later roadmap, and Codex/ChatGPT Work division remain unchanged.

The substantive updates concern these four areas:

| Refinement | Already supported by the original proposal | Change needed |
|---|---|---|
| Unified discussion and artifacts | Saved conversations, submission revisions, evidence-linked feedback | Remove the mutually exclusive Discuss/Build session type; make multiple evolving artifacts part of one exercise. |
| Structured simulations | Versioned exercises, behavior profiles, rubrics, pinned content | Define the exercise specification and enforce separate learner, facilitator, and evaluator access. |
| Session continuity | Persistence, pause/resume, recoverable AI requests | Replace the 24-turn cutoff with a soft checkpoint and explicit context management. |
| First complete checkpoint | A one-concept vertical slice preceded content expansion | Make this the first acceptance milestone, sequence web then Expo, and gate expansion on both. |

## 1. One exercise session with conversation and artifacts

**Discuss and Build become two views of the same exercise session.** You can discuss requirements, draft an API, write pseudocode, revise a schema, and defend decisions without creating separate sessions.

On web, conversation and artifacts can appear alongside each other. Expo uses separate views within the same session. Switching views preserves the exercise, counterpart, conversation, and work.

### Minimal model changes

- **PracticeSession:** replace its exclusive Discuss/Build mode with an `interaction_style`: coaching, interviewing, collaborative scoping, or design review. Keep its owner, pinned exercise revision, lifecycle, and assistance history.
- **ArtifactRevision:** replace the proposed `Submission` table. Each immutable row contains a session ID, stable artifact ID, revision number, title, format/language, text, and timestamp. Grouping revisions by artifact ID supplies artifact identity without another table.
- **SessionMessage:** retain ordered conversation turns and record the artifact revisions associated with a turn.
- **AIRequest and Feedback:** reference the exact transcript boundary, exercise revision, context checkpoint, and artifact revisions used.

Supported artifact formats are plain text, Markdown, pseudocode, SQL, Python, TypeScript, and API definitions represented as text or JSON/YAML. The pilot uses simple text editors.

An explicit submission or feedback checkpoint captures a set of artifact revision IDs. It does not duplicate the artifact bodies or require another submission entity.

### Editing and AI behavior

Artifact saves use optimistic revision checks. Conflicting edits from two devices are surfaced rather than silently merged. Save operations are idempotent, and unchanged content does not create another revision.

Before sending a discussion turn, the client confirms that its relevant artifact edits have saved. The AI request then captures those revisions. Editing can continue while a response is generated, but the resulting response identifies the revision it reviewed.

The AI may suggest changes in conversation; it does not overwrite your artifacts. Feedback can cite both a transcript turn and an artifact revision, including a verifiable excerpt. Feedback on an older revision remains available and is visibly identified as such.

Add artifact save/list/history operations beneath the session API. The planned submission operation becomes a checkpoint over saved revisions. Existing review endpoints remain unchanged.

**Acceptance additions:** multiple artifact types in one session; concurrent editing conflicts; edits during generation; feedback tied to the correct revision; and cross-device resumption of both conversation and artifacts.

## 2. A minimal, versioned simulation specification

An exercise remains a versioned curriculum item. Its specification has three explicit sections:

| Section | Contents | Access |
|---|---|---|
| **Learner brief** | Scenario, objectives, initial functional/nonfunctional requirements, expected work artifacts, prerequisite concepts, and understandable assessment dimensions | Learner UI and conversational counterpart |
| **Facilitator configuration** | Hidden scenario facts, disclosure cues, permitted hints, behavior profile/version, and clarification guidance | Server-controlled facilitation |
| **Assessment reference** | Reference reasoning, defensible alternatives, trade-offs, detailed rubric anchors, misconception mappings, and remediation concept IDs | Evaluator only |

The entire exercise revision is pinned when the session starts. Reference reasoning describes acceptable approaches and their conditions; it must not treat one architecture as the only correct answer.

Learner-facing APIs use explicit allowlisted response models. They never serialize the complete exercise specification. Private fields are excluded from HTML, client bundles, session exports, and conversational prompts that do not need them.

As selected, “private” means private within the learning experience. Reference source can remain versioned in the public repository and is therefore inspectable by someone reading that source. [Repository visibility](https://github.com/Kriordan/personal_portfolio)

### Hidden constraints and clarification

Each hidden constraint has a stable ID, an authored fact, and disclosure cues—for example, “reveal when the learner asks about traffic volume.”

For exercises using hidden constraints:

1. A bounded selection step examines the learner’s turn and disclosure cues, returning eligible constraint IDs.
2. The server validates those IDs and supplies the corresponding facts to response generation.
3. Successfully disclosed facts are committed with the response and added to the session’s visible requirements record.

This uses the existing provider adapter and worker, not another agent framework. The selection step does not receive reference solutions. The conversational generation step receives approved facts, not the entire unrevealed fact set.

Facts absent from the specification remain unspecified. A learner’s proposed assumption is recorded as an assumption; the counterpart must not silently turn it into an authoritative scenario requirement.

### Distinct interaction styles

- **Interviewer:** asks clarifying or challenging follow-ups and withholds teaching and solutions during the attempt.
- **Coach:** uses questions, counterexamples, and graduated hints; assistance is recorded.
- **Collaborative facilitator:** helps negotiate requirements, dependencies, scope, and milestones.
- **Design reviewer:** challenges a proposal while acknowledging defensible alternatives.

Changing from interviewing to coaching is explicit and recorded. It does not reset the session or erase the distinction between assisted and unaided work.

Public assessment dimensions remain transparent. Detailed answer keys and evaluation anchors stay evaluator-only. Returned feedback explains relevant findings without returning the private reference packet.

**Acceptance additions:** paraphrased clarification questions reveal appropriate constraints; unrelated questions do not; private reference material never enters learner responses or inappropriate prompts; alternative valid solutions are accepted; and an interviewer does not prematurely teach.

## 3. Long conversations with preserved context

**Remove the hard 24-turn limit.** Keep 24 learner turns as a configurable default check-in point where the application offers a progress checkpoint, continuation, or feedback. Continuing keeps the same session and artifacts.

Turn count, suggested duration, context allowance, and output limits become server-configured policy. The existing monthly budget, generation deadlines, and output bounds remain enforced.

### Durable session brief

Maintain a visible, editable brief containing:

- Established requirements and disclosed constraints.
- Working assumptions and unresolved questions.
- Decisions, rationale, and alternatives considered.
- Current artifact references.
- Assistance received and the next intended step.

Entries distinguish scenario facts, learner decisions, and unconfirmed model interpretations. Important entries link to their originating messages or artifact revisions. You can pin or correct entries.

Store versioned context checkpoints as structured system records in `SessionMessage`; no separate memory service or vector database is required. Original transcript turns and artifact revisions remain intact.

### Context construction

Each conversational request includes:

1. Pinned exercise instructions and approved scenario facts.
2. The current session brief, including pinned requirements and decisions.
3. Current relevant artifact revisions.
4. Recent turns.
5. A bounded summary of earlier conversation, with source references.

Start with a configurable **32,000-token input allowance**, initiating compaction around 75% utilization. Compaction uses the same worker and budget accounting as other AI requests.

Summaries are working context, not replacements for the transcript. They must not silently promote assumptions to requirements, retain superseded decisions as current, or substitute an old artifact summary for the latest selected revision.

If essential context cannot fit, pause generation and explain the specific constraint. Offer a focused artifact selection or a permitted context adjustment; preserve the session. Do not silently truncate artifacts or unexpectedly finish the exercise.

If compaction fails, retain the last valid checkpoint and all original work. The user can retry without reconstructing the session.

### Feedback on substantial sessions

Feedback must cite original transcript or artifact evidence, not a summary as though it were the learner’s words. For sessions exceeding a single evaluation context, use bounded evaluation passes followed by synthesis through the same worker. Record coverage and avoid claiming evaluation of omitted material.

Disclosure, compaction, and evaluation passes all count toward cost reservations. Reaching the budget limit stops further paid generation while keeping reading, editing, saving, export, and later resumption available.

**Acceptance additions:** a scripted conversation exceeding 24 learner turns, at least two forced compactions, a restart, a revised assumption, and multiple artifact revisions must preserve the correct current state. Also test failed compaction, insufficient budget, and oversized essential context without data loss or automatic session completion.

## 4. Revised milestones and the first end-to-end checkpoint

Replace the original early infrastructure-first milestones with the following acceptance sequence. Foundation work still happens, but it is contained within the first usable experience.

| Milestone | Scope | Acceptance gate |
|---|---|---|
| **1. One complete concept on web** | Idempotency lesson, one purposeful visualization, four review questions, one interviewer-style exercise, simple artifacts, saved conversation, context continuity, feedback, and resumption | Demonstrate the complete learning cycle described below. Stop for your approval. |
| **2. The same experience in Expo** | Reuse the backend and content; add native lesson, review, conversation, artifact, feedback, and recovery views | Complete the cycle on Expo and resume a session across web and mobile without losing or overwriting confirmed work. Stop for approval. |
| **3. Expand to the full pilot** | Fourteen concepts, approximately 42 questions, representative Build work, the remaining interaction styles, and the short diagnostic | Existing quality gates pass; distinct discussion behaviors and new content are reviewed. Stop for approval. |
| **4. Evaluate educational value** | The previously proposed four-week trial with delayed, unaided explanations and transfer exercises | Review learning evidence, usability, feedback quality, and measured cost before choosing the next expansion. |

The later curriculum, assessment, isolated execution, voice, personalization, and maintenance roadmap remains unchanged and separately approved.

### Milestone 1 demonstration

Using the idempotency concept:

1. Read the lesson and inspect the retry visualization.
2. Complete retrieval practice using the existing scheduler.
3. Start a technical exercise and discover a hidden requirement through clarification.
4. Create an API outline, SQL schema, and pseudocode as small text artifacts within that session.
5. Discuss the proposal, receive a challenge, and revise an artifact.
6. Pause, close the application, and resume with requirements, decisions, transcript, and saved revisions intact.
7. Finish the exercise and receive feedback citing both conversational evidence and specific artifact revisions.
8. Follow a suggested remediation link and inspect the saved session.

The feedback must identify a meaningful strength, an evidenced concern where present, and a useful next step. It must accept a defensible alternative and report insufficient evidence where appropriate.

Only one interaction style and one exercise are required at this checkpoint. Additional content, personalities, voice, syntax-rich editors, and code execution cannot become prerequisites for accepting it.

### Verification and approval boundaries

Retain the original regression, security, content, provider-evaluation, accessibility, and migration requirements, scoped to each delivered milestone. Add the artifact, private-reference, and long-session tests above. The first checkpoint includes owner isolation, budget enforcement, interruption recovery, private-page analytics exclusion, and export/delete behavior.

Each milestone ends with a runnable demonstration, test evidence, known limitations, and any incurred AI/hosting cost. **Your approval is required before starting the next milestone.** Approval of the revised architecture does not authorize completing the entire roadmap.

Implementation remains unstarted. The first implementation scope is Milestone 1 only.
