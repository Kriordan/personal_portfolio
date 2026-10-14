# Learning smoke test

Checklist for the [Learning modernization slice](learning-modernization-plan.md). Implementation, fixture results and the matching preview/backend release are recorded below. Leave an item unchecked unless its entire stated behavior was exercised.

Failure injection uses a disposable fixture with temporary notes/database and two users. A production rating changes your personal review schedule; use only cards you intend to review. Browsing and revealing answers should not change progress.

## Browse and study

- [ ] Cold launch, sign in/restore, and open Learning from Tools. Verify Home/Tools/Me and signed-out route protection still work.
- [ ] See the server's due total and a session action for at most 20 cards. Browse all notes; search title/summary/tags with mixed case/whitespace; combine search with All / Due and each sort. Clear filters after a no-results state.
- [ ] The main review action clearly reviews all due notes regardless of browse filters. Sorting notes does not reorder the scheduler's review queue.
- [ ] Open a note. Read the summary, counts and tags; show and hide each of Q&A, cloze, command, incident, and code-difference answers. Long code retains line breaks and remains selectable/readable. Browsing changes no progress/log rows.
- [ ] Review due cards in just this note. Only that note's eligible cards appear, capped at 20. Check zero-card and no-due states independently.
- [ ] Invalid/missing note links show an unavailable state and Back to Learning. Test warm and terminated-preview links signed in and signed out.

## Review and save confirmation

- [ ] Start a queue with more than 20 due cards. It includes exactly 20; the total due count remains distinct. New and due cards appear, suspended/future cards do not, and overview totals agree with the fixture.
- [ ] Show an answer, then exercise Again/Hard/Good/Easy on separate intended cards. The app advances only after confirmation, announces success, and shows the saved next-review result for the correct previous card.
- [ ] Double-tap and rapidly tap different rating buttons. Only one intended rating and one log are committed for that attempt. The visible card cannot be rated again while saving.
- [ ] End after a few confirmed ratings. Return to Learning and the website: due counts refresh and saved progress remains. Start again from a fresh queue. Complete a batch with more cards still due: it says Session complete, with Review more, without claiming all caught up.
- [ ] Background/foreground and reconnect mid-session. The active card, reveal state, queue order and confirmed progress remain stable. No new queue replaces the session unexpectedly.
- [ ] With known-offline connectivity, try rating. It fails immediately, preserves the card/answer, and does not submit on reconnect. Retry deliberately once online.
- [ ] In the fixture, commit a rating but lose its response. The app checks its receipt and advances once without another schedule change. Repeat with delayed commit, failed status reads, and relaunch during uncertainty. A missing receipt is not presented as proof that nothing saved.
- [ ] Retry an uncertain request using the same attempt ID/payload; exactly one rating is applied. A conflicting reuse is rejected. Compare with the fixture's actual progress/log/receipt rows.
- [ ] Rate the same card in a second client before submitting the original snapshot. The stale client gets a clear conflict and can load a fresh queue, without applying another stale rating.
- [ ] Sign out during a delayed save and sign into the second fixture account. No previous user's card, receipt, count or late-result announcement appears. The two accounts' progress remains independent.
- [ ] Expired access-token refresh succeeds during a read and a save. A fully expired session returns to login without exposing personal progress.

## Layout and recovery

- [ ] A failed initial fetch offers retry. A failed refresh keeps loaded notes and clearly labels stale counts. Test no notes, no matches, no due cards, an empty note, unavailable note, save failure and receipt uncertainty separately.
- [ ] Check iPhone light/dark, normal/largest Dynamic Type, a smaller device, search with the software keyboard, and long native sort labels. Menus, wrapped titles, errors and rating actions remain fully visible or reachable by scrolling.
- [ ] Use VoiceOver for note rows, search, sort/filter, reveal, rating explanations, pending controls, confirmation announcements and session summary. Answer content is not announced before reveal.
- [ ] On Android, exercise the same browse/review/recovery flows, native control widths, maximum fonts, keyboard, TalkBack, pull-to-refresh, and gesture/three-button navigation insets. Record an interaction result separately from build/install success.
- [ ] On mobile web, verify search/filter/sort, card rendering, keyboard navigation, review confirmation/recovery and Back. Keep the existing website's scheduling and Markdown sanitization behavior compatible.

## Regression and release

- [ ] Grocery: create/edit/delete/completion, website-created item events, foreground/reconnect recovery and account permissions.
- [ ] Wishlist: CRUD/photo selection/removal/discard, photo renewal after 15 minutes and foreground recovery; retain earlier unverified acceptance items.
- [ ] Library: pin/unpin/search/sort without clipping, saved sync receipt/recovery, playlist playback handoff, and watched-membership display. Use a fixture for move failures; never move a live item merely for regression coverage.
- [ ] Home/Tools/Me, logout cache clearing, protected routes and cold deep links still work. No new dependency/security exceptions appeared.
- [ ] Record passing automated checks, PostgreSQL concurrency/migration evidence, native screenshots, and the exact preview/backend pairing. Install the new standalone iPhone preview and perform a deliberate real review; successful build/download alone does not complete device acceptance.

## Recorded results

October 14 planning baseline: the existing API test fixture reproduced duplicate rating application (two identical POSTs, two logs) and suspended-card count drift (one due in overview, zero in queue). These findings are implementation requirements, not passes for the checklist above. No production learning data was read or changed.


### October 14 implementation validation

