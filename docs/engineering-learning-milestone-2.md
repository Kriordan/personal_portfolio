# Engineering Learning: Milestone 2 checkpoints

Keith approved **2a: Learn and Review on iPhone** on November 13, 2026, after
prioritizing phone access over further web trial tooling. The
[approved architecture](engineering-learning-revised-plan.md) remains in force.
Work remains incremental, with a separate commit and meaningful tests per
checkpoint. Important new architectural choices require discussion. Deployment
still requires explicit approval.

| Checkpoint | Scope | Status |
| --- | --- | --- |
| 2a | Native idempotency lesson, retry demonstration, explicit enrollment/bookmark, versioned recall review, shared schedule and recovery. | Released November 13 as v173 / iPhone build 9 from `eee8b9e`; Keith reported it looks good on his iPhone. |
| 2b | Native interviewer conversation and web/phone session continuity. | Released November 13 as v175 / iPhone build 10 from `a905098`, with Keith's explicit approval. Keith subsequently reported that Discuss looks good on his iPhone. |
| 2c.1 | Native artifact and learner-note editing within the existing shared session. | Released November 14 as v177 / iPhone build 11 from `8e3bff8`, with Keith's explicit approval. Keith subsequently reported that Build looks good on his iPhone. |
| 2c.2 | Native feedback snapshots, findings, citations, and revision loop. | Released November 16 as v179 / iPhone build 14 from `8b508f3`, with Keith's explicit approval. Physical iPhone acceptance remains pending. |

Do not add concepts, voice, new personalities, an offline sync system, or an
editor platform to these checkpoints. Mobile self-assessment is a later scope
decision; its existing web/API implementation is preserved.

## Checkpoint 2a

The existing Expo 57 app now opens a concise concept library, with Learn/Review
tabs and the legacy notes catalog retained. Lessons use the server's visible
content and preserve code formatting. The retry demonstration is a deterministic
native sequence, not an executable sandbox. Enrollment and Save my place are
explicit, matching the web semantics.

Five read/write adapters in `project/api/learning.py` expose the existing
curriculum and scheduler over JWT. They retain the hosted owner/draft boundary,
`private, no-store` responses, exact question versions, optimistic revision
checks, and durable rating receipts. Existing progress APIs are reused. There
is no schema change or new dependency.

Mobile pending ratings now retain their optional content version. Old notes
requests still use their original route and receipt shape. A small bookmark
controller persists the original intent before a write, checks current server
progress after an uncertain outcome, and never repeats a write automatically.
Another device's newer bookmark is not overwritten. Logout disposes both
controllers and clears account-scoped caches/pending state through the existing
authentication cleanup path.

### Verification

- **53 backend tests passed**, covering the new adapters, existing web concept
  experience, progress routes, legacy Learning API, and private hosted access.
  This included actual PostgreSQL 16.15 competing phone/web ratings and existing
  migration/bookmark concurrency tests against an isolated database. No new
  migration is needed.
- **142 mobile tests passed** in an isolated copy of the reviewed source,
  including 13 new contract/recovery/cache/simulation tests. Cases include lost
  responses, restart, explicit retry, duplicate taps, storage failure, offline
  refusal, account switching, newer web bookmarks, and version mismatch.
- TypeScript and ESLint passed. The iOS production Hermes bundle exported
  successfully and was checked for private reference/evaluation markers. A
  clean `preview` export also verified the embedded hosted API origin.
- Native iPhone 18 Pro / iOS 27 simulator walkthrough passed: disposable sign-in
  (including token refresh), concept browsing, explicit enrollment, lesson
  section selection, bookmark save and resumption, answer reveal, and completing
  all four questions. The home due count reached zero; the legacy notes catalog
  remained accessible.
- With the fixture committing a rating but losing its response and refusing
  receipt reads, the phone retained the revealed question and disabled ratings.
  After background/foreground and restored receipt reads it advanced once.
  Server counts stayed at one log/receipt for that question. The finished
  walkthrough had four logs, four receipts, no changes to the other account,
  and **zero AI spending**.
- Maximum simulator text size was exercised for lesson/review rendering and
  answer reveal; text wrapped, and standard size was restored. Accessibility
  labels/state were inspected. A full VoiceOver interaction audit, small-device
  scrolling coverage, Android acceptance, and physical iPhone installation are
  still unverified. The QA harness embeds the new production Hermes bundle in
  an existing compatible simulator binary; it is not evidence of a newly signed
  physical-device archive.

