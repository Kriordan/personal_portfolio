# Mobile UI first slice — updated October 1, 2026

## Delivered

The SDK 57 compatibility update and the Home / Tools / Me shell plus Grocery slice are implemented. The architecture remains Expo Router, TanStack Query, the existing typed API clients, and Flask domain services. Website item/category form handlers now broadcast the existing Socket.IO events after saving. Endpoint URLs, response schemas, database schema, and Socket.IO payloads are unchanged.

- Expo 57.0.25, React Native 0.86.3, matching Expo packages, Reanimated 4.5.1 and Worklets 0.10.1; Node minimum 22.13.
- `expo-build-properties` enables the scene lifecycle required by Xcode 27. Native projects remain generated and ignored.
- SDK 57 native tabs are isolated in one layout; feature flows stay in the standard root stack with their existing URLs and centralized authentication protection.
- Home uses real owned/shared list counts and links. Tools lists the five existing services and filters their names locally. Me displays the account and signs out.
- Grocery has owned/shared sections, native create/category/item forms, virtualized item sections, accessible completion controls, and all three completed-item display modes.
- Native focus/connectivity feeds TanStack Query. Profile data participates in query recovery after network failure. Room status becomes connected only after a successful join acknowledgement; rejoining invalidates stale list data.
- REST responses remain authoritative. Submission locks prevent repeated taps before rerender; known-offline mutations fail immediately and are not queued. Toggle mutations never retry automatically.
- Preview and production EAS builds reject an absent, non-HTTPS, or loopback API URL. The preview profile explicitly uses the deployed Heroku API; production still requires its EAS environment configuration.

Wishlist, Library, Learning, and Jobwizard remain reachable and use centralized route protection. Their individual screen redesigns are the next migration stages after reviewing this first slice and completing its remaining native checks. Global search, new mobile domains, sharing extensions, offline editing, and OTA updates are outside this slice.

## Automated verification

Run from the repository root:

```sh
npm run typecheck --prefix mobile
npm run lint --prefix mobile
npm test --prefix mobile
poetry run python -m unittest discover -s tests
```

| Check | Result |
| --- | --- |
| Strict TypeScript | Passed |
| Expo ESLint | Passed, no warnings |
| Mobile regression tests | 13 passed |
| Backend unittest suite | 96 passed |
| `npx expo install --check` in `mobile/` | Dependencies compatible |
| iOS development-client build with Xcode 27 | Succeeded, zero errors |
| EAS iPhone preview against the live API | Succeeded September 30; user confirmed physical installation and a created list visible on the website |
| Android ARM64 development-client build | Succeeded on September 29; installed and exercised on a 16 KB-page emulator |
| Web export | Succeeded, 22 static routes |
| Android JavaScript/Hermes export | Succeeded; this is not an Android native build |

Mobile tests exercise actual TanStack Query cache and mutation behavior: duplicate/echoed events, website string item IDs, stale in-flight fetches, reconnect invalidation (including live events during the recovery fetch), scoped settings/reorder invalidation, all completion modes, logout cache clearing, offline queuing prevention, lost-response retry prevention, and the preview/production URL guard. The Node runner prints a module-type inference warning when loading TypeScript; tests pass without changing the Expo package's module format.

Backend coverage now also checks shared-list reads and mutations, owner-only sharing/settings, cross-list IDs, revoked membership, display settings visible to a shared member, and website-session/JWT socket interoperability with outsider rejection.

## iOS native checks

Tested in the rebuilt development client on an iPhone 18 Pro simulator running iOS 27. The generated application contains the scene manifest and `EXExpoAppSceneDelegate` configuration.

Interactive testing used this repository's real Flask app against an isolated temporary SQLite database and disposable accounts. It did not modify the normal development database or invoke external integrations. Access tokens in that fixture expired after ten seconds to exercise refresh-and-retry.

Verified:

- Cold development-client launch, restored session, login, expired-token refresh, sign-out to the protected login screen, and account display.
- Home counts and list links; Tools filtering; create-list navigation and back navigation.
- Native category/item sheets, keyboard submission, item quantity, completion updates, and connected/disconnected indicators.
- Phone-to-website additions and two-way completion updates. Website-to-phone additions were not adequately isolated from refetches in the original check; see the September 30 correction below.
- A failed category submission retains its text; restoring the API and retrying saves it. Rejoining refreshes missed state.
- Light/dark rendering and the largest Dynamic Type setting. Heading scale is capped at 2×; body text and native controls follow the system size. Runtime size changes restore normal layout without a reload. Error recovery screens scroll at large sizes.
- Item checkbox roles and checked/busy states in the native accessibility tree.
- Warm custom-scheme links to `/lists/1` and a Back destination in the shell.

Native testing found and fixed missing sheet height at the React Native/Expo UI boundary, final-character loss during keyboard submission, string item IDs emitted by the website, stale text measurements after Dynamic Type changes, unreadable raw networking errors, and profile data that did not recover after a failed initial fetch.

The September 29 regression pass also reproduced a visible field value getting ahead of its React change event during rapid entry. Login and Grocery forms now keep Expo UI observable text state and read its current value at submission time, including button submission and non-final fields. Rapid email/password entry now signs in successfully; item name, quantity, and notes were saved intact, and reopening the item sheet showed cleared fields. These checks also verified the iOS native-width modifiers introduced during Android testing. A final bundle reload verified restored authentication, Home rendering, sign-out, secure password entry, and successful login after the Android password component and shared screen-layout changes.

## Android native checks — September 29, 2026

Android Studio setup is complete. The local build uses Java 17, Gradle 9.3.1, Android platform 36, Build Tools 36.0.0, and NDK 27.1.12297006. Gradle downloaded the missing build components using the SDK licenses already accepted during setup.

The ARM64 development APK built successfully in 8 minutes 23 seconds (455 tasks). It is generated at `mobile/android/app/build/outputs/apk/debug/app-debug.apk` and remains ignored by Git. No application-source changes were needed for the Android build. There were non-fatal dependency/Gradle deprecation warnings.

