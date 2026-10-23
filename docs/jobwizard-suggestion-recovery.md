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
- [ ] Install the updated iPhone preview; paste the exact Justworks link; confirm either reviewable suggestions or a visible, actionable error. Record the error if rejected. The original production HTTP 400 cause remains unconfirmed until this check supplies further evidence.
- [x] Apply selected suggestions, save and reopen in the disposable iPhone simulator fixture; reviewed title/company and all four bullets persisted.
- [ ] Confirm manual saving remains available after a rejected extraction on the physical iPhone.

The Expo account was upgraded to Starter on October 23, so the free cloud-build quota is no longer the planned constraint. A replacement signed preview is pending the approved Apple distribution-certificate rotation and Apple sign-in. Keep the existing certificate valid until the replacement preview is ready, then revoke it as approved. No replacement preview is available yet.

The simulator URL was entered through accessibility automation; it is not evidence for the physical iPhone's paste behavior. Native fixture providers are mocked and incur no Browserless/OpenAI calls. Preserve all earlier unchecked items in [extraction validation](jobwizard-extraction.md), [Jobwizard smoke tests](jobwizard-smoke-test.md), [mobile validation](mobile-ui-validation.md), and [security follow-ups](security/dependabot-2026-10-05.md). Production rollout evidence is tracked separately in PR #121.

Android development automation note: fast hardware-key entry containing two `r` characters within 200 ms triggers React Native's development reload shortcut because Compose fields are not Android `EditText` views. Entering the URL in chunks avoids that shortcut. This observation is limited to the development client and is not evidence for a Release-build paste failure.
