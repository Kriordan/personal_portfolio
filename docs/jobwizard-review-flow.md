# Jobwizard form and suggestion review — October 26, 2026

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
- [ ] User approval of these simulator screenshots before any new EAS preview.
- [ ] Physical iPhone: paste the actual Justworks listing, Suggest details, review/edit/deselect, Apply and Save; also manually save after a definitive rejected extraction. Fixture use of the URL does not validate the production listing.
- [ ] Complete Android hardware Back/gesture and text-entry checks. The integrated emulator did not forward host keyboard/back actions reliably; touch navigation, selection and save checks above succeeded.
- [ ] Complete VoiceOver/TalkBack focus order/announcements, smallest supported devices, maximum accessibility text sizes, software keyboard and dark-mode combinations.
- [ ] Preserve prior offline/background/relaunch/account-switch and signed-image expiry checks in the linked checklists; this change does not close them.

No new EAS/cloud build, deployment, OTA update or signing change was performed. The earlier preview `6424dc30-5b56-4de8-bef7-9c1c58abd1d4` predates the index and this form cleanup. Apple certificate D6D52 revocation remains user-operated after replacement installation. Sentry remains separate PR #123. Dependency exceptions and their November 5 review are unchanged.

Related: [Jobwizard smoke test](jobwizard-smoke-test.md), [extraction checklist](jobwizard-extraction.md), [mobile UI validation](mobile-ui-validation.md).
