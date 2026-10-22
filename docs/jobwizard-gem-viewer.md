# Gem capture and in-app screenshot viewer — October 22, 2026

This slice builds on merged PR #117 (`60d36d9`) and production Heroku v147. Browserless capture is enabled there, and the user confirmed that capture works on their physical iPhone. PR #118 was subsequently merged as `80cd71a` and deployed as Heroku v148; the production verification and width follow-up are recorded below. Job-detail extraction remains deferred.

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

Observed Android emulator (Pixel 10, API 36.1): in-app opening, button zoom, page controls through the footer, reset, Android Back to the same detail, failed-image state and successful manual access renewal. Header spacing was corrected during this check. Drag automation did not establish working panning; physical pinch/pan and TalkBack remain open. Combined viewer fixture results: 32 image reads, 40 status reads, one pre-existing capture, zero capture calls.

The [internal iPhone preview](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/3e975954-9013-4933-abae-a0bcdfa1c789) finished successfully from `b025b1d`. The subsequent source change only adds Android header spacing; iPhone behavior is unchanged. It uses the existing production HTTPS API. Existing screenshots can be viewed immediately; Gem capture requires the reviewed backend deployment.

Native screenshots: [iPhone](assets/jobwizard-gem-iphone.png), [Android](assets/jobwizard-gem-android.png).

- [x] User installed/reviewed the new iPhone preview and confirmed pinch and drag work on the physical device (October 22).
- [ ] Physical iPhone: explicitly confirm all four edges/footer, reset/Close, no browser launch and no extra capture. The user confirmation above establishes pinch/drag, not every remaining checklist item.
- [ ] After merge/backend deployment, deliberately recapture the existing Gem job. Verify the final receipt, correct title/description/footer, private delivery and production elapsed time. Retain any previous good image on failure.
- [x] Android emulator: opening, button zoom, paging, reset, Back and image-error recovery.
- [ ] Physical Android: pinch/pan, accessibility and device-specific performance.
- [ ] Leave active/backgrounded beyond signed-link lifetime; foreground offline, recover online, then sign out/switch account. Verify no prior-account image or completion survives.
- [ ] Complete smaller-device, largest Dynamic Type, dark-mode, VoiceOver and TalkBack checks. Buttons are labelled; screenshot text is still an image, not extracted accessible job text.

All unchecked items in [the Jobwizard smoke checklist](jobwizard-smoke-test.md) and earlier Grocery/Wishlist/Library/Learning checklists remain open. The November 5 dependency-security follow-up and Python runtime patch follow-up are unchanged. Merge/deploy this backend after review; no new provider key, AWS policy, paid plan or capture gate change is needed.


## Production deployment and capture-width follow-up

Merged PR #118 (`80cd71a`) deployed to Heroku v148 on October 22. The web dyno is up; public home returns 200, unauthenticated capture status returns 401, authenticated private status returns 200 with `private, no-store`, and migration remains `e1f2a3b4c5d6`. Deployed Gem policy/recipe hashes match the reviewed source. The existing provider key, capture gate and private storage configuration are unchanged.

A single production capture of the existing Gem job returned a success receipt in 10.901 seconds, but visual verification showed a clipped right edge: the PNG was 800 × 7692 instead of the intended 1280-pixel width. HTTP success and valid PNG bytes did not establish complete content. That verification receipt was corrected to `failed`; its private object was retained and is no longer offered as a successful image. No prior user capture was changed.

The follow-up captures the measured document rectangle explicitly with `clip` and `captureBeyondViewport`, avoiding reliance on the hosted browser's `fullPage` sizing. The worker also compares decoded image dimensions against the measured bounds before upload; missing/malformed bounds, or clipped width/height, fail without storage or an automatic retry. This is a fidelity fix, not a claim that dimensions alone prove every word is present. [Puppeteer screenshot option reference](https://pptr.dev/api/puppeteer.screenshotoptions).

Two isolated Heroku readiness captures with the modified files succeeded without changing the deployed release or saved jobs:

| Listing | Dimensions | Capture + private upload | Visual check |
| --- | --- | ---: | --- |
| Same Function Health Gem listing | 1280 × 7692 | 9.618 s | Full title/right edge and form/footer visible |
| Previously tested long Ashby listing | 1280 × 9090 | 7.812 s | Final benefits and both disclosure paragraphs visible |

The corrected Gem [top](assets/jobwizard-gem-width-top.png) and [footer](assets/jobwizard-gem-width-footer.png) are retained as evidence. Readiness objects remain private under `j/6f985eb13c29463a98349d6fe0c149b1.png` and `j/ed0d4c386e634fb8977a2fc5b197759d.png`; the app identity has no deletion permission. This follow-up passed 225 backend tests with real disposable PostgreSQL (one Linux-only skip on macOS) and all nine root/provider tests. A regression test proves clipped and malformed dimensions never reach S3 or retry the provider.

The width fix still needs review/deployment before production Gem capture can be accepted. No new iPhone build, migration, dependency, credential or AWS permission is needed. All remaining lifecycle, privacy, accessibility, Android gesture and security follow-ups stay open.