The checkout also contained unrelated interval-timer work. Verification uses a
temporary copy of committed baseline files plus only this checkpoint's changes;
the commit and signed release exclude the unrelated edits. The simulator
uses an isolated QA app identifier and disposable accounts against a temporary
fixture, not hosted personal progress or paid AI.

**Build gotcha:** changing `EXPO_PUBLIC_API_URL` between local and hosted exports
reused a Metro transform with the old fixture URL. `expo export --clear` produced
the correct hosted bundle, which was inspected directly. Clear build caches
for the signed preview too and inspect the downloaded bundle's origin; resolved
app config alone is not enough evidence.

### Approved release — November 13

Keith explicitly approved deployment and the standalone preview. The exact
application source is **`eee8b9e4a45cf5739e500f4c5b3319918957327f`**. Heroku
**v172** deployed it successfully; **v173** then updated only the existing
error-monitoring release tag to that commit. No Learning configuration, database
schema, signing access, or infrastructure changed. Predeployment backup **b013**
completed. The schema remains `e4f5a6b7c8d9`.

Read-only checks on both hosted domains verified owner access, anonymous 401,
non-owner 404, draft labels, private cache headers, lesson/queue/progress reads,
explicit versioned answer reveal, legacy notes and practice-session access.
Public pages and the web login gate remained available. Before/after database
fingerprints matched for review history/receipts, bookmarks, self-assessment,
practice sessions, artifacts, messages, feedback, and the AI ledger. No learner
enrollment, rating, reflection, practice work, or paid request was created.

The original **$5 lifetime allowance**, **$1 verification portion**, **$50 monthly
cap**, and call/context limits are unchanged. The ledger plus carried spending
still counted **$0.076025**, leaving **$4.923975** at release verification; no
pending or running AI requests existed. Local paid AI remains frozen.

Standalone [iPhone build 9](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/eb7be266-9a98-484d-b4fa-8bdc4f75e836)
finished at **4:59:44 p.m. EST**. Its upload contained 908 source files matching
the approved commit, with no local settings, credentials, databases, generated
folders, or interval-timer changes. Existing signing credentials were frozen
and reused; the internal profile still contains one iPhone. Caches were cleared.
No App Store/TestFlight submission or OTA update was made.

The downloaded 16,986,363-byte IPA is an `iPhoneOS` build, bundle identifier
`com.kriordan.personalportfolio`, version 1.0.0/build 9. Its Hermes bundle contains
the new screens and hosted API origin, with no fixture URL or private reference/
evaluation markers. The packaged app config records the correct source commit.
The archive log confirms the existing Sentry source-map upload; its debug ID
matches the downloaded Hermes bundle. No new error event was generated.
See [artifact evidence](assets/learning-2a-iphone-2026-11-13/release.json).
Raw archives, provisioning identifiers, and operator records stay under the
ignored private `.local/learning-pilot/iphone-2a-deployment/` directory.

At release verification, physical installation and a deliberate review were
still pending; build/download verification did not substitute for phone use.
Keith subsequently reported that Learn/Review look good on his iPhone and approved
checkpoint 2b. Future deployments and content expansion require separate approval; 2c.1 and 2c.2 are recorded below.

See the [phone and hands-on engineering guide](learning-checkpoint-2a-iphone-guide.md).

## Checkpoint 2b — Discuss and conversation continuity

The native concept workspace now has Learn, Review, and Discuss tabs. Discuss
lists the account's recent active/paused sessions, starts an explicit new session,
and opens the exact shared web session. Switching to Learn/Review preserves that
session selection. A virtualized transcript shows the interviewer conversation,
with a multiline composer and pause/resume controls. Scenario, revealed
requirements, learner assumptions/decisions, spending status, and saved artifacts
are available separately for reference. Artifact citations open the exact saved
revision, with a notice when a newer revision exists. Native editing and feedback
remain checkpoint 2c.

