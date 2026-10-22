# Jobwizard extraction evaluation — October 22, 2026

## Decision

Proceed with the approved **review-before-save** implementation using Browserless for public text, deterministic title/employer parsing, and `gpt-6-luna` for factual highlights. The evaluation supports this direction; it does **not** establish production readiness or unattended accuracy. Keep manual saving available, source excerpts visible, and failed/partial results explicit. No production deployment, database change, or mobile change occurred in this evaluation.

Ten usable real listings cover Gem, Greenhouse, Lever, Ashby and Workday, two each. A six-case synthetic set checks negative sponsorship language, degree alternatives, confidential employers, multiple currencies, conflicting work arrangements, dense constraints and an embedded instruction attack. The [labelled assertions](../../scripts/fixtures/job-extraction-labels.json) were prepared from source review before model scoring; they are not model inputs.

**Results:** direct titles matched all ten listings; employers were corroborated on nine. Booz Allen's Workday legal-entity label could not be corroborated sufficiently, so the employer is explicitly missing for manual entry. No material invented pay, location eligibility, sponsorship or qualification was observed in the retained final summaries. Eight listings cover the labelled critical checks; the two longest/most constrained listings retain useful but partial summaries with review warnings. This is an assisted manual audit of a small selected sample, not a statistical accuracy claim.

## What the real pages taught us

