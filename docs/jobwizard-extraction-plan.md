# Jobwizard detail extraction plan

October 22, 2026. Proposed next slice: suggest the job title, employer and a short factual summary from a public listing, let the user review the result, and save only the details they accept. Preserve immediate manual saving and optional screenshot capture afterward.

Evaluation checkpoint (October 22): see [the real-listing evaluation](evaluations/jobwizard-extraction-2026-10-22.md) and its recorded failures/partial results. Selected candidate is `gpt-6-luna`, with server-supplied excerpts from model-selected source IDs. The local key is configured and tested. Backend persistence and mobile review/save are implemented; see [implementation and validation](jobwizard-extraction.md). Production configuration and physical-device acceptance remain outstanding.

## Baseline and product decisions

Start from merged PR #119, `9fae9dd2f3ddd6f2c72e68c041dd2df9df64158a`, deployed as Heroku v149. Its production Gem check returned a complete 1280 × 7692 image in 11.675 seconds; title/right edge/footer and private delivery were verified. This supersedes the awaiting-deployment statements in the earlier Gem documents. The user confirmed the existing iPhone viewer's pinch and drag.

Keep Expo 57, Expo Router, @expo/ui, TanStack Query, Flask and PostgreSQL. Prioritize iOS, support Android, and retain web as a development convenience. Read the exact SDK 57 documentation before changing mobile code.

The user confirmed the three product choices on October 22: extraction before saving and on existing jobs, a factual listing summary, and OpenAI for the bullet summary using public listing text only. The remaining behavior below defines the recommended implementation.

| Decision | Selected behavior and implementation defaults |
| --- | --- |
| Entry points | Suggest details after pasting a URL in Add job, and on existing job details. |
| Saving | Review/edit suggestions before saving. Manual title/company/URL entry and immediate saving remain available. |
| Important details | Up to eight factual bullets. Prefer fewer useful bullets over filling a quota. |
| Summarization | OpenAI summarizes only the public listing text. Extract title/company directly where possible. This requires a separate server-side API key and metered API usage. |
| Replacement | Never silently overwrite manual fields or a saved summary. Existing values require explicit selection before replacement. |
| Screenshot | Independent optional action; extracting details neither creates nor requires an image. |

Personalized fit scoring, resume comparison, application tracking, background imports, additional ATS platforms and screenshot/OCR extraction are deferred. OpenAI is the selected summary provider; model selection, server-side key configuration and measured quality/cost remain implementation tasks.

## User flow

In Add job, put the listing URL first and offer **Suggest details**. Explain that Browserless reads the public page and, when enabled, OpenAI summarizes its listing text. Keep manual title/company fields available. Save continues to require valid title, company and URL; a URL-only saved-record model is outside this slice.

Show **Reading listing…**, then **Preparing suggestions…**, followed by a review with editable title/company and removable/editable bullets. **Use suggestions** fills the draft; **Save job** commits it. Editing the URL invalidates pending suggestions. A late response must not overwrite fields typed while extraction was running. Leaving the screen preserves recovery information, not an assumption that work finished.

For an existing job, **Suggest details** opens the same review with current and proposed values. Default to retaining nonempty title/company and any existing summary until the user chooses replacements. Apply accepted fields together using the current job revision and the existing mutation receipt pattern. A conflict preserves the draft for comparison with the latest saved record.

On job details, put **Important details** above the screenshot, rendered as selectable accessible text. Include **From listing · fetched date** and an expandable **View source** excerpt for each generated bullet. Edited bullets are labelled as edited by the user; do not imply their new wording was model-verified. Changing the listing URL retains the previous summary with a clear outdated label. Refreshing never re-extracts automatically.

## What to extract

| Field | Rules |
| --- | --- |
| Job title | Preserve the role's actual title and level; remove only verified job-board decoration. |
| Company | Identify the hiring organization, not Gem, Workday or another hosting platform. Preserve confidential-employer wording rather than guessing. |
| Location and work arrangement | Include office locations, remote/hybrid/on-site, eligible countries/states, time-zone restrictions and office attendance when stated. Remote does not mean worldwide. |
| Compensation | Preserve currency, range, pay period and location-specific qualifications. Distinguish base pay from bonus/equity. Never estimate missing pay. |
| Employment | Full-time, part-time, contract or internship, and contract duration when stated. |
| Responsibilities | One or two concise bullets describing the main work. |
| Requirements | Essential skills, experience or qualifications; keep required and preferred distinct. |
| Other constraints | Explicit sponsorship/work authorization, travel, clearance, deadline or application instructions. A question on an application form is not evidence of the employer's policy. |

Omit absent facts from the compact summary. In review, make missing title/company and material ambiguities explicit. Preserve negative statements and alternatives: “no sponsorship” must not become “sponsorship,” and “degree or equivalent experience” must not become “degree required.” Avoid generic culture/benefits boilerplate when it displaces a useful constraint. If there are more material constraints than eight bullets can represent faithfully, flag additional detail rather than claiming completeness.