Keith explicitly chose **device-persistent unsent drafts**, scoped to the account
and session and cleared on sign-out. iOS uses the existing SecureStore/Keychain
dependency with `WHEN_UNLOCKED_THIS_DEVICE_ONLY`; no transcript or reference
packet is persisted locally. A small index tracks at most 20 draft-bearing
sessions for cleanup. The UI distinguishes saving, saved, and failed local saves.
Oversized messages remain editable but cannot bypass the existing 8 KiB send
limit. Drafts retain their original transcript, brief, and artifact revisions.
If the web changes those inputs, the learner must review and explicitly adopt
the updates before sending. Drafts do not sync across devices and are never sent
automatically.

All mutations use one durable pending-operation journal and an immutable UUID.
Automatic recovery only reads the existing receipt API. A missing receipt never
proves a send failed; only an explicit retry replays the original payload and ID.
Device-storage failure prevents the network write. Confirmation removes only a
matching draft before dropping the journal, so a cleanup interruption remains
recoverable. Account disposal fences late callbacks; serialized cleanup cannot
be undone by a late draft write. Existing JWT refresh and account-keyed query
caches are reused. Foreground reads refresh shared work; backgrounded screens
do not poll for AI replies.

One additive backend safeguard was needed: `POST .../reply` accepts optional
`expected_sequence`. Under the existing owner lock, a phone retry aimed at an old
conversation returns `409 stale_transcript`, instead of requesting a reply to a
newer web message. The expectation participates in the receipt digest; replays
still return their original result after a reply arrives. Legacy callers that
omit it retain their existing behavior and receipt hashes. Deploy this compatible
backend change before distributing the new phone build. **No migration,
dependency, worker, provider, prompt, content, or spending configuration changes.**

The 24-turn check-in remains advisory. Long conversations offer the existing
explicit recent-messages continuation, explaining that older messages stay saved
but are no longer read by the interviewer. Oversized essential context is
reported without silent omission. Budget exhaustion preserves reading and
message saving; retries still pass through the existing server budget/lease
controls. The original $5 lifetime allowance, its $1 verification portion,
monthly cap, and per-call/context limits are unchanged. Verification uses fake AI
only and consumes **no paid allowance**.

### Verification and release gate

- Mobile controller/client/auth tests cover immutable sends, lost responses,
  restart, duplicate taps, exact citations, explicit retry/continuation,
  offline/storage failures, account disposal, token refresh, and draft cleanup.
  **162 mobile tests passed**, including 20 new recovery/draft/auth cases.
  TypeScript, ESLint, and a production iOS Hermes export passed.
- The 21 PostgreSQL durable-reply tests passed, including the new retry-versus-web
  send race. The 56 API/web/privacy/session/migration checks also passed after
  rerunning the three migration checks with matching PostgreSQL 16 backup tools.
  An initial restore failed with the default mismatched backup utility; no
  application change was needed. There is no new schema migration.
- Native iOS 27 walkthrough with disposable accounts verified session start,
  conversation/reply, exact v1 artifact citations after another client saved v2,
  scenario/work reading, Learn-to-Discuss continuity, pause/resume, and a send
  whose response was lost while recovery reads failed. Foreground recovery
  restored one learner turn and one reply without resending. The other account's
  data stayed empty. Fake-provider ledger entries are simulated charges, not
  paid usage.
- Native draft checks confirmed saving on the device, recovery after terminating
  and relaunching the app, and retaining the text while disabling Send after a
  different client changed its cited artifact. Sign-out followed by sign-in
  removed the local draft while preserving all seven saved transcript messages.
  Recovery notices sit beside the composer, and initial scrolling follows the
  latest conversation until the learner scrolls to older messages.
- An isolated source copy and its own committed dependencies exclude unrelated
  interval-timer/security work in the checkout. Using the working tree's evolving
  dependency installation initially failed a dependency test; installing the
  committed lockfile in the disposable copy resolved it. Production Hermes export
  passed and the actual bundle was checked for the fixture origin and private
  reference markers. Native QA reuses a compatible simulator binary; signed
  physical-device acceptance, VoiceOver, and Android acceptance remain release
  checks, not claims of this walkthrough.

Implementation was committed separately as **`a905098`**. Keith subsequently
explicitly approved deploying that exact commit and creating the standalone
iPhone preview. The release below preserves the existing pilot settings.

### Approved 2b release — November 13

