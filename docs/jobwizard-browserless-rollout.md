# Browserless capture rollout — October 22, 2026

This implements the approved next step after [the public-listing evaluation](evaluations/browserless-2026-10-22.md). Save remains immediate. Capture is a separate, explicit action; no automatic retries, proxy/CAPTCHA services, paid upgrade, browser SDK, database migration or background worker was added.

## Behavior and limits

The adapter uses Browserless's [Function REST API](https://docs.browserless.io/rest-apis/function) to inspect a description before taking one full-page PNG. It requires a visible heading and at least 300 description characters, loaded fonts, and stable description/layout for 1.25 seconds within a bounded readiness window. Known expired, blocked, unavailable and unfinished pages produce an explicit failed receipt. HTTP 200 alone does not mean success. Capture success means a checked image was stored; it does not independently verify every word. The original link and preview remain available.

Supported HTTPS listing routes are Greenhouse (`boards.greenhouse.io`, `job-boards.greenhouse.io`, `job-boards.eu.greenhouse.io`), Lever (`jobs.lever.co`, `jobs.eu.lever.co`), Ashby (`jobs.ashbyhq.com`) and Workday tenant hosts (`*.wdN.myworkdayjobs.com`). Custom domains and other boards remain saveable/openable but are not capturable in this first release. Arbitrary query parameters, fragments and nonstandard ports are rejected; known source/UTM parameters are accepted. Avoid private or tokenized URLs.

Initial DNS must resolve entirely to public addresses. The remote browser restricts main navigation to the same HTTPS origin and resources to the selected platform's enumerated CDN hosts plus Google Fonts. Cross-origin redirects, frames, media and arbitrary resource hosts are blocked. No cookies or logged-in sessions are supplied. This constrains exposure to the evaluated platforms; it is not a claim that hosted Browserless DNS/private-network isolation was independently audited. Third-party images/custom fonts outside the allowlist may be absent. Embedded videos are intentionally omitted.

The controlled Function recipe fixed the long Ashby disclosure-text defect observed with `/screenshot`; it avoids scrollPage and viewport resizing. It is not a claim that every future tall page will render correctly. Text is not removed or rewritten.

The provider has a 16-second global deadline, the child 21 seconds and the parent 22 seconds, including validation and S3 upload. Streams are bounded, decoded images are limited to 24 megapixels, and sanitized PNGs to 8 MiB. Two PostgreSQL session advisory slots limit this app across processes/dynos. The account dashboard and other clients can still consume Browserless capacity. Capacity/quota/authentication/timeouts receive safe, fixed messages. Retrying a completed failed receipt replays it; another capture requires a new deliberate action. Previous good images, owner checks, source-URL tracking, job locks and 15-minute signed URLs are preserved.

## Evidence

Four local adapter captures (one per platform) succeeded in 4.319–7.661 seconds. The long Ashby page rendered its final disclosure paragraphs; the Genesys Workday page rendered through accommodations and equal-opportunity text.

Two captures ran in an isolated one-off Heroku dyno using the production Python runtime and existing private bucket. The modified worker files and existing Browserless token were supplied only to that disposable process; this did not deploy a release, enable the gate or write production jobs.

| Public listing | Capture + private S3 upload | Dimensions | Signed read | Unsigned read |
| --- | ---: | --- | --- | --- |
| Ashby long description | 9.617 s | 1280 × 9090 | 200, private/no-store | 403 |
| Genesys Workday | 11.279 s | 1280 × 5081 | 200, private/no-store | 403 |

Retained readiness objects: `j/4ad24aa38c1a402f8d1db217d0027c7c.png` and `j/6f28bc2b1f8041629f742e2c8d0c603a.png`. The application IAM policy intentionally lacks deletion permission. These are public job-page snapshots stored privately. Signed links and credentials are not in Git.

Automated validation: 223 backend tests (one Linux-only parent-death check skipped on macOS), including real PostgreSQL cross-process capacity/process-death tests; 76 mobile tests; typecheck/lint; 8 root/provider tests; 18 browser security checks; all-platform Expo exports. CI must also pass on the final PR commit.

Native evidence and remaining acceptance are tracked in [the smoke checklist](jobwizard-smoke-test.md). The fixture can load existing readiness images with `JOBWIZARD_PREVIEW_CAPTURE_RESULTS=/absolute/private/results.json`; it never calls Browserless. Fixture data and production saved jobs remain separate.

## Deployment sequence

1. Merge the reviewed PR, then deploy that merged backend to Heroku with `JOBWIZARD_CAPTURE_ENABLED=0`. The currently deployed v144 still uses ApiLeap; enabling it would not enable Browserless.
2. Configure the existing Browserless key as the server-only `BROWSERLESS_API_TOKEN` through a secret-safe method. Keep the verified private bucket/region and existing narrow `j/` IAM policy. Do not put the key in Expo variables, Git, CLI arguments or logs. No new key or broader AWS permission is needed.
3. Install the updated iPhone preview, which names Browserless and displays detailed failures. Older previews retain their old provider disclosure and should not be used for acceptance.
4. Verify health, unauthenticated/private status responses, and the deployed source. Set `JOBWIZARD_CAPTURE_ENABLED=1`, then deliberately capture one supported public listing through the authenticated app. Check the final receipt, preview/full image, signed-only delivery, provider units and no duplicate capture. If this fails, restore the gate to `0` while preserving saved jobs/previous images.
5. Record the release/build IDs and acceptance evidence. Keep Android interaction, accessibility, physical-device, background/relaunch, signed-link expiry and inherited feature validation items open until exercised.

Rollback is the capture gate (`0`); saving/editing jobs continues. Do not delete old captures, old provider credentials or jobs as part of rollback. Review whether the old ApiLeap credential can be retired separately after adoption.
