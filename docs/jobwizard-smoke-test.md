# Jobwizard smoke test

**Current status:** see [Validation status and follow-ups](validation-status.md) for the October 27 recovery results and remaining work. This is the full regression checklist; a combined item stays unchecked when only a narrower scenario has passed.

Checklist for the [Jobwizard modernization plan](jobwizard-modernization-plan.md), approved October 21 with immediate saving and optional screenshot capture afterward. Leave an item unchecked unless its entire stated behavior was exercised.

Use the disposable two-account fixture for failures and concurrency. Live acceptance should use a clearly labelled **Jobwizard smoke test** record and a public nonpersonal listing. Do not send a private/tokenized listing to the screenshot provider merely to test the integration. Archive the test record afterward; permanent deletion is outside this slice.

## Browse and details

- [ ] Open the three-dot job actions menu. Show listing opens only a valid HTTP(S) URL; Copy link copies the exact saved URL and announces success; Edit preserves the current form; Archive changes to Restore after confirmation. Dismiss without selecting and repeat with an unresolved operation.
- [ ] Expand/collapse Source beside saved bullets and within suggestion review. Check evidence, edited/outdated notices, long text, large text, keyboard focus, VoiceOver/TalkBack labels and 44-point touch targets. Copy feedback must not add a large layout jump.

- [ ] Cold-launch the new preview, restore/sign in, and reach Jobwizard through Home and Tools. Confirm protected routes and Me sign-out still work.
- [ ] Active is the default view. Search title, company and hostname using mixed case/whitespace. Combine search with Active/Archived/All and each sort. Clear a no-results query without losing the selected filter.
- [ ] Newest/oldest saved, Company A–Z and Title A–Z are stable with equal values. Unknown save dates sort last; legacy dates are not presented as verified publication/save dates.
- [ ] Scroll hundreds of fixture rows. Long titles, companies and domains wrap without covering controls. Return from detail or the browser with browse state and scroll position preserved.
- [ ] Open a job and launch its HTTP(S) listing. Handle launch failure without changing job state. A malformed/unsafe legacy URL cannot launch and offers editing.
- [ ] Test missing, foreign, deleted and malformed IDs, signed in and signed out, with warm and terminated-preview links. Each reaches an unavailable/login state with a route back, without an endless spinner.
- [ ] Distinguish No saved jobs, No active jobs, No archived jobs and No matches. Initial failure offers retry; failed refresh retains loaded jobs with a stale-data message.

## Add, edit and archive

- [ ] Add a job with title, company and URL. Save succeeds with screenshot service/storage unavailable, opens the confirmed detail and creates one record.
- [ ] Type rapidly and double-tap Save. All characters persist and only one intended submission is committed. The URL field uses appropriate keyboard/capitalization behavior.
- [ ] Exercise blank, non-string/malformed API input, invalid schemes, credential-bearing URLs, control characters and length boundaries in the fixture. Show useful field errors without truncating drafts or exposing exception details.
- [ ] Cancel a clean form. Edit each field, attempt Back/Close/swipe dismissal, cancel Discard, and confirm the draft survives. Confirm Discard only when intended. Repeat on Android Back and mobile web navigation.
- [ ] Save an edit, reopen the record and verify its original saved date is unchanged. Changing the listing URL does not automatically capture a new screenshot or mislabel the previous one as current.
- [ ] Archive a job and verify it leaves Active only after confirmation. Find it in Archived/All, restore it, and verify the same ID and screenshot remain. Rapid repeated Archive/Restore actions settle at the confirmed desired state.
- [ ] Edit/archive the same job from a second fixture client. The stale editor gets a clear conflict, retains proposed changes and can load the latest record. No later write silently overwrites the competing change.
- [ ] Lose a successful create/edit/archive response. Read the receipt, recover the committed result and verify one write. A failed/missing status read does not assert failure or automatically resubmit. Explicit retry uses the same request ID and frozen payload.
- [ ] Relaunch during an unresolved save and recover its account-scoped status. Sign out during a delayed response, then sign into the other account; no old draft, receipt, cached job or completion announcement appears.
- [ ] Start offline and save: immediate failure with the draft retained. Reconnect: reads may refresh, but no write runs until a deliberate retry.

## Screenshots