Application source **`a905098961b1e64611d4d21f56eef8a5674d6a38`** is live on
Heroku. Backup **b014** completed before code release **v174**; **v175** updated
only the existing error-monitoring release tag. The schema is still
`e4f5a6b7c8d9`. No infrastructure, Learning configuration, or signing access changed.

Checks on both hosted origins verified owner access, anonymous 401, non-owner
404, private cache headers, draft labels, lesson/review/progress reads, and the
phone's session and exact-artifact-revision reads. A deliberately stale reply
request returned `409 stale_transcript` without creating a receipt, saved turn,
or AI request. Before/after fingerprints matched for learning progress, saved
practice work, feedback, and the AI ledger. Verification made **zero paid AI calls**.

The **$5 lifetime allowance**, **$1 verification portion**, **$50 monthly cap**,
and call/context limits are unchanged. Counted spending plus carried usage was
**$0.076025**, leaving **$4.923975** at release verification. No AI requests were
pending or running; local paid AI remains frozen.

Standalone [iPhone build 10](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/45ce8b80-8d63-415f-a0d7-887d77b09aef)
finished on November 13 at **7:50:27 p.m. EST**. Its 920 uploaded source files
matched the approved commit and excluded unfinished interval-timer/security
work, local settings, databases, and credentials. Caches were cleared and
existing signing credentials were frozen and reused. The same provisioning
profile still includes the registered iPhone.

The downloaded 17,014,307-byte IPA is an `iPhoneOS` archive for
`com.kriordan.personalportfolio`, version 1.0.0/build 10. Its packaged config
records the exact source commit. The Hermes bundle contains Learn, Review,
Discuss, local-draft status, and the hosted API origin; fixture origins and
private reference/evaluation markers are absent. Sentry's completed source-map
upload has the same debug ID as the downloaded bundle. No test error event,
App Store/TestFlight submission, or OTA update was created.

See [release evidence](assets/learning-2b-iphone-2026-11-13/release.json).
Raw archives, provisioning identifiers, and operator records remain under the
ignored private `.local/learning-pilot/iphone-2b-deployment/` directory.
Keith subsequently reported that Discuss looks good on his iPhone and approved
2c.1. That acceptance is separate from the archive verification above.

Open the build link in Safari on the registered iPhone and tap **Install**.
In the app, open **Tools → Learning → Idempotency → Discuss**. Resume an existing
session, inspect **Scenario & work**, and type a draft to try closing/reopening
the app before sending. Sent messages use the same session as the website and
the existing shared allowance. Native artifact editing is now the approved 2c.1 checkpoint below. Native feedback
is implemented in the separately approved 2c.2 checkpoint below.

### Hands-on engineering checks

Use a disposable fixture (`scripts/learning-preview-fixture.py --concept`) for
experiments. Its two documented test accounts and fake AI keep real progress and
paid usage untouched. Point a local phone QA build at that fixture; never put a
local origin into the distributed preview.

1. In HTTPie/Postman, sign in to the fixture, keep its JWT in a local variable,
   and inspect `GET /api/v1/learning/practice/sessions`. Compare its session ID
   with the phone's session label. Inspect `GET .../sessions/<id>`: messages,
   artifact revisions, brief, reply state, and revealed requirements are distinct.
2. Save an API artifact through the existing web workspace. Send a message on
   the phone, then edit that artifact again on the web. Open the phone message's
   citation: it must show the original revision, while Scenario & work shows the
   latest. In browser DevTools, inspect the existing web requests and compare
   the revisions with the phone API response.
3. In Postman, POST the same `/turns` body twice with the **same** `request_id`,
   `expected_sequence`, `artifact_revisions`, and `brief_revision`. Then GET
   `/receipts/<request_id>` and the session. There should be one saved learner
   turn and one reply request. Change the body while reusing that ID: expect
   `409 request_conflict`. These are mutation experiments: use the fixture only.
4. Type an unsent phone draft and wait for its saved notice. Close/reopen the app,
   resume that session, then change its work from the web. Inspect how the phone
   preserves the draft and requires reviewing the new context. Sign out and back
   in: the unsent local draft should be gone; sent server work remains.
5. For recovery, set the fixture's `practice` mode to `lost`. It commits the
   mutation and loses the response. Observe the receipt read, not a second POST.
   `reads: failure` also blocks receipt reads; restore `reads: success` and reopen
   the app to recover. Keep tokens and private bodies out of screenshots/logs.


