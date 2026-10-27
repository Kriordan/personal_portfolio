# Jobwizard detail extraction — October 22, 2026

**Current status:** see the [validation ledger](validation-status.md) for October 27 acceptance and remaining work. The production record below consolidates the documentation from PR #121; its original first-cleanup/concurrency follow-ups remain open unless explicitly verified.

## Delivered behavior

Based on merged PR #119 (`9fae9dd`, production v149), this slice implements the approved [plan](jobwizard-extraction-plan.md) and [real-listing evaluation](evaluations/jobwizard-extraction-2026-10-22.md). Expo 57, Expo Router, @expo/ui, TanStack Query, Flask and PostgreSQL remain in place.

Paste a supported public Gem, Greenhouse, Lever, Ashby or Workday listing into Add job, then choose **Suggest details**. Browserless reads the page; OpenAI prepares up to eight factual bullets using only public source text. Manual saving remains available if either stage is unavailable. Screenshot capture remains a separate action after saving.

Review title, employer, editable/removable bullets and original source excerpts. **Use selected suggestions** fills the draft; **Save job** persists it. Nonempty manual fields and an existing summary default to preservation. Existing jobs show current and proposed values; replacements require explicit selection. Late manual typing is protected, and URL/revision mismatches cannot apply old suggestions. A previous listing URL can be deliberately restored after reopening an unfinished new-job flow.

Saved details appear above Screenshot on mobile and on the existing website detail page. They show the fetched date, original excerpts, edited labels and a partial-result warning when needed. A URL edit preserves the old summary with an outdated label. Refresh and app recovery never start new provider work. Unsaved review edits are in memory; leaving a review requires confirmation, and reopening recovers the server suggestions, not unsaved wording.

## Persistence, limits and operations

Migration `f2a3b4c5d6e7` adds nullable `job.accepted_details` and owner-scoped `job_extraction` receipts. Existing fields, ownership, archives and screenshots are preserved. Collection responses omit accepted details; detail and mutation responses include them. Legacy updates preserve details they do not submit.

- `POST /api/v1/jobwizard/extractions`: caller-generated UUID, frozen URL and optional owned job/revision; commits a source receipt before returning.
- `POST /api/v1/jobwizard/extractions/<id>/summary`: consumes that source once. Replaying a completed/failed request does not call a provider again.
- `GET /api/v1/jobwizard/extractions/<id>`: owner-scoped recovery only. Lost-process operations become interrupted under the account lock.
- Job create/PATCH accepts selected bullet indices and edited text atomically with the job and existing mutation receipt. Excerpts come from the server, never from caller-supplied provenance. Revision conflicts preserve the mobile draft. After comparing a newer revision, stale selected bullets must be discarded or re-extracted before saving; the client explains this before sending another rejected mutation.

One extraction runs per account. Extraction and capture share two Browserless slots; summarization has one separate slot. Persistent limits allow ten new extraction attempts and twenty summaries per account/hour. An explicit failed-summary retry creates a linked receipt and reuses the original source without extending its expiry. Paid calls are not automatically retried after failure, backgrounding, reconnect or restart.

Read workers have an 18-second alarm/19-second parent timeout; summary workers use 10/11 seconds. These leave normal persistence overhead below Heroku's initial 30-second router limit, but do not establish a hard database-lock/load SLA. Production timing under concurrent capture/extraction remains a rollout check. Status receipts handle an uncertain client response.

Normalized source is capped at 80,000 characters; excess input is rejected rather than truncated. Output is bounded to eight 300-character bullets. Strict schema, source IDs and numeric checks reject malformed or unsupported output; semantic correctness still needs review. Instructions in a listing are data, and the model receives no tools, user profile, notes, screenshot or credentials. Responses use `store: false`; this is not a promise of zero provider retention.

Unaccepted source expires after 24 hours and becomes inaccessible. Run `flask --app project prune-job-extractions` daily through the deployment's maintenance scheduler. Expired receipts/source are deleted, while accepted excerpts and job mutation receipts remain durable. Extraction UUID replay protection lasts while the receipt exists; clients must use a fresh UUID for deliberate work after expiry. Acceptance immediately removes the full source/result from the extraction receipt. Logs/API errors contain fixed codes/messages rather than provider bodies or secrets.

Server configuration (enabled after merge; see the production rollout below):

| Variable | Value/purpose |
| --- | --- |
| `JOBWIZARD_EXTRACTION_ENABLED` | `1` enables new work; absent/other values disable it |
| `BROWSERLESS_API_TOKEN` | Existing server credential, shared with capture |
| `OPENAI_API_KEY` | Server-only credential; never an Expo public variable |
| `JOBWIZARD_SUMMARY_MODEL` | Defaults to evaluated `gpt-6-luna` |