- [x] Confirm a normal job save does not call ApiLeap/S3. Only the explicit Capture action starts capture, and its explanation identifies that the listing link goes to the screenshot service.
- [ ] Capture a fixture page and verify progress, completion time and the uncropped preview. Open the full screenshot and return. Opening a screenshot must not start a new capture.
- [ ] Double-tap capture, navigate away/back and background/foreground the app. One attempt/provider call runs; status resumes from the server. No unattended retry purchases another capture.
- [ ] Fail provider authentication, quota, timeout, status, content type, image decoding and S3 upload independently in the fixture. The job remains saved, no invalid image reference is published, and any previous good screenshot remains available.
- [ ] Interrupt the capture process after its running receipt exists. It becomes Interrupted after the lock is released; a failed status read retains uncertainty. Retry is deliberate and follows resolution of the previous attempt.
- [ ] Edit the URL while capture is running. The old-page result cannot become the current screenshot for the new URL. Archive during capture without losing the record or exposing another account's image.
- [ ] Verify private storage with a synthetic image: unsigned original access denied, owner-authorized link works, foreign-account requests fail, link expires and renewal works. Never print signed URLs or credentials.
- [ ] Leave the app active and backgrounded beyond the image-link lifetime, then read the image again. Verify renewal on foreground/refresh/error, offline recovery and no persistent private-image cache after logout.
- [ ] Exercise legacy bare-key, static-path, missing, malformed and inaccessible screenshot references. Verify the migration/mapping preserves records without claiming unverified legacy object privacy. Older preview compatibility limits are recorded.
- [ ] Perform one deliberate live capture only after provider/private-storage readiness is verified. A successful fixture test does not establish live credentials, quota or storage permissions.

## Shared data, layout and regression

- [ ] The same account sees website/second-device saves, edits and archive changes after focus/foreground/reconnect/pull-to-refresh, including within 30 seconds. Refresh does not overwrite a dirty editor.
- [ ] The second fixture account cannot read or mutate the first account's jobs, images or receipts. Missing and foreign records receive equivalent 404 responses. Personal responses use private/no-store caching.
- [ ] Check iPhone light/dark, normal/largest Dynamic Type, a smaller phone, software keyboard, long native menu labels and tall screenshots. Heading, fields, errors, Save/Cancel and capture controls remain fully visible or scrollable.
- [ ] Complete VoiceOver and TalkBack passes: logical focus, field labels, row labels, sort/filter selection, archive state, screenshot alternatives, pending/success announcements and error recovery.
- [ ] On Android, exercise browse/add/edit/archive/capture/recovery, keyboard, native widths, pull-to-refresh and gesture/three-button navigation insets. Record actual interaction separately from build/export/install success.
- [ ] On mobile web and the existing website, verify owner-scoped browse/form/archiving, invalid-form recovery, links, image delivery and confirmed writes. Website layout redesign is not required.
- [ ] Regression: Grocery CRUD/completion and website events/reconnect; Wishlist CRUD/photos/discard/15-minute renewal; Library search/sort/pins/sync receipts/playback/watched workflow; Learning study/review receipts; Home/Tools/Me, logout clearing and protected links. Preserve earlier unverified checks.

## Release evidence

- [x] Record full backend/PostgreSQL, mobile, browser, migration, typecheck/lint, exports, Expo compatibility and audit results. Confirm actual CodeQL findings on PR head/merge references, not only scan-job success.
- [ ] Record implementation source, additive migration head, Heroku release and healthy old/new-client responses. Keep legacy job ownership, IDs, dates and screenshot references intact.
- [x] Inspect the EAS upload for excluded secrets/local databases and build a fresh internal iPhone preview with the approved signing setup and HTTPS API. Record build ID/link and matched backend release.
- [ ] Install that preview on the physical iPhone and complete a deliberate add/edit/archive/restore flow. Record device/OS, screenshots and exact checked steps; build/download success alone is not acceptance.

## Planning evidence

October 21: all **17 existing Jobwizard API/service tests pass** on the merged baseline. Disposable probes reproduce malformed-input exceptions, acceptance of an unsafe URL scheme, a successful response with a failed screenshot reference, missing explicit cache privacy, and the invalid website form's missing template. These findings establish requirements only; none of the implementation checklist is complete.


## Implementation evidence — October 21

The organizer, additive migration `e1f2a3b4c5d6`, account-scoped mutation receipts, revision checks, and optional durable capture attempts are implemented. New captures use private `j/` object keys and 15-minute signed links. Legacy image references are retained but shown as unavailable until their storage mapping/privacy can be verified. Older previews can save/read jobs but cannot display the new private captures.