## Checkpoint 2c.1 — Build editing on iPhone

Keith approved this implementation, tests, and a separate commit on November 13,
2026. The implementation is `6a1db6e`; the maximum-text follow-up is `8e3bff8`.
Keith explicitly approved deploying `8e3bff8` and creating its standalone iPhone
preview on November 14. The completed release is recorded below.

The fourth concept tab opens Build in the same session as Discuss. It edits the
exercise's existing API, SQL, and pseudocode artifacts, plus learner assumptions,
questions, decisions, and next steps. Each part has an explicit Save action.
Notation choices come from the learner-visible artifact definition; this is a
plain text editor, with no execution or additional editor infrastructure.

Build uses the existing JWT PUT endpoints, optimistic base revisions, immutable
artifact history, and `save` receipts. There are **no backend, schema, provider,
prompt, curriculum, dependency, or spending-setting changes**. Existing Learn,
Review, scheduling, and progress behavior is retained. Reference solutions and
evaluation material remain server-side and are not imported into the app.

### Continuity and decisions

- Unconfirmed Build edits use the same approved privacy policy as Discuss drafts:
  account/session-scoped Keychain storage, `WHEN_UNLOCKED_THIS_DEVICE_ONLY`, and
  serialized cleanup on sign-out. Only pending edits are retained; no transcript
  or private reference packet is stored. A separate index tracks at most 20
  sessions with Build drafts. Drafts never sync or write to the server automatically.
- The existing single pending-operation journal now also accepts artifact/brief
  saves. It stores the immutable payload and UUID before any PUT. A lost response
  triggers receipt reads; only explicit retry replays a write. Confirmation clears
  only the matching part, retaining other edits. Storage/cleanup failure keeps the
  draft and journal recoverable. Signing out fences late writes and callbacks.
- A newer web revision preserves the phone draft and blocks Save. The learner
  compares the saved work, then either discards the local draft or explicitly
  keeps it with the new base revision. Keeping a draft does not save it. Notes
  replace the entire brief, so the comparison explains that other notes must be
  retained manually. There is no automatic merge or last-write-wins overwrite.
- Note IDs, types, pinned status, and existing evidence links survive editing.
  Editing a cited artifact changes its current head; old conversation citations
  continue opening the exact immutable revision.
- Discuss blocks Send until every Build edit in that session is saved or discarded.
  An already-written conversation draft still requires the existing explicit
  review/adoption of changed work before sending.
- Saving a paused session resumes it under the existing backend behavior. The
  button says so explicitly. Saving work itself queues no AI reply or evaluation.
- The server limits stay authoritative: 64 KiB per artifact, 2 KiB per note, and
  50 notes. Unfinished notes and over-byte-limit Unicode remain local and editable,
  with Save disabled and a visible explanation.

### Verification

- **179 mobile tests passed**, including 17 new deterministic tests for PUT
  contracts, exact revisions, byte limits, note evidence, coalesced draft writes,
  restart, multiple pending parts, conflict handling, lost responses, immutable
  retries, duplicate taps, storage/cleanup failures, sign-out races, and the
  Discuss guard. TypeScript and ESLint passed.
- **57 backend tests passed** against the appropriate existing fixtures, including
  actual PostgreSQL 16 concurrency and migration checks. Four new PostgreSQL
  tests exercise duplicate maximum-size PUTs, receipt replay after a newer web
  edit, competing phone/web brief saves, and artifact saves racing a discussion
  turn. No new migration is required. No AI request/charge is created by a save.
- A production iOS Hermes export passed. Verification uses an isolated copy of
  committed baseline `ab7b987` plus only this checkpoint; unrelated interval and
  dependency-security work in the shared checkout is excluded. The actual bundle
  contains the intended QA origin and Build screens, with private reference/
  evaluation markers absent.
- The native iPhone 18 Pro / iOS 27 walkthrough uses an isolated QA app and
  disposable local accounts with fake AI. API/SQL/pseudocode saves, pinned
  decisions, unfinished-work Send blocking, and the subsequent interviewer's
  exact saved-artifact citations were verified. A web save produced a visible
  conflict; explicit comparison/keep/save preserved the chosen draft.