A Pixel 10 emulator with an Android 16 / API 36.1 ARM64 image completed installation and booted. `getconf PAGE_SIZE` reported 16384. The development APK installed successfully.

Actual startup exposed a native crash: Expo UI accepted `width: '100%'` in TypeScript but Android's native modifier required a numeric dimension. Native controls now use platform-specific width modifiers (`fillMaxWidth` on Android and an infinite maximum-width frame on iOS), while web retains percentage widths. Android subsequently rendered the login screen without that crash. React Native container widths were left intact.

Docking Running Devices in Android Studio resolved the emulator-control problem. Interactive testing used the same isolated Flask fixture described above, including ten-second access tokens and the existing website as a second client.

Verified:

- Login, invalid-credential feedback, restored session, expired-token refresh during reads and writes, account display, and sign-out to the protected login screen.
- Home counts and real list links; Tools name filtering; owned/shared Grocery sections; create-list navigation and normal Back navigation.
- Create category, keyboard submission, native item sheet and category picker, and exact preservation of item name, quantity, and notes.
- Two-way completion changes and phone-to-website additions, with connected/disconnected feedback. The original claim of two-way live additions was too broad; see the September 30 correction below.
- Returning from the background refetches changes made on the website. Disabling emulator connectivity produces an immediate failed category submission without losing its draft. Reconnecting and retrying saves the draft and restores items added while disconnected.
- Category and global completed-item sections, with the global setting loaded after reopening the list.
- Light/dark rendering, maximum Android font size, collection scrolling, and reachable sheet actions. Normal text size, light appearance, and connectivity were restored afterward.
- A warm custom-scheme link to the shared `/lists/2` route and Back navigation to the previous list.
- Login with the docked software keyboard: the form and Sign in button remain above the keyboard, and button submission succeeds.

The keyboard pass exposed two additional issues. SDK 57's universal `secureTextEntry` masks text without requesting a password keyboard on Android. The Android password field now uses Expo UI's Compose `TextField` with a password keyboard, disabled autocorrection, and password autofill semantics; the software keyboard no longer displays text suggestions. Android screen compositions also use `KeyboardAvoidingView` to keep the login controls above the keyboard. Both fixes were verified in the running native app after reloading the bundle.

An existing website limitation remains: its settings form saves `completed_display_mode` without broadcasting `settings_updated`. An already-open mobile list therefore learns that website setting change on a subsequent fetch (reopening the list was verified), rather than immediately. The mobile event handler and cache regression coverage support `settings_updated` when emitted. No Flask or socket-protocol change was made for this limitation.

## iPhone preview — September 30, 2026

The user selected a standalone preview against the existing live backend. The `preview` profile embeds `https://keithriordan.herokuapp.com`; its EAS environment had no variables, so the public API origin is explicitly recorded in `eas.json`. An unauthenticated request to `/api/v1/auth/me` returned the expected JSON 401 over HTTPS. This confirms reachability and the authentication route, not authenticated production feature behavior.

TypeScript, lint, all 10 mobile tests, and `git diff --check` passed after extending the API URL guard to previews. The inspected EAS upload archive included the uncommitted redesign and excluded local environment files, credentials, databases, dependencies, and generated native projects. EAS metadata records the previous Git HEAD because the changes are not yet committed; the uploaded source includes the current working tree.

[iOS preview build `2c5db3b7-ac92-4a66-befe-cd7af0186eba`](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/2c5db3b7-ac92-4a66-befe-cd7af0186eba) finished successfully at 15:50 UTC using existing remote signing credentials and the provisioning profile containing the registered iPhone. The native build took approximately five minutes after queueing. EAS confirms a physical-device, internal-distribution preview, and the generated IPA returned HTTP 200. No backend deployment, App Store submission, TestFlight submission, or OTA update was performed.

The user subsequently confirmed successful installation on their physical iPhone, creation of a list, and that the same list appears in the deployed website. This verifies the initial authenticated create/read flow against shared live storage. It does not yet verify live item events, reconnect behavior, or the remaining physical-device checks. The user also reported a positive initial visual review.

That check exposed a missing website navigation link: `/lists` already exists in production, but the authenticated header did not link to it. A Grocery link has been added locally and its signed-in, signed-out, overview, and detail rendering checked. The navigation fix is not yet deployed; the direct Lists URL works now.

## PR integration — September 30, 2026

The branch incorporates `main` through `01a8035`, preserving its dependency-security changes, install-script policy, UUID override, dependency compatibility check, and existing development-build documentation. The mobile lockfile was regenerated from that security-fixed baseline while retaining every direct dependency version used by the installed iPhone preview. After installing the merged mobile and Python lockfiles, TypeScript, lint, all 10 mobile tests, the dependency compatibility checks, all 92 backend tests, and a production iOS JavaScript/Hermes export passed. Local Expo dependency validation also passed in offline mode.

The existing iPhone preview predates this merge's transitive dependency updates. It remains the UI smoke-test build; a fresh native preview should be produced before promoting the merged dependency tree. A fresh npm audit reports the previously documented decoder issue (three moderate entries through its parents) and newer brace-expansion advisories (one high entry). The affected brace-expansion versions match `main`; the UI change does not resolve those newly reported advisories.

## Remaining release checks

### Physical-device realtime bug and correction — September 30

Keith confirmed phone-to-website additions and two-way completion updates, but website-created items required pull-to-refresh on the iPhone, including after returning from the background. The website's item/category forms saved successfully without broadcasting any creation event. The original interoperability tests emitted socket events directly and missed this real form path. The native checks above therefore overstated website-to-phone live creation coverage.

The website now emits `item_added` and `category_added` after persistence, using the same serializers as the REST responses. Broadcast failures are logged without reporting an already-saved item as a failed save. Grocery detail and overview queries refetch on foreground/network recovery even within the 30-second freshness window and independently of a socket rejoin.

