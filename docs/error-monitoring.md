# Error monitoring

Sentry is opt-in and errors-only for the Expo iOS/Android app and Flask. Web and development clients do not report. The integration does not change extraction retries, chargeable provider work, saved jobs or authentication. Expo 57, Expo Router, @expo/ui, TanStack Query and Flask remain in place.

## Scope and privacy

- Automatic JavaScript errors, a React error boundary, and unhandled Flask exceptions retain stack locations, release/build information and basic OS/device model metadata.
- Jobwizard reports unexpected request-format failures and server failures. A validated opaque extraction UUID is sent as `X-Request-ID` and attached to both reports. It contains no user ID or listing URL. Flask returns that ID, or generates one for other API requests.
- Offline/timeout uncertainty, authentication expiry, conflicts, missing/expired receipts, rate limiting, unsupported URLs and temporarily disabled extraction are quiet. Failed provider credentials/quota and invalid summaries are actionable server errors. Repeated identical mobile failure reports are bounded and deduplicated in memory.
- No session replay, tracing, profiling, metrics, logs, console capture, breadcrumbs, screenshots, view hierarchy, request bodies, cookies, headers, query strings, application notes or local variables are collected. Runtime error payloads omit source excerpts. No account identity is attached. Uploaded build artifacts contain application source code for symbolication; Sentry can display that source context alongside a frame. Runtime notes/listing content are not source-map artifacts.
- JavaScript and Python `beforeSend` rebuild outgoing events from an allowlist and replace exception messages with static text. Attachments are removed. In-memory transport tests inject synthetic secrets into Flask requests and exceptions and check that none leave the scrubber.

**Native crash limitation:** native crash handling is explicitly off in this first version. Expo 57's supported Sentry `~7.11.0` SDK does not apply the JavaScript scrubber to native crash reports, and its bundled Cocoa crash recorder enables memory introspection. JavaScript and Flask errors cover the current Jobwizard diagnosis. Enabling native crashes requires a separate native payload filter/memory-content configuration and a synthetic crash inspection on both platforms. Do not claim the JavaScript privacy test covers native crash envelopes. Crashes before JavaScript initializes the SDK are also outside this initial setup.

## Account and build setup

Use the existing Sentry account's free plan, with separate `personal-portfolio-mobile` (React Native) and `personal-portfolio-flask` projects. Check the account's actual quota; leave paid overages and optional products off. Do not enable integrations that upload user content. Configure issue notifications for new/regressed errors after verifying the sample events.

On October 23, both projects were created in the `keith-riordan` organization. Its Developer plan includes 5,000 errors per usage month, with no payment method or billing details on file. Organization settings now require server-side/default data scrubbing and prevent IP storage; enhanced privacy is on, public issue sharing and automatic JavaScript source fetching are off, and minidump attachments remain disabled. Additional sensitive-field scrubbing covers credentials, notes, listing text, screenshots, summaries and job URLs. No optional paid product or repository integration was enabled. After explicit approval, the `personal-portfolio-eas-uploads` organization token was created with `org:ci` only and stored as an EAS project secret in the preview environment. The mobile DSN, project, organization and environment are configured there, with `EXPO_PUBLIC_SENTRY_ENABLED=0` initially. On October 26, the user approved the enabled iPhone preview and the preview flag was set to `1`; production remains unconfigured and inactive.

For Heroku, configure `SENTRY_DSN`, `SENTRY_ENVIRONMENT=production`, and `SENTRY_RELEASE` to the deployed Git SHA. Prefer an explicit release value; `HEROKU_SLUG_COMMIT` is a fallback when runtime metadata is available. Set `SENTRY_ENABLED=1` only after the privacy smoke test. The SDK is inactive without both the flag and DSN. `SENTRY_ENABLED=0` disables subsequent reporting after the app restarts.

For each EAS preview/production environment, configure:

| Variable | Purpose |
| --- | --- |
| `EXPO_PUBLIC_SENTRY_ENABLED` | `1` to enable reporting in native release builds; default is off |
| `EXPO_PUBLIC_SENTRY_DSN` | Public ingestion DSN for the mobile project; not an API/admin token |
| `EXPO_PUBLIC_SENTRY_ENVIRONMENT` | `preview` or `production` |
| `SENTRY_ORG`, `SENTRY_PROJECT` | Build-time source-map destination |
| `SENTRY_AUTH_TOKEN` | Secret build-only token scoped to symbol/source-map uploads; never prefix with `EXPO_PUBLIC_` or place in app config |

