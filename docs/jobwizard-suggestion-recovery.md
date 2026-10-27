# Jobwizard suggestion recovery — October 23, 2026

The installed PR #120 preview could show a disabled **Suggest details** action after restoring an old request. A deliberate retry enabled the action, but subsequent attempts appeared to flicker without visible feedback. Production router logs showed extraction POST requests rejected with HTTP 400 before a receipt was created. The user confirmed that no error text appeared beneath the action.

A direct production read of the supplied Justworks listing (`https://job-boards.greenhouse.io/justworks/jobs/8179751`) succeeded in 5.416 seconds and returned **Senior Software Engineer, Backend** at **Justworks**. It did not summarize or save a job. This establishes that the clean listing URL is supported; it does not explain the installed client's rejection. No URL allowlist or provider security boundary has been relaxed.

## Recovery and feedback changes

- A definite read-stage rejection (400, 404 or 410) clears its persisted recovery request. It no longer comes back as unknown work when the form reopens. If durable cleanup fails, the original UUID remains available for safe recovery.
- A missing receipt stops repeated timer polling and explains the deliberate same-request retry. A missing GET alone never starts new provider work or discards the frozen request: the original POST could still be committing.
- Same-request retry can finish the summary when the user is still on the matching draft in the foreground. Leaving, backgrounding or changing the draft requires explicit continuation.
- Errors use the app's visible, wrapping error component with accessibility alert semantics. Working and completed suggestions have status text beside the action; completed results explicitly direct the user to the review below the form fields.

## Validation and remaining acceptance

- [x] 94 mobile tests; TypeScript and ESLint.
- [x] Production JavaScript/Hermes exports for iOS, Android and web; EAS upload archive excludes local credential files.
- [x] iPhone 18 Pro / iOS 27 development client against the disposable local fixture: restored missing receipt, deliberate retry, visible unsupported-link rejection, corrected supported URL, two-stage completion and reachable review.
- [x] Verify the final working/complete status copy in the iPhone 18 Pro / iOS 27 development client.
- [x] Pixel 10 / Android 16 API 36.1 development client against the disposable fixture: visible missing-receipt explanation, deliberate same-request retry, visible unsupported-link rejection, rejected request absent after reopening, working/complete status copy and reachable successful suggestion review.
- [x] October 25 replacement iPhone preview [39bb5cb8](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/39bb5cb8-6682-4aed-ae06-fca1f0a3ef94) finished from commit `621ff2706800b1174f874877621fb3f147014b81` (version 1.0.0, build 1). The downloaded IPA passes strict/deep code-signature verification. Its signing certificate and embedded profile both use the replacement serial ending `FBC7A`; the profile includes the registered iPhone and disables debugging. IPA SHA-256: `005d1f518e3a3cf13c7bd050c81986bb7131e947493de33e58d9febbaec3ca9c`.
- [x] October 27: on the existing Sentry-enabled iPhone preview `b12a71da`, the user pasted the exact Justworks link and confirmed “Suggestions appear.” This closes the reported paste-flow acceptance check; it does not identify the original HTTP 400 cause.
- [x] Apply selected suggestions, save and reopen in the disposable iPhone simulator fixture; reviewed title/company and all four bullets persisted.
- [x] October 27: after the unsupported `https://example.com` listing, the user saved title “Recovery check”, company “Test”, and confirmed “Manual save and reopen work” on the same physical iPhone preview. Archiving that disposable production job was suggested but is not confirmed.

The Expo account was upgraded to Starter on October 23. On October 25, the user completed Apple account recovery, created the replacement distribution certificate and assigned a new ad hoc profile (`X5N67M5X4X`) including their iPhone. EAS built the replacement preview non-interactively with frozen credentials and no Apple login. The user will handle Apple sign-in and certificate changes going forward. The old exposed certificate ending `D6D52` still needs user-performed revocation after installing the verified replacement preview; creation of the replacement does not revoke the old one. The two targeted physical-device checks above are now accepted; broader checks remain in the current ledger.

The simulator URL was entered through accessibility automation; it is not evidence for the physical iPhone's paste behavior. Native fixture providers are mocked and incur no Browserless/OpenAI calls. Preserve all earlier unchecked items in [extraction validation](jobwizard-extraction.md), [Jobwizard smoke tests](jobwizard-smoke-test.md), [mobile validation](mobile-ui-validation.md), and [security follow-ups](security/dependabot-2026-10-05.md). Production rollout evidence is tracked separately in PR #121.

Android development automation note: fast hardware-key entry containing two `r` characters within 200 ms triggers React Native's development reload shortcut because Compose fields are not Android `EditText` views. Entering the URL in chunks avoids that shortcut. This observation is limited to the development client and is not evidence for a Release-build paste failure.

## October 25: compact job details

Job details now put **Show listing, Copy link, Edit job, and Archive/Restore job** in an accessible three-dot menu beside the heading. iOS uses a SwiftUI menu; Android uses a native Compose menu; web has a dismissible keyboard-accessible fallback. The caption shows the website and saved date instead of a long URL. Copying reports success without adding a row. Opening retains the safe-URL check; editing and archive/restore retain the existing operation and revision guards.

Each saved bullet has a compact **Source** disclosure beside it; the review form also uses the plain Source link. Evidence and edited/outdated/partial provenance remain intact. Touch targets remain at least 44 points tall.

- [x] iPhone 18 Pro / iOS 27: accessible menu trigger and all four labels, copy feedback, browser handoff, existing edit form, archive/restore, saved and review Source expansion/collapse, compact wrapping layout.
- [x] Pixel 10 / Android 16 API 36.1: native menu opens with all four labels, Copy link feedback, archive then restore the same job, saved Source expansion/collapse, compact layout with wrapped bullets. Native rebuild/install succeeded.
- [x] Web fixture: keyboard focus enters the action dialog, Escape/Cancel dismiss and restore trigger focus, Copy link feedback, Source expansion, and disabled Show listing for the unsafe legacy URL. Full assistive-technology and larger-text passes remain open in the smoke checklist.
- [x] TypeScript, lint, 94 mobile tests, SDK compatibility and all-platform exports. Root/mobile security gates pass with the separately documented October 25 Zod exposure exception; no advisory is dismissed or deadline extended.
- [x] All seven PR checks pass at implementation commit `a54b9b5`; no open CodeQL findings on PR head or merge references. Updated iPhone preview [6424dc30](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/6424dc30-5b56-4de8-bef7-9c1c58abd1d4) finished October 25 at 17:41 UTC from that commit. Its downloaded IPA passes strict/deep signature verification, uses replacement certificate `FBC7A`, includes the registered iPhone, and disables debugging. Version 1.0.0/build 1; SHA-256 `6620f2d0bc0f70cc883511a9b8a6998dc7a0c264dd8304f0d65f73af90286399`.
- [x] The user accepted the compact layout and subsequent form preview before merge. On October 27, the Justworks paste flow also passed in the newer Sentry-enabled physical iPhone preview `b12a71da`.

See [Validation status and follow-ups](validation-status.md) for remaining accessibility, lifecycle, production-diagnosis and user-operated certificate-revocation work. The October 27 recovery fixes have simulator/test evidence; the existing physical preview predates those fixes.