- A SQL save committed while its response and receipt reads failed. Closing the
  app, restoring reads, and resuming recovered exactly one revision without
  another PUT. A 65,536-byte pseudocode draft survived process termination and
  then saved successfully through the native journal and Keychain.
- The native walkthrough prompted a compact Build heading and full-width work
  choices. **The maximum-text recheck completed November 14.** It exposed a
  remaining issue when changing Dynamic Type while the app was open: the numeric
  tab widths could still crowd scaled labels. Tabs now use native text measurement
  before wrapping; the tab list remounts when font scale changes so iOS measures
  it again. At `accessibility-extra-extra-extra-large`, all four labels fit in
  two readable rows, including after switching Discuss → Build in the same
  session. Restoring `large` returns the tabs to one row.
- At maximum text size, the API notation choices and editor, note type choices,
  wrapped pin label beside its switch, draft status, Save actions, and note-removal
  confirmation remained readable. Artifact and pinned-note saves advanced their
  revisions and remained visible after returning to the Build overview. The
  simulator's original `large` text size was restored and keyboard capture was
  turned off. The final source passed all **179 mobile tests**, TypeScript, ESLint,
  and a fresh production Hermes export. No backend behavior changed in this
  visual-review follow-up; the PostgreSQL results above belong to the main
  checkpoint verification.
- A full software-keyboard pass and native sign-out repeat remain manual release
  checks; account cleanup and late-write fencing are covered by deterministic
  tests. See the guide's maximum-text regression steps for repeating this review
  on the signed iPhone preview.

The **$5 lifetime allowance, $1 verification portion, $50 monthly cap, and per-call/
context limits are unchanged**. All checkpoint AI responses are mocked/fake;
paid AI spending is zero. Fixture ledger amounts are simulated, not hosted usage.

Native QA embeds the production JS bundle in an existing compatible simulator
binary. A newly signed physical-device archive, physical iPhone acceptance,
Android acceptance, and a full VoiceOver interaction audit remain unverified.

**QA gotcha:** do not type a 64 KiB stress-test value as individual automated
keystrokes. That flooded the simulator's keyboard queue. Seeding 65,535 bytes via
the disposable API, adding one character on the phone, then closing/reopening
and saving verified the intended storage/recovery boundary without the key flood.

See the [short hands-on guide](learning-checkpoint-2c1-iphone-guide.md).

### Approved 2c.1 release — November 14

Application source **`8e3bff84998f65091735c58af21ff5d152cbf074`** is live on
Heroku. Backup **b015** completed before code release **v176**; **v177** updated
only the existing Sentry release tag. Schema `e4f5a6b7c8d9`, the one Basic web
dyno, owner access policy, exact draft approval, and all Learning settings remain
unchanged.

On both hosted origins, owner lesson/review/progress/session reads, anonymous
401, non-owner 404, private cache headers, draft labels, and exact artifact
revision reads passed. A deliberately stale artifact save returned
`409 stale_artifact`; a note save citing a nonexistent future brief revision
returned `400 invalid_request`. Neither produced a receipt. PostgreSQL
fingerprints confirmed that progress, saved work, feedback, receipts, and the
AI ledger stayed unchanged during verification. No paid AI call was made.

The **$5 lifetime allowance, $1 verification portion, $50 monthly cap, and
per-call/context limits are unchanged**. Counted spending and carryover remained
**$0.076025**, leaving **$4.923975** at verification. No AI requests were pending
or running, and local paid AI remains frozen.

Standalone [iPhone build 11](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/077bde85-d29e-448b-9855-9d61a7b2635e)
finished November 14 at **7:10:44 a.m. EST**. All **929 uploaded source files**
matched the approved commit; unfinished interval/security work, local databases,
settings, and credentials were excluded. EAS caches were cleared and existing
signing credentials were frozen and reused. The provisioning profile still
includes the same registered iPhone.

The downloaded **17,032,177-byte IPA** is an `iPhoneOS` archive for
`com.kriordan.personalportfolio`, version 1.0.0/build 11. Its packaged source
commit matches `8e3bff8`; its Hermes bundle includes Build editing, saved-draft
and comparison controls, the existing Learn/Review/Discuss screens, and the
hosted API origin. Fixture origins and private reference/evaluation markers are
absent. The completed Sentry source-map upload's debug ID matches the packaged
bundle. No test error event, App Store/TestFlight submission, or OTA update was
created.