## Validation evidence

Automated providers are mocked except the explicitly recorded public-listing evaluation, final Gem readiness check and production rollout below. Native checks use `scripts/jobwizard-preview-fixture.py`, disposable SQLite/accounts and fake providers. Those fixture checks do not write production jobs or incur provider charges.

| Check | Result |
| --- | --- |
| Backend unit/integration discovery | 251 tests pass; one Linux-only parent-death case skipped on macOS |
| PostgreSQL 18 | Populated upgrade/downgrade, process death, locking and cross-process replay cases ran locally; no PostgreSQL skip |
| Python consistency/security | Poetry lock check, `pip check`, pip-audit pass |
| Mobile | 89 tests, TypeScript, ESLint and local SDK 57 compatibility pass |
| Exports | Web, iOS and Android production JS/Hermes exports pass; these are not native builds |
| Root/provider | 11 tests pass, including Gem capture bounds/readiness regressions |
| Browser | 18 security checks and 9 extraction DOM checks pass |
| npm audit gates | Root/mobile pass with only the three existing documented exceptions |
| Live worker/service integration | One Gem listing: read 7.388s, summary 5.029s, seven bullets saved/reopened, accepted receipt verified |

The live integration used the existing `gem-function` sample (Function Health, Staff Software Engineer — Frontend/UI), one Browserless call and one OpenAI call, with the job saved only to disposable SQLite. Its successful result complements, and does not erase, the partial/failure outcomes in the evaluation report.

The online Expo package check recommends newer SDK 57 patch releases for Expo/UI/Router and several bundled packages. The installed dependency compatibility check passes, and no mobile packages were changed here. Plan a separate SDK 57 patch refresh with native rebuilds. The npm audit discovered new DOMPurify advisories; the root package and two Learning CDN references were patched to 3.4.17 with matching SRI. See the [security log](security/dependabot-2026-10-05.md).

### Native interaction checks

**iPhone 18 Pro / iOS 27 simulator, existing Expo 57 development client:** paste URL → two-stage suggestions → keep manually typed title → edit one bullet → remove another → apply → save. The saved title, three bullets, edited label and original source persisted. Existing-job review defaulted title/company/summary to preservation and displayed the current summary. A later Android save caused the iPhone's older draft to receive a revision conflict while retaining its selected bullets. Keyboard entry and long-form scrolling were exercised.

**Pixel 10 / Android 16 API 36.1 ARM64 emulator, existing development client:** reopened the iPhone-created job with its edited bullet and source; extracted again, compared current/proposed values, explicitly selected title/summary, applied and saved four bullets. A development reload recovered the completed receipt using GET without another provider call. Native bullet keyboard editing was exercised separately. The full review and apply/save controls remained reachable.

Native testing fixed two issues: a late manually entered title could remain selected for replacement, and Android's grouped form row only displayed the first child of a multi-root review component. The review and bullet editors now each expose one native Column root. Existing-summary rows have distinct React keys.

Evidence: [iPhone saved details](assets/jobwizard-extraction/iphone-saved.png), [iPhone review](assets/jobwizard-extraction/iphone-review.png), [Android saved details/source](assets/jobwizard-extraction/android-saved.png). An additional native provider-failure check was blocked when the Mac locked; automated failure/manual-save checks pass, and physical failure-screen validation remains open.

### Review and installable iPhone preview

