# Engineering Learning: Milestone 2 checkpoints

Keith approved **2a: Learn and Review on iPhone** on November 13, 2026, after
prioritizing phone access over further web trial tooling. The
[approved architecture](engineering-learning-revised-plan.md) remains in force.
Work remains incremental, with a separate commit and meaningful tests per
checkpoint. Important new architectural choices require discussion. Deployment
still requires explicit approval.

| Checkpoint | Scope | Status |
| --- | --- | --- |
| 2a | Native idempotency lesson, retry demonstration, explicit enrollment/bookmark, versioned recall review, shared schedule and recovery. | Released November 13 as v173 / iPhone build 9 from `eee8b9e`; physical-device acceptance remains. |
| 2b | Native interviewer conversation and web/phone session continuity. | Proposed; not authorized yet. |
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

**Physical-device installation and a deliberate review are still pending.**
Build/download verification does not substitute for Keith trying the phone app.
Future deployments, 2b/2c, and content expansion require separate approval.

See the [phone and hands-on engineering guide](learning-checkpoint-2a-iphone-guide.md).
