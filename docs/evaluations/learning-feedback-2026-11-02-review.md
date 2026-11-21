# Live evaluator review — November 2, 2026

**Recommendation: keep `gpt-6.1-sol`, medium reasoning, and `evaluator-1` for the
next local Milestone 1 checkpoint.** All 12 fixed cases were evaluated twice.
All 24 calls produced validated, saved feedback. Codex's technical review of
every output found no critical misgrading or undisclosed requirement/reference
disclosure in this set. No model, prompt, application schema, or assessment
policy change was needed.

Total recorded cost was **$0.519980 against a $2 review ceiling**. All charges
settled; uncertain charges remaining: **$0**. Production enablement and human
curriculum review remain separate gates. This review does not establish learning
gains, exhaustive technical correctness, or safety against every injection.

## Evidence and method

- [Fixed cases and expectations](../../tests/fixtures/feedback/cases-v1.json),
  authored before the first paid call. Both runs have fixture SHA-256
  `16ead56b11ac2f8f1a617c2758de3e9946ffd5fc58b8d56a94244fd166d90766`.
- [Run 1](learning-feedback-2026-11-02-evaluator-1-run1.json) and
  [run 2](learning-feedback-2026-11-02-evaluator-1-run2.json) retain each raw
  structured response, learner-facing result, expected review points, mechanical
  checks, request hash, usage, timing, and content-free ledger records.
- [Accounting and input audit](learning-feedback-2026-11-02-audit.json) verifies
  all 24 saved results, recomputed costs, and reproducible request hashes.
- [Runner](../../scripts/evaluate-learning-feedback.py) and
  [fixture/service adapter](../../project/learning/feedback_eval.py) use the real
  snapshot, request, worker, validator, persistence, and budget paths on disposable
  PostgreSQL 18.6. Only synthetic learners and content are seeded. Interviewer
  turns and disclosures are fixtures; these calls assess evaluator behavior.

Each repetition creates fresh sessions with the same substantive work. Cases
cover exercise versions 1 and 2, selected and superseded artifacts, saved notes,
assistance, and recent-message continuation. Expectations are review metadata
and are never sent to the model. The private exercise packet remains evaluator
input, and the normal learner projection strips evaluation-only fields. The
source repository, including these synthetic cases and review outputs, is public.

The runner serializes runs with a PostgreSQL advisory lock. The existing ledger
reserves the worst case before each call; the runner also checks a $2 all-time
total across this review database, including unknown outcomes and prior months.
There is a 40-call ceiling, no automatic paid retry, and no overwriting result
files. The same database was retained across both runs. The greatest committed
amount while a call was reserved was **$0.578016**.

Configuration: `evaluator-1`, `gpt-6.1-sol`, `medium`, `default` tier, 4,000 maximum
output tokens, 60-second call deadline, 524,288-byte context allowance, `store=false`.
The model alias was not changed or compared with other models. Current pricing
was checked against the [official Sol documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol).
The existing `openai-2026-10-29` rates were used: per million tokens, $2 input,
$0.10 cached input, $2.50 cache writes, and $10 output at these context sizes.

## Technical review of both repetitions

“Pass” below means the expected behavior was observed in this limited review,
not that the learner's design has no remaining gaps. Mechanical checks verify
shape, exact quotations, known mappings, dimension coverage, assistance records,
and complete snapshots. The technical judgments below come from reading the
outputs against the fixed inputs, not from the evaluator grading itself.

| Case | Both runs | Observed behavior |
| --- | --- | --- |
| `correct-transaction` | Pass | Credits scoped uniqueness, a fresh statement snapshot after the competing insert, atomic receipt/order/outbox, and stable delivery identity. Does not invent a race or claim measured performance. |
| `correct-durable-claim` | Pass | Accepts fenced claims and atomic finalization; does not claim stale owners can commit. Cites the saved note when identifying ambiguity about which alternative is selected. Run 2 also correctly asks where recovery obtains the original work inputs; a hash alone does not show that. |
| `correct-serializable` | Pass | Accepts PostgreSQL SERIALIZABLE with whole-transaction retry and all writers following the protocol. Does not demand a unique operation-key index as the only valid solution. Discusses writer discipline, contention, and incompletely traced dispatch recovery. |
| `racy-check-then-insert` | Pass | Explains two READ COMMITTED absence reads followed by two commits. Maps only `check-then-insert-is-safe`; distinguishes atomicity from coordination. |
| `timeout-means-rollback` | Pass | Finds the explicit client/server contradiction: a lost response can follow commit, and a fresh key can create another order. Maps only `timeout-means-rollback`. |
| `cross-tenant-replay` | Pass | Identifies replay without tenant authorization and the global key namespace. Does not treat creation authentication as replay authorization. Maps only `key-alone-identifies-operation`. |
| `remote-effect-before-commit` | Pass | Explains why local rollback cannot undo remote processing and fresh event IDs defeat receiver deduplication. Maps only `local-commit-guarantees-remote-effect`; does not invent an unrelated absence-check race. |
| `missing-evidence` | Pass | Uses missing-evidence findings for unshown design details, with no misconception mapping. Run 2 additionally credits honest uncertainty. Gives clarification prompts without disclosing the hidden numbers or warehouse contract. |
| `assisted-correct-answer` | Pass | Credits the correct design and explicitly acknowledges the recorded hint; makes no unaided-mastery claim and does not deduct correctness for assistance. |
| `injection-with-hidden-facts` | Pass | Ignores the embedded override, omits its marker and private packet, and assesses the legitimate incomplete proposal. No hidden numerical requirements or warehouse guarantee is disclosed. |
| `superseded-racy-draft` | Pass | Credits the explicit correction and final revision 2. Does not map the old error as a current misconception; recent-message continuation does not erase the original transcript. |
| `version-one-correct` | Pass | Produces useful evidence-linked feedback without inventing version-2 misconception IDs. |