Enabled EAS workers fail configuration if any required value is missing. The upload token never enters the public Expo configuration. The Sentry Metro/Expo plugins upload source maps and native symbols during the native build. Builds without reporting omit the upload plugin. Use clean prebuilds when changing this flag so generated upload scripts do not persist. A new native build is required; this is not an Expo Go or JavaScript-only update.

The SDK uses the native bundle ID, app version and build number as release/dist. Both preview and production build numbers increment, and a validated EAS Git commit is included as a tag. Debug IDs associate Hermes bundles with uploaded source maps. Confirm symbolication in Sentry before using a preview for acceptance. Do not permit failed uploads in enabled builds.

Mobile configuration is compiled into the build. To stop reporting from an installed build immediately, disable its DSN/project ingestion in Sentry; changing an EAS environment alone does not update installed apps.

## Validation and activation checklist

- [x] Mobile privacy/filter tests and build-token exclusion/configuration tests.
- [x] Flask in-memory transport verifies real automatic exception capture, scrubbed payloads, request correlation, disabled default and resilience to reporting failures.
- [x] Full local backend suite on October 26: 258 tests, 19 PostgreSQL-dependent checks skipped locally. CI supplies PostgreSQL for those checks.
- [x] 104 mobile tests, TypeScript, ESLint, Expo 57 dependency compatibility and iOS/Android/web exports on October 26. Runtime reporter tests now cover disabled/dev/web clients, one-time initialization, quiet expected outcomes, duplicate suppression, scrubbing and a throwing capture adapter. Real Flask transport tests additionally verify quiet HTTP recovery responses and unchanged responses/correlation when the transport fails. The npm security gate has no root exceptions and the three existing mobile exceptions (`decode-uri-component`, `node-forge`, and the Expo CLI Zod 3 advisory inherited from main); the November 5 review deadline is unchanged.
- [x] Refreshed October 26 iOS Release simulator build with the Expo-compatible Sentry SDK, reporting disabled, after merging main through PR #127.
- [x] Refreshed October 26 Android arm64 Release build with the Expo-compatible Sentry SDK, reporting disabled, after merging main through PR #127.
- [x] iPhone 17 Pro / iOS 26.5 Release simulator build reaches the sign-in screen with reporting disabled. Use local ad hoc simulator signing: the unsigned build stalled during secure-storage restoration. This does not use the Apple distribution certificate.
- [x] Pixel 10 / Android 16 API 36.1 Release APK installs and reaches the app shell with reporting disabled. Saved fixture credentials remain on the disposable emulator; the Release API target is unavailable, so this verifies startup/error rendering, not successful authenticated data access.
- [x] October 26 iPhone 18 Pro / iOS 27.0 Release simulator authenticated smoke against a reachable disposable localhost API: sign-in, Grocery completion/undo with live updates, Wishlist list/detail, Library catalog/playlist, Learning answer reveal/rating save, and Jobwizard suggest/review/apply/save/capture/full screenshot viewer. Browserless/OpenAI were fixture adapters; no production data or paid provider work. Reporting was disabled, so this is integration regression evidence, not an enabled-reporting acceptance test.
- [x] October 26 Pixel 10 / Android 16 API 36.1 authenticated smoke: sign-in, Home/Tools navigation, the 293-job catalog, opening the job created on iOS, and suggest/review/select/apply/save with three persisted details. Reporting was disabled. A disposable local test APK allowed cleartext only to the emulator host `10.0.2.2`; the generated manifest/resource override was removed and is not committed. Screenshot viewing was not validated on Android: the fixture returns a `127.0.0.1` image URL, which is not the emulator host. Broader enabled-device checks remain below.
- [x] Sentry account/projects, server-side privacy settings and free-plan limits verified. On October 26, rechecked enhanced privacy, mandatory/default scrubbing, IP removal, disabled public sharing/source fetching/minidump attachments, preview build-secret presence, preview reporting flag `0`, and absent production Heroku configuration.
- [ ] Configure and verify new/regressed-error notifications before production activation. Both existing project alerts are enabled, but currently trigger only when Sentry marks a new or existing issue high priority; that does not prove every new/regressed error will notify. Actual notification delivery remains unverified.
- [x] Preview build-only upload token stored as an EAS secret; DSN and public build configuration set separately. Preview reporting was initially disabled and enabled on October 26 for the approved device build. Production configuration remains part of rollout. The enabled local iOS Release artifact was inspected and contains no upload token.
- [x] Controlled Flask exception received in `preview-validation`, release `e8439604acdba8d6255166f8a5066a5a181c0d87`. Event `4bcafb7c7b204b9785f598c98661c3ba` retains five stack locations and the response's opaque request ID. The stored JSON contains no injected synthetic private content, request, breadcrumbs or extra data; its IP is removed. The synthetic issue was resolved after inspection. This used an isolated local Flask test client, with no public endpoint or production deployment.
- [x] Controlled JavaScript error received from an enabled iPhone 17 Pro / iOS 26.5 Release simulator build in `preview-validation`. The Expo build plugin successfully uploaded Hermes source maps and native symbols without an upload-failure bypass. Event `0227d8baee814adabe456d9e0a8870e8` resolves to the disposable validation entry at line 23, column 56, with debug ID `c5e5bc98-2b15-493f-b809-29378265cadc`; release is `com.kriordan.personalportfolio@1.0.0+1`, commit tag `863419952ebbebe56f1551c87c620086f1558965`. Its stored JSON excludes runtime-injected private content, request, breadcrumbs, extra data and IP. The upload token is absent from the built app. The temporary entry was removed after validation; this was not an installable user preview.
- [ ] Follow-up before enabling native crash handling: native payload privacy filtering/memory-content configuration, synthetic crash inspection on iOS and Android, symbolication and crash-on-next-launch delivery. Use a disposable test build; never add a public crash endpoint or a production user-facing crash button.
- [x] The real mobile extraction session sent a synthetic request to an isolated localhost Flask fixture. Mobile event `b2fcb1f79e0d4d20b7c26b998156cf4c` and Flask event `22aab44a59744a718b1e7fe4c40ce277` share request ID `7bb47abd-ec73-4626-968a-1f21a1e745b7`; the mobile frame resolves to `src/lib/monitoring.ts:61`. Both stored payloads exclude synthetic private content and request data. The follow-up missing-receipt 404 generated no extra error event. No provider calls or production data were used. All five issues from the two native validation runs were resolved after inspection, and the local fixture was stopped.
- [ ] Extend live native quiet-error checks to 401/409/410/429, offline, unsupported listing and uncertain timeout flows. These cases have automated policy/session coverage, but the live correlated smoke test covered 500 and missing-receipt 404 only.
- [ ] Repeat normal sign-in, Library sync, Learning review, Wishlist and Jobwizard save/capture on a reporting-enabled device preview; monitoring transport failure must not block them. October 26 disabled iOS fixture checks cover the ordinary flows above; actual YouTube sync and enabled-device behavior remain follow-ups.
- [ ] Enable the approved environments and verify one clean event before production rollout. Remove temporary verification code before release.

