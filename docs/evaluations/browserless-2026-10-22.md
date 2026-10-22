# Browserless evaluation — October 22, 2026

**Recommendation: proceed with a small Browserless REST integration, behind the existing disabled capture gate.** The service is fast enough in this local sample to justify retaining the bounded synchronous capture flow initially. Production readiness still requires render checks, the long-page issue below, and a Heroku → Browserless → private S3 timing check. This evaluation does not establish a general success rate or justify enabling capture today.

PR #116 is merged at `a5a536481875aecf75667b2da8983c27cb39f770`. Only the evaluation script, public test manifest and documentation changed. No production jobs, Heroku configuration, S3 objects, subscriptions or app dependencies were changed. The existing API key was used from a mode-0600 temporary file outside the repository, then removed.

## Results

Twelve public listings from four recruiting platforms were checked against current source descriptions. The first recipe produced **9/12 complete, readable job captures**. A separately recorded second recipe fixed both Workday pages, bringing the combined result to **11/12**. One long Ashby listing remains partial. These combined results are not a single-recipe 11/12 benchmark.

| Platform / listing | Initial local time | Download | Dimensions | Initial visual result | Explicit follow-up |
| --- | ---: | ---: | --- | --- | --- |
| Greenhouse / CLEAR | 8.47 s | 666 KiB | 1264×5064 | Complete | — |
| Greenhouse / Scale infrastructure | 8.91 s | 734 KiB | 1264×5058 | Complete | — |
| Greenhouse / Scale enterprise | 7.04 s | 766 KiB | 1264×5374 | Complete | — |
| Lever / SEP | 7.96 s | 367 KiB | 1264×2392 | Complete | — |
| Lever / Filevine | 4.84 s | 581 KiB | 1264×3113 | Complete | — |
| Lever EU / Prima | 4.45 s | 487 KiB | 1264×3259 | Complete | — |
| Ashby / Ashby | 7.35 s | 1718 KiB | 1264×8535 | Two final disclosure lines partly missing; video area blank | 8.80 s: same issue; alternate capture option also failed |
| Ashby / Sentry | 4.36 s | 757 KiB | 1264×2934 | Complete | — |
| Ashby / Mechanize | 4.72 s | 423 KiB | 1264×1761 | Complete | — |
| Ashby / Elicit | 5.56 s | 1312 KiB | 1264×4808 | Complete, including photograph | — |
| Workday / Visa | 5.37 s | 501 KiB | 1264×1376 | Ends during responsibilities | 8.66 s: complete, 1264×3604 |
| Workday / Genesys | 3.39 s | 6 KiB | 1280×900 | Loading dots only | 8.07 s: complete, 1264×5124 |

Initial local latency: **median 5.46 seconds, range 3.39–8.91 seconds**, including unsuccessful visual results. Every capture, including follow-ups, finished below the 18-second local threshold. All passed the existing 8 MiB / 24-megapixel image limits. These times include provider response, download and image sanitization from the Mac, **not Flask startup, database work or S3 upload**. One run per listing cannot establish reliability, a percentile or performance under concurrent load.

Every actual browser capture returned provider HTTP 200 and target HTTP 200, including the loading screen, truncated images and expired-job control. All stylesheet failure counts were zero; each Greenhouse response reported one failed resource without a visible loss of job-description text. Therefore neither HTTP status nor those counters prove screenshot completeness. Workday cookie notices remained visible but did not cover the descriptions in the successful follow-ups.

The known expired SmartRecruiters listing correctly showed an expiration notice, but also returned HTTP 200. It is excluded from the twelve current listings and must not be counted as a successfully preserved job description. The Example Domain positive control was readable in 3.36 seconds.

The Ashby source contains the missing disclosure text in its DOM; a normal signed-out Chrome full-page screenshot also renders it correctly. Browserless reproduced the defect in three deliberate captures. Its main job description, qualifications, interview process and benefits remain readable, but it fails the strict completeness check. The underlying rendering cause is not established. The alternate `captureBeyondViewport: false` experiment also changed image dimensions and added a large blank lower area, so it is rejected as a default.

## Method and accounting

The [public manifest](../../scripts/fixtures/browserless-public-jobs.json) contains exact URLs and selection notes. The [evaluator](../../scripts/evaluate-browserless.py) imports no Flask code, reads no application `.env`, and writes no production database or S3 data. It allows only reviewed public HTTPS hosts, rejects URL credentials/query strings/fragments, checks initial DNS for public addresses, caps bytes/pixels/time, sanitizes images, and uses a fresh output directory for each explicit run. There are no client retries, requested proxies, CAPTCHA solvers, cookies or persistent browser profiles.

All requests used `POST https://production-sfo.browserless.io/screenshot`, provider timeout 18,000 ms, local deadline 22 seconds, 1280×900 requested viewport, scale 1 and full-page PNG. Recipes were:

1. **Initial:** `domcontentloaded` with a 10-second navigation timeout, one-second settling delay, `scrollPage: true`. One positive control, twelve listings and one expired control.
2. **Settled:** same limits, five-second settling delay and `scrollPage: false`. Exactly three selected problem pages, preserving their initial failures in the report.
3. **Viewport-resize:** settled settings plus `options.captureBeyondViewport: false`. Exactly one Ashby probe; rejected.

There were **18 completed browser captures**, with **18 distinct request IDs charged one unit each in Browserless request logs**. Two duplicated display rows were deduplicated by request ID. An earlier HTTP 401 was caused by the browser tool returning a redacted placeholder for the masked key field; it occurred before capture and was corrected explicitly using the existing displayed key. Thus there were 19 local HTTP requests, not 19 browser captures. The evaluator now rejects that placeholder before making a request.

Provider logs also contained browser-unavailable/429 events that did not reach this sequential client as failures; their exact internal cause is unverified. They are not application retries or additional completed captures. The dashboard initially lagged the per-request logs, then reconciled to **18/1,000 units used, 982 remaining**, 18 successful requests, zero proxy/CAPTCHA units and peak concurrency one. No active sessions remained. No paid upgrade or overage occurred.

Raw timing, hashes, visual verdicts, per-request units and request IDs are in [the results JSON](browserless-2026-10-22-results.json). Full images and normal-browser comparisons are retained locally outside Git at `/Users/keithriordan/.codex/visualizations/2026/10/07/01a11437-6281-71e3-aa87-78a540a913da/browserless-evaluation/`. Full job advertisements are not added to the repository as binary fixtures.

## Integration recommendation

Use the hosted REST screenshot endpoint initially: Flask already has Requests/Pillow and the private image pipeline. These results do not show a need to add a local Playwright browser, an SDK, a paid plan or a separate background worker. Keep the 22-second total budget and explicit user-initiated capture; saved jobs must continue to save immediately. A durable background worker remains an option if realistic Heroku measurements or broader target coverage require a longer budget.

The next bounded implementation should:

- Add a server-only Browserless adapter and dedicated credential configuration, preserving ownership checks, durable attempt receipts, lock handling, image limits, private `j/` storage and 15-minute signed delivery. Preserve previous good images on failure and the existing disabled gate until readiness is proven.
- Introduce bounded page-readiness checks for supported hosts, using actual job-description content and stable layout. The five-second delay demonstrates the timing problem; it is not proof that a fixed delay will always suffice. Explicitly classify loading, expired, blocked and unavailable pages. Keep the preview and original listing link: capture completion means an image was stored, not that every word was independently verified.
- Resolve or explicitly scope the long Ashby rendering limitation before claiming complete capture support. Evaluate a focused content capture or controlled rendering recipe in that implementation; do not apply the failed viewport-resize recipe globally or silently recapture at extra cost.
- Cap service-wide concurrency at the free account's two sessions and handle capacity/quota/authentication/timeouts clearly, with deliberate retries only. Verify account-level usage after a real end-to-end readiness check.
- Run regression cases for duplicate capture, interruption, URL edits during capture, preserved previous images, account isolation, malformed/non-image responses, image-size limits and S3 failure. Validate one long description and one dynamic Workday page through Heroku/private S3 and the iPhone preview; Android and accessibility follow-ups remain required.

Before enabling public URL capture, retain the application's URL/DNS checks and document provider-side redirect and network restrictions accurately. The public source has an overridable private-network guard; its default does not establish the hosted cloud's deployed policy. This evaluation did not probe private networks or verify hosted redirect/DNS isolation. Confirm the hosted behavior or constrain the supported target set; initial DNS checking alone is not a complete guarantee. See [Browserless's configuration source](https://github.com/browserless/browserless/blob/main/src/config.ts).

## Data handling and reference documentation

Only public, signed-out listing URLs were sent. Browserless's [request logs](https://docs.browserless.io/overview/request-logs) include target URLs and per-request usage; the free plan offers an eight-hour searchable lookback. That is not a promise that all backend data is deleted after eight hours. Its [privacy policy](https://www.browserless.io/privacy-policy) states that page contents are not retained, while [session replay](https://docs.browserless.io/baas/monitor-sessions/session-replay) is a separate opt-in paid feature. Replay was not enabled. Continue keeping credentials server-side, avoid sensitive URL tokens and private sessions, and retain private S3 delivery for captured images.

Implementation references: [screenshot API](https://docs.browserless.io/rest-apis/screenshot-api), [readiness and response diagnostics](https://docs.browserless.io/rest-apis/request-configuration), [timeouts](https://docs.browserless.io/rest-apis/timeouts), [Puppeteer screenshot options](https://pptr.dev/api/puppeteer.screenshotoptions), and [Heroku request timeout](https://devcenter.heroku.com/articles/request-timeout).

All inherited [Jobwizard smoke checks](../jobwizard-smoke-test.md), native/accessibility follow-ups and the November 5 dependency-security review remain unchanged. This evaluation does not complete the production screenshot or device acceptance checklists.