- **194 backend tests pass**, including ten PostgreSQL integration tests. The four Learning PostgreSQL tests exercise simultaneous first reviews, duplicate replay, stale revisions, a process killed before commit, receipt recovery from a fresh process, and populated migration upgrade/downgrade with duplicate preflight. Existing scheduler, website, Library, Wishlist, Grocery and authorization regressions pass.
- **65 mobile tests pass**, including 13 Learning state/cache tests. TypeScript, ESLint, all-platform production exports, SDK 57 compatibility, and the root/mobile audit gates pass. Python audit reports no known vulnerabilities. The website's real browser renderer/save handlers pass **18 checks**, including rapid taps, failed-save retention, identical retry, receipt confirmation and stale-queue recovery.
- **iPhone 18 Pro / iOS 27.0 development client**, disposable API: sign out/in, protected session restoration, browse 206 notes / 640 eligible cards, title sort, mixed-case/whitespace search, note-specific review, all five card formats, and explicit reveal work. The fixture includes 200 synthetic notes, long code, one suspended card and one future card. Browsing/revealing left zero logs/receipts before review.
- A double-tapped Good rating with a deliberately lost post-commit response advanced once and left **one log / one receipt**. A second Hard attempt with both write/status failures retained its answer and disabled other ratings. Its recovery controls were reachable by scrolling. Reloading the JavaScript runtime restored the unresolved attempt on Learning and did not resubmit it. Restoring connectivity performed reads only; deliberate Retry produced exactly **two total logs / two receipts**, ratings `[4, 3]`.
- Dark appearance and maximum Device Hub text setting **11** were exercised; the native sort menu displays every label, and long review content scrolls to the final action. Original Light appearance/text setting **3** were restored. This is not a completed VoiceOver or combined software-keyboard/large-text pass. Screenshots: [review](screenshots/learning-modernization/ios-review.png), [pending save](screenshots/learning-modernization/ios-pending.png), [card types](screenshots/learning-modernization/ios-card-types.png), [largest-text menu](screenshots/learning-modernization/ios-sort-largest-dark.png).
- **Mobile web / account 2** showed its independent 640-card due count while account 1 had 638. A full 20-card session advanced only after each save, displayed five of each rating, and offered Review more without an all-caught-up claim. Review more fetched another 20-card batch from **620 remaining due**. [Session summary](screenshots/learning-modernization/web-session-complete.png). Fixture tokens expire after ten seconds, exercising refresh during the run.
- **Android limitation:** Pixel 10 booted and its existing development client/API port routing were verified, but Android Studio exposed no running-device target and computer-use could not attach to the standalone emulator. No new Android interaction pass is claimed. Android production export and shared behavior tests pass; native interaction, TalkBack, keyboard, maximum fonts and navigation-inset checks remain pending.
- The read-only production migration preflight found migration `c9d0e1f2a3b4`, zero duplicate progress groups, zero progress rows and zero review logs. No production rating was submitted. The additive migration stops before changing schema if duplicate progress exists.
- The EAS archive contains the Learning sources and excludes local environment/credential files, databases, dependencies and generated native projects; the inspector's own Git metadata is excluded from that assessment.

The grouped checklist above remains unchecked where it includes an untested condition. Full VoiceOver/TalkBack, combined largest-text/software-keyboard checks, native cold links, offline device transitions, delayed-save logout/account switching, and standalone physical-device acceptance still need an explicit pass. Automated coverage is not a substitute for those interactions. All earlier Grocery/Wishlist/Library follow-ups, Android preview, production EAS environment, Google Testing/credential work, and the November 5 security-exception deadline remain open as previously recorded.


Additional October 14 checks: a disposable **iPhone SE (3rd generation) / iOS 27.0** passed software-keyboard sign-in/search and a readable two-column rating layout. [Keyboard](screenshots/learning-modernization/ios-se-keyboard.png) · [Review](screenshots/learning-modernization/ios-se-review.png). A second fixture client committed the same card after the SE loaded its queue. The SE retained its answer, rejected the stale rating, and loaded a fresh four-card note queue; saved totals remained three logs/receipts, including only the competing client's new rating. No stale write was applied. Web checks also verified an empty note, a no-results combination of search and Due filter, invalid and missing note URLs, retained content/counts after failed refresh, and successful explicit retry.


### Released preview and backend

[PR #112](https://github.com/Kriordan/personal_portfolio/pull/112) contains backend commit `457298c` and mobile source **`89a76443418a96ca843766bd9331c3511005d6a0`**. Backend, mobile, web, and all CodeQL jobs pass on this application source; the PR-specific CodeQL query returned zero open findings.

The approved deployment released **Heroku v139 on October 14 at 4:11 p.m. EDT**, from `89a7644`. A separate production process verified migration **`d0e1f2a3b4c5`**, the receipt table, the unique progress constraint, the repository's 37 valid cards, and the unchanged 186-playlist catalog. Production review logs remained zero. The website returned 200; protected Learning notes/receipt routes returned the expected JSON 401 with `private, no-store`. The web dyno is up. Legacy-client behavior is covered by the shared API regression suite; no production learning rating was submitted.

The [Learning iPhone preview](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/7ab8e8b9-b47f-4b82-838f-24311018c9a1) **finished at 4:17:17 p.m. EDT on October 14** from the same application source. It is an internal-distribution physical-device build using the existing registered-device signing credentials and `https://keithriordan.herokuapp.com`. No new signing credential, App Store/TestFlight submission, OTA update, or PR merge was made. The IPA download endpoint returned HTTP 200. Installation and a deliberate physical-iPhone review remain pending; successful build/download checks do not establish that acceptance.

The iPhone SE additionally preserved its current command card, revealed answer, 20-card snapshot and progress across background/foreground. The release-evidence commit changes documentation/screenshots only, so it does not require another backend deployment or application build. Earlier follow-ups remain open except for GitHub's now-confirmed closure of Mako alert #248.

The disposable fixture API, Metro, PostgreSQL server, iPhone simulator and Android emulator were stopped after validation. The temporary iPhone SE simulator was deleted; the existing iPhone simulator was restored to Light appearance and its original text size.
