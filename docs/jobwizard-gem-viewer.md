# Gem capture and in-app screenshot viewer — October 22, 2026

This slice builds on merged PR #117 (`60d36d9`) and production Heroku v147. Browserless capture is enabled there, and the user confirmed that capture works on their physical iPhone. Gem support and this viewer require the new reviewed release. Job-detail extraction remains deferred.

## Scope

Capture accepts public HTTPS `jobs.gem.com/<company>/<jobpost-id>` pages, including known source/UTM attribution and Gem's `src` parameter. Custom domains, application subroutes, fragments, credential-bearing URLs, arbitrary query parameters and nonstandard ports remain unsupported. Saving and opening those jobs still work.

The Gem profile waits for the job heading and rendered description, including fonts and stable layout. Its resources are limited to the existing same-origin/Google Fonts rules plus `static.gem.com`, `usercontent.zscdn.net` and `maxcdn.bootstrapcdn.com`. Cross-origin navigation, frames, media and unrelated resources remain blocked. Description readiness excludes the application form, while the full-page screenshot includes the blank form. Existing one-attempt receipts, two PostgreSQL slots, deadlines, private S3 ownership, image limits and deliberate retries are unchanged.

Open full screenshot now opens a protected Expo Router fullscreen modal using the saved job ID. Signed URLs are fetched through the account-scoped query, never copied into navigation. The image starts at full width and supports pinch/double-tap zoom, panning, zoom/page/reset buttons, and Close or Android Back. Expo Image uses no memory/disk cache; the image is unmounted on account change. Expired access refreshes, and a failed image gets one automatic renewal per artifact followed by an explicit recovery button. Viewing or renewing access never starts a capture.

The implementation uses existing Expo Image, Gesture Handler and Reanimated dependencies. Galeria was inspected but not added: its native loaders and whole-image initial fit do not expose the required cache and tall-image presentation controls. Web remains a scrollable development fallback. No dependency or migration was added.

## Live Gem evidence

Public rendering samples, not job recommendations:

| Listing | Result | Local adapter time | Image |
| --- | --- | ---: | --- |
| [Function Health, Staff Software Engineer](https://jobs.gem.com/function-health/am9icG9zdDpyJtbQYuSC0l_lOd7kZ9-n) | Success | 10.024 s | 1280 × 7692; 1,244,931 bytes |
| [DeepInfra, Software Engineer](https://jobs.gem.com/deep-infra/am9icG9zdDr3xy5kCFcEUbterRQTwOHi) | First attempt: page_not_ready | 10.102 s | No image published |
| Same DeepInfra listing, explicit follow-up | Success | 6.500 s | 1280 × 3446; 392,190 bytes |
| [Bilt, Software Engineer AI](https://jobs.gem.com/bilt/am9icG9zdDp_UbLc7VvvxH5UBGl-J5a0) | Success | 8.374 s | 1280 × 5647; 773,436 bytes |
| Nonexistent Gem job ID | page_expired | 4.338 s | No image published |

A separate DeepInfra diagnostic between attempts found its complete description and fonts ready with no stylesheet failure. The initial failure appears transient; its precise cause is unproven and it is retained in the evidence. There were six deliberate provider sessions including that diagnostic, with no automatic retry/proxy/CAPTCHA. These timings are from the Mac and exclude S3 upload, so they do not establish Gem's production end-to-end latency. The three returned images were visually checked through their final description/form/footer. Provider markup may change and should fail explicitly if readiness no longer matches.

## Validation and release acceptance

Automated: 224 backend tests with real disposable PostgreSQL (one Linux-only parent-death test skipped on macOS), 80 mobile tests, nine root/provider tests, 18 browser security checks, TypeScript, lint, Expo 57 dependency compatibility and iOS/Android/web exports. New tests cover Gem route/query restrictions, resource isolation and image zoom/bounds/pixel limits.

Observed iPhone simulator (18 Pro, iOS 27): protected in-app opening, correct Gem image, double-tap and button zoom, page buttons through the footer, reset, Close back to the same detail, failed-image message and successful manual access renewal. Fixture counts stayed at one existing capture and zero provider calls. Simulator automation delivered zero-distance drag events, so physical pinch/pan acceptance remains open rather than being inferred from the buttons.

- [ ] Install the new internal preview on the physical iPhone. Open an existing screenshot; zoom/pan to all four edges and the footer; reset and Close. Confirm no browser opens and no capture starts.
- [ ] After merge/backend deployment, deliberately recapture the existing Gem job. Verify the final receipt, correct title/description/footer, private delivery and production elapsed time. Retain any previous good image on failure.
- [ ] Confirm full viewer behavior on Android, including Back, zoom, panning and image-error recovery. Record actual interactions separately from exports.
- [ ] Leave active/backgrounded beyond signed-link lifetime; foreground offline, recover online, then sign out/switch account. Verify no prior-account image or completion survives.
- [ ] Complete smaller-device, largest Dynamic Type, dark-mode, VoiceOver and TalkBack checks. Buttons are labelled; screenshot text is still an image, not extracted accessible job text.

All unchecked items in [the Jobwizard smoke checklist](jobwizard-smoke-test.md) and earlier Grocery/Wishlist/Library/Learning checklists remain open. The November 5 dependency-security follow-up and Python runtime patch follow-up are unchanged. Merge/deploy this backend after review; no new provider key, AWS policy, paid plan or capture gate change is needed.