Automated validation: final Linux CI passed **217 backend tests**, including all PostgreSQL cases and the worker parent-death test. **75 mobile tests**, TypeScript, lint, Expo 57 dependency compatibility and iOS/Android/web production exports passed. Existing **18 browser security checks** and **4 root tests** passed. Python audit found no known vulnerabilities; root/mobile audits matched their existing bounded exceptions. The November 5 security review deadline is unchanged.

Observed native evidence: iPhone 18 Pro simulator, iOS 27.0, development client against the disposable fixture (320 jobs for account 1, three for account 2). Company A–Z menu displayed all four labels; mixed whitespace search found the expected record. Add saved immediately and opened details; capture required a separate deliberate confirmation. A tall synthetic screenshot appeared. Archive/restore retained the ID and image. Cancelling the dirty-form discard prompt retained all fields. A competing API edit received a 409 in the open editor; the draft stayed intact, Compare latest showed the competing version, and explicit Keep my draft followed by Save succeeded. Screenshot evidence is retained locally at [iPhone details](assets/jobwizard/iphone-detail.png).

Interactive website fixture: login, form-based save, detail, archive and restore succeeded. The form's POST method was explicitly repaired and regression-tested. The shared service preserves unchanged oversized legacy fields during unrelated edits, including website edits.

The EAS archive inspection contained 487 files and the intended Jobwizard sources, with no local credential files, private keys or databases. No new framework/package dependency or security exception was introduced.

Still open: physical preview installation; Android interactions (the emulator is running but Android Studio did not expose it for UI automation, and project sync reported a local toolchain error); complete VoiceOver/TalkBack, smaller devices, large text/software keyboard, dark mode, cold protected links, native relaunch/account-switch and 15-minute image renewal. These are not implied by unit tests, exports or build success. All inherited feature checklists remain open where previously unverified.

Live storage configuration is explicitly approved for IAM user `portfolio-heroku-prod`, bucket `portfolio-wishlist-prod` in `us-west-2`, `j/` only. The exact additive policy is [jobwizard-storage-policy.json](security/jobwizard-storage-policy.json). The policy was applied and Heroku v141 configured the bucket/region. All four Block Public Access flags are enabled. A 2×2 synthetic upload succeeded; unsigned access returned 403, the 15-minute signed link returned 200 with private/no-store. Test object: `j/a98908141c214dd79286663a9a46fcf2.png` (retained; application permissions intentionally exclude deletion). Two deliberate `https://example.com` capture attempts failed; the diagnostic attempt confirmed HTTP 500 and a non-image response from ApiLeap. No capture object was published. `JOBWIZARD_CAPTURE_ENABLED` must be `1` only after a successful provider readiness check; the production setting remains disabled. Do not substitute another provider or reuse credentials at another service without approval. Initial target DNS is checked for public addresses; Flask only calls the fixed ApiLeap endpoint. Provider-internal redirect/DNS behavior is outside this application's verification and must not be represented as a complete target-isolation guarantee.

Additional iPhone check: a saved edit deliberately returned a failed response, and receipt reads were temporarily unavailable. The app retained the pending operation and draft. Restoring receipt reads recovered the saved job automatically without another write: 325 fixture jobs and 10 receipts both before and after recovery.

The preliminary iPhone build `fb74be7d-900d-41bd-8cda-d877d278cf4d` is superseded by the final preview below.


## Final release evidence

