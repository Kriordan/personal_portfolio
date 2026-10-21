# Learning mobile modernization plan

October 14, 2026. The first deliverable is a cohesive browse, study, and review flow with reliable rating saves. Keith selected **browsing and review, with authoring deferred**, and **up to 20 due cards per session, followed by Review more**.

## Starting baseline

Use merged `main` at **`af9fed2d3aa3ffe5e1514cae70cb5fdcb5353cfb`**. Its ancestry includes Grocery and the application shell through PR #94, Wishlist through #107, Library through #108 and #109, and security cleanup through #111. The local review branch has the same file contents as that baseline.

Keep Expo **57**, Expo Router, **@expo/ui**, TanStack Query, and Flask. Prioritize iPhone, validate Android, and retain web for development. Follow the [SDK 57 documentation](https://docs.expo.dev/versions/v57.0.0/) and existing native control wrappers. Do not combine this slice with a framework upgrade or routine dependency refresh.

The latest verified backend is **Heroku v138**, with Mako 1.4.3. The accepted Library preview is [build fe0a5328](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/fe0a5328-7e5f-4c6e-aac6-6f42dd24fef9), source `d8c7111`. Keith reported that it looks good and merged #109; that general acceptance does not establish each unitemized checklist result. A new preview will be needed for Learning.

## Existing behavior and concrete gaps

The repository contains **four JSON notes and 37 cards**: 23 Q&A, seven cloze, one command, four code differences, and two incident cards. These counts describe repository content, not a live account's due queue. The same notes are available to authenticated accounts; `ReviewProgress` and `ReviewLog` belong to each user. Reading a note or revealing an answer does not alter progress.

The three existing screens are `mobile/src/app/learning/index.tsx`, `[id].tsx`, and `review.tsx`. They use typed calls in `mobile/src/lib/learning-api.ts`. Flask exposes notes, note detail, a due queue, and rating submission under `/api/v1/learning`. The website and API share `project/services/learning_service.py`; SM-2/HLR scheduling, topic interleaving, and the rating scale already exist.

The current screens use an unvirtualized notes/card collection, plain text card bodies, and a narrow row of four rating buttons. There is no search or note-specific review. The queue is a snapshot, but ratings only invalidate overview counts when the entire queue finishes. The screens do not use the newer collection/error/recovery patterns from Wishlist and Library. Rating mutations inherit TanStack's online mode, so an offline submission can pause until connectivity returns.

Two defects were reproduced on the unchanged baseline using the existing API fixture and temporary SQLite storage:

- Two identical successful rating POSTs with the same `session_id` produced **two review logs**. A session ID groups reviews; it does not prevent duplicate application. Losing a response and tapping again can advance the schedule twice.
- One suspended card with a past due date produced **overview due count 1, queue length 0**. The summary and queue use different eligibility rules.

There is also no database uniqueness constraint on `(user_id, card_id)` in `ReviewProgress`, and the rating service does not serialize concurrent updates. The implementation should address rating integrity with the UI, while retaining scheduler behavior.

The website also contains a public long-form Web Performance reference. It is separate from the flashcard JSON/API and remains a website reference in this slice. Mobile authoring would additionally require a durable content-storage decision: the existing admin incident endpoint writes local JSON files.

## Product defaults

| Area | First deliverable |
| --- | --- |
| Entry | Learning heading, brief explanation that progress is personal, due summary, and **Review up to 20 cards**. Show the actual session size when fewer are due. |
| Browse | All notes visible by default. Search title, summary, and tags locally; add an All / Due filter. Default order is due count descending, then title. Offer Title A–Z and Newest created in a native menu; missing dates sort last. Browse order never changes scheduler order. |
| Note rows | Title, short summary, card count, textual due count, and compact tags. Match the rounded cards, spacing, and semantic colors of Wishlist and Library. Use the existing virtualized collection approach without adding a list dependency. |
| Note detail | Readable summary and expandable cards in source order, with an explicit Show answer / Hide answer action and expanded accessibility state. **Review due cards in this note** uses the same 20-card limit. Browsing never records a rating. |
| Review | One card at a time: topic, progress, prompt, then an explicit reveal. After revealing, show Again, Hard, Good, and Easy, with short explanations. Use two columns at ordinary widths and stack at large text sizes. Keep actions reachable by scrolling. |
| Ratings | Retain Again=0, Hard=3, Good=4, Easy=5 and existing SM-2/HLR algorithms. Advance only after a confirmed committed result. Show a brief saved/next-review message tied to the previous card. |
| Session end | Show confirmed reviews and rating totals, then **Review more** and **Back to Learning**. An interrupted session retains every committed review; a new session fetches the current due queue. Do not label a completed 20-card batch as all caught up unless the server confirms no due cards remain. |
| Refresh | Refresh notes and due counts on route focus, foreground, reconnect, and pull-to-refresh, including within the normal freshness window. Keep the active review snapshot stable across those events. |
| Offline | Previously loaded notes remain readable in memory. Ratings fail immediately when known offline; reconnect does not submit them automatically. Full offline storage and offline review are deferred. |

Search/filter/sort are browsing controls. The primary review action covers all due notes even when browse filters are active; its label must make that scope clear. Note-specific review is the explicit way to restrict a session. Browse preferences can remain in navigation state for this first slice; cross-device preference sync is deferred.

Support all five card types with selectable text, preserved line breaks, monospace commands/code, and clear Before / After or Cause / Fix / Prevention sections. Support the small text-formatting subset needed by current notes; raw HTML is rendered inert and remote media is not loaded automatically. Preserve the existing flat `prompt`/`response` fields for old clients; add optional structured presentation fields if needed rather than recovering code structure by splitting arbitrary prose.

No new mobile authoring, import/generation workflow, scheduler settings, streaks, reminders, global search, rating undo, full-session resume after termination, or public-reference redesign is included. Uncertain rating recovery across termination is included because it protects already-attempted saves.

## Rating confirmation and API work

Rating is a short database operation. Keep a normal response after commit; it does not need a worker queue or push notification. Add a durable receipt so the app can recover confirmation when the response is lost.

1. **Unify eligibility.** Use one rule for summary counts and queue membership: include valid new/due cards, exclude suspended cards. Count rendered cards consistently. Apply an optional validated `note_id` filter before queue construction and an optional `limit` after interleaving. Return the eligible total alongside the selected cards. Omitted parameters preserve old-client behavior.
2. **Give each attempt a stable ID.** A modern rating POST includes a UUID `request_id`, the card ID, rating, session ID, elapsed response time, and the progress revision observed in the queue. Freeze that payload once sent. A synchronous client lock closes the double-tap gap before disabled controls rerender.
3. **Commit once.** Add an account-scoped receipt with a unique `(user_id, request_id)` key. In one database transaction, serialize that user's rating operations, check a prior receipt and the expected progress revision, compute the scheduler result, save progress and one log, and store the response receipt. Repeating the same ID/payload returns the saved result; reusing an ID with different input returns 409. Two clients rating the same stale revision cannot both advance it. Use the same service transaction for website ratings, including old callers without an idempotency ID, and increment the revision for those callers too.
4. **Protect existing data.** Use an additive migration for receipts/revision state and enforce a single progress row per user/card. Preflight existing duplicates before adding uniqueness; do not silently remove or merge learning history. Keep existing logs and scheduled dates intact. Exercise migrations on populated PostgreSQL fixtures.
5. **Recover confirmation.** An authenticated receipt lookup exposes only the requesting account's result. A timeout shows **Checking whether your rating saved** and performs reads on reconnect/foreground. A missing receipt means no confirmed result was found; it does not prove a still-running transaction cannot commit. Offer an explicit retry with the same frozen ID/payload. Failed status reads retain uncertainty. Never create a new attempt simply because a prior response is missing.
6. **Handle interruptions.** Persist only the minimal unresolved-attempt metadata under the signed-in account using existing storage facilities. Do not persist a full queue or credentials in it. Check the receipt after relaunch before allowing another rating for that attempt. Logout removes device recovery state and invalidates callbacks so late responses cannot affect another account. Server receipts remain account protected.
7. **Refresh correctly.** On each confirmed save, reconcile the session once and invalidate notes/detail counts without replacing the active queue. On a stale-card conflict, explain that progress changed elsewhere and offer a fresh queue; do not silently re-rate it. Navigating back keeps saved progress. A pending/uncertain save remains recoverable when the user returns.

Validate JSON object shape, integer ratings, IDs, bounded session strings, and nonnegative elapsed times without coercing fractional values or booleans into ratings. Preserve valid legacy 0–5 ratings and response fields. Return private/no-store responses for personal progress and receipts. The existing website need not be redesigned; its rating client should use the same attempt ID/revision protections where it submits reviews.

## Loading and recovery states

Use the shared `PageHeading`, `ScreenState`, `InlineError`, native field/action wrappers, and semantic theme colors. Loading is labelled. An initial failure offers retry and a useful route back. A background refresh failure retains readable content and identifies counts as last loaded.

Distinguish **No notes yet**, **No matching notes**, **No cards due**, **This note has no cards**, **Note unavailable**, and **Session complete**. Invalid route parameters must not leave a disabled query showing an endless spinner. A failed rating retains the visible card and answer; a failed receipt read must not imply that the rating failed. Success is stated only for confirmed saves.

On iOS, use the Library menu's repaired measurement pattern so wrapped labels reserve their full height. On Android, preserve numeric native width modifiers and keyboard/inset handling. All buttons need text labels, touch targets, and busy/disabled states; reveal and save announcements must work with a screen reader. Long code can scroll within its own block without pushing controls off screen.

## Delivery and validation

Ship one Learning slice in a reviewable PR, with separate backend-integrity and mobile-flow commits. Add `learning-model`/cache/session helpers and hooks as needed so tests exercise state transitions and real TanStack behavior rather than duplicating components. Reuse the existing collection and native controls; extract only the small shared menu abstraction needed by both features.

Automated acceptance:

- Due counts equal eligible queue counts, including new, future, suspended, malformed/unsupported content, note filtering, UTC boundaries, and a 20-card limit after interleaving.
- All five card types preserve content; existing SM-2, HLR, queue-builder, and website renderer/security tests still pass.
- Real PostgreSQL tests prove duplicate-ID replay, changed-payload rejection, concurrent first reviews, stale revisions, rollback/process interruption, receipt privacy, and exactly one committed log for a retried attempt. A lost HTTP response followed by a fresh process can recover the committed receipt.
- Mobile tests cover rapid taps, offline non-queuing, receipt recovery, stale responses, logout/account switching, partial-session exit, no background queue replacement, every-save count refresh, and no false all-caught-up message after a batch.
- Search/filter/sort compose predictably, invalid IDs terminate cleanly, and refresh failures retain content. The existing 52 mobile and 185 backend tests are the pre-slice reference counts, not the expected final totals.
- TypeScript, ESLint, all-platform production exports, Expo dependency compatibility, Python/root/mobile audit gates, relevant browser checks, and all CI/CodeQL jobs pass. No security exception is widened or extended to make the slice pass.

Create a disposable Learning fixture with two users, all card types, hundreds of synthetic notes/cards, long text/code, suspended/future cards, empty states, and controllable failed/delayed/lost responses. Disable dotenv/cloud credentials and use temporary storage. Never use a real account's learning history for failure injection.

Native acceptance requires actual iPhone and Android interaction tests, not just exports or a successful APK. Test normal and maximum text, light/dark, a smaller iPhone, software keyboard/search, VoiceOver/TalkBack, native menus, review controls, foreground recovery, Android navigation insets, and cold signed-in/signed-out deep links. Record screenshots and device/OS/source identifiers. Use [the Learning smoke checklist](learning-smoke-test.md).

Deploy backward-compatible backend changes and verify migration, health, and old-client behavior before distributing the new mobile flow. Produce a fresh internal iPhone preview from a recorded commit with the existing approved signing setup and HTTPS API configuration; inspect the upload for excluded secrets/local databases. Record its build link and matching Heroku release. A deliberate normal review changes personal scheduling, so use cards the tester intends to review. Keep failure testing in the fixture. No App Store/TestFlight or OTA release is part of this deliverable.

## Follow-ups carried forward

Keep the detailed evidence and unchecked items in [mobile validation](mobile-ui-validation.md), [Grocery](grocery-editing-smoke-test.md), [Wishlist](wishlist-smoke-test.md), [Library](library-smoke-test.md), and the [original iPhone checklist](iphone-smoke-test.md). General user acceptance and PR merges do not mark individual checks complete.

- Full VoiceOver/TalkBack, smaller-device/large-text/software-keyboard combinations, cold preview links, Android interaction coverage, pull-to-refresh, and gesture/three-button insets remain unitemized or incomplete where recorded.
- Retain Grocery website-event/reconnect checks and Wishlist real-photo CRUD/discard plus signed-photo renewal after 15 minutes. Their existing verified checks remain valid; do not repeat them solely to inflate validation counts.
- Retain Library sync timeout/relaunch recovery, personal-pin isolation, watched-membership semantics, and deliberate live move acceptance after broader Google consent. Do not treat opening YouTube as watched history.
- Google External/Testing token expiry, Branding/publishing, and inventory of old credential consumers before credential retirement remain separate work. The three npm advisories and the **November 5, 2026** exception deadline remain tracked in [the security review](security/dependabot-2026-10-05.md). Mako is fixed and merged through #111; confirm GitHub's alert closure separately.
- A distributable Android preview and production EAS environment configuration remain separate release follow-ups.

This planning pass changed no application behavior, production data, dependencies, or deployed build. Its targeted fixture checks establish the two baseline defects above; implementation and native acceptance are the next work.
