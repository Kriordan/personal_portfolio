# Jobwizard smoke test

Checklist for the [Jobwizard modernization plan](jobwizard-modernization-plan.md), approved October 21 with immediate saving and optional screenshot capture afterward. Leave an item unchecked unless its entire stated behavior was exercised.

Use the disposable two-account fixture for failures and concurrency. Live acceptance should use a clearly labelled **Jobwizard smoke test** record and a public nonpersonal listing. Do not send a private/tokenized listing to the screenshot provider merely to test the integration. Archive the test record afterward; permanent deletion is outside this slice.

## Browse and details

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

- [ ] Confirm a normal job save does not call ApiLeap/S3. Only the explicit Capture action starts capture, and its explanation identifies that the listing link goes to the screenshot service.
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

- [ ] Record full backend/PostgreSQL, mobile, browser, migration, typecheck/lint, exports, Expo compatibility and audit results. Confirm actual CodeQL findings on PR head/merge references, not only scan-job success.
- [ ] Record implementation source, additive migration head, Heroku release and healthy old/new-client responses. Keep legacy job ownership, IDs, dates and screenshot references intact.
- [ ] Inspect the EAS upload for excluded secrets/local databases and build a fresh internal iPhone preview with the approved signing setup and HTTPS API. Record build ID/link and matched backend release.
- [ ] Install that preview on the physical iPhone and complete a deliberate add/edit/archive/restore flow. Record device/OS, screenshots and exact checked steps; build/download success alone is not acceptance.

## Planning evidence

October 21: all **17 existing Jobwizard API/service tests pass** on the merged baseline. Disposable probes reproduce malformed-input exceptions, acceptance of an unsafe URL scheme, a successful response with a failed screenshot reference, missing explicit cache privacy, and the invalid website form's missing template. These findings establish requirements only; none of the implementation checklist is complete.


## Implementation evidence — October 21

The organizer, additive migration `e1f2a3b4c5d6`, account-scoped mutation receipts, revision checks, and optional durable capture attempts are implemented. New captures use private `j/` object keys and 15-minute signed links. Legacy image references are retained but shown as unavailable until their storage mapping/privacy can be verified. Older previews can save/read jobs but cannot display the new private captures.

Automated validation: **214 backend tests** passed with all PostgreSQL integration tests enabled before the final capture guard checks; Linux CI subsequently passed **215 tests**, including killing a capture child when its parent dies, including migration preservation, duplicate submissions, stale writes, process-death recovery and screenshot failures. **75 mobile tests**, TypeScript, lint, Expo 57 dependency compatibility and iOS/Android/web production exports passed. Existing **18 browser security checks** and **4 root tests** passed. Python audit found no known vulnerabilities; root/mobile audits matched their existing bounded exceptions. The November 5 security review deadline is unchanged.

Observed native evidence: iPhone 18 Pro simulator, iOS 27.0, development client against the disposable fixture (320 jobs for account 1, three for account 2). Company A–Z menu displayed all four labels; mixed whitespace search found the expected record. Add saved immediately and opened details; capture required a separate deliberate confirmation. A tall synthetic screenshot appeared. Archive/restore retained the ID and image. Cancelling the dirty-form discard prompt retained all fields. A competing API edit received a 409 in the open editor; the draft stayed intact, Compare latest showed the competing version, and explicit Keep my draft followed by Save succeeded. Screenshot evidence is retained locally at `/private/tmp/jobwizard-evidence/iphone-detail.png`.

Interactive website fixture: login, form-based save, detail, archive and restore succeeded. The form's POST method was explicitly repaired and regression-tested. The shared service preserves unchanged oversized legacy fields during unrelated edits, including website edits.

The EAS archive inspection contained 487 files and the intended Jobwizard sources, with no local credential files, private keys or databases. No new framework/package dependency or security exception was introduced.

Still open: physical preview installation; Android interactions (the emulator is running but Android Studio did not expose it for UI automation, and project sync reported a local toolchain error); complete VoiceOver/TalkBack, smaller devices, large text/software keyboard, dark mode, cold protected links, native relaunch/account-switch and 15-minute image renewal. These are not implied by unit tests, exports or build success. All inherited feature checklists remain open where previously unverified.

Live storage configuration is explicitly approved for IAM user `portfolio-heroku-prod`, bucket `portfolio-wishlist-prod` in `us-west-2`, `j/` only. The exact additive policy is [jobwizard-storage-policy.json](security/jobwizard-storage-policy.json). The policy was applied and Heroku v141 configured the bucket/region. All four Block Public Access flags are enabled. A 2×2 synthetic upload succeeded; unsigned access returned 403, the 15-minute signed link returned 200 with private/no-store. Test object: `j/a98908141c214dd79286663a9a46fcf2.png` (retained; application permissions intentionally exclude deletion). Two deliberate `https://example.com` capture attempts failed; the diagnostic attempt confirmed HTTP 500 and a non-image response from ApiLeap. No capture object was published. `JOBWIZARD_CAPTURE_ENABLED` must be `1` only after a successful provider readiness check; the production setting remains disabled. Do not substitute another provider or reuse credentials at another service without approval. Initial target DNS is checked for public addresses; Flask only calls the fixed ApiLeap endpoint. Provider-internal redirect/DNS behavior is outside this application's verification and must not be represented as a complete target-isolation guarantee.

Additional iPhone check: a saved edit deliberately returned a failed response, and receipt reads were temporarily unavailable. The app retained the pending operation and draft. Restoring receipt reads recovered the saved job automatically without another write: 325 fixture jobs and 10 receipts both before and after recovery.

The completed preliminary iPhone build `fb74be7d-900d-41bd-8cda-d877d278cf4d` (source `bc92118`, 17:46:29 UTC, IPA HEAD 200) will be replaced to include clearer capture-unavailable wording. Do not use it as the final release reference.