See [release evidence](assets/learning-2c1-iphone-2026-11-14/release.json).
Raw archives, provisioning identifiers, and operator records stay under the
ignored private `.local/learning-pilot/iphone-2c1-deployment/` directory.
Physical installation/acceptance and the remaining keyboard/VoiceOver checks
are separate from archive verification. Keith subsequently reported that Build
looks good on his iPhone and approved 2c.2 below; that does not establish a full
VoiceOver audit.

## Checkpoint 2c.2 — Feedback and revision on iPhone

Keith approved implementation, tests, and a separate commit on November 16,
2026, while retaining approval before deployment. The base is `b9727b4`, which
already merged `origin/main` at `8034001`; the interval timer, preview-update
configuration, and dependency-security work from main are preserved.

Build now includes **Feedback & snapshots** in the existing shared session.
Saving a snapshot freezes the displayed saved conversation boundary, all saved
artifact revisions, and saved learner notes. It runs existing syntax checks
without requesting AI. **Request feedback** is a separate explicit action.
Saved findings show their evidence and next step, link to immutable artifact
revisions or original learner turns/notes, and offer a return to the relevant
lesson section or editable work. Learn/Review/Discuss/Build navigation preserves
the selected session and snapshot. Older feedback remains available and is
labelled when the current work has changed.

### Decisions and boundaries

- Reuse existing JWT submission/feedback endpoints and the approved editable
  session lifecycle. There are **no backend runtime, schema, provider, prompt,
  curriculum, dependency, or infrastructure changes**.
- Reuse the account-scoped durable operation journal for `submit` and `feedback`.
  Persist the immutable payload and UUID before POST, verify receipt operation,
  session, snapshot boundary, and artifact/brief revisions, and recover by reads.
  Only an explicit retry repeats the original POST. An explicit new evaluation
  attempt warns that the previous attempt may count toward the allowance.
- Block snapshot creation until local Build edits and unsent Discuss drafts are
  resolved and protected. A newer web change is rejected by the existing server
  freshness checks; it is never overwritten by a stale snapshot request.
- Assess one complete snapshot per call. Oversize/budget refusals are visible;
  there is no silent omission, automatic paid retry, or new context policy.
  Work remains editable while evaluation runs. Poll only while the screen is
  visible and the app is in the foreground; saved results resume after reopening.
- Keep snapshot/feedback response caches in memory and scoped to account/session.
  Original evidence is loaded from learner-safe endpoints, never from private
  reference packets. The public repository caveat still applies: server-side
  delivery boundaries are not a claim that authored source files are secret.
- Existing review scheduling and user progress remain unchanged. Feedback is a
  judgment to examine; a missing observation is not a failing grade. Native
  agree/disagree annotations, adding follow-up recall cards, self-assessment,
  export, and deletion UI remain separate scope decisions; existing web features
  are preserved. This checkpoint does not declare all of Milestone 2 complete.

### Verification

- **208 mobile tests passed**, including 12 new deterministic contract, snapshot,
  citation, stale-view, budget/size, duplicate-tap, account-switch, offline,
  storage/cleanup, restart, and exact retry tests. TypeScript and ESLint passed.
- **780 backend tests ran successfully (779 passed, one existing Linux-only
  skip on macOS)**, including **225 integrated practice browser checks**. Five
  new tests ran against real **PostgreSQL 16**, covering duplicate snapshots,
  concurrent web editing, duplicate/lost feedback requests with one settled
  charge, edits during evaluation, and budget reductions before/after queueing.
  Existing migration tests ran against that isolated database; no migration was
  added. The fixture provider is deterministic throughout.
- A production-mode iOS Hermes export passed. Its bundle contains the intended
  local QA origin and feedback screens; private reference/evaluation markers
  are absent. Native QA used an existing compatible simulator binary with this
  bundle, a separate QA identifier, and OTA updates disabled in that QA copy.
  This is not a newly signed physical-device archive.
- Native iPhone 18 Pro / iOS 27 walkthrough: open saved feedback, follow the
  exact API revision, revise/save to revision 2, see the earlier-snapshot notice,
  follow a lesson remediation link, and return to the same snapshot/session.
