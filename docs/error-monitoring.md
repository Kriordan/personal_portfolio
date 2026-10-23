# Error monitoring

Sentry is opt-in and errors-only for the Expo iOS/Android app and Flask. Web and development clients do not report. The integration does not change extraction retries, chargeable provider work, saved jobs or authentication. Expo 57, Expo Router, @expo/ui, TanStack Query and Flask remain in place.

## Scope and privacy

- Automatic JavaScript errors, a React error boundary, and unhandled Flask exceptions retain stack locations, release/build information and basic OS/device model metadata.
- Jobwizard reports unexpected request-format failures and server failures. A validated opaque extraction UUID is sent as `X-Request-ID` and attached to both reports. It contains no user ID or listing URL. Flask returns that ID, or generates one for other API requests.
- Offline/timeout uncertainty, authentication expiry, conflicts, missing/expired receipts, rate limiting, unsupported URLs and temporarily disabled extraction are quiet. Failed provider credentials/quota and invalid summaries are actionable server errors. Repeated identical mobile failure reports are bounded and deduplicated in memory.
- No session replay, tracing, profiling, metrics, logs, console capture, breadcrumbs, screenshots, view hierarchy, request bodies, cookies, headers, query strings, application notes, local variables or source excerpts are intentionally collected. No account identity is attached.
- JavaScript and Python `beforeSend` rebuild outgoing events from an allowlist and replace exception messages with static text. Attachments are removed. In-memory transport tests inject synthetic secrets into Flask requests and exceptions and check that none leave the scrubber.

**Native crash limitation:** native crash handling is explicitly off in this first version. Expo 57's supported Sentry `~7.11.0` SDK does not apply the JavaScript scrubber to native crash reports, and its bundled Cocoa crash recorder enables memory introspection. JavaScript and Flask errors cover the current Jobwizard diagnosis. Enabling native crashes requires a separate native payload filter/memory-content configuration and a synthetic crash inspection on both platforms. Do not claim the JavaScript privacy test covers native crash envelopes. Crashes before JavaScript initializes the SDK are also outside this initial setup.

## Account and build setup

Use the existing Sentry account's free plan, with separate `personal-portfolio-mobile` (React Native) and `personal-portfolio-flask` projects. Check the account's actual quota; leave paid overages and optional products off. Do not enable integrations that upload user content. Configure issue notifications for new/regressed errors after verifying the sample events.

On October 23, both projects were created in the `keith-riordan` organization. Its Developer plan includes 5,000 errors per usage month, with no payment method or billing details on file. Organization settings now require server-side/default data scrubbing and prevent IP storage; enhanced privacy is on, public issue sharing and automatic JavaScript source fetching are off, and minidump attachments remain disabled. Additional sensitive-field scrubbing covers credentials, notes, listing text, screenshots, summaries and job URLs. No optional paid product or repository integration was enabled. The `org:ci` upload token is prepared but awaits explicit credential-creation approval; DSNs have been saved privately, not committed or activated in production.

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
- [x] Full local backend suite: 256 tests, 19 PostgreSQL-dependent checks skipped locally. CI supplies PostgreSQL for those checks.
- [x] 98 mobile tests, TypeScript, ESLint, Expo 57 dependency compatibility and iOS/Android/web exports. After the October 23 `braces` advisory withdrawal, the npm security gate has no root exceptions and only the two existing mobile exceptions.
- [x] Final iOS Release simulator build with the Expo-compatible Sentry SDK, reporting disabled.
- [x] Android arm64 Release build with the Expo-compatible Sentry SDK, reporting disabled.
- [x] iPhone 17 Pro / iOS 26.5 Release simulator build reaches the sign-in screen with reporting disabled. Use local ad hoc simulator signing: the unsigned build stalled during secure-storage restoration. This does not use the Apple distribution certificate.
- [ ] Android Release launch and full authenticated native regression checks. The build passes; the integrated emulator is running, but the remaining UI checks are not yet complete.
- [x] Sentry account/projects, server-side privacy settings and free-plan limits verified.
- [ ] Build-only upload token and DSNs configured without exposing secrets in source, logs or bundles.
- [x] Controlled Flask exception received in `preview-validation`, release `e8439604acdba8d6255166f8a5066a5a181c0d87`. Event `4bcafb7c7b204b9785f598c98661c3ba` retains five stack locations and the response's opaque request ID. The stored JSON contains no injected synthetic private content, request, breadcrumbs or extra data; its IP is removed. The synthetic issue was resolved after inspection. This used an isolated local Flask test client, with no public endpoint or production deployment.
- [ ] Controlled JavaScript error visible in the correct environment; uploaded source maps resolve frames to source and releases identify the tested commits/builds.
- [ ] Follow-up before enabling native crash handling: native payload privacy filtering/memory-content configuration, synthetic crash inspection on iOS and Android, symbolication and crash-on-next-launch delivery. Use a disposable test build; never add a public crash endpoint or a production user-facing crash button.
- [ ] Correlate one synthetic failed Jobwizard operation across mobile and Flask using the same UUID. Verify expected 401/404/409/410/429, offline, unsupported listing and uncertain timeout flows remain quiet and do not retry provider calls.
- [ ] Verify normal sign-in, Library sync, Learning review, Wishlist and Jobwizard save/capture still work; monitoring transport failure must not block them.
- [ ] Enable the approved environments and verify one clean event before production rollout. Remove temporary verification code before release.

The Jobwizard recovery fix is reviewed separately in PR #122. Its original physical iPhone HTTP 400 cause is still unconfirmed. Monitoring helps diagnose a recurrence; it is not evidence that the defect is resolved. Preserve unchecked items in [suggestion recovery](jobwizard-suggestion-recovery.md), [extraction validation](jobwizard-extraction.md), [mobile validation](mobile-ui-validation.md), and [dependency security follow-ups](security/dependabot-2026-10-05.md).

References: [Expo Sentry integration](https://docs.expo.dev/guides/using-sentry/), [Flask integration](https://docs.sentry.io/platforms/python/integrations/flask/), [React Native data collection](https://docs.sentry.io/platforms/react-native/data-management/data-collected/).
