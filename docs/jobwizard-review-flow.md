# Jobwizard form and suggestion review — October 26, 2026

**Current status:** the user accepted this form preview and it was merged before Sentry PR #123. The [validation ledger](validation-status.md) records October 27 recovery checks and remaining work; historical test counts below retain their original scope.

This mobile-only follow-up builds on PR #122's recovery, detail actions and compact index. It keeps Expo 57, Expo Router, @expo/ui, TanStack Query and the existing Flask API. No migration, provider request format, production configuration or dependency changes are needed.

## Implemented flow

- Add/Edit opens a compact form: Listing URL with Suggest details and an information button, Job title, Company, and a short details card when a summary exists. Cancel and Save remain in the toolbar. The repeated introductory paragraph is removed.
- Ready suggestions open a focused Review screen within the existing form. Edit remains a single native sheet; Help and Review do not stack another modal. Back returns to the draft without applying suggestions.
- Job title and Company have distinct section headings. Existing nonempty text defaults to Keep mine; empty fields default to Use listing. Equal values show Matches your draft. Choices survive Back, but a subsequent manual edit resets the replacement choice for that field.
- Existing details default to Keep current details. Replace with suggestions exposes reversible checkbox rows and a selected count. Each row has inline Source and Edit actions. Editing retains the original source quote and its provenance notice. Deselecting all cannot erase an existing summary; a new job may skip all suggested bullets.
- Apply to draft is separate from Save. The form shows the draft detail count; View details allows inspecting/revisiting or discarding selected bullets. Native input values are read synchronously before comparison, extraction and saving.
- General provider/privacy/accuracy explanation lives under About suggestions. Partial/conflicting results, actual errors, stale URL/revision warnings and durable-operation recovery stay visible. Screenshot help is similarly disclosed beside its heading; the deliberate capture confirmation remains.
- Native inputs use the existing platform-specific width helper. Android rejects percentage widths in these native modifiers; this was caught and fixed during emulator validation.

## Local validation

All jobs, summaries and errors below came from `scripts/jobwizard-preview-fixture.py`, a disposable local SQLite fixture with mocked Browserless/OpenAI. No production jobs or paid provider calls were used.

- iPhone 18 Pro / iOS 27 development client: Add → Suggest → Review → Apply → Save succeeded using the reported Justworks URL as fixture input. A manually entered title remained selected; the empty company accepted Cedar Labs. Editing a bullet, toggling Source, returning to the form, reopening Review and deselecting one of four bullets retained the correct text/selection. The saved job contained the three selected details with edited provenance.
- Existing-job review defaulted to Keep current details and kept an identical company compact. Selecting Replace and deselecting every bullet showed the explicit selection error. Applying Keep current retained the three saved details.
- A simulated extraction timeout remained visible. Cancelling the dirty-form discard prompt retained the manually edited title. Manual Save succeeded and preserved the existing details.
- Larger iPhone text (Device Hub Text Size 7, restored to 3 afterward): form controls wrapped, Review title wrapped without overlap, comparison rows remained readable, and the Apply footer was reachable by scrolling. This is a bounded larger-text check, not all accessibility sizes or devices.
- Pixel 10 / Android API 36.1 development client: Add/Edit and Review rendered; an existing job completed Suggest, explicit title replacement, Back/reopen with the selection retained, Apply and Save. Existing summary and source provenance survived. The native input width crash was corrected and the flow retested successfully.
- Cross-device conflict: Android saved a changed title while an older iPhone editor stayed open. The iPhone save was rejected with a visible conflict; Compare latest showed Android's title. Explicit Keep my draft adopted the newer revision while retaining iPhone text.
- Lost-response recovery: the next iPhone save committed while its response and receipt reads failed. Recovery controls and the original draft remained visible. Restoring receipt reads automatically opened the confirmed saved job. Fixture counts stayed at 325 jobs / 9 mutation receipts before and after recovery, proving no duplicate write during recovery.

Automated validation: TypeScript, ESLint, all 97 mobile tests (including selection validation, Unicode boundaries and manual-edit protection), dependency compatibility, and iOS/Android/web production exports. Session tests retain URL/revision binding, frozen request IDs, lost-response recovery, account isolation and no automatic paid retries. Native screenshots complement these checks; exports are not device acceptance.

## Screenshots

- [Compact Add draft](assets/jobwizard-review/draft-iphone.png)
- [iPhone Review](assets/jobwizard-review/review-iphone.png)
- [Compact Edit](assets/jobwizard-review/edit-iphone.png)
- [Visible extraction failure](assets/jobwizard-review/failure-iphone.png)
- [Larger iPhone text](assets/jobwizard-review/large-text-iphone.png)
- [Android Edit](assets/jobwizard-review/edit-android.png)
- [Android Review](assets/jobwizard-review/review-android.png)