## Extraction design

The existing Browserless recipe already selects a heading and rendered description for readiness, but returns only the image and dimensions. Separate the shared navigation/readiness policy from screenshot creation, and add a text extraction operation. Preserve the deployed explicit-bounds screenshot path and its image-dimension validation.

1. Accept only the currently supported public Gem, Greenhouse, Lever, Ashby and Workday URL forms. Reuse host/resource restrictions, same-origin navigation checks, deadlines and shared Browserless capacity. Do not turn the Flask server into an arbitrary URL fetcher.
2. Read bounded `JobPosting` JSON-LD, including arrays and `@graph`, and match it to the current listing. Parse it as data without executing it or fetching linked contexts. Candidate fields include title, hiringOrganization, employmentType, jobLocation, applicantLocationRequirements, baseSalary and validThrough. The [JobPosting reference](https://developers.google.com/search/docs/appearance/structured-data/job-posting) defines these fields; their presence and accuracy still need validation on each page.
3. Cross-check structured candidates against visible heading/employer/description. Use tested platform-specific selectors when structured data is missing. Conflicting or multiple unmatched postings produce a partial result for review. Do not infer an employer from a URL slug, or blindly use the page title as the job title.
4. Extract bounded visible description blocks with stable source IDs, preserving headings and lists. Exclude navigation, cookie overlays, related jobs, application forms, hidden content and scripts. Use profile-specific readiness; extraction should not depend on image pixel limits or font-loading rules needed only for screenshots. Return an explicit incomplete/too-large state instead of silently dropping the end of a long description.
5. Send only normalized public listing text and relevant structured facts to a small text model through the OpenAI Responses API with a strict schema. No browsing tools, external actions, images, account data, private notes or credentials are supplied to the model. Browserless's existing [Function API](https://docs.browserless.io/rest-apis/function) can return extracted JSON, so another browser provider is unnecessary.
6. Require each suggested field/bullet to reference source block IDs and supporting excerpts. Validate lengths, enums, source membership, quote matches and numeric facts before presenting the result. Invalid or unsupported items are omitted with a partial-result explanation. Source matching improves auditability but does not prove the summary's meaning; review and evaluation remain necessary. [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) constrains the response shape, not factual correctness.

Treat all page content as untrusted input, including instructions embedded in descriptions or JSON-LD. The model has no tools or authority to modify a job. Escape all displayed source text and never render scraped HTML. Missing values stay missing. Do not show model-generated confidence percentages.

Use `store: false` for Responses and no conversation history. This does not promise zero provider retention: OpenAI documents default abuse-monitoring retention of up to 30 days, subject to its stated exceptions and approved controls. See [API data controls](https://developers.openai.com/api/docs/guides/your-data). The app's disclosure should identify the actual data and providers involved.

Screenshot-based extraction remains a fallback proposal for a later slice, particularly for expired pages with a saved image. Tall images require careful handling and vision models have documented [small-text and other limitations](https://developers.openai.com/api/docs/guides/images-vision). The first release reads the current page; it must not imply that new text came from an older screenshot.

## Persistence and reliable completion

Add an owner-scoped extraction attempt that can exist before a job is saved. Record its request ID, optional job ID, frozen source URL/revision, stage/status, timestamps, error code, structured candidates, bounded source blocks/hash, result, and parser/model/prompt versions. Draft attempts do not appear as saved jobs.

Add optional accepted details/provenance to the job through an additive migration. Retain current required fields, IDs, ownership, archive state, dates and screenshots. Keep summaries out of the collection response unless needed there; the detail response returns them. Legacy API and website edits must preserve details they do not submit. Website details can display the accepted bullets without a separate website redesign.

Proposed operations:

| Operation | Behavior |
| --- | --- |
| POST `/jobwizard/extractions` | Read the validated listing once and commit its source/metadata receipt. An existing job must be owned by the caller. |
| POST `/jobwizard/extractions/<id>/summary` | Summarize that stored source once, without loading the page again. |
| GET `/jobwizard/extractions/<id>` | Read durable status/result; never initiate paid work. |
| Existing create/PATCH | Accept reviewed details and an owner-checked extraction reference atomically with the saved job and mutation receipt. |

Use two bounded server requests because [Heroku's initial request timeout is 30 seconds](https://devcenter.heroku.com/articles/request-timeout). The foreground UI can chain the two stages as one deliberate action. Target a maximum of 20 seconds for reading and 12 seconds for summarizing, including their subprocess/network deadlines and persistence margin; validate these budgets under load. Do not append a model call to the existing 22-second screenshot operation or run untracked background threads. This release does not promise unattended completion after the app closes between stages; show **Continue preparing details** when only the source stage completed.

Reuse idempotency, database fencing/capacity and interrupted-operation recovery patterns. Duplicate requests cannot start duplicate provider calls; receipt lookup follows a lost response. An explicit retry of a failed stage creates a new linked attempt, leaving prior successful data intact. Backgrounding/reconnecting performs status reads, not automatic paid retries. Logout clears local account recovery/cache state and suppresses late callbacks.

Preserve metadata if summarization fails, and preserve accepted details if re-extraction fails. Show distinct unsupported, expired, blocked, incomplete, provider-unavailable, rate-limit, failed and interrupted states. An HTTP 200 alone is not extraction success.

Use one active extraction per account, share the existing two Browserless slots across capture and extraction, and add separate summary concurrency/rate limits. Bound normalized source to 80,000 characters and each review to eight bullets of at most 300 characters. Reject excess source rather than silently truncating it. Keep unaccepted source/drafts for 24 hours, deny access after expiry, and prune them through a maintenance path; accepted fields retain only the source excerpts/provenance needed for review. Track stage timing and usage counts without logging listing text, keys or signed URLs.

## Bounded first deliverable and validation

One cohesive PR delivers URL-to-review for new and existing jobs, title/company suggestions, editable source-backed bullets, accepted-detail persistence, reliable stage receipts and the iPhone/Android UI. Screenshots stay independently available. Enable live AI summarization after the selected OpenAI model, key configuration and measured quality/cost are settled.

Begin with a labelled evaluation of at least two public listings from each supported platform, plus fixtures for missing/malformed JSON-LD, multiple jobs, confidential employers, absent salary, multiple currencies/locations, negative sponsorship language, preferred-versus-required qualifications, very long text, expired/blocked pages and embedded prompt injection. Reuse the earlier public-listing set where still available and record replacements for expired URLs.

Compare a deterministic baseline with a small structured-output model. Select and pin the least costly model that meets the acceptance criteria; record its exact name, current rates, token usage, total estimated cost per listing and stage latency before enabling it. Model availability, account credentials and cost have not been established by this planning task.

Acceptance requires correct title/employer on every labelled supported sample, or an explicit missing/ambiguous result. All displayed material facts must be supported; no invented compensation, location eligibility, sponsorship or qualifications are acceptable. Report extraction coverage separately from correctness, and explicitly score omissions of critical constraints. Schema validity alone does not pass evaluation.

Automated checks cover populated PostgreSQL migration preservation, owner isolation, URL/resource policy, input/output bounds, malformed/provider responses, refusal, numeric/source validation, process death, concurrent/double submissions, request replay, uncertain outcomes, stage recovery, URL changes, stale edits and account switching. Verify real fake-provider call counts. Run the backend/PostgreSQL, mobile, root/provider and browser-security suites; mobile typecheck/lint, Expo 57 checks, all-platform exports, dependency audits and CI/CodeQL. Preserve every screenshot regression, including the Gem width and long Ashby footer cases.

Native checks exercise paste URL → suggest → edit/remove → save → reopen, existing-job comparison, manual-save fallback, missing metadata, provider failure, keyboard, smaller iPhone, largest text, light/dark, VoiceOver/TalkBack, background/foreground and account switch. Create a new internal iPhone preview from a recorded commit. Record Android interaction evidence separately from build success.

### Smoke checklist

- [ ] Save a job manually with extraction disabled or unavailable; no browser/model call occurs.
- [ ] Extract a supported public listing; verify title/company and every bullet against the source, including omissions and negative constraints.
- [ ] Edit title/company and a bullet, remove another bullet, save and reopen; accepted values and provenance persist.
- [ ] Extract for an existing job; decline replacements, then deliberately apply selected changes without losing screenshots or archive state.
- [ ] Change the URL or type while extraction runs; no stale response overwrites the current draft.
- [ ] Double-tap, lose a response, background/relaunch and reconnect; receipts establish the result without duplicate provider work.
- [ ] Fail each provider stage separately; manual saving and previously accepted details remain usable.
- [ ] Test two accounts and late callbacks; no extraction, source excerpt or saved details cross accounts.
- [ ] Verify readable native text, keyboard reachability, long bullets, accessibility and full screenshot viewing on iPhone and Android.
- [ ] After review/merge, deploy the additive backend with extraction disabled, verify old/new-client compatibility, configure the approved provider, then enable and perform one deliberate production acceptance check. Record migration, release, preview, usage and source identifiers.

## Follow-ups preserved

Keep all unchecked items in [mobile validation](mobile-ui-validation.md), [Jobwizard smoke tests](jobwizard-smoke-test.md), [Gem/viewer evidence](jobwizard-gem-viewer.md), and the Grocery/Wishlist/Library/Learning checklists open unless directly observed. In particular retain physical Android pinch/pan; the remaining physical iPhone edges/footer/reset/Close checks; background/expiry/offline/account-switch behavior; smaller devices, large text, dark mode and VoiceOver/TalkBack; the November 5 [dependency-security review](security/dependabot-2026-10-05.md); and the Python runtime patch follow-up. Production v149 acceptance closes the Gem capture-width deployment check only.