[PR #120](https://github.com/Kriordan/personal_portfolio/pull/120) contains the implementation. Code commit `5d1ddcdd7289b0f6aea60e8edbe092c36911a2dc` passed all seven GitHub checks (backend, web, mobile, three CodeQL analyses and the CodeQL result). The branch had no open CodeQL alerts when checked.

[Internal iPhone preview](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/ac514269-4280-4b73-8475-ccc3484208d3): EAS build `ac514269-4280-4b73-8475-ccc3484208d3`, finished October 22 at 20:25 UTC, from code commit `5d1ddcd`, profile `preview`, app 1.0.0/build 1. The archive is available for installation and uses the existing registered iPhone/provisioning profile. No signing credentials were changed. The upload archive was checked for local credentials before submission.

This preview targets the existing production Flask API. Extraction is now enabled there after merge; the installed preview needs no rebuild for this server rollout. The recorded native interaction checks used the disposable local fixture. The final revision-conflict prompt refinement passed mobile regression, type/lint/export and CI checks; physical-device confirmation remains part of acceptance.

## Smoke and rollout checklist

### Production rollout — October 23, 2026 UTC

PR #120 merged as `fcf02bf9cf0d51d3238a85d2dd0702db1d1ab787`. Database backup `b010` completed before deployment. Heroku code release v150 succeeded, and migration `f2a3b4c5d6e7` is installed. All four existing jobs retained the same pre-migration field fingerprint. Deployed extraction/parser/capture hashes match the merged source. Public home returns 200; unauthenticated jobs return 401; authenticated list/detail/capture-status reads return 200 with private responses.

Config release v151 securely installed the existing OpenAI key and selected `gpt-6-luna`, initially with extraction disabled. Heroku Scheduler `scheduler-triangular-76540` now runs `flask --app project prune-job-extractions` daily at **04:30 UTC** on a Basic dyno, with the first scheduled run due October 24. The addon uses its free standard plan; scheduled dyno runtime is billed separately. A manual run of this deployed command exited successfully and removed zero receipts. Use the `project` factory, not `run.py`, whose import starts the web server. Source becomes inaccessible at its 24-hour expiry; physical deletion follows at the next successful cleanup, so a daily schedule does not promise deletion exactly at 24 hours.

Release **v152** enabled `JOBWIZARD_EXTRACTION_ENABLED=1`; screenshot capture remains enabled. The web dyno is healthy. Authenticated requests through the public production API exercised the same `gem-function` listing used in the evaluation:

| Production check | Result |
| --- | --- |
| Read public listing | 7.156s HTTP route; 5.649s provider worker; title/company and source persisted |
| Summarize | 9.493s HTTP route; 8.042s worker; eight suggestions, 5,179 input / 358 output tokens using `gpt-6-luna` |
| Recover/replay | GET returned the completed result; replaying both stages retained the same result and metrics without new provider work |
| Review/save/reopen | Seven bullets saved with server excerpts; one edited bullet retained its edited label; save replay and mutation receipt returned the original result |
| Acceptance and compatibility | Full source/result cleared from the accepted extraction receipt; collection omitted details; a legacy-shaped PATCH preserved accepted details |
| Independent Gem capture | 14.441s; valid 1280 × 7692 PNG; signed fetch succeeded and unsigned access returned 403 |
| Existing data | All four pre-existing jobs still match their original field fingerprint; only the new validation job was archived |

This consumed one listing read, one summary and one independent screenshot capture. Title/company and all seven accepted bullets were checked against the fetched listing. The listing gives no numeric pay range, visa, travel or closing-date constraint; none was invented. One suggestion mentioned design systems, which appears in source block `s49` but was absent from that bullet's cited excerpts. That phrase was removed during review, and the generic hiring-fraud notice was deselected. This is evidence that semantic citation coverage still requires review, even when the validator reports no warning; it is not a claim of universal extraction accuracy.

At the time of this October 23 rollout, physical extraction acceptance and the first scheduled cleanup were pending. On October 27 the user confirmed suggestions appear for the original Justworks URL and manual save/reopen works after an unsupported listing. Full fact-by-fact acceptance, scheduled cleanup execution evidence and production concurrency measurements remain unconfirmed.

Completed in automated/native fixture checks:

- [x] Owner isolation, stale URL/revision, forged evidence, bounds, failure/expiry and disabled-provider behavior.
- [x] Duplicate submission, lost response, stage replay, process death and source-only recovery with explicit continuation.
- [x] Atomic acceptance/reopen, edited provenance, old-client preservation and omitted collection summaries.
- [x] iPhone new-job review/edit/remove/save and existing defaults; Android existing-job comparison/apply/save.
- [x] Cross-device revision conflict retains the draft.

Production rollout and physical acceptance:

- [x] Review and merge the PR, deploy the additive migration with extraction disabled, and confirm compatible read/save/capture API behavior.
- [x] Configure the approved OpenAI key securely on Heroku, select the evaluated model, configure daily pruning, then enable extraction.
- [x] Record release, migration, model, stage latency/usage, replay/acceptance status and independent capture through the production API.
- [ ] On the new iPhone preview, extract one real supported listing; check every accepted fact and omitted constraint against the source, then save and reopen. Confirm independent screenshot capture/viewing.
- [ ] Confirm the first scheduled cleanup completes successfully.
- [ ] Check concurrent capture/extraction timing and provider budgets. Disable the feature flag to stop new work if acceptance fails; keep the additive migration/data.

Follow-ups remain open: physical iPhone acceptance, physical Android gestures, smaller devices/largest text/light-dark/VoiceOver/TalkBack, full device background/expiry/offline/account-switch matrix, and all earlier unchecked [mobile](mobile-ui-validation.md), [Jobwizard](jobwizard-smoke-test.md), [Gem/viewer](jobwizard-gem-viewer.md), Grocery/Wishlist/Library/Learning items. Preserve the November 5 dependency exception review. Python 3.13.18 is now verified in the deployed v160 runtime; see the current ledger for the remaining runtime trust-probe evidence.
