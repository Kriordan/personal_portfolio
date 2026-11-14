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
| 2b | Native interviewer conversation and web/phone session continuity. | Released November 13 as v175 / iPhone build 10 from `a905098`, with Keith's explicit approval. Physical-device acceptance pending. |
| 2c | Native saved artifacts and feedback within the same practice session. | Proposed; not authorized yet. |

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
checkpoint 2b. Future deployments, 2c, and content expansion require separate approval.

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
Physical installation and use of build 10 remain Keith's acceptance step;
archive verification does not substitute for that check.

Open the build link in Safari on the registered iPhone and tap **Install**.
In the app, open **Tools → Learning → Idempotency → Discuss**. Resume an existing
session, inspect **Scenario & work**, and type a draft to try closing/reopening
the app before sending. Sent messages use the same session as the website and
the existing shared allowance. Native artifact editing and feedback remain 2c,
which requires separate approval.

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