- [PR #116](https://github.com/Kriordan/personal_portfolio/pull/116), application/backend source **`0f2a580`**. Backend, mobile, web and all CodeQL jobs passed on this source. CodeQL analysis records match the PR head commit; queries for open findings at both `refs/pull/116/head` and `refs/pull/116/merge` returned zero.
- **Heroku v144** deployed from `0f2a580`, migration **`e1f2a3b4c5d6`** verified. Production had zero saved jobs before and after the additive migration; populated-fixture preservation is covered in PostgreSQL tests. Health returned 200; unauthenticated job/status routes returned private/no-store JSON 401. The website redirects signed-out visitors to login. Read-only production verification confirmed the final Unicode boundary fix and disabled capture gate.
- [Final internal iPhone preview `2fc3dec3-0464-4c97-9181-20baf3832898`](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/2fc3dec3-0464-4c97-9181-20baf3832898) finished at **17:55:31 UTC** on October 21 (1:55 p.m. EDT), app source **`ade51e0`**. The subsequent `0f2a580` change is backend/test only. IPA HEAD returned 200. Existing registered-device signing credentials and the HTTPS Heroku API were reused. No App Store/TestFlight or OTA release occurred. Physical installation/acceptance remains open.
- Private screenshot storage is enabled and verified; **ApiLeap capture is disabled** with `JOBWIZARD_CAPTURE_ENABLED=0` because the provider returned HTTP 500. Do not mark live screenshots ready or enable the gate until a deliberate public capture succeeds. No provider/credential substitution was made.
- Additional iPhone failure check: a failed list refresh retained 292 cached active jobs with explicit stale-data text; Retry recovered after fixture reads were restored. [Overview](assets/jobwizard/iphone-overview.png), [stale refresh](assets/jobwizard/iphone-stale-refresh.png), [detail](assets/jobwizard/iphone-detail.png).
- The disposable API, Metro, PostgreSQL and emulator processes started for validation were stopped. All earlier feature and accessibility follow-ups remain as listed above.

## Browserless evaluation — October 22

PR #116 merged as `a5a5364`. The user approved a bounded evaluation of Browserless on public job listings, not production provider replacement or a paid subscription. The evaluation is complete on `feature/browserless-evaluation`: **9/12 current listings passed the initial visual check; two explicit Workday follow-ups raised the combined result to 11/12**. One long Ashby page still has missing parts of final disclosure lines. Eighteen completed captures consumed 18 units according to distinct provider request IDs. The existing key was used temporarily outside the repository and removed afterward. See the [full evaluation and next implementation scope](evaluations/browserless-2026-10-22.md) and [machine-readable evidence](evaluations/browserless-2026-10-22-results.json). Production capture remains disabled.

Evaluation artifacts:

- [`scripts/evaluate-browserless.py`](../scripts/evaluate-browserless.py): a standalone evaluator using the existing Requests/Pillow dependencies. It does not import Flask, read the app's `.env`, access production jobs, or upload to S3. A dry run validates the selection without credentials or network calls. Each explicit run uses a fresh output directory and makes one sequential request per selected entry, with no automatic retry or requested proxy/CAPTCHA options.
- [`scripts/fixtures/browserless-public-jobs.json`](../scripts/fixtures/browserless-public-jobs.json): 12 public listings across Greenhouse, Lever/Lever EU, Ashby, and Workday, plus an Example Domain control and a known expired SmartRecruiters listing. Search results for two older listings redirected to careers pages; those were replaced before selecting the sample. These are rendering samples, not job recommendations.
- The selected Greenhouse/Lever descriptions were verified through current public pages. Normal-browser checks confirmed all four Ashby descriptions and both Workday descriptions. Workday content appeared after the initial page response, making premature capture a specific risk to evaluate. Local baseline text is in `/private/tmp/browserless-evaluation/`.

The initial recipe uses a 1280×900 viewport at device scale 1, full-page PNG, `domcontentloaded`, a one-second settling delay, and scrolling for lazy content. Provider time is capped at 18 seconds; the local operation is capped at 22 seconds and uses the production 8 MiB / 24-megapixel image limits. This measures capture/download/image processing from the Mac, **not Heroku latency or S3 upload time**. The 18-second local threshold reserves some time for storage; it does not prove the production deadline is met.

Evaluation checks (production readiness remains separate):

- [x] Verify the merged baseline, compile the evaluator, and complete its 14-entry dry run.
- [x] Sign in; verify free allowance and account usage before running the positive control, then the 12-listing sample and expired control. Never print the token, provider request URL containing it, or raw error bodies.
- [x] Record actual account/request-log units before and after. Do not equate elapsed local time with billed browser time.
- [x] Review every returned image against the source: correct title/company, readable description, qualifications and final section, no obstruction, missing lower content, login screen, or challenge page. A valid PNG or HTTP 200 is insufficient.
- [x] Classify source expiration/redirect separately from provider failures. Check target response status and failed stylesheet counters when returned; absent metadata means unknown.
- [x] Record latency, download size, dimensions, errors, and image-review verdicts. Any targeted second recipe must be recorded separately from the initial result; do not silently replace failures with retries.
- [x] Assess provider retention/logging and target restrictions before recommending production use. Keep existing private S3 ownership and expiring delivery.
- [x] Recommend the next implementation only after results: bounded synchronous provider replacement if it meets the budget, or a separate durable background-capture design if slow pages need more time.

Reference documentation: [screenshot API](https://docs.browserless.io/rest-apis/screenshot-api), [request options and response diagnostics](https://docs.browserless.io/rest-apis/request-configuration), [timeouts](https://docs.browserless.io/rest-apis/timeouts), [usage logs](https://docs.browserless.io/overview/request-logs), [pricing](https://www.browserless.io/pricing). All existing native, accessibility, production capture, and dependency follow-ups remain open where unverified.

## Browserless implementation — October 22

The user approved the recommended implementation after the evaluation. See [rollout details and limits](jobwizard-browserless-rollout.md). The adapter now uses the Function REST API, description/layout readiness checks, constrained platform/CDN requests, one capture per deliberate attempt and two shared PostgreSQL capacity slots. The preview names Browserless and shows safe failure reasons while retaining previous good images. Existing unchecked acceptance items above remain open.

- [x] Capture one public listing each on Greenhouse, Lever, Ashby and Workday with the adapter. Local runs took 4.319–7.661 seconds. The long Ashby disclosure paragraphs and dynamic Workday final description rendered.
- [x] Run long Ashby and Workday captures in an isolated Heroku dyno through private S3: 9.617 and 11.279 seconds; signed reads 200/private-no-store, unsigned reads 403. No production jobs or web release were changed.
- [x] Verify failure receipts, no unattended retries, duplicate request replay, preserved previous images, source edits, account isolation, malformed/oversized responses, private storage checks and cross-process capacity/death recovery in automated tests.
- [x] On iPhone 18 Pro/iOS 27 simulator, show both real private S3 readiness images through the disposable fixture. Open the full Ashby image in Safari and return. Confirm Browserless disclosure. Deliberately simulate an expired listing; show its specific error and retain the previous Workday image.
- [ ] Install and accept the updated physical-iPhone preview against the deployed Browserless backend.
- [ ] After merge/deployment, verify one app-initiated capture against the authenticated production route and reconcile the provider usage receipt. The isolated Heroku worker checks above do not replace this release check.
- [ ] Exercise the changed capture messages and retained image on Android; an export alone is not interaction evidence.
- [ ] Complete the inherited VoiceOver/TalkBack, large-text/small-device, background/relaunch/account-switch and 15-minute signed-access renewal checks.

Backend regression: 223 tests on macOS with real disposable PostgreSQL (one Linux-only check skipped). Mobile: 76 tests, typecheck/lint. Root/provider: 8 tests. Browser security: 18 checks. iOS/Android/web exports passed. The gate remains `0` on production v144 until the reviewed replacement is merged and deployed. Dependency exceptions and their November 5 review are unchanged.

The [updated iPhone preview](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/254badeb-dd80-4afa-8406-7c7f7645f5ba) finished October 22 at 15:09:06 UTC from `209bd6c` (subsequent changes are backend/CI/docs only); IPA HEAD returned 200. Browserless usage reconciled at 28/1,000 units, leaving 972; no paid upgrade, proxy or CAPTCHA use. Temporary key material and preview/test processes were cleaned up after validation.

## Production Browserless acceptance and Gem/viewer follow-up — October 22

PR #117 merged as `60d36d9` and was deployed with the user's approval: code v145, existing Browserless key v146, capture enabled v147. Migration remains `e1f2a3b4c5d6`. An authenticated production-route capture completed in 11.01 seconds (1280 × 9090), with one capture, signed HTTP 200 and unsigned HTTP 403. The labelled validation job was archived. The user subsequently confirmed screenshot capture working on their physical iPhone; Gem was unsupported in that release. This supersedes the historical disabled-gate statements above, without implying the broader unchecked physical/native flows passed.

The next slice adds constrained Gem support and an in-app fullscreen viewer. See [implementation, live samples and acceptance checklist](jobwizard-gem-viewer.md). Job-detail extraction is deferred. Existing stored screenshots remain usable; the viewer needs the new mobile preview and Gem capture needs the merged backend deployment. No new credential or storage permission is required.


October 22 deployment follow-up: the user confirmed the PR #118 preview looks good and physical-iPhone pinch/drag works. v148 deployed the merge, but the first Gem production image was clipped and its verification receipt was corrected to failed. The explicit-bounds capture and pre-upload dimension check are documented in [the Gem release evidence](jobwizard-gem-viewer.md#production-deployment-and-capture-width-follow-up). Other unchecked device/lifecycle/accessibility items remain open.

## October 22: listing extraction follow-up

Use the [extraction smoke/rollout checklist](jobwizard-extraction.md#smoke-and-rollout-checklist) for optional title/company/bullet suggestions before save and on existing jobs. Accepted details persist separately from screenshots. Prior screenshot/storage/physical-device follow-ups above remain open unless explicitly recorded as completed.


## October 25: compact index review (local development clients)

The index now has search/Add icons beside its heading, a short count/privacy caption, and inline native filter/sort menus with the selected values visible. Search expands only when requested; Cancel clears it and restores the compact list. See the [research and design decision](jobwizard-modernization-plan.md#index-layout-refinement--october-25-2026).

- iPhone 18 Pro / iOS 27: verified Active/Newest overview (291 active synthetic jobs), native sort selection to Company A–Z, Archived filter (30), composed Cedar search (7), no-matching state, Cancel clearing/collapsing to 30, Add form navigation, and retained filter/sort on return. Accessibility exposes named search/Add buttons and filter/sort popup controls with their selected values. This is not a full VoiceOver audit.
- Pixel 10 / Android API 36.1: verified menu checkmarks, Company A–Z ordering, Archived filter (30), Cedar search (7), and Cancel. Native validation caught and corrected the SVG data-URL encoding required by Android; all four icons render. Existing save confirmation remains visible below the controls.
- TypeScript, ESLint, 94 existing mobile tests, and iOS/Android/web production exports passed. The final icon/layout adjustments were checked with native rendering and another typecheck/lint/export pass. No backend behavior changed and no paid provider was used.
- Evidence: [iPhone overview](assets/jobwizard/index-iphone.png), [native sort menu](assets/jobwizard/index-sort-iphone.png), [combined search/filter](assets/jobwizard/index-search-iphone.png), [Android](assets/jobwizard/index-android.png). All listings in this evidence are disposable fixture data.

**No new EAS build was started.** The existing preview `6424dc30-5b56-4de8-bef7-9c1c58abd1d4` predates these index changes. The user requested screenshot approval before another cloud preview; continue local iteration until that approval. Preserve the original Justworks physical-iPhone acceptance, manual-save-after-rejection check, full VoiceOver/TalkBack, larger text/smaller-device/software-keyboard combinations, and earlier lifecycle/expiry checks. Old certificate D6D52 revocation remains user-operated after replacement installation. Sentry stays in separate PR #123; dependency exceptions still require the November 5 review.

## October 26: compact form and focused suggestion review

The approved cleanup is implemented separately from PR #122. See [flow, native screenshots and acceptance checklist](jobwizard-review-flow.md). Add/Edit keeps routine fields compact; Review separates comparisons and reversible bullet choices from saving. Optional explanation is disclosed, while real errors and recovery remain visible. Local iPhone and Android checks covered deliberate Apply/Save, retained values and summaries; iPhone checks additionally covered larger text, extraction failure, conflict with an Android edit and recovery of a committed save with a lost response. Production/physical-device and inherited accessibility/lifecycle checks remain open as explicitly listed there. No cloud preview was started.

The user subsequently approved the [combined iPhone preview](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/2a14bf09-edcd-4690-b810-c322f1b5b9c3), which finished October 26 at 17:21:26 UTC from `fd4d990`. The downloaded IPA passed strict/deep signature verification with replacement certificate `FBC7A` and the registered-iPhone profile. Follow the [physical-device checklist and merge order](jobwizard-review-flow.md#physical-iphone-acceptance-and-merge-order): accept on the phone, merge #122 first, then retarget #127 to `main` and confirm its full checks before merging. No backend deployment or certificate change was performed.

## October 27 reliability follow-up

See the [current reliability evidence](validation-status.md#jobwizard-reliability-pass--october-27) for physical Greenhouse acceptance, scheduled cleanup, user-confirmed Apple certificate revocation, iOS lost-save/capture restart recovery, image-access expiry, unresolved-capture account isolation, Android concurrent URL edit, and malformed-URL guidance on both hosts. These scoped checks supersede the corresponding pending notes above; they do not close every combined checklist item. The later [protected-link and account-session pass](validation-status.md#protected-links-and-account-sessions--october-27) records the exact iOS cold-link, delayed refresh/save/capture and Android warm-link cases, plus a fixed cross-account token race. Combined checklist items remain open for untested permutations, committed-save account switching, Android Release/hardware, accessibility and live provider concurrency. Android cold links require a Release artifact because the development launcher failed before routing.

## PR #133 physical preview

[Version 1.0.0 (5)](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/59802c2d-c886-4ac8-aef8-3dae4ae487ad) includes #132 and #133. Follow the [focused device checklist](validation-status.md#pr-133-iphone-preview--october-27); physical acceptance is pending. It does not close the remaining full-matrix items above.