- Saving snapshot 3 increased the fixture's snapshot/receipt counts by one,
  leaving feedback count and simulated spending unchanged. The separate feedback
  POST committed while its response and subsequent reads failed. After process
  termination, reconnection, and resumption, the phone recovered its saved
  feedback: exactly one additional feedback request, receipt, and simulated
  charge, with the other account and review logs unchanged.
- At maximum simulator Dynamic Type, the four tabs wrap into two readable rows;
  snapshot choices, evidence text, and next steps remain readable. Normal text
  size and keyboard capture were restored. The walkthrough led to shorter
  introductory text, collapsed snapshot details, and resetting scroll position
  when moving from feedback to an editor or the proposal overview.

The **$5 lifetime allowance, $1 verification portion, $50 monthly cap, and all
per-call/context limits remain unchanged**. This checkpoint used **zero paid
AI calls**. Fixture ledger values are simulated; no hosted balance was queried
or changed. Full VoiceOver interaction, Android, software-keyboard coverage,
and the updated signed preview on Keith's physical iPhone remain release checks.

Implementation validation above preceded deployment. Keith subsequently approved
deploying `8b508f3` and creating the updated standalone preview; the release is
recorded below. See the [hands-on guide](learning-checkpoint-2c2-iphone-guide.md).

### Approved 2c.2 release — November 16

Application source **`8b508f3b66ec4221e030519e9102c34a8dcab326`** is live on
Heroku. Backup **b016** completed before code release **v178**; **v179** updated
only the existing Sentry release tag. Schema `e4f5a6b7c8d9`, the one Basic web
dyno, owner policy, exact draft approval, and every Learning setting are unchanged.

On both hosted origins, owner lesson/review/progress/session/snapshot/feedback
reads, anonymous 401, non-owner 404, private cache headers, and draft labels passed.
Saved feedback covered its complete original snapshot, and **eight evidence
citations per origin** matched their original saved sources. Database fingerprints
confirmed that progress, saved work, feedback, receipts, requests, and the spending
ledger stayed unchanged throughout verification. No paid AI request was made.

The **$5 lifetime allowance, $1 verification portion, $50 monthly cap, and
per-call/context limits remain unchanged**. Counted spending including carryover
remained **$0.076025**, leaving **$4.923975** at verification. No AI requests were
pending or running; local paid AI remains frozen.

Standalone [iPhone build 14](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/a55838d8-8dd0-40c0-a9dd-f5d43c9fd3b7)
finished November 16 at **12:12:58 p.m. EST**. All **969 uploaded source files**
match the approved commit, and the archive's Git metadata matches `8b508f3`.
Three already-ignored legacy YouTube JSON files were excluded; there were no
extra or modified source files. Local settings, credentials, and databases were
excluded. Both existing dependency audits passed with zero findings/exceptions,
and Expo native dependency compatibility passed. EAS caches were cleared and
existing signing credentials were frozen and reused.

The downloaded **17,539,601-byte IPA** passes strict/deep signature verification.
It is an `iPhoneOS` archive for `com.kriordan.personalportfolio`, version 1.0.0 /
build 14, with the same registered iPhone and provisioning profile. Its packaged
commit and hosted API origin match the approved release. Learn/Review/Discuss,
Build editing, and the new feedback/revision controls are present; local fixture
origins and private reference/evaluation markers are absent.

Main's native interval timer, background audio, and existing `preview` update
channel are preserved. The runtime remains
`77b0440fdf8c270adcb7939e8c162f453f8e5ad4`. Expo 57's `Expo.plist` records
`file:fingerprint`; verification resolves that indirection through the packaged
`EXUpdates.bundle/fingerprint`, rather than comparing the literal sentinel to the
hash. The Sentry source-map upload completed, with its debug ID matching the
packaged Hermes bundle. No OTA update, App Store/TestFlight submission, or test
error event was created.

See [release evidence](assets/learning-2c2-iphone-2026-11-16/release.json).
Raw archives, provisioning identifiers, and operator records stay in the ignored
private `.local/learning-pilot/iphone-2c2-deployment/` directory. The preview runs
without the Mac. Physical installation/acceptance and the outstanding VoiceOver,
keyboard, and Android checks remain separate from archive verification.