| Platform / listing | Result and material finding |
| --- | --- |
| [Gem / Function Health](https://jobs.gem.com/function-health/am9icG9zdDpyJtbQYuSC0l_lOd7kZ9-n) | Correct title/employer, US/Canada eligibility and experience threshold. Required frontend/backend skills remain distinct from nice-to-haves. No pay was invented. |
| [Gem / Bilt](https://jobs.gem.com/bilt/am9icG9zdDp_UbLc7VvvxH5UBGl-J5a0) | Gem uses multiple description sections. The initial reader captured only the introduction; the corrected reader includes the final compensation section. Preserves office location, level-dependent pay, bonus and equity. |
| [Greenhouse / CLEAR](https://job-boards.greenhouse.io/clear/jobs/8107053) | No JobPosting JSON-LD. A title-matched page-title pattern supplies `CLEAR - Corporate`. Summary correctly treats the stated range as total compensation including equity. |
| [Greenhouse / Scale AI](https://job-boards.greenhouse.io/scaleai/jobs/4665557005) | Preserves the repeat-application waiting period. Separates the job's listed cities from Seattle in the pay disclosure, with a review warning. |
| [Lever / SEP](https://jobs.lever.co/sep/80cd8c15-bafc-49a9-b8f1-5d407e891ec0) | Preserves US work authorization, no sponsorship, OPT/CPT exclusion, no relocation funding, and professional-experience requirements. |
| [Lever / Filevine](https://jobs.lever.co/filevine/0679e9c6-2033-43ac-bd3c-d50f0c76439e) | The visible header says on-site; the description permits remote/hybrid arrangements. Summary retains both and asks the user to confirm. |
| [Ashby / Ashby](https://jobs.ashbyhq.com/ashby/0f5dbf59-687b-4d88-88a7-73ee0a66b48d) | Partial: preserves US remote scope, on-call and in-person meetings. Pay is condensed by level; exact location-specific bands and the optional-stack qualification need the source view. Server forces an additional-details warning. |
| [Ashby / Sentry](https://jobs.ashbyhq.com/sentry/5ee81d6f-e837-43bb-af06-8f26c992a766) | JSON-LD says TELECOMMUTE while visible text requires three San Francisco office days. The summary preserves the visible attendance requirement and the base-pay distinction. |
| [Workday / Genesys](https://genesys.wd1.myworkdayjobs.com/en-US/Genesys/job/Software-Engineer_JR112513-1) | Uses the role heading rather than “Careers at Genesys.” Visible brand corroborates the longer legal entity. Preserves Galway attendance and degree/language alternatives. |
| [Workday / Booz Allen](https://bah.wd1.myworkdayjobs.com/en-US/BAH_Jobs/job/Software-Engineer_R0247468) | Partial: employer needs manual entry. Preserves clearance/polygraph, assessment, interview restrictions and deadline. Education/experience alternatives are condensed, with an additional-details warning. Generic remote-policy boilerplate is not treated as this role's work arrangement. |

The Visa and Cisco candidates did not reach readiness within the allowed window. Their failures remain recorded; Booz Allen is an explicit replacement. Do not count a failed page or an HTTP 200 alone as a usable listing. There were 24 deliberate Browserless requests across the initial reader, targeted repairs, final set and replacement—not ten total requests. No automatic retries, proxies, CAPTCHA bypasses, application submissions or screenshot uploads were used.

## Prompt and evidence selection

The deterministic comparator selects up to eight short verbatim blocks by constraint/pay/location/requirement keywords. It performs adequately on SEP, but misses context split across paragraphs, ranks company funding as compensation, loses long salary disclosures and includes generic remote-policy text. It is a simple comparator, not a claim that all non-AI approaches were exhausted.

Three prompt versions were evaluated on frozen public text:

| Version | Public responses | Finding |
| --- | --- | --- |
| 1: generated quotes | 10/10 valid JSON | Some bullets reached the character limit awkwardly; some quotes covered only part of a bullet; two Function Health bullets were rejected by evidence/number checks. |
| 2: shorter bullets | 10/10 valid JSON | Better prose, but repeated quotations increase response size and still require exact-match checks. |
| 3: source references | 8/10 valid JSON on first attempt | Model returns source IDs. Server attaches the exact saved excerpts. One malformed response and one timeout were rejected. Separately recorded deliberate follow-ups succeeded 2/2. |

**Do not report the final recipe as a single-run 10/10 success.** Every failure remains in the [results JSON](jobwizard-extraction-2026-10-22-results.json). Two follow-ups demonstrate recovery, not a measured reliability rate. No malformed output is silently repaired and no timed-out request is automatically replayed.

Selected versions: parser `job-text-2`, prompt `job-summary-3`, validator `job-evidence-2`. Input consists only of normalized public listing blocks, each at most 400 characters and at most 80,000 characters in total. The model has no tools or conversation history. Responses use `store: false`; the [API data controls](https://developers.openai.com/api/docs/guides/your-data) still describe default abuse-monitoring retention. Source IDs are validated and their excerpts are supplied by the server, not generated by the model. Numeric facts must occur in cited blocks. These checks do not prove semantic entailment.

The server conservatively flags uncited constraint blocks, complex pay scales, long sources, rejected bullets and reported conflicts. It never relies solely on the model's “more details” flag. Source provenance indicates where a suggestion came from, not that every implication has been independently verified.

Final synthetic results: five complete cases and one partial result. In the dense-constraint case, a travel percentage cited the wrong block; the numeric guard removed that bullet and forced a partial-result warning. The embedded instruction to fabricate high pay, sponsorship and worldwide remote eligibility was ignored. All synthetic inputs remain in [the fixture file](../../scripts/fixtures/job-summary-adversarial.json).

## Latency, usage and cost

The chosen public page reads took **2.58–8.26 seconds**, median **4.45 seconds**. The final recipe's eight first-attempt successes took **3.10–4.49 seconds** to summarize. Its failures took 9.76 seconds for malformed output and 11.04 seconds for a network timeout. Follow-ups took 6.20 and 4.50 seconds. These are local observations, not Flask/Heroku end-to-end timings or load-test percentiles. The proposed separate 20-second read and 12-second summary requests remain appropriate to validate during implementation.

The tested model was exactly `gpt-6-luna`, with reasoning disabled. Current documented rates per million tokens are $0.10 input, $0.125 cache writes, $0.01 cached input and $0.50 output. The evaluator records actual input/cache/output token counts. See [the official model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna).

- Estimated model cost for a successful cold summary: **$0.00040–$0.00106 per listing**, mean about **$0.00061** (about six cents per 100 summaries).
- Known model usage across all evaluation versions and follow-ups: **$0.02617**. One timed-out request returned no usage and may still be billable; it is excluded from that known total.
- There were 51 OpenAI attempts: one initial credit-balance rejection, 48 calls across three versions/public-plus-synthetic sets, and two deliberate follow-ups. No key or arbitrary provider error body is stored in the report.
- Browserless remains a separate request/allowance cost. This evaluation did not reconcile its request logs or current billing, so the model estimate must not be presented as an all-inclusive infrastructure price. Recheck the existing account allowance before enabling the feature in production.

Keep this named model configurable server-side. No dated snapshot identifier was returned by the API or established by the model documentation. Re-evaluate after an intentional model/prompt/parser change; no evidence here requires a larger model or paid Browserless upgrade.

## Code and checks

The evaluation added reusable bounded normalization/validation, a separate Browserless text operation, explicit local evaluation scripts, labelled synthetic fixtures, and regression tests. Screenshot capture still uses its existing measured full-page bounds; extraction does not depend on font readiness or screenshot pixel limits.

Passed locally:

- 12 Python parser/validator tests: malformed/ambiguous metadata, missing employer, confidential name, limits/redirects, source preservation, server excerpts, unknown IDs, numeric rejection and coverage warnings.
- Actual headless-Chrome extraction checks: hidden/form/navigation content excluded, multiple/nested description sections, header constraints, complete tail and oversize rejection.
- Existing screenshot/resource-policy and dependency tests, plus text-operation checks for blocked pages and independence from image limits/fonts.
- Existing browser security checks; Python compilation and diff whitespace checks.

Full raw captures, model responses and source hashes are retained locally outside Git at `/Users/keithriordan/.codex/visualizations/2026/10/07/01a11437-6281-71e3-aa87-78a540a913da/jobwizard-extraction-evaluation/`. Repository results contain metadata and findings, not full third-party job advertisements or credentials.

## Next implementation work

Continue the [approved plan](../jobwizard-extraction-plan.md): owner-scoped durable read/summary attempts, additive accepted-details storage, fenced/idempotent provider operations and the shared new/existing-job review UI. Preserve missing-employer input, partial warnings, visible conflicts, deliberate retry and immediate manual saving. Do not hide a source's location-specific pay ranges behind an aggregate range without a details warning.

Before rollout, validate populated PostgreSQL migration/ownership/concurrency/recovery, old/new-client compatibility, native iPhone/Android review and accessibility, and a recorded iPhone preview. Complete CI/CodeQL and deploy only through the planned gated release. The earlier screenshot/device/lifecycle follow-ups, November 5 security review and Python runtime patch remain open; this evaluation closes none of them.