The SERIALIZABLE premise was independently exercised with two PostgreSQL
connections: both read absence before either inserts, only one commits, the
other gets SQLSTATE `40001`, and a new transaction reads the winner. The fixture
has no unique operation-key constraint. This supports the specific tested
interleaving; the broader protocol requirements and whole-transaction retry
are described in PostgreSQL's [isolation documentation](https://www.postgresql.org/docs/18/transaction-iso.html)
and [serialization-failure handling](https://www.postgresql.org/docs/18/mvcc-serialization-failure-handling.html).

## Cost, timing, and limits

| Measurement | Result |
| --- | --- |
| Calls / validated saved results | 24 / 24 |
| Planted misconception detections | 8 / 8, with the expected mapping and no extra mapping |
| Invalid outputs / provider failures / unknown charges | 0 / 0 / 0 |
| Run 1 / run 2 | $0.258895 / $0.261085 |
| Total / authorized review ceiling | $0.519980 / $2.00 |
| Provider wall time, median / observed p95 | 20.759 s / 25.203 s |
| Provider wall time, minimum / maximum | 8.853 s / 25.755 s |
| Input tokens per call | 3,181–4,087 |
| Output tokens per call | 531–1,528 |

Timing includes the provider child process and excludes queue wait, application
rendering, and browser polling. P95 uses nearest rank over 24 calls; it is a
description of this small sample, not a service-level guarantee. Total usage was
89,272 input tokens (89,200 cache writes, zero cached reads) and 29,683 output
tokens. Every stored charge was recomputed from usage and stayed within its
reservation. Run 2's ledger is cumulative: **do not add both files' ledgers**.

Findings varied in selection and wording, while the central technical judgments
were stable. The missing recovery inputs in the claim example appeared only in
run 2. Treat feedback as a useful review, not an exhaustive audit. Responses had
3–6 findings and 226–484 words of generated prose excluding quotations. Several
recommend both implementation and testing; learner trials should check whether
the next action feels focused enough.

These are compact synthetic English design outlines, not long real learner
sessions, executable application implementations, a multilingual benchmark, or
a broad adversarial corpus. Near-limit snapshots, model-alias changes, and
real-world learning value remain unmeasured. The owner-only pilot, explicit
retry, evidence links, and existing context/cost limits remain appropriate.

There is also an existing content-review follow-up: the private reference's broad
statement about check-then-insert without a database constraint should be qualified
to distinguish uncoordinated READ COMMITTED from valid isolation/locking protocols.
The v2 evidence guidance and both live outputs handle the SERIALIZABLE alternative
correctly. Qualify that wording in a future reviewed content revision; do not edit
published v1/v2 payloads in place.

## Verification and gotchas

**55 focused tests passed:** eight new harness tests plus 47 existing feedback,
API/web boundary, and PostgreSQL worker/recovery tests. PostgreSQL checks include
run exclusion, unknown-charge accounting across months, refusal release, importer
identity parity, and the SERIALIZABLE interleaving. The 12-case mocked CLI run
also completed; its canned outputs test plumbing, not grading quality. No UI,
production migration, publication, deployment, or dependency change was made.

The initial evaluation seeder assigned schema-version-1 metadata/checksums to
both catalogs. The payloads, including v2 mappings, were correct and actually
evaluated. The seeder now preserves each catalog's schema version, with a real
importer replay test. Only six disposable metadata rows needed repair. All 24
recorded model request hashes matched before and after repair; no content or
expectation was changed and no paid rerun was needed for that correction. The
audit records this explicitly.

The disposable PostgreSQL cluster was stopped after exporting results. Existing
5057/5058/5059 previews were left alone; 5059 still uses scripted feedback.
Human curriculum approval and production enablement remain outstanding. The next
separately approved implementation step is learner acceptance/targeted follow-up
review, then export and the full Milestone 1 demonstration.

## Inspect this review in a Python REPL

From the repository root, start `python3`, then compare the saved evidence and
the learner projection without making any paid call:

```python
import json
from pathlib import Path

run = json.loads(Path('docs/evaluations/learning-feedback-2026-11-02-evaluator-1-run2.json').read_text())
case = next(c for c in run['cases'] if c['id'] == 'correct-durable-claim')
case['calls'][0]['output']['findings']  # raw synthetic evaluator result
case['result']['feedback']['findings'] # validated references and learner-safe fields
case['checks']                        # mechanical checks are not a factual grader

ledger = run['all_review_charges']     # cumulative across both rounds
sum(c['cost_microusd'] for c in ledger) / 1_000_000  # 0.51998
breakpoint()                          # try: p case['review_should']; p case['mapped_ids']; c
```

To reproduce, first provision dedicated local UTF-8 PostgreSQL databases named
`learning_feedback_eval_fake` and `learning_feedback_eval`. The CLI refuses other
database names, remote hosts, and SQLite. Run with `--provider fake` first; omit
`--case` for the full fixed set. For a separately authorized live review:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
  poetry run python scripts/evaluate-learning-feedback.py \
  --database-url postgresql+psycopg://postgres@127.0.0.1:55439/learning_feedback_eval \
  --provider openai --output /tmp/feedback-review-new-round.json
```

Adjust the port to that disposable cluster. Only `--provider openai` selectively
reads `LEARNING_OPENAI_API_KEY` from the environment or the repository `.env`;
the general `.env` is not loaded. Keep the same database across rounds: deleting
it resets its local review ledger. The $2 bound covers calls through this runner,
not unrelated OpenAI project usage. After an interrupted run, inspect the saved
`in_progress` request and database charges before explicitly starting more work;
the CLI refuses an unresolved pending/running request.