New regression tests first reproduced the missing website broadcasts, then passed after the fix. They exercise real owner/shared-member form submissions to a JWT room listener, exact REST/event payload equality, room isolation, rejected forms, and transport failure after persistence. Mobile tests cover immediate item reconciliation, a missing category, and recovery of fresh data without a socket callback. TypeScript, lint, all 13 mobile tests, all 96 backend tests, and `git diff --check` pass.

The running iOS 27 simulator received website-created items (including quantity/notes) and categories without refreshing. A separate item created through the local REST API without a socket event appeared automatically when the app returned from the Home Screen; logs confirm foreground reads and expired-token recovery. These checks used the isolated fixture, not production. The under-30-second recovery boundary is covered by the automated QueryObserver tests.

The September 30 preview contains the reported foreground-recovery bug. Retest on the physical iPhone with the replacement preview and website release v123 described below. Android's earlier coverage remains valid for its stated paths; this follow-up has not yet been rerun on Android.

The [October 1 replacement iPhone preview](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/cc6436f8-861c-4df2-be59-e96d3207dc17) built successfully from commit `53c00ca7e0decb66c037ce0120a88fa5ac4b5143`, finishing at 12:06:50 UTC. It includes the foreground recovery fix and the merged dependency updates. EAS reports a finished internal-distribution physical-device build with an installable artifact, signed using the existing registered-iPhone profile. Installation and physical-device retesting are pending.

### Website deployment — October 1

The user's initial `git push heroku mobile-redesign` uploaded a feature branch, which Heroku explicitly skipped building. Deploying with `git push heroku mobile-redesign:main` built commit `9f69b1c0` successfully and released **v123** at 13:43:40 UTC. This includes the website creation broadcasts, Grocery navigation link, and merged backend dependency fixes. There are no database migrations relative to the previous live release v122 (`ae68ac24`).

After release, Heroku reports `web.1` up; the website returns HTTP 200, `/api/v1/auth/me` returns the expected JSON 401 without credentials, and `/lists` redirects unauthenticated requests with HTTP 302. These verify startup and routing, not an authenticated production sync test. The physical iPhone retest remains the next check. The GitHub PR remains open for those results.

### Outstanding checks

Use the [iPhone smoke-test checklist](iphone-smoke-test.md) for the physical-device pass. PR screenshots were captured from the iOS simulator using the isolated fixture: [Home](screenshots/mobile-redesign/ios-home.png) and [Grocery detail](screenshots/mobile-redesign/ios-grocery.png). The floating gear belongs to the development client and is absent from the standalone preview.

1. **Full screen-reader and physical-device pass.** Accessibility-tree inspection is not a complete VoiceOver/TalkBack audit. Check focus order, announcements, combined large-text/software-keyboard form scrolling, smaller devices, and Android gesture/three-button navigation insets. Manual Android pull-to-refresh still needs an unambiguous verification.
2. **Preview/release cold deep links.** A terminated development client intercepts plain custom-scheme links with its launcher. Warm links and normal cold development-client startup passed; a preview binary must verify cold links directly into a protected feature, including when signed out.
3. **Further live-API checks and production configuration.** Physical iPhone installation and shared list persistence are user-confirmed. Verify live item changes in both directions and reconnect recovery on the physical device. An Android preview and the production EAS API environment remain outstanding.
4. **Continue staged migration.** Once the native-platform gate passes, migrate Wishlist, Library, Learning, then Jobwizard while preserving their existing behavior.

The iOS simulator's original light appearance and standard text size were restored after the September 28 checks. The September 29 follow-up used the same isolated fixture approach. The installed development clients and generated native projects remain available for local development. At the September 29 handoff, both simulators were signed into the disposable account on Home; the isolated API (port 5057), Android Metro (8088), and iOS Metro (8089) were left running for review. The website test session was signed out and its temporary tab closed. Those demo services use temporary data, not the normal development database; the standalone iPhone preview instead uses the live backend.

## Grocery editing follow-up — October 3, 2026

Keith reported successful retesting and merged PR #89, then found that the first slice omitted edit/delete controls. This follow-up adds native item/category/list editing and confirmed deletion, plus advisory duplicate warnings when creating or renaming items. Item edits preserve completion and can move items between categories. Whole-list changes are owner-only; shared members may change items/categories. Category/list deletion removes their contents in the same database transaction. There is no database schema migration or new dependency.

The new PATCH/DELETE endpoints authorize against persisted ownership/sharing and validate complete patches before mutation. Server-issued events after commit trigger authoritative reads on mobile and reload the website's current list; a deleted list redirects the website to its overview. The website receives these changes but does not gain editing or duplicate-warning controls in this change. Mutations do not retry or queue offline, and failed forms retain their input.

All 104 backend tests and 18 mobile tests passed. New regression coverage exercises permission and cross-list boundaries, foreign-key-enforced deletion cascades, invalid-patch atomicity, completion preservation, authorized socket rooms, persisted success despite transport failure, cache reconciliation, and duplicate suggestions. TypeScript, ESLint, and an Android production JavaScript/Hermes export passed. An Android export verifies bundling, not native interaction behavior.

On the iPhone 18 Pro / iOS 27 simulator, a disposable SQLite fixture passed: editing name/quantity/notes; singular/plural duplicate warning and Add anyway; canceling deletion; deleting only the extra item; moving a completed item while retaining checked state; renaming/deleting a nonempty category; and renaming/deleting an owned list. The existing Flask website reflected each change without manual refresh. The shared list did not expose whole-list Edit. No production user data was changed.

The [Grocery editing smoke test](grocery-editing-smoke-test.md) covers the physical iPhone pass. The October 1 installed preview cannot expose these new controls; use the October 3 preview and backend release below. Android interaction checks for the new sheets and a full VoiceOver/TalkBack pass remain outstanding.