## Acceptance checklist

- [x] Inspect the short form, section hierarchy, inline actions and optional help on iOS and Android.
- [x] Preserve manual title/company values, source text, edited bullets and selections through internal Back/help navigation.
- [x] Verify selected bullets persist only after Apply followed by Save; keeping an existing summary does not replace it.
- [x] Verify visible extraction failure, dirty-draft cancellation, manual saving, revision conflict and lost-response recovery on the local iPhone fixture.
- [x] Check a larger iPhone text setting and reach the bottom of Review without clipped actions.
- [x] User approved an iPhone device preview after reviewing the simulator screenshots on October 26.
- [x] User installed preview `2a14bf09`, confirmed it looks good on the physical iPhone, and explicitly approved merging on October 26. This records device/UI acceptance; the individual failure/accessibility/lifecycle scenarios below remain open unless separately verified.
- [ ] Physical iPhone: paste the actual Justworks listing, Suggest details, review/edit/deselect, Apply and Save; also manually save after a definitive rejected extraction. Fixture use of the URL does not validate the production listing.
- [ ] Complete Android hardware Back/gesture and text-entry checks. The integrated emulator did not forward host keyboard/back actions reliably; touch navigation, selection and save checks above succeeded.
- [ ] Complete VoiceOver/TalkBack focus order/announcements, smallest supported devices, maximum accessibility text sizes, software keyboard and dark-mode combinations.
- [ ] Preserve prior offline/background/relaunch/account-switch and signed-image expiry checks in the linked checklists; this change does not close them.

At the local-review stage, no new EAS/cloud build, deployment, OTA update or signing change was performed. The earlier preview `6424dc30-5b56-4de8-bef7-9c1c58abd1d4` predates the index and this form cleanup. Apple certificate D6D52 revocation remains user-operated after replacement installation. Sentry remains separate PR #123. Dependency exceptions and their November 5 review are unchanged.

## Physical-iPhone acceptance and merge order

The user approved a preview build on October 26. It includes both PR #122 and this follow-up, PR #127, and uses the deployed Heroku API. Use a clearly labelled test job because saves affect the live account.

The [iPhone preview `2a14bf09`](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/2a14bf09-edcd-4690-b810-c322f1b5b9c3) finished October 26 at **17:21:26 UTC** from application commit `fd4d990e56747d6b8e17146ab7c208db7897edf3` (version 1.0.0/build 1). The downloaded IPA passes strict/deep signature verification, uses replacement certificate `FBC7A` in both its signature and embedded profile, includes the registered iPhone, and disables debugging. Its JavaScript bundle contains the production API URL and excludes the local fixture URL. IPA SHA-256: `bb70ea406ef27c22febcf8dbc2c525d9da0e459ac62c3a5a342ef5357bcf44fd`. The inspected upload matches the intended source and excludes local environment/credential files, dependencies, databases and generated native projects. EAS used frozen existing credentials without Apple sign-in or signing changes. Successful build and signature checks do not establish physical-device acceptance.

1. Verify the compact index: expand/cancel search, select filter and sort, and open Add job.
2. Paste the reported Justworks listing. Confirm Suggest details starts, opens Review when ready, and shows a useful error if extraction fails. Manual saving must remain possible after a definitive rejection.
3. Enter a manual title before Review. Check Keep mine, Source, editing/deselecting a bullet, Back/reopen, and Apply to draft. Save and reopen the job to verify the selected values/details persisted.
4. Edit the saved job. Verify existing values/details default to Keep, keyboard controls remain reachable, and Cancel asks before discarding a changed draft. Inspect the detail actions and full screenshot viewer.
5. Repeat the main form/review with a larger text setting; check visible failures/recovery rather than retrying an uncertain operation as a new request.

On October 26, the user confirmed the preview looks good on the physical device and authorized merging. PR #122 merged as `152a0a74cb1df5b501465ca7d91651be9cb4b495`; #127 was then retargeted to `main`, with its diff verified to contain only this follow-up. Merge #127 after its full CI and CodeQL checks pass. The three checks on the earlier stacked PR alone do not establish the post-retarget security-check result. These mobile changes do not require a Flask deployment. Broader unchecked validation and security follow-ups above remain open.

Related: [Jobwizard smoke test](jobwizard-smoke-test.md), [extraction checklist](jobwizard-extraction.md), [mobile UI validation](mobile-ui-validation.md).
