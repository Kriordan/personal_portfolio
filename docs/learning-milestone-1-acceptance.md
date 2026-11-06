# Milestone 1 walkthrough and accessibility review

November 3 walkthrough, updated November 6, 2026 · checkpoints 5f/5g · idempotency on web only

**Current judgment: Milestone 1 is ready for local pilot use.** Keith reviewed
Learn/Review and Discuss/Build and reported that both looked good. On November 6,
he delegated the remaining content and AI feedback judgment to Codex. The review
and reference correction are recorded in the [November 6 addendum](#november-6-delegated-content-and-feedback-review).

The single-concept flow works locally from Learn through Review, Discuss, Build,
saved feedback, revision, and resumption. This checkpoint fixes keyboard and
accessibility issues found during that walkthrough. It does not sign off the
curriculum, prove learning outcomes, or authorize deployment or Milestone 2.

Keith decided that **enrollment, saved reading position, and self-assessment belong
in a separate checkpoint before content expansion**. They remain unimplemented;
they are not prerequisites for this Milestone 1 review. No new progress model,
infrastructure, migration, provider call, or dependency was introduced here.

## Walkthrough evidence

The native in-app browser used an isolated, scripted preview on port 5064. Chrome
regressions used disposable fixtures; database concurrency and migrations ran
against a separate PostgreSQL 18.6 cluster. Existing previews were preserved.

| Flow | Observed result |
| --- | --- |
| Learn | Opened lesson sections with the keyboard, followed the retry simulation, and returned through the shared concept navigation. The final simulation step now leaves focus on **Start again**. |
| Review | Revealed and explicitly rated a normal question. The due count changed from four to three; navigating or reading did not rate anything. |
| Discuss | Continued the same session and asked **How long do clients retry?** The authored retry/retention requirement appeared in Brief, linked to its reply. Conversation entries retained their original artifact citations. |
| Build | Saved API revision 2, schema revision 1, pseudocode revision 1, and a pinned decision note. Changed tabs using arrow keys without losing drafts. |
| Feedback and revision | Opened the seeded snapshot 2: a strength, a race concern, missing-evidence guidance, and exact old-revision evidence. Opened API revision 1 after revision 2 existed. Saved agreement with the concern and an explanation, then explicitly rated its optional follow-up question. |
| New snapshot | Saved snapshot 9 with the revised artifacts, note, and five conversation turns; generated and reloaded scripted feedback. The old snapshot and response remained available. |
| Continuity | Saved and paused, returned via Learning home, explicitly resumed, then paused again and closed/reopened the browser tab. Saved content, disclosed requirement, feedback, and exact session identity survived. |
| Export and deletion | Downloaded and parsed the recovered session's JSON: three artifacts with revision history, five turns, two brief versions including the empty initial version, two submissions, one disclosure, and one follow-up rating. Inspected deletion counts and used **Keep the session**. Actual deletion, cascades, ownership, and retained recall history are covered by automated route/PostgreSQL tests; the demonstration session was kept. |
| Accessibility and recovery | Checked keyboard navigation, visible focus, 320-pixel reflow, native accessibility-tree names/groups, linked validation/conflict messages, and feedback focus. Automated fixtures also cover save/send/feedback failures, receipt replay, concurrent edits, blocked browser storage, no-JavaScript operation, and budget/restart recovery. |

The fake interviewer matches authored clarification cues; it does not evaluate
free paraphrases. Snapshot 2 is a deliberately authored feedback example. Newly
requested fake feedback may say it cannot judge the design. Use this preview to
assess the interaction and persistence, not evaluator quality. The separate
[bounded live evaluator review](evaluations/learning-feedback-2026-11-02-review.md)
records the technical-quality evidence and its limitations.

## Fixes and regression coverage

| Finding and fix | Where / regression |
| --- | --- |
| The last retry step disabled the focused button and dropped focus onto the document. Move it to **Start again** only when that button was focused. | `project/static/js/learning-concept.js:95`; two renderer checks also prove unrelated focus is left alone. |
| Artifact and Notes fieldsets were given `role="tabpanel"`, overriding native group semantics with a role not permitted on fieldsets. Put tab semantics on a wrapping div; retain fieldset/legend groups. | `_practice_artifacts.html:9`, `_practice_notes.html:1`; integrated browser checks verify all panel/tab relationships and named native groups. |
| Invalid message/artifact/note fields and conflicted artifacts did not describe their inline recovery messages. Associate the existing messages with the controls. Make overflowing saved conflict text keyboard focusable. | `_practice_artifacts.html:7`, `_practice_conversation.html:19`, `_practice_notes.html:11`; rendered-form tests verify actual description targets, draft retention, and conflict instructions. |
| Feedback completion removed the focused Refresh link; saved responses and note citations did not consistently retain a useful keyboard location. Focus the result heading only when replacing its focused content, make findings valid focus targets, and open/focus cited saved notes. | `project/static/js/learning-feedback.js:44`, `_practice_feedback.html:4`; Chrome checks cover completion, focus elsewhere, note evidence, and the finding after saving a response. |
| Narrowing a desktop workspace could hide the focused composer or artifact and drop focus onto the document. Select the pane being edited and preserve its focus. | `project/static/js/learning-workspace.js:249`; native reproduction plus Chrome checks in both directions. Explicit tab navigation remains covered. |
| Revision history and deletion confirmation still used the portfolio header and lacked Learning's skip target. Use the shared compact shell and focusable main; make saved revision text keyboard scrollable. | `practice_history.html:1`, `practice_delete.html:1`; route checks and native keyboard/skip-link verification. |

Template paths above are relative to `project/learning/templates/learning/`.
The review used the [Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines/blob/main/command.md),
the W3C [tabs pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/),
[fieldset role restrictions](https://www.w3.org/TR/html-aria/#el-fieldset), and
[status-message guidance](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html).

One implementation gotcha: browsers can blur a newly hidden pane before dispatching
`resize`. The fix handles both events, queues a microtask for lost focus, and only
repairs it when focus fell to the document. A requestAnimationFrame-only approach
failed in the headless browser fixture. The regression waits for the observable
focus/view result. Do not broaden this into unconditional focus restoration.

## Automated verification

- Full discovery: **674 tests run, 673 passed, one existing Linux-only skip** on
  macOS, with isolated PostgreSQL 18.6. Includes migration/metadata parity,
  concurrent publication/saves/feedback/export, ownership, budget accounting,
  interruption, deletion, and retry regressions. No schema change in 5f.
- Integrated Chrome: **225 practice checks** (20 added), **70 concept**, and
  **60 hub** checks, included in discovery.
- Renderer/security scripts: **104 checks** (23 + 9 + 29 + 43), including two new
  retry-completion focus assertions. **13 Node tests** and dependency integrity
  passed. No stylesheet or dependency change required a rebuild.
- After the final deletion-shell adjustment, the **13 discussion/web tests**
  passed again. `git diff --check` passed.
- All providers were scripted, dotenv was disabled, and actual AI cost for this
  checkpoint was **$0**. Fictional fixture ledger charges are not real spending.

No database/service/API/scheduling logic changed. Existing tests continue to
exercise native POST/CSRF handling, receipts, conflicts, snapshots, budgets,
ownership, private projections, and recovery. Source in this repository remains
public; server-side projection boundaries do not make repository content secret.

## Try it yourself — about ten minutes

The current [preview](http://127.0.0.1:5064/learning/) contains the saved walkthrough.
Sign in with `learning1@example.test` / `LearningPreview123!`. These are disposable
fixture credentials. To start a fresh copy later:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
  poetry run python scripts/learning-preview-fixture.py \
  --concept --feedback-example --port 5064
```

Only run this command when that port is free. Restarting resets the temporary
data; fixture session IDs change. Templates reload automatically; Python changes
require restarting the fixture. The earlier preview on 5063 is independent.

1. **Follow the learning flow.** Open Idempotency, read a section, step through the
   retry example, reveal/rate a Review question, and enter Discuss/Build. Ask the
   exact clarification above, edit an artifact and a note, save, pause, and reopen.
2. **Exercise the keyboard.** Use Tab/Shift+Tab and Enter. Arrow between Discuss/
   Build and the work tabs. Finish the retry example; focus should land on Start
   again. In DevTools Console, inspect `document.activeElement.id` after a step.
   In Elements → Accessibility, inspect a work tab, its controlled panel, the
   named fieldset inside it, and an invalid field's description.
3. **Reflow while editing.** Focus the message box on desktop, then narrow the
   window or Device Toolbar to 320 CSS pixels. The composer should remain visible
   in Discuss. Repeat for an artifact: Build should stay visible. Try 200% and
   400% browser zoom yourself and check that controls remain reachable.
4. **Read evidence, then revise.** In Checks, open the original scripted example,
   inspect its cited revision, save a response, and try its optional practice.
   Return to the same session, edit, then Save and check. Compare old versus new
   snapshots. Fresh fake feedback is plumbing evidence, not a technical grade.
5. **Watch requests.** In Network, enable Preserve log and use All/Doc to see
   native saves, redirects, and CSRF form data. Use Fetch/XHR for status polling.
   Saving must not send a new discussion turn; a GET must not save or resume work.
   Use the [5e guide](learning-checkpoint-5e-test-guide.md) for exact HTTPie/Postman
   calls and a Python REPL inspection of the exported session. Keep cookies and
   tokens local when copying requests.
6. **Listen if you use a screen reader.** Confirm the selected tab/panel and field
   name are understandable; trigger an empty message error; follow a conflict
   instruction and saved evidence link; request feedback and check the status
   announcement. Note the browser/reader/version and any repeated or missing
   speech. Then verify the skip link on an artifact revision and the delete
   confirmation; choose Keep the session.

## Limits and remaining acceptance

This was a targeted keyboard, DOM/accessibility-tree, and responsive review,
**not a WCAG conformance audit**. A sampled workspace had no duplicate IDs, broken
ARIA references, or unnamed form controls. A limited foreground/background sample
of 40 visible text nodes found no contrast candidates below the applicable ratio;
it is not a complete contrast audit.

VoiceOver/NVDA spoken output and standalone Safari/Firefox remain unverified.
The November 6 delegated review below completes the remaining local technical
assessment. Human publication attestation and production rollout approval remain
outstanding. Long-term unaided retention/transfer belongs to the planned personal
trial. Enrollment/reading position/self-assessment is the separate approved
placement decision above; implementation still needs its own checkpoint approval.
Expo and content expansion also require explicit approval.

## November 6 delegated content and feedback review

Keith delegated the remaining content and AI feedback review to Codex on
November 6. This records Codex's assessment and recommendation. No human-review
attestation was entered into an application database.

The lesson, four questions, scenario, clarification facts, alternatives, rubric,
and misconception mappings support the intended learning loop. The exercise asks
for reasoning about identity, concurrency, failure, and recovery. The hidden
retention/load/warehouse details are fictional exercise inputs that can be
discovered through clarification. The rubric and mapping guidance accept
defensible alternatives, separate missing evidence from contradictions, and credit
explicit corrections. The remaining concrete correction was the overly broad
private statement that a check followed by an insert always requires a database
constraint.

`catalog-v3.json` corrects that statement in exercise revision 3. Its wording
distinguishes an uncoordinated READ COMMITTED sequence from uniqueness, correctly
scoped locking, and SERIALIZABLE with whole-transaction retries. It asks the
learner to account for participating writers, cleanup, and the competing caller's
recovery. This matches PostgreSQL's
[isolation semantics](https://www.postgresql.org/docs/18/transaction-iso.html#XACT-SERIALIZABLE)
and [complete-transaction retry requirement](https://www.postgresql.org/docs/18/mvcc-serialization-failure-handling.html).
The lesson's intended-effect definition and its delivery reasoning agree with
[HTTP semantics](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2) and
[AWS's outbox guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html).

The recorded live review contains 12 cases run twice. Rechecking the summaries,
concerns, and alternative/recovery findings in both repetitions supports keeping
the current evaluator. It identifies the four planted misconceptions, accepts
the SERIALIZABLE and fenced-claim alternatives, credits corrected drafts, and
labels incomplete work as missing evidence. Recorded interviewer examples cite
the proposal and ask the learner to repair a concrete failure case. Existing
findings also acknowledge assistance and distinguish planned tests from measured
results. The [live review](evaluations/learning-feedback-2026-11-02-review.md)
retains the complete outputs and original limitations.

Feedback density is a pilot observation to track. Three to six findings can give
the learner several tasks at once. The evidence-backed concerns and concrete next
steps are sufficient to start local use. A change to ordering, prompts, or the
assessment format should follow observed difficulty choosing a next action.

Verification for this correction:

- **679 tests run, 678 passed, one existing Linux-only skip**, on macOS with
  isolated PostgreSQL 18.6. Five tests were added for version identity, private
  projections, source-route exclusion, import/replay and saved progress, and
  feedback against each session's pinned reference.
- The full run includes **225 practice, 70 concept, and 60 hub browser checks**,
  migration/concurrency/recovery regressions, and the real PostgreSQL SERIALIZABLE
  interleaving test. `git diff --check` passed.
- The preview fixture selects the new manifest when `--feedback-example` is used.
  Catalog/spec format stays 2, the exercise becomes 3, and lesson/questions stay 2.
  Only one new row is inserted when the manifest follows revision 2.
- A separate [corrected preview](http://127.0.0.1:5065/learning/) was started with
  the same disposable credentials. Login and the saved-session API returned
  exercise revision 3 with the private cache policy and no reference material.
  The earlier preview on 5064 retains its existing sessions.
- This follow-up uses saved live evidence and mocked integration responses.
  Additional paid AI cost is **$0**. A fresh live evaluation of revision 3 was not
  run; the historical paid results remain pinned to revisions 1 and 2.

The local implementation and delegated technical review are complete. The
remaining publication and cross-browser/assistive-technology limits above stay
visible in the handoff. The next implementation checkpoint is enrollment, reading
position, and self-assessment, subject to separate approval before content expansion.