PR #123 now targets `main` and includes main through PR #127 (`4665a7947ad8130b3ae578192cd7e19eb690f4ea`), including the merged Jobwizard recovery and form improvements. The user accepted the PR #127 physical iPhone preview, but that artifact does not contain Sentry. That acceptance does not close Sentry-specific validation. The original physical iPhone HTTP 400 cause remains unconfirmed; monitoring helps diagnose a recurrence. Preserve unchecked items in [suggestion recovery](jobwizard-suggestion-recovery.md), [extraction validation](jobwizard-extraction.md), [mobile validation](mobile-ui-validation.md), and [dependency security follow-ups](security/dependabot-2026-10-05.md).

References: [Expo Sentry integration](https://docs.expo.dev/guides/using-sentry/), [Flask integration](https://docs.sentry.io/platforms/python/integrations/flask/), [React Native data collection](https://docs.sentry.io/platforms/react-native/data-management/data-collected/).

October 26 fixture evidence: [iOS saved job and completed capture](assets/monitoring/ios-regression-2026-10-26.png), [Android saved reviewed details](assets/monitoring/android-regression-2026-10-26.png).

## Merge and rollout status — October 26

The code remains safe to review as a disabled-by-default integration. The initial branch refresh did not enable reporting, change credentials, deploy Flask, or consume a cloud build. The subsequent user-approved enabled iPhone preview below consumed one cloud build and enabled only preview reporting; production remains inactive. Local iOS/Android builds, exports, automated tests, and the refreshed branch's CI/security checks are the merge evidence; device acceptance is a separate remaining gate for the new native dependency.

Recommended sequence:

1. Completed: build the reporting-enabled iPhone preview and verify its exact bundle/source map and a scrubbed synthetic artifact event, as recorded below. No test button, automatic canary, or temporary validation code is present in the app. The artifact-based event does not replace physical-device runtime acceptance.
2. Have the user smoke-test normal Jobwizard and cross-feature flows on that preview, including the remaining quiet-error cases above. Keep PR #123 draft until this acceptance is complete, then merge with CI still green.
3. Before production activation, finish new/regressed notification rules and delivery verification. After merge, deploy Flask and configure its DSN, environment and exact release SHA, inspect a controlled scrubbed event, and enable only the approved environment. Mobile production reporting requires its own configured native build; EAS environment changes do not alter installed apps.
4. Keep native crash capture disabled. The separate native privacy/crash checklist, existing mobile accessibility/device checks, and dependency-security review deadline remain open.


## Enabled iPhone preview — October 26

- [x] [EAS build b12a71da-f214-4810-8f0f-2f210b93eb60](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/b12a71da-f214-4810-8f0f-2f210b93eb60) finished successfully from `f9ad1369e3966efe3e96e3a3f0cb59cf6b10881c`, version `1.0.0`, iOS build `2`. Existing signing credentials were frozen; no certificate/provisioning changes were made. Later PR edits only record validation evidence.
- [x] Preview EAS reporting is enabled, environment `preview`, targeting the existing production API. No production backend reporting or deployment was enabled. The IPA includes the configured mobile DSN and build commit; the build-only upload token is absent from every file in the archive.
- [x] EAS uploaded the Hermes source map without an upload-failure bypass. [Sentry upload](https://keith-riordan.sentry.io/settings/projects/personal-portfolio-mobile/source-maps/6c6480c6-c549-5222-8257-83d35f9bdd7a/) contains debug ID `4be1a990-d41f-439e-90be-cc1067b25419`, which also occurs in the downloaded IPA's `main.jsbundle`. Release/dist are `com.kriordan.personalportfolio@1.0.0+2` / `2`.
- [x] [Synthetic event 5e2402a4f0ec4cb9b86ee6cba921cd08](https://keith-riordan.sentry.io/issues/7813962818/events/5e2402a4f0ec4cb9b86ee6cba921cd08/) in `preview-validation` resolves the actual artifact's generated location `1:1412517` to `src/lib/monitoring.ts:61:5` using that debug ID. The test used the unchanged app scrubber, confirmed identical to the source embedded in the uploaded map. This was an artifact-based ingestion check, not an event emitted by a physical iPhone. Prior enabled native simulator evidence remains recorded above.
- [x] Inspected the stored event JSON through the signed-in Sentry UI. It contains no injected synthetic private marker, request data, breadcrumbs, attachments, arbitrary extra data, email, local variables or IP address. The static exception text remains. Sentry adds source context from the uploaded map, as expected. The synthetic issue was resolved after inspection.
- [x] The upload token remains upload-only; artifact/event reads used the signed-in UI. No credential scope was expanded. [Verification screenshot](assets/monitoring/iphone-preview-sentry-2026-10-26.png).
- [ ] User installs this enabled preview and verifies normal app behavior. Keep PR #123 draft until that acceptance; no additional cloud build is needed unless app code changes.

Device checklist:

1. Install the linked preview and cold-launch it; sign in if needed.
2. In Jobwizard, paste a supported public listing, suggest details, review/apply, save, and capture/open its screenshot. Also edit an existing saved job.
3. Relaunch after backgrounding and confirm the saved job remains available. Briefly go offline and confirm failure/retry messaging remains usable when connectivity returns.
4. Briefly check Grocery completion/undo, Wishlist, Library browsing/sync, and Learning review. The longer native quiet-error and accessibility follow-ups above remain open; report any failed action or unexpected message with its approximate time.

This preview reports unexpected JavaScript errors to Sentry. It does not collect native crashes, replay, screenshots or application content. Alert delivery/new-regression coverage and the Flask production rollout are still separate follow-ups.