The [October 3 iPhone preview](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/5acf57e2-adcf-43ec-b48f-e22fb7894772) finished successfully at 16:50:22 UTC from `0e603eabba8924b2c9f9d026b332454f3cf14b52`. EAS reports a physical-device internal-distribution build with an IPA artifact, using the existing registered-iPhone signing profile. [PR #94](https://github.com/Kriordan/personal_portfolio/pull/94) is open. Its CodeQL jobs completed successfully but reported three findings; see the October 4 correction below. The temporary local API and Metro used for simulator testing were stopped afterward.

### Grocery editing backend deployment — October 3

At Keith's request, `git push heroku grocery-editing:main` deployed commit `7f777992` as **Heroku v124** at 18:08:23 UTC, replacing v123 (`9f69b1c0`). There are no migration-file changes relative to v123. The existing startup command runs `flask db upgrade`; the new process's logs show Alembic initialization with no revision upgrade, followed by successful Flask startup.

Heroku reports v124 current/succeeded and `web.1` up. Read-only HTTP checks returned 200 for the website, JSON 401 for unauthenticated `/api/v1/auth/me`, and 302 for unauthenticated `/lists`. OPTIONS requests to list, category, and item routes all returned 200 and advertised PATCH and DELETE. These checks establish startup and route availability; no authenticated production mutation was performed. The October 3 iPhone preview is now ready for Keith's live smoke test. Reload the website once to load the new edit/delete event listeners before checking synchronization.

### Item interactions follow-up — October 3

At Keith's request, item rows now have separate sibling touch targets: the checkbox toggles completion; the name, quantity, notes, and remaining row body open item editing. The checkbox has a 60-point-wide target with a minimum height of 64 points. Category and owned-list Edit links are replaced by 48-point three-dot buttons that open the existing native rename/delete sheets. Each control keeps an explicit accessibility label and hint; the checkbox also exposes its checked state.

TypeScript, ESLint, an Android production JavaScript/Hermes export, and `git diff --check` passed. On the iPhone 18 Pro / iOS 27 simulator, tapping an item body or notes opened its populated editor without changing completion, and the checkbox checked and unchecked the item without opening the editor. Category and list options opened the correct rename/delete sheets. Accessibility-tree inspection confirmed separate named item actions, checkbox states, and category/list options. These checks used the isolated local fixture; no live data was changed. This presentation-only change requires a replacement preview, with no further backend deployment or migration.

The [replacement iPhone preview with the updated tap targets](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/0b07f387-1894-4cd8-a9f6-dc9e96a9415b) finished successfully at 00:02:33 UTC on October 4 (October 3 evening in New York), from `0ded1725e2c90d6df5124ad4e4990650110e36f6`. EAS reports an installable physical-device preview artifact. It uses the existing Heroku v124 API. PR #94's CodeQL jobs completed with the three findings described below, and the local fixture/Metro servers were stopped after testing. Physical-device verification of the revised interactions remains the next step.

### Grocery API error handling — October 4

GitHub Advanced Security reported three `py/stack-trace-exposure` findings on the list, category, and item edit/delete handlers. The earlier statements that CodeQL "passed" described successful scan jobs, not the absence of findings. Those handlers returned `str(error)` for any `ValueError`, potentially exposing internal exception details.

Expected edit validation now raises a dedicated exception containing a validation code. The API maps only known codes to application-owned messages; unknown codes return a generic validation message. Other `ValueError` failures roll back the transaction, log details on the server, and return a generic JSON 500 response. Neither exception text nor unknown codes are returned to clients. Existing validation messages, authorization, and successful mutation behavior are preserved.

Regression coverage first reproduced the old behavior, then passed after the fix. It covers all six PATCH/DELETE actions, rollback without realtime broadcasts, private diagnostic logging, exact validation messages, and rejection of unexpected exception text/codes. All **107 backend tests** and `git diff --check` passed. No mobile source, dependency, model, or migration files changed for this fix; the existing iPhone preview remains compatible.

Commit `1d63b8a149ae060440312836732506b8a23e083e` was pushed to PR #94. The Python and JavaScript/TypeScript CodeQL analyses completed successfully at approximately 19:37 UTC with **zero findings**. The PR alert query returned no open alerts, and alerts [30](https://github.com/Kriordan/personal_portfolio/security/code-scanning/30), [31](https://github.com/Kriordan/personal_portfolio/security/code-scanning/31), and [32](https://github.com/Kriordan/personal_portfolio/security/code-scanning/32) each report their PR occurrence as **fixed**. None were dismissed.

The same commit was deployed as **Heroku v125** at 20:10:42 UTC, replacing v124. Heroku reports the build succeeded, v125 is current/succeeded, and `web.1` is up. Startup logs show Alembic initialization without any revision upgrade, followed by successful Flask startup. Read-only checks returned website 200, unauthenticated account JSON 401, Lists login redirect 302, and OPTIONS 200 with PATCH/DELETE for all three edit routes. These establish startup and route availability; error handling and rollback were tested locally without injecting failures into live data. The installed iPhone preview requires no replacement for this backend fix.

## Wishlist modernization — October 6, 2026

The implementation starts from the security-fixed `9db7c9c` tree, then advances to its unchanged merge tree `b03b5f5` (PR #98). Expo remains 57.0.25 with the existing React/React Native/Router matrix. Dependency security floors and narrow audit exceptions remain intact.

Wishlist uses virtualized photo rows, newest-first local search, readable detail/photo fallbacks, a New gift route, and a native edit sheet opened by the three-dot button. The same sheet contains confirmed deletion, matching Grocery's interaction. Native text is read synchronously on submission; failed drafts are retained. Forms protect changed drafts and lock pending submissions. Their headings scroll with the fields so large text cannot consume the entire form viewport.

TanStack Query keeps authoritative REST results, cancels obsolete reads, refreshes on focus/foreground/reconnect, and blocks offline queuing or automatic mutation retries. A late mutation cannot restore private data after logout. Lost-response messaging directs users to check saved data before repeating a create; exactly-once creation is not claimed. Wishlist does not add realtime events.

### Photo contract and compatibility

- POST/PUT URLs and response fields stay the same. PUT accepts `remove_image: true` (JSON boolean or multipart `"true"`) to clear the reference; omitted/false preserves it. Upload replaces the photo. Removal plus upload, invalid flags, and removal on POST are rejected.
- Both text fields must contain trimmed text of at most 140 Unicode code points. PUT still accepts omitted text fields. Website validation and safe error rendering use the same service.
- Native selection converts one still photo to JPEG at quality 0.8 with a maximum 2048px edge, without upscaling. Expo 57's default fetch **rejects the old `{uri, name, type}` multipart descriptor**. Native now sends an Expo File; browsers send a Blob/File. A regression executes the installed Expo multipart converter.
- Pillow validates actual JPEG/PNG bytes, rejects animation/corruption, caps input at 5 MiB/25 megapixels, fixes orientation, resizes, and re-encodes without metadata. Wishlist requests have a 6 MiB ceiling. Unique compact S3 keys prevent filename collisions and set the correct content type.
- Missing storage configuration/credentials or upload failure returns a safe explicit error without saving the requested database change. Database failures roll back. Removal and gift deletion work without S3 access.
- Removing/replacing/deleting a photo does **not** delete stored objects. Existing public URLs remain public; upload-success/database-failure can leave an orphan. Object tracking, cleanup, migration of old public media, camera, galleries, and schema migrations are outside this slice. Private delivery for new photos was subsequently approved; see below.
- Native testing also found that `User.gifts` was annotated as a scalar relationship. Adding a second gift attempted to clear an existing gift's owner. It is now a collection, with a multi-gift creation regression. This is an ORM mapping correction, not a database migration.

### Verification completed during implementation

- Full backend suite: **124 tests passed**, including 24 Wishlist tests. Mobile suite: **29 tests passed**. TypeScript, ESLint, Expo dependency compatibility, all-platform JavaScript/Hermes exports, and `git diff --check` passed.
- Python audit: no known vulnerabilities. Root/mobile npm gates passed with the same documented exceptions from the October 5 security review. Root audit-gate/CDN checks and Sass build passed; existing Sass deprecation warnings remain.
- iOS 27 / iPhone 18 Pro development-client build succeeded with zero errors and one existing build-phase warning. Android ARM64 development APK built successfully and installed on the existing emulator. These are native builds, separately from exports.
- On iPhone, the disposable Flask fixture verified login, browse/detail, native text entry, form scrolling, selected JPEG conversion/upload, expired-token refresh with multipart replay, editing, saved-photo removal, canceling discard while preserving text/photo state, canceling deletion, and server-confirmed deletion. All entered punctuation and final characters persisted. The fixture uses temporary storage, not S3 or production data.
- Native testing fixed a too-narrow photo preview at the React Native/Expo UI boundary and replaced overlapping option/edit sheet transitions with one editor.
- [PR #107](https://github.com/Kriordan/personal_portfolio/pull/107) CI passed for implementation commit `84cff34191529c60a72928605bd0bad3b055ca33`: backend, mobile, web, and both CodeQL analyses. The PR-specific CodeQL alert query returned **zero open findings**; this is separate from scan-job success.

### iPhone preview and backend release status

The [Wishlist iPhone preview](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/38115e8e-06bd-4e9e-844e-11cdbaef57c1) finished successfully at **11:59:44 UTC on October 6** from `84cff34191529c60a72928605bd0bad3b055ca33`. EAS reports an internal-distribution physical-device build, and its IPA download returned HTTP 200. It uses the existing registered-iPhone signing profile and `https://keithriordan.herokuapp.com`. No App Store/TestFlight submission or OTA update was made. Installation and the physical-device smoke test remain pending.

With Keith's explicit approval, commit `84cff34191529c60a72928605bd0bad3b055ca33` was deployed to the existing Heroku app `keithriordan` as **v127 at 11:25:22 a.m. EDT on October 6**. It replaces v126, which only added the Wishlist bucket setting to the previous `1d63b8a1` release. Heroku reports v127 current/succeeded and `web.1` up. The normal macOS Git credential helper resumed successfully; no alternative authentication token was extracted.

There are no migration-file changes relative to the previous deployed code. Startup logs show Alembic initialization without a revision upgrade, followed by successful Flask startup. Read-only HTTPS checks returned website 200, unauthenticated account/Wishlist JSON 401, Wishlist/Lists login redirects 302, and OPTIONS 200 with the expected Wishlist POST/PUT/DELETE and Grocery PATCH/DELETE methods. These verify startup and routing, not authenticated production photo behavior; no production gift was created or changed during deployment checks.

The deployment includes the merged backend dependency-security fixes and Pillow 12.3.0. Heroku reported that a newer Python 3.13 patch and stack are available; this deployment retained the approved commit's Python 3.13.11 and Heroku-24 configuration. Runtime upgrades remain separate from this slice.

### Mobile dependency gate and resolution — October 6

The release-documentation update triggered [mobile CI run 37487943035](https://github.com/Kriordan/personal_portfolio/actions/runs/37487943035), which failed its audit gate on [GHSA-pqg4-j6r4-53mv](https://github.com/advisories/GHSA-pqg4-j6r4-53mv). The audit surfaced this `shell-quote` advisory after the earlier successful implementation checks. The mobile lockfile then resolved **1.9.0**; the first patched version is **1.11.0**. Exploitation requires quoting an attacker-controlled line terminator after a comment token and executing the resulting shell command. Dependency-path presence is not proof of exploitability in the shipped app, but the failing security gate blocked promotion. No exception or suppression was added. Backend, web, and both CodeQL scan jobs passed on the documentation revision; the Flask deployment and startup checks above succeeded.

The follow-up security commit updates only the locked **shell-quote** package to **1.12.0**, which includes the fix and fits React DevTools' existing dependency range. Expo and all other locked dependencies remain unchanged. A regression exercises normal argument quoting and rejection of line terminators after comments, without executing shell output. A clean npm install, the exact audit gate (same three reviewed exceptions), dependency compatibility, 30 mobile tests, production iOS/Android/web exports, TypeScript, and ESLint pass locally. See the [security follow-up](security/dependabot-2026-10-05.md#october-6-follow-up-wishlist-pr-mobile-audit). The updated PR checks must pass before merging.

### Remaining acceptance gates

The original pass was interrupted when the Mac locked. The follow-up below verifies iPhone heading layout, native dismissal/canceled-discard restoration, and final post-deletion navigation. Full Android photo/CRUD interactions, actual swipe gestures, larger-text/software-keyboard and VoiceOver/TalkBack passes, smaller-device checks, durable screenshot artifacts, web interaction testing, and cold preview links remain pending.

Use the [Wishlist smoke-test checklist](wishlist-smoke-test.md) with deployed `158a85c` and updated preview `657dcd8c` below. Keith subsequently reported testing the mobile preview and that it looks good, and marked the PR ready for review. This records his preview acceptance; individual checks he did not itemize remain unchecked. The preview predates the shell-quote tooling update. Remaining native/accessibility checks are tracked above; the mobile CI failure is addressed by the security follow-up.

Keith created `portfolio-wishlist-prod` in `us-west-2` with ACLs disabled and Block Public Access enabled, and set `WISHLIST_S3_BUCKET=portfolio-wishlist-prod` in Heroku (verified). He also reported creating the dedicated `portfolio-heroku-prod` IAM user, with no console login and a policy granting `s3:PutObject` only on `arn:aws:s3:::portfolio-wishlist-prod/w/*`. He replaced both Heroku AWS credential values, creating config releases **v128/v129**; **v129** is current/succeeded with the unchanged `84cff34` application code and `web.1` up.

A one-off process using the app's configured credentials called STS and confirmed identity **`portfolio-heroku-prod`**. It then used the actual deployed `upload_image_to_s3` function to upload a generated solid-color 16×16 JPEG successfully. No credential values were read into the conversation, and no gift or user record was read or changed. The synthetic test object is `w/d4431b7a4958492aa3d4efde05d01404.jpg` in `portfolio-wishlist-prod`; it is retained for image-read verification and can be removed through the administrator's S3 console afterward. This confirms the identity and allowed upload, not an exhaustive audit of every attached IAM policy.

The earlier deployed `84cff34` app used direct public image URLs. An unauthenticated GET of the synthetic image followed a redirect from the global S3 hostname to `portfolio-wishlist-prod.s3-us-west-2.amazonaws.com` and returned **403 AccessDenied**. The website and unauthenticated account route still returned 200/401 respectively. No bucket policy or public-access setting was changed. Keith subsequently approved private storage with owner-authorized temporary image links, replacing the original public-URL decision.

### Private photo delivery follow-up

The follow-up implements 15-minute S3 SigV4 links in the existing `image_url` response field for immutable `w/<uuid>.jpg|png` references in the configured bucket. API and website serialization require the gift owner's ID. The database continues storing compact permanent references, with no migration. A signing outage leaves the unsigned private reference available for the photo-unavailable fallback and removal/replacement, without turning a successful save into a reported failure. The website's Wishlist-only 404 handler also preserves the HTTP error status when a gift is missing or belongs to another user.

Uploads and signed downloads specify `private, no-store`; Wishlist API/HTML responses have the same cache directive. The mobile photo component disables image caching; foreground queries renew every ten minutes, with existing focus/reconnect recovery. The website gets fresh links on page reload. Expiry prevents new downloads; it does not erase a displayed/downloaded image, and deletion/removal does not revoke a link already issued. Legacy external/public images retain their prior behavior and are not signed or migrated.

The app uses an explicit regional SigV4 client and the website CSP allows the configured bucket's exact global/regional hosts. Configure **`WISHLIST_S3_REGION=us-west-2`** in production and add **`s3:GetObject`** alongside PutObject on **`arn:aws:s3:::portfolio-wishlist-prod/w/*`** for `portfolio-heroku-prod`. Keep ACLs disabled and Block Public Access enabled. No ListBucket, DeleteObject, PutObjectAcl, public bucket policy, or administrator access is needed.

Local follow-up validation: **133 backend tests and 30 mobile tests pass**, plus TypeScript, ESLint, all-platform exports, and whitespace checks. New tests use real botocore signing with dummy credentials to verify region, 900-second expiry, refreshed signatures, owner boundaries, strict object scope, unchanged stored references, safe signing failure, website rendering, and cache/CSP headers. A TanStack Query timer test verifies renewal while active, no requests while asleep/offline, and recovery on foreground/reconnect. Deployment and live AWS read/expiry checks subsequently passed as recorded below. Physical-device checks and the separate dependency audit gate remain open.

Before the policy update, a read-only production probe confirmed `portfolio-heroku-prod` but both unsigned and signed GETs returned **403**. No records or storage settings were changed by that probe. Backend/web CI and both CodeQL analyses passed for `013b7bd`; mobile CI remains blocked by the previously documented shell-quote advisory. The local browser runner timed out launching Chrome; the equivalent web CI job passed.

The iPhone 18 Pro simulator loaded the updated client against the disposable fixture. Creation and detail display of a synthetic photo succeeded. The new-form and edit headings scroll with their content; native dismissal displayed the discard alert, and Cancel restored the draft title and photo. Remove/Undo and subsequent save preserved the photo and edited title. An open edit form now receives renewed photo links without replacing its draft text baseline. Preview build `cde8257d-bc4d-4289-9ab9-6148a26409ac` was canceled before completion to include that final edit-form correction; it is not the installable deliverable.

Final follow-up source is **`158a85c1bb74a0d4cd13c644d5e3428df47b26f5`**. Backend/web CI and both CodeQL analyses pass on this commit; mobile CI explicitly reports the same shell-quote advisory. Its [updated iPhone preview](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/657dcd8c-bfa4-47ca-9b4f-aed3535cc082) **finished at 12:19:33 p.m. EDT on October 6**. It includes editor renewal and disabled photo caching. Direct HEAD and one-byte GET probes of the EAS artifact URL returned 403 from expo.dev/Cloudflare, so download/installation has not been verified; build success alone is not a passed physical-device test.

The simulator's final deletion check showed a successful expired-token refresh, DELETE 200, return to Wishlist, and exactly the three original fixture gifts. Android's existing ARM64 client loaded the updated bundle, signed out of a stale earlier-fixture session, signed into the current fixture, browsed Wishlist, and rendered the New gift form. The Android form pass was interrupted by an unexpected development-bundle reload during description entry/scrolling; no crash appeared in the sampled error log. Android creation/photo/edit/delete behavior is not yet accepted.

Keith confirmed saving the restricted PutObject/GetObject policy and handling the Git credentials locally. Deployment completed as **Heroku v131 (`158a85c1`) at 12:48:05 p.m. EDT on October 6**. Heroku reports v131 current/succeeded and `web.1` up. `WISHLIST_S3_REGION=us-west-2` was set in v130. No alternate credential-extraction mechanism was used.

The deployed `project.wishlist_storage.photo_url` helper was exercised in a Heroku one-off using the retained synthetic 16×16 JPEG and the actual `portfolio-heroku-prod` credentials. Unsigned regional GET returned **403 AccessDenied**. The normal **900-second** signed link returned **200**, 632 bytes, a valid 16×16 image, **`private, no-store`**, and no redirect. A test-only three-second link first returned 200 and then **403 with “Request has expired”** after six seconds. A newly generated normal link returned **200** again. The shorter TTL was patched only in the isolated probe process; production requests retain the 15-minute lifetime. Signed URLs and credential values were not printed. No gift/user records or S3 objects were created, changed, or deleted by these read checks.

Post-deploy HTTPS checks returned website **200**, unauthenticated account/Wishlist/Grocery API **401**, and Wishlist/Grocery website login redirects **302**. Wishlist API/HTML responses have `private, no-store`; the live CSP permits the exact configured regional image host. This completes deployment and storage-read/expiry verification. It does not replace the authenticated phone/website photo smoke test or an audit of other policies attached to the IAM identity.

`JOBWIZARD_S3_BUCKET` is unset in Heroku, while the generic `S3_BUCKET` is `jobwizard-test`; the current upload code does not read that generic setting. Additional Jobwizard permissions have not been added speculatively. The previous administrator key must only be retired after replacement checks and an inventory of any other consumers.

The local EAS archive inspection included the Wishlist sources and excluded local environment files, credentials, databases, dependencies, and generated native projects. The tracked `.env.example` contains only development URL examples and is included intentionally. The existing headless browser security runner is separate from interactive Wishlist web testing.

## Library modernization — October 7, 2026

### Baseline and behavior

Started `feature/library-modernization` from merged main **`c59c488`** (PR #107), including Grocery/shell PR #94, dependency-security PR #98, and the Wishlist shell-quote **1.12.0** follow-up. Expo 57.0.25, Expo Router, `@expo/ui`, TanStack Query, Flask, lockfiles, compatibility overrides, and audit exceptions are unchanged.

Library now uses virtualized playlist/video rows, native local search, counts, expandable descriptions, stable artwork fallbacks, shared watched labels, and explicit loading/empty/no-results/unavailable/error states. Existing routes and successful API payloads remain unchanged. Search retains API ordering; video order is newest added first rather than YouTube playlist position. YouTube watch links open externally and never mutate watched status.

Refresh reads the saved shared catalog. Manual sync keeps its existing access for all signed-in users and confirms its effect on everyone. The app locks a pending import synchronously across navigation, rejects known-offline attempts without queueing, and never retries failed/uncertain imports automatically. A 30-second client deadline bounds auth refresh, transport, and body reading; a late auth refresh cannot launch another POST after expiry. Timeout means completion unknown, since server work may continue. Sync success invalidates Library queries, cancels older reads, and remains distinguishable from a later refresh failure. Logout cache clearing prevents late results from restoring sync state.

Flask rolls back failed imports and returns sanitized JSON: unavailable credentials/configuration 503, upstream failure 502, unexpected failure 500. Website sync gets a safe flash message. No database migration or new worker/status service is introduced. Importer upsert semantics remain: unavailable/removed upstream items are not purged, and watched data remains shared. Playlist timestamps are not presented as last-sync times. Personal OAuth, personal watch history, embedding, background imports, and cross-device import coordination remain deferred.

### Automated verification

- **42 mobile tests** pass, including QueryObserver recovery inside the 30-second freshness window; stale-read cancellation; offline/no-replay behavior; repeated-tap locking; logout during sync; and request expiry during token refresh.
- **137 backend tests** pass, including two-account/website catalog reads, unchanged success responses, sanitized failure status mapping, rollback of partially written imports, repeated upserts, shared watched preservation, and retained unavailable records.
- TypeScript, ESLint, Expo compatibility/XML/UUID/Metro/shell-quote regressions, root audit-gate/CDN tests, **13 browser security checks**, Sass, Poetry lock consistency, and Python dependency consistency pass.
- Root/mobile audit gates pass with the same reviewed exceptions; Python audit reports no known vulnerabilities. GitHub subsequently reported an additional Mako advisory; see the [October 7 exposure review and update follow-up](security/dependabot-2026-10-05.md#october-7-follow-up-new-mako-alert). The November 5 exception expiry and the three earlier upstream advisories remain tracked; nothing was suppressed.
- Production iOS/Android/web exports pass. Xcode simulator and Android debug builds pass. The Android APK installed on the API 36.1 ARM64 emulator, with page size **16384**.

### Native checks and limits

The iPhone 18 Pro / iOS 27 simulator used `scripts/library-preview-fixture.py`, never production data or live import credentials. Verified login, expired-token recovery, Tools navigation, overview/title-description search, video no-results/clear search, expanded descriptions, the 150-video catalog, missing-link disabled state, shared watched labels, cancel/confirm sync, import success, retained content on refresh failure, and warm Library navigation. YouTube opened in Safari after fixing a method-binding issue found during testing; returning preserved the playlist position. The launch-error UI was exercised before that correction.

Light/dark rendering and scrolling at maximum Dynamic Type were inspected. This is not a complete software-keyboard or screen-reader audit. Screenshots: [overview](screenshots/library-modernization/ios-library.png), [playlist](screenshots/library-modernization/ios-playlist.png), [dark playlist](screenshots/library-modernization/ios-playlist-dark.png), and [maximum text](screenshots/library-modernization/ios-large-text-dark.png). The floating gear is development-client UI. Original light appearance and standard text size were restored.

The first Xcode build found an ignored `.xcode.env.local` pointing to a removed Homebrew Node binary; it now points to installed Node 24.14.0. An unsigned simulator build lacked SecureStore's keychain entitlement. Rebuilding with normal simulator signing and reinstalling restored authentication successfully. No tracked native project or signing configuration changed.

Android build/install/startup and sign-out passed. Interactive entry through the embedded emulator caused unexpected development-bundle reloads; Library interactions, software-keyboard behavior, and TalkBack are not accepted on that evidence. Full Android feature validation remains required. UI automation also stalled twice for extended periods; elapsed time is not device-test evidence.

### Preview and release

With Keith's explicit approval, `feature/library-modernization` was pushed and opened as draft [PR #108](https://github.com/Kriordan/personal_portfolio/pull/108). Backend, mobile, web, and all CodeQL jobs passed on **`44cbd1cacc8164fa5f52cd55bf2173bf5afcee6e`**. The PR-specific CodeQL query returned **zero open findings**, separately from scan-job success. The implementation commit is `ebe8e99`; `44cbd1c` adds validation documentation.

The [Library iPhone preview](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/fe2b446b-5742-4202-a0cc-0d91fb9d8228) finished successfully at **2:02:38 p.m. EDT on October 7** from `44cbd1cacc8164fa5f52cd55bf2173bf5afcee6e`. EAS reports an internal-distribution physical-device build, and its IPA download returned HTTP 200. It uses the existing registered-iPhone signing profile with frozen credentials and `https://keithriordan.herokuapp.com`. No App Store/TestFlight submission or OTA update was made. Installation and the physical-device smoke test remain pending.

The inspected EAS archive includes Library sources and excludes local environment/credential files, databases, dependencies, and generated native projects. The inspection creates its own Git metadata. Successful build and artifact checks do not establish installation or authenticated live behavior.

After Keith approved the normal macOS Keychain prompt, the authorized Git push completed and deployed **`40c3732`** as **Heroku v132 at 9:46:04 p.m. EDT on October 7**, replacing v131 (`158a85c1`). No alternative authentication credential was extracted. Heroku reports v132 current/succeeded and `web.1` up. The deployed commit differs from preview source `44cbd1c` only in validation/security documentation, so the existing iPhone preview contains the matching application code and needs no replacement.

There are no migration-file changes relative to v131. Startup logs show Alembic initialization with no revision upgrade, followed by successful Flask startup. Read-only HTTPS checks returned website 200; JSON 401 for unauthenticated account, Library overview, playlist, and video routes; login redirects 302 for Library, Lists, and Wishlist; and OPTIONS 200 advertising POST for `/api/v1/library/sync`. These verify startup, authentication boundaries, and route availability. Authenticated production sync and error injection were not performed; error mapping and rollback were tested locally. No production data was changed by the checks.

Use the [Library smoke-test checklist](library-smoke-test.md) for remaining acceptance. Preserve all earlier Grocery/Wishlist follow-ups: physical editing/realtime recovery, Android sheets/CRUD/photos and refresh, actual discard gestures, private-photo renewal beyond 15 minutes, full VoiceOver/TalkBack, large text with software keyboard, smaller devices, cold preview links, and interactive web behavior. Android preview, production EAS environment configuration, security exception review, and the separate credential-consumer inventory before administrator-key retirement remain open. Wishlist v131's successful storage probe and Keith's preview acceptance are retained without implying unitemized device checks passed.

Additional local checks: the rebuilt iOS client showed the invalid-playlist state with a Back to Library action. Mobile web signed in as the second disposable user, displayed the same catalog, filtered playlists by description, rendered playlist detail/shared watched/missing-link states, and showed video no-results correctly. Browser confirmation was displayed and dismissed without an import. Full web failure/launch testing remains unchecked.

### Live sync connection follow-up — October 10

Keith's iPhone test reached the Library sync endpoint but returned the connection-unavailable state. The production log at **11:39:36 a.m. EDT** specifically reported missing YouTube credentials. A read-only deployment probe confirmed the Google client settings and playlist-ID file were present, while the token file was absent. The earlier fixture tests mocked credentials/imports, and deployment probes checked unauthenticated routing; neither established a working live Google connection.

The repair replaces dyno-local token storage with an encrypted database record, adds administrator-only reconnect/check/revoke forms, and uses the same shared connection for API, website, and CLI calls. It includes additive migration `f6a7b8c9d0e1`, a separate server encryption key, and the `cryptography` dependency. Expo, mobile code, existing catalog rows, successful API payloads, and authenticated sync permissions remain unchanged. See the [connection runbook](library-youtube-connection.md). Local validation and deployment/consent results are recorded below when complete; all earlier device follow-ups remain open.

**151 backend tests** pass, including the real OAuth client's mocked code exchange with PKCE, durable refresh in a fresh app instance, shared API credential selection, permission/CSRF/state/replay checks, encrypted storage, failed replacement preserving the prior connection, and migration upgrade/downgrade/upgrade preserving a saved playlist. Poetry consistency, `pip check`, `pip-audit`, and whitespace checks pass. The only new locked packages are `cryptography 50.0.2`, `cffi 2.1.1`, and `pycparser 3.11`; existing versions and security exceptions are unchanged. GitHub's separately tracked Mako alert remains open despite the clean Python audit. The administrator page was inspected in a disposable local browser fixture without contacting Google. Live Google consent and a successful production import remain pending.
