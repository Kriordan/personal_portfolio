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
- [ ] Install the updated iPhone preview; paste the exact Justworks link; confirm either reviewable suggestions or a visible, actionable error. Record the error if rejected. The original production HTTP 400 cause remains unconfirmed until this check supplies further evidence.
- [x] Apply selected suggestions, save and reopen in the disposable iPhone simulator fixture; reviewed title/company and all four bullets persisted.
- [ ] Confirm manual saving remains available after a rejected extraction on the physical iPhone.

The Expo account was upgraded to Starter on October 23. On October 25, the user completed Apple account recovery, created the replacement distribution certificate and assigned a new ad hoc profile (`X5N67M5X4X`) including their iPhone. EAS built the replacement preview non-interactively with frozen credentials and no Apple login. The user will handle Apple sign-in and certificate changes going forward. The old exposed certificate ending `D6D52` still needs user-performed revocation after installing the verified replacement preview; creation of the replacement does not revoke the old one. Physical-device acceptance remains unchecked above.

The simulator URL was entered through accessibility automation; it is not evidence for the physical iPhone's paste behavior. Native fixture providers are mocked and incur no Browserless/OpenAI calls. Preserve all earlier unchecked items in [extraction validation](jobwizard-extraction.md), [Jobwizard smoke tests](jobwizard-smoke-test.md), [mobile validation](mobile-ui-validation.md), and [security follow-ups](security/dependabot-2026-10-05.md). Production rollout evidence is tracked separately in PR #121.

Android development automation note: fast hardware-key entry containing two `r` characters within 200 ms triggers React Native's development reload shortcut because Compose fields are not Android `EditText` views. Entering the URL in chunks avoids that shortcut. This observation is limited to the development client and is not evidence for a Release-build paste failure.
