# Validation status and follow-ups

Updated October 27, 2026. This is the current index for mobile/Jobwizard/Sentry acceptance. Feature smoke-test files retain their detailed scenarios and dated evidence. Only an explicitly tested scenario is closed; general device approval does not imply every failure, accessibility or concurrency case passed.

## Verified baseline and rollout

| Area | Current evidence |
| --- | --- |
| Main | Recovery work starts at `e2d9794`, merged PR #130, including Sentry #123 and runtime security #129. Expo 57, Expo Router, @expo/ui, TanStack Query and Flask are retained. |
| Flask production | Verified October 27 as Heroku **v160**, source/release `5f1e8872fca486991f306679067194a83d2c9481`, Python **3.13.18**, Sentry SDK **2.73.0**, reporting enabled in `production`. The deployment preserved newer production work from `8754d28`; do not deploy the older local main over that baseline. |
| HTTP errors | PR #130 deployed: six deployed HTML error regression checks passed. Live homepage returned 200; protected APIs 401; unknown HTML GET/HEAD 404. |
| Sentry alerts | New-issue and resolved-issue-regression rules configured for both projects, with email test delivery verified. A real controlled Flask regression email arrived October 27 at 13:23 UTC. Scrubbed stored events and request correlation were inspected; synthetic issues resolved. |
| Mobile preview | Existing [iPhone build b12a71da](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/b12a71da-f214-4810-8f0f-2f210b93eb60), version 1.0.0/build 2, has preview reporting enabled. Exact artifact source maps and scrubbed artifact event were verified; user accepted it on a physical iPhone. [Detailed evidence](error-monitoring.md#enabled-iphone-preview--october-26). |
| Mobile production | A production EAS reporting environment/build has not been enabled. Changing environment variables does not alter installed apps. Native crash collection remains intentionally disabled. |

The initial simulator/recovery pass made no deployment, credential, provider or monitoring-policy changes and consumed **zero cloud builds**. The separately approved PR #131 device preview below uses **one cloud build**, with the existing signing and monitoring configuration. Production rollout artifacts are preserved in [Sentry rollout](assets/recovery-validation-2026-10-27/sentry-production-rollout.json) and [HTTP deployment](assets/recovery-validation-2026-10-27/html-error-status-deployment.json). The earlier rollout's HTTP 200 exception responses are historical evidence of the bug subsequently fixed in PR #130.

## Physical iPhone acceptance completed October 27

- [x] In Add job, paste the exact original Justworks URL (`https://job-boards.greenhouse.io/justworks/jobs/8179751`) and tap Suggest details: user confirmed **“Suggestions appear.”**
- [x] After the unsupported `https://example.com` response, manually save title “Recovery check”, company “Test”, then reopen: user confirmed **“Manual save and reopen work.”** Archiving that test job is not confirmed.

Both used the existing enabled preview against production. They close the original paste/feedback and manual-save follow-ups, but do not prove the cause of the original HTTP 400 or acceptance of the newer recovery fixes below.

## PR #131 iPhone preview — October 27

[Install build c1b66139](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/c1b66139-4de0-4196-8202-8d6556b08b8c): **1.0.0 (3)**, internal iPhone preview, built from app commit `d532de62c0c62bead610b3024a34e96bc47627d3`. Later documentation-only commits do not change this app. The build finished successfully; the downloaded IPA passes strict signature verification, includes the registered iPhone, uses replacement certificate ending `FBC7A`, and targets the production API. No credentials were changed.

Sentry source-map upload completed without a bypass. Debug ID `e8cc8f0e-1ee7-4edd-a990-78222d4ef483` occurs in both the uploaded-map record and the IPA's Hermes bundle. The existing enabled preview configuration is retained. This build's upload/artifact match is verified; a new synthetic Sentry event was not sent. Prior symbolication, privacy and alert-delivery evidence remains above. [Artifact verification](assets/recovery-validation-2026-10-27/iphone-preview-build-3.json).

**Device acceptance is pending.** Install this preview over the existing app, then use disposable jobs for the checks below. These requests use the live backend; reviewing facts and saving remain deliberate actions.

- [ ] **Rejected request survives no longer than it should:** in Add job, paste `https://example.com` and tap **Suggest details**. Expect the readable unsupported-listing message. Force-quit and reopen the app without saving. Open Add job and paste a supported listing: **Suggest details** should work, with no stale **Retry same request** or unfinished-work state from `example.com`.
- [ ] **Review, apply, save, reopen:** use `https://job-boards.greenhouse.io/justworks/jobs/8179751` (or another current supported public listing if it has been removed). Expect visible progress and suggestions, never only a flicker. Compare the title, company and accepted bullets with the source; edit one bullet and exclude another. Tap **Apply to draft**, save, and reopen. Selected facts and edits should persist; excluded facts should be absent.
- [ ] **Offline recovery:** in a fresh Add form, paste the supported URL, enable Airplane Mode and turn Wi-Fi off, then tap **Suggest details**. Expect readable connection feedback and retained form text. Restore connectivity: a new extraction must wait for your tap. Tap **Suggest details** once to continue.
- [ ] **Background recovery:** immediately after starting that request, go to the Home Screen for about 30 seconds, then return. Expect suggestions or a clear recovery action such as **Check suggestion status** / **Continue preparing details**. Use the offered action once. If the result finishes too quickly to interrupt, record that limitation; do not repeatedly restart requests. The app must remain usable, without a permanently disabled action or silent flicker.
- [ ] **Manual fallback:** after an unsupported listing, manually enter a title/company, save and reopen. Archive disposable test jobs afterward. The earlier build passed this; this check confirms the new artifact keeps it working.

Optional follow-ups: open an existing full screenshot and check pinch, drag and close; leave an unaccepted suggestion receipt for more than 24 hours, then reopen and confirm an expired message, fresh **Suggest details**, and no stale **Review**, **Continue**, or **Retry same request**. Expiry is already verified with the native fixture and regression tests, so an overnight wait is not required for the core acceptance pass. Do not change the phone clock or deliberately exhaust quotas. Server rejection, committed-response loss, account races and reporting outages remain covered by the controlled checks below, not inferred from this physical checklist.

For failures, record the step, visible message and approximate time. Do not include credentials or personal notes. PR #131 remains unmerged until the user accepts the device result; no Flask deployment is required for these mobile fixes.

## Recovery fixes and local validation

Four defects were reproduced and fixed in the mobile extraction session:

1. Definitively rejected reads (including rate limits, conflicts and explicitly disabled extraction) retained their recovery request and could reopen as unknown work. Clear that request after a definitive rejection, retaining it if durable cleanup fails.
2. An unclassified HTTP 503 was treated as definitive even if work had committed. Keep the same UUID and recover by reading its receipt; only the coded `unavailable` response is a definitive 503 rejection.
3. A late rejection from a disposed account could clear another account's pending request. Ignore responses after disposal before touching recovery storage.
4. Expired receipts left stale review/continuation/retry actions. Clear the expired result/request so deliberate fresh extraction is available.

Regression tests cover these transitions, account isolation and retention of a ready source when summarization is rate-limited. The initial three regression cases failed before the fix. Final checks: **109 mobile tests**, TypeScript, ESLint and Expo 57 dependency compatibility pass; **44 targeted backend tests** cover monitoring, extraction, capture and Jobwizard API/service behavior. Backend providers in those tests are mocked.

Native fixture conditions:

- iPhone 18 Pro / iOS 27: existing local Release native app with current production-mode Hermes JavaScript, ad hoc simulator signing only.
- Pixel 10 / Android 16 API 36.1: locally built development host with production-mode JavaScript (`--no-dev --minify`). This activates the real JS reporter without claiming Release APK or physical Android acceptance. Use Java 17 for the local native build; Android Studio's bundled newer Java failed native configuration.
- Both target disposable SQLite accounts at localhost, fake Browserless/OpenAI/storage adapters, and a local Sentry envelope collector. No real provider or Sentry traffic. The local collector has positive unexpected-error events from each platform, so quiet-error counts are not evidence from a disabled reporter.
- A previous Android Release artifact could not reach the local HTTP fixture. Production network security was not changed. The local development host and emulator port forwarding supply the test connection.

| Scenario | Result and scope |
| --- | --- |
| Rate limit/conflict/unavailable | iOS 429/409/coded-503 show wrapping errors, keep manual saving available, clear rejected recovery work and emit no event. Android 429 also passes with no event. |
| Unsupported URL | iOS `example.com` gives the real API's unsupported-listing message; no receipt/provider work or telemetry event. Physical manual save/reopen also accepted above. |
| Expired receipt | Actual fixture receipt expiry returns 410; iOS clears Review/Retry/Continue and offers Suggest details. No new event. |
| Authentication expiry | iOS forced 401 plus rejected refresh returns to sign-in; signing into account 2 opens an empty Add form with no account-1 URL/result. No event. Late-response storage race also has a focused regression test. |
| Lost successful response | iOS committed read and summary replaced by generic 503 responses recover by GET, with one read and one summary provider call. Android also recovered the completed read and summary with exactly one additional call per provider, reaching Suggestions ready. Unexpected 503 events retain an opaque request ID; missing-receipt 404 stays quiet. |
| Foreground timeout | iOS 30-second fixture read outlasts client timeout. Status recovery reaches “Some details are ready” and explicit “Continue preparing details”; one read, no automatic summary, no new event. |
| Background/process restart | iOS interrupted during a slow read, then relaunched: receipt recovery offers explicit continuation without repeating the read or starting a summary. |
| Offline/reconnect | Android Wi-Fi and mobile data temporarily disabled in the emulator: immediate reconnect message and no POST/event. Restoring both connections does not start provider work. |
| Reporting outage | iOS unexpected 500 attempts local telemetry delivery while the collector returns 503. App stays usable; same-request recovery, review/apply/save, capture and full viewer succeed with reporting still unavailable. One saved job and one capture/provider call. Android reads that saved job and opens/zooms/moves/resets/closes the full screenshot. |
| Payload privacy | Native local events retain static exception text, OS/build/stack metadata and opaque correlation. No request, breadcrumbs, extra data, attachments, listing URL or account identity. The SDK adds the neutral IP placeholder `0.0.0.0`; this is not a collected client address. Actual server-side IP removal was verified during the prior Sentry rollout. |

Evidence: [local counters and privacy assertions](assets/recovery-validation-2026-10-27/local-results.json), [iOS rejected request](assets/recovery-validation-2026-10-27/ios-rejection.png), [expired receipt](assets/recovery-validation-2026-10-27/ios-expired-receipt.png), [timeout recovery](assets/recovery-validation-2026-10-27/ios-timeout-recovery.png), [relaunch recovery](assets/recovery-validation-2026-10-27/ios-relaunch-recovery.png), [viewer with reporting unavailable](assets/recovery-validation-2026-10-27/ios-viewer-reporting-unavailable.png), [Android rejection](assets/recovery-validation-2026-10-27/android-rejection.png), [offline feedback](assets/recovery-validation-2026-10-27/android-offline.png), [Android viewer](assets/recovery-validation-2026-10-27/android-viewer.png), [Android recovered suggestions](assets/recovery-validation-2026-10-27/android-recovered.png).

### Repeating the focused checks

Run `PYTHON_DOTENV_DISABLED=1 poetry run python scripts/jobwizard-preview-fixture.py`; it binds only to `127.0.0.1:5058`. Use the disposable credentials in its header. Native local configuration uses API `http://127.0.0.1:5058`, monitoring environment `local-recovery-validation`, enabled flag `1` and fake DSN `http://public@127.0.0.1:5058/1`; never use production DSNs for this failure matrix. Android needs local port forwarding and a development host. Keep EAS URL restrictions intact.

`POST /fixture/state` controls the fixture; `GET /fixture/results` reports provider, request and event counters; `/fixture/events` holds only synthetic scrubbed payloads. Restore each mode before the next case. `extraction_http` forces a rejection before work; `extraction_response: "lost"` returns 503 after commit; `expire_extractions: true` expires saved receipts; `auth: "expired"` rejects requests and refresh; `telemetry: "failure"` simulates ingestion failure. Read delay 30 seconds exercises client uncertainty. These controls exist only in the standalone local script, never production routes.

## Remaining work, in order

| Priority | Follow-up and completion evidence |
| --- | --- |
| PR #131 device acceptance | Approved preview **1.0.0 (3)** is ready; run the checklist above before merging. Earlier physical acceptance used build 2 and does not validate these fixes. Physical overnight expiry remains optional/unconfirmed; controlled native expiry validation has passed. |
| Native breadth | Complete the remaining full combinations in [Jobwizard smoke tests](jobwizard-smoke-test.md): save/capture concurrency, lost writes, image-link expiry, account switch during unresolved save/capture, and terminated protected deep links. Current focused checks do not close those combined items. Repeat the full failure matrix in an Android Release build/on hardware. |
| Accessibility | VoiceOver/TalkBack, largest text sizes, keyboard/small-phone layout, focus restoration and announcements across forms, review, menus and viewer remain open. |
| Other features | Retain [Grocery/shell reconnect and sharing checks](mobile-ui-validation.md), [Wishlist signed-image/upload lifecycle](wishlist-smoke-test.md), [Library sync/pin/watched behavior](library-smoke-test.md), and [Learning uncertain review/account switching](learning-smoke-test.md). Earlier disabled-reporting fixture smokes do not prove every enabled-device scenario or live YouTube sync. |
| Extraction operations | Confirm retained evidence of the first daily cleanup execution and concurrent capture/extraction timing/provider budgets. The deployed schedule and successful manual cleanup are documented in [extraction rollout](jobwizard-extraction.md); configuring the schedule alone does not prove later executions. |
| Runtime trust | Python 3.13.18 deployment is verified. Retain an explicit result of the 12 TLS trust checks on that deployed runtime; the older v154 probe is not a rerun. [Runtime record](security/runtime-security-2026-10-26.md). |
| Security — November 5 | Re-review the exact mobile `decode-uri-component`, `node-forge` and Expo CLI/Zod 3 exceptions by **November 5, 2026**. No deadline, advisory dismissal or mitigation changed. [Security record](security/dependabot-2026-10-05.md). |
| Credential ownership | User-operated revocation of old Apple certificate ending `D6D52` remains unconfirmed; the working replacement ends `FBC7A`. Preserve the old AWS administrator credential consumer-inventory/retirement follow-up. Do not assume creating replacements retired old credentials. |
| OAuth durability | Last recorded Google OAuth External/Testing seven-day authorization follow-up remains open; current console state was not inspected in this pass. |
| Monitoring expansion | Native crashes stay disabled until native payload/memory privacy, symbolication and next-launch delivery are inspected on both platforms. Mobile production reporting needs its own authorized configured native build. |

Production reporting and alert delivery are already complete; they are not remaining setup tasks. Normal unexpected incidents should be reviewed through the existing Sentry rules. No recurring automation or additional paid monitoring product was enabled.
