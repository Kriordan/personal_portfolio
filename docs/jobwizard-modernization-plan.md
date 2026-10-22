# Jobwizard modernization plan

October 21, 2026. Deliver a reliable, private saved-jobs organizer that follows the Grocery, Wishlist, Library and Learning mobile patterns. Keith selected **search, sorting, add/edit and reversible archiving**, with application stages, interview notes and reminders deferred.

**Approved October 21:** save the job immediately, then offer an optional **Capture screenshot** action. Automatic capture is outside this slice.

## Baseline and constraints

Start implementation from merged `main` at **`73d62db81f59b53d30e7a626b5ed4ce540756e07`**, the merge of [PR #112](https://github.com/Kriordan/personal_portfolio/pull/112). It includes Grocery/shell #94, Wishlist #107, Library #108/#109, security cleanup #111, Learning, the two corrected CodeQL findings, and the October 21 dependency updates. Implementation branch: `feature/jobwizard-modernization`.

**Heroku v140** is deployed from that merge commit. Production checks verified migration `d0e1f2a3b4c5`, the corrected Learning handlers, Certifi 2026.10.19 and Pillow 13.0.0. The current [Learning iPhone preview](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/7ab8e8b9-b47f-4b82-838f-24311018c9a1) remains compatible; Jobwizard implementation will need a new preview.

Keep Expo **57**, Expo Router, **@expo/ui**, TanStack Query and Flask. Prioritize iOS, support Android, and keep web as a development convenience. Use the [exact SDK 57 reference](https://docs.expo.dev/versions/v57.0.0/) and the established native-control wrappers; this is not a framework upgrade. Current regression baseline: **195 backend tests, 65 mobile tests and 18 browser checks**.

GitHub currently lists only the three retained npm alerts: `braces`, `node-forge` and `decode-uri-component`. Preserve their existing bounds and **November 5, 2026** review deadline. The October 21 `follow-redirects` alerts no longer appear among open default-branch alerts. Follow [the security review](security/dependabot-2026-10-05.md), including checking actual CodeQL findings on both PR head and merge references rather than equating a successful scan with zero findings.

## Current behavior and gaps

The mobile feature consists of overview, detail and new-job screens. Flask exposes owner-scoped list, create and detail APIs; the website uses the same service. Jobs are **private per account**. A second account receives 404 for another account's job. Refreshing another device on the same account reads the same saved records; there is no Jobwizard realtime event stream.

Records contain title, company, listing URL, screenshot reference and `posted_date`. There are no application stages, notes, edit/archive endpoints or reliable capture-status records. List ordering is unspecified. The mobile overview renders all rows in a ScrollView; failed refreshes replace retained content. Invalid numeric routes can leave disabled queries displaying a spinner. Native search, sorting, explicit field labels, discard protection and link-launch recovery are missing.

Creation calls ApiLeap and uploads its response to S3 **before committing the job**. The HTTP request has no explicit timeout or status/image validation. An upload failure can return false after assigning an image filename, and the service ignores that return value. The mobile client and website construct screenshot URLs using the hardcoded `jobwizard-test` bucket. A legacy seed instead stores a `/static/img/job_listings/...` path. Ownership of the database record does not establish that its existing screenshot object is private or accessible.

The screen's **Posted** label is misleading for ordinary saves: the service fills `posted_date` with the current time. A seed explicitly supplies an older date, so existing values cannot all be asserted to be actual save timestamps or listing publication dates.

Planning validation used disposable SQLite fixtures and mocked screenshot calls; no production jobs or provider credentials were read or modified. All **17 existing Jobwizard API/service tests pass**, but additional probes reproduced:

- Non-object JSON and non-string titles raise unhandled `AttributeError` exceptions.
- A `javascript:` listing URL is accepted with HTTP 201.
- A screenshot method returning false can still produce HTTP 201 with a nonexistent screenshot reference.
- Private list responses lack an explicit `private, no-store` policy.
- The invalid website form attempts to render the absent `jobwizard.html` template.

These are implementation requirements, not completed acceptance checks.

## Recommended product behavior

| Area | First deliverable |
| --- | --- |
| Overview | Jobwizard heading, short explanation that jobs are private, an **Add job** action, search and a native sort control. Use the shared rounded cards and semantic theme colors. |
| Browse | Default to **Active** jobs, with **Archived** and **All** views. Search title, company and listing hostname; trim whitespace and match all search terms without case sensitivity. Search and filters compose. |
| Order | Default to **Newest saved**; also offer Oldest saved, Company A–Z and Title A–Z. Use stable ID ties and place unknown save dates last. Preserve search, filter, sort and scroll position when returning from details. |
| Rows | Job title, company and source domain, with a saved date when known and an Archived label where relevant. Keep screenshots on details so a long collection does not download full-page images. |
| Detail | Title, company, full selectable listing URL, saved date when known, archived state, screenshot state and a prominent **Open listing** action. Options contain Edit and Archive/Restore. Opening a listing never changes job state. |
| Add/edit | Three labelled fields: title, company and URL. URL keyboard, no capitalization/correction for the URL, inline validation, reachable Save/Cancel and keyboard dismissal. Use the established native text-state handling so rapid typing is not lost. |
| Save | Commit text independently of screenshot availability. Open the confirmed job detail after creation. Preserve the draft on failure and explain uncertain outcomes separately from definite rejection. |
| Archive | Set a desired archived state; do not toggle blindly. Hide archived jobs from Active after server confirmation and offer Restore. Retain the job and its screenshot. Permanent deletion is deferred. |
| Screenshot | Recommended default: explicit optional capture from details. Show No screenshot, Capturing, Available, Failed/Unavailable, and Interrupted/Unconfirmed states separately. A screenshot failure never makes a saved job disappear or suggests that the job itself failed to save. |
| Reading screenshots | Show an uncropped, aspect-preserving preview using the existing image facilities, with **Open full screenshot** for browser scrolling/zoom. Label the capture date and whether the saved listing URL has since changed. Never silently recapture on edit, focus or refresh. |
| Refresh | Refresh on route focus, foreground, reconnect and pull-to-refresh, even within the normal query freshness window. Keep readable cached content after refresh failures and show a stale-data message. There is no new live-sync or push-notification feature. |
| Offline | Loaded jobs remain readable in memory. Mutations fail immediately when known offline; reconnect performs reads, not queued writes. Full offline storage and background mutation queues are deferred. |

Editing should not overwrite a dirty draft when a background read changes the record. Show a conflict and let the user load the latest version while preserving their proposed changes. Closing a dirty form asks whether to discard; cancelled dismissal must preserve every field. Logout clears account-specific cache/recovery state and prevents late callbacks from affecting the next account.

For dates, add an explicit saved timestamp for new records and retain `posted_date` for compatibility. Do not backfill unknown historical save times with migration time or relabel a legacy publication date as Saved. Preserve the old date as legacy metadata, with a clear Date recorded label if displayed; unknown save dates sort last. Editing never changes the original save date.

Use a synchronous submission lock as well as disabled controls. Different deliberate saves may represent distinct jobs even when URLs match; request idempotency prevents accidental replay, not every intentional duplicate. Do not impose a URL uniqueness constraint or strip query parameters that identify a job listing.

## Bounded first deliverable

Ship one cohesive PR with separate commits for backend correctness/data changes, the mobile organizer, and screenshot integration/validation. The deliverable is the complete browse → add → detail → edit/archive/restore flow, with existing screenshots handled honestly and optional capture isolated from saving.

Retain the full-list API for this slice and use the existing virtualized-list approach. Search/sort/filter operate on the fetched collection without silently truncating it. Validate hundreds of records in the fixture; add pagination only if measured payload/rendering costs make that contract inadequate, rather than adding an untested limit. No list package is required just for this feature.

Reuse `PageHeading`, `ScreenState`, `InlineError`, `NativeField`, `NativeAction`, the repaired `NativeChoice` menu, native-width helpers and the Wishlist draft/discard patterns. Keep the iOS menu's measured height and Android numeric widths. Build small Jobwizard model/cache/mutation helpers so tests exercise real behavior rather than copying component implementations.

The website needs compatible owner-scoped operations, recoverable form errors, safe links and screenshot delivery, plus a way to view and restore archived jobs. Reuse the shared service; do not undertake a separate website redesign. Repair the missing invalid-form template path and quote external-link attributes with appropriate new-tab protections.

Out of scope: application stages, application/interview notes, reminders, automatic job-board imports or scraping, AI extraction, resumes/cover letters, sharing extensions, favorites, full offline sync, permanent deletion, a general task queue, and a custom native image editor/viewer. Automatic screenshot capture is also outside this recommended scope unless selected and replanned explicitly.

## API and persistence

1. **Keep ownership central.** Every read, mutation, capture-status lookup and screenshot authorization must resolve the requesting owner. Missing and foreign jobs return the same 404. Return private/no-store for personal JSON and website responses; never trust a client-supplied user ID.
2. **Validate at the shared service boundary.** Require a JSON object for API writes, actual strings, trimmed required values and explicit length limits (recommended 200 characters each for title/company and 2,048 for URL). Accept only well-formed HTTP(S) listing links without embedded credentials or control characters. Reject unsafe legacy links at launch/capture time and offer editing; do not silently rewrite or delete stored data. Preserve existing long values until deliberately edited, with field-specific remediation rather than truncation.
3. **Add archive and revision metadata.** Use additive migrations for nullable saved/updated/archive timestamps and an integer record revision. Existing records remain active and owned by the same user. Preserve all dates, screenshot references and job IDs. Test upgrade/downgrade on populated PostgreSQL fixtures; make no destructive ownership backfill.
4. **Expose compatible operations.** Keep list/create/detail routes and current fields. Add PATCH for editable fields and explicit archive/restore state. New clients send the observed revision. Prevent lost updates with an atomic revision check; stale edits receive a fixed public 409 message. New optional response fields describe archived state, revision and screenshot metadata. Legacy list requests retain their all-record semantics; modern clients filter explicitly. Legacy creates remain accepted without triggering the old screenshot dependency.
5. **Make retries safe.** Modern create/edit/archive requests use account-scoped UUID request IDs and frozen payloads. Commit the mutation and its response receipt atomically, with unique owner/request keys. Identical replay returns the original result; conflicting reuse returns 409. A receipt lookup supports lost-response recovery. Check the receipt before the revision so an acknowledged-but-lost successful edit can be replayed safely.
6. **Recover without inventing success.** Persist only the minimal unresolved operation under the active account using the existing secure-storage facilities. Missing receipts are not proof that an in-flight transaction cannot commit. Read status on foreground/reconnect; an explicit retry resends the same attempt. Never automatically retry a POST or resurrect a previous account's draft/receipt. A successful write followed by a failed refresh is described as a refresh problem.
7. **Reconcile clients.** On confirmation, update the relevant detail/list cache and invalidate affected lists. Keep browse controls stable, and clear only drafts whose save was confirmed. The website should submit stable request IDs and use the same validation/conflict rules; older API callers still receive compatible success/error shapes where applicable.

## Optional screenshot capture

The approved design uses a separate, user-triggered capture request to keep the ordinary save path fast and independent of external services. It does not require a new always-running worker. If reliable capture cannot fit within a bounded request, stop and propose a durable worker design; do not run untracked background threads in a web dyno.

- Extract the current model method into an injectable provider/storage service. Check configuration before contacting the provider. Capture only a validated public HTTP(S) URL; block local/private targets and embedded credentials, and assess provider redirect/target restrictions. Do not fetch arbitrary listing pages directly from Flask. Clearly explain at the action that the listing URL is sent to the screenshot service.
- Use explicit connection/read/upload limits and an overall deadline below the web request budget. Validate provider status, media type, actual image bytes, size and decoded dimensions before publishing a screenshot. Bound downloads and memory use, close responses, and sanitize provider/storage errors without logging credentials or tokenized listing URLs.
- Persist a capture attempt and its source URL/revision before work starts. Use a per-job cross-process lock and stable attempt ID so repeated taps/recovery do not purchase duplicate captures. Publish success and the verified artifact reference together. Failed upload must never create a successful screenshot reference. Keep prior good images available if a replacement fails.
- Recover an abandoned in-progress attempt as Interrupted once no process holds its lock. A timed-out phone reads status without repeating the capture. A later explicit retry creates a clearly separate attempt only after the prior one has been resolved. A lost status read never resets an uncertain capture to a fresh request.
- Recheck ownership and listing revision before attaching the result. Editing the URL during capture must not silently attach an old-page image as current. Retain the prior snapshot with its captured source/date and mark it outdated; offer deliberate recapture. Archiving retains snapshots and does not initiate provider work.
- Derive image locations on the server rather than constructing bucket URLs in clients. New screenshots use private storage and owner-authorized, short-lived links, with expiry metadata and renewal on foreground/refresh/image error. Use the established no-disk-cache policy for private mobile images. Never persist signed URLs as canonical screenshot IDs or put them in logs.
- Inventory the existing bucket, IAM permissions and legacy reference formats during implementation using read-only checks. Ownership checks and a signed URL alone do not revoke existing public object/static-file access. Preserve legacy references until a verified storage mapping/migration is ready; keep inaccessible images as explicit Unavailable states. Do not concatenate arbitrary references, silently make a bucket public, or claim legacy screenshots are private without checking the storage policy and original URLs.
- Keep `listing_image` compatible for older clients, but do not make new private images public to satisfy the old hardcoded URL builder. Older previews may continue saving/browsing jobs while lacking new private screenshot display; the updated website and Jobwizard preview use the new image metadata. Document that limit at release.

If provider credentials, quota or private storage are unavailable, saved-job browsing/editing still works. Disable capture with a useful unavailable state. Live capture readiness is a separate check from fixture success, and requires one deliberate nonpersonal public listing rather than failure injection against real jobs.

## States and validation

Distinguish initial loading/error, No saved jobs, No active jobs, No archived jobs, No search matches, Job unavailable, stale refresh, field validation, stale edit, save outcome unknown, capture unavailable/failed/interrupted, and expired image access. Each state keeps a useful route back or recovery action. Invalid, zero, negative, fractional, nonnumeric and array route IDs must terminate in an unavailable state rather than a disabled-query spinner.

Add a disposable fixture with two users, several hundred jobs, long titles/companies/URLs, Unicode, equal/missing dates, archived entries, invalid legacy links, bare-key/static-path image references, tall synthetic screenshots and controllable read/write/capture/status failures. Disable dotenv/cloud metadata and mock ApiLeap/S3. No production data or external provider writes are used for failure tests.

Automated acceptance:

- All existing Jobwizard ownership and website/API tests; strict input validation, safe URL handling, cache privacy, unavailable routes and retained invalid-form fields.
- Search/filter/sort composition, stable ties and unknown dates; rapid native typing and double taps; dirty-form discard/cancel; failed refresh with retained content.
- PostgreSQL migration preservation, concurrent duplicate creates, same-ID/different-payload rejection, stale edits/archive races, atomic rollback and receipt recovery from another process.
- Screenshot provider timeout, non-image/error payload, oversized image, missing configuration, upload failure, process death, duplicate attempts and changed URL during capture. Verify actual provider-call counts with fakes.
- Cross-account screenshot/status protection, legacy reference validation, expired-link renewal and image caching behavior. Account switching must suppress old data and late callbacks.
- Real TanStack focus/foreground/reconnect behavior and mutation non-queuing; read recovery after a lost response; no duplicate automatic write.
- Backend suite including PostgreSQL integration tests; mobile tests/typecheck/lint; Expo 57 compatibility; all-platform production exports; root/browser checks; Python/root/mobile audits; and all CI/CodeQL checks. No widened security exceptions.

Native acceptance and release:

- Exercise actual iPhone and Android interactions, including smaller iPhone, normal/largest text, light/dark, software keyboard, native menus, form dismissal and signed-in/signed-out cold links. Verify VoiceOver/TalkBack focus, labels, pending announcements, errors and archived/capture states. Android build/install alone does not close interaction checks.
- On the same account, change jobs on the website or second fixture client while the app is backgrounded, then verify fresh data on return within the normal freshness window. Keep a dirty editor intact and surface revision conflicts.
- Run the [Jobwizard smoke checklist](jobwizard-smoke-test.md), record screenshots and device/OS/source identifiers, and preserve unrelated checklists.
- Deploy the backward-compatible Flask changes and verify migration/health before distributing a fresh internal iPhone preview from a recorded commit, using existing approved signing and HTTPS API settings. Inspect the EAS archive for excluded secrets/databases. Record the preview/build ID and matching backend release. Physical installation and a deliberate normal save remain distinct from build success. No App Store/TestFlight or OTA release is included.

## Follow-ups carried forward

Keep the detailed results and unchecked items in [mobile validation](mobile-ui-validation.md), [Grocery](grocery-editing-smoke-test.md), [Wishlist](wishlist-smoke-test.md), [Library](library-smoke-test.md), [Learning](learning-smoke-test.md) and [the original iPhone checklist](iphone-smoke-test.md). A merged PR or general positive review does not mark individual device tests complete.

- Full VoiceOver/TalkBack, large-text/software-keyboard combinations, cold protected preview links, Android interactions/navigation insets/pull-to-refresh, and a distributable Android preview remain open where not specifically verified.
- Retain Grocery physical website-event/reconnect verification and Wishlist real-photo CRUD/discard, private-photo renewal beyond 15 minutes and foreground recovery. Existing passed evidence remains valid.
- Retain Library timeout/relaunch status recovery, personal-pin isolation and deliberate live watched-playlist move acceptance after broader Google consent. Opening a video is not viewing history.
- Retain Learning physical-preview review, offline transitions, delayed-save logout/account switching and uncompleted accessibility checks. Its CodeQL correction and backend deployment are complete; its unitemized device checks are not.
- Retain production EAS environment configuration, Google External/Testing expiry/branding/publishing, credential-consumer inventory before retirement, and the November 5 dependency-exception review. This slice adds no scheduled monitoring or unrelated dependency refresh.

Implementation is in progress. See the smoke-test evidence for completed checks and remaining acceptance. Production storage permission changes were explicitly approved on October 21; the additive policy was applied and verified. The existing ApiLeap endpoint returned HTTP 500, so live capture remains disabled until a successful readiness check.
