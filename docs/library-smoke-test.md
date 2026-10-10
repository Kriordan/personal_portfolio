# Library smoke test — October 10, 2026

Use the Library preview and backend release recorded in [mobile validation](mobile-ui-validation.md#library-modernization--october-7-2026). A successful native build is not a passed physical-device test. Record device/OS, source commit, build ID, backend release, and actual results for each checked step.

Use the [October 10 sort-repair iPhone preview](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/e9120677-79a9-4b11-b671-4f089a79c088), source **`c28b0b1`**, with **Heroku v136**. It finished at **3:34:13 p.m. EDT** and the IPA HEAD check returned 200. The repair passed simulator checks; installation/physical acceptance remain pending. It replaces preview `b73edbc5`, whose sort controls clipped on iPhone. The October 7 preview contains source `44cbd1c` and does **not** contain the new sync receipts or sorting controls.

Library is one shared catalog for all signed-in accounts. Pull-to-refresh reads saved data. **Sync from YouTube imports into that shared catalog using the server's connection**, and affects everyone. Pins are private to each account. The optional Move to watched workflow changes the connected owner's two configured playlists. Opening YouTube never moves a video or marks it watched. Do not use live sync/moves for failure injection; use the fixture below.

The October 10 connection repair and Google consent succeeded. A fresh server process used the saved connection successfully; the production import committed at **2:37:16 p.m. EDT**, leaving **186 playlists / 10,918 video entries**. The old phone preview timed out before receiving success and still displayed 178 playlists. This establishes that import's completion, not acceptance of the new receipt UI. See the [YouTube connection runbook](library-youtube-connection.md), including the remaining Google Testing-mode expiry follow-up.

## iPhone checklist

- [ ] Install the new preview, cold-launch, restore/sign in, and open Library from Tools. Verify Home, Tools filtering, Me, sign-out, and protected-route privacy.
- [ ] Browse playlists, including long titles and absent/broken artwork. Search title and description, mix case/whitespace, try no matches, and clear. Verify Recently updated (default), Title A–Z/Z–A, and Newest/Oldest created. A numbered title sorts naturally. Search preserves the chosen sort; reopening the app preserves the device preference.
- [ ] Sort layout regression: on overview and playlist details, verify the entire selected option and all menu choices are reachable. Check Recently updated and YouTube playlist order at normal and largest text sizes. Wrapped labels must reserve their full height above the first card; test again on a smaller phone with the keyboard shown.
- [ ] Open a playlist, expand/collapse its description, search its videos, and scroll a long collection. Check the empty-playlist state. Missing watch links are disabled; **In watched playlist** is identified as last-confirmed membership rather than viewing history.
- [ ] Verify Newest added (default), Oldest added, YouTube playlist order, and Title A–Z/Z–A with hundreds of videos. Newest/oldest refers to addition to the YouTube playlist, not the video's original publication. After the first new sync, upstream positions are available; missing positions sort last. Confirm changing order does not alter YouTube or another device's preference.
- [ ] Tap a video with YouTube installed and without it. The HTTPS watch link opens the app/browser. Return and verify search/scroll position. Exercise launch failure locally and retry. No watched status changes.
- [ ] Cancel the sync confirmation and verify no import runs. Confirm a deliberate import, tap repeatedly, and navigate away/back while pending. Only one shared import runs across accounts/processes; browsing remains usable.
- [ ] In the fixture, test missing authorization (503), upstream failure (502), unexpected failure (500), and a delay over 30 seconds. Errors contain no provider details. A timeout continues status checks without repeating the POST. Completion shows the server finish time and checked/added/changed/unchanged/skipped counts, then refreshes the catalog automatically.
- [ ] Complete an unchanged import: zero added/changed still shows a successful completion time. Compare counts with the fixture; video counts are playlist entries, not distinct YouTube videos. Removed/unavailable saved records remain retained and are not proof of exact upstream mirroring.
- [ ] Start an import from another account while Library is open, then while this app is backgrounded. Verify running state, completion, and catalog refresh on return. Relaunch the app and confirm the saved result survives. A newer shared result must replace this device's earlier successful receipt.
- [ ] Locally interrupt the importer process after it creates a running receipt. Verify the next status check reports Interrupted with no partial catalog writes. Retrying requires a deliberate new sync; no automatic job replay occurs. PostgreSQL integration tests cover real cross-process exclusion and restart recovery.
- [ ] Start offline and try syncing: immediate failure, no queue. Reconnect and verify no import starts until deliberately confirmed. Keep loaded content after a failed refresh; restore connectivity and retry.
- [ ] Verify a successful import followed by a failed read is described as a refresh failure, not a failed import.
- [ ] Fail only the status check: retain the last confirmed result, identify that status could not refresh, and offer Check sync status. No receipt yet must not be presented as completed. Lock the phone during a slow import, then return: foreground status recovery is supported; this slice does not send OS push notifications while the app is closed.
- [ ] Use the website and another account to confirm the same catalog. Background the app, change fixture data, return within 30 seconds, and verify recovery. Repeat after reconnect and with manual pull-to-refresh.
- [ ] Open an invalid/deleted playlist link. Verify unavailable feedback and Back to Library. Test warm and terminated-preview links to `personal-portfolio:///library/PLAYLIST_ID`, signed in and signed out.
- [ ] Check light/dark mode, largest Dynamic Type with the software keyboard, and a smaller phone. Search, rows, errors, and actions remain reachable. Use VoiceOver to check focus order, labels, watched-membership badges, confirmation buttons, and announcements.
- [ ] Regression: Grocery create/edit/delete/completion and website creation events/reconnect; Wishlist CRUD, photo selection/removal/discard, private-photo renewal after 15 minutes, and foreground recovery. Preserve the existing checklists' unchecked items.

## Android and web

- [ ] On the rebuilt Android ARM64/16 KB-page client, repeat Library browsing/search, YouTube handoff/return, confirmation, sync failure, offline/reconnect, and invalid links.
- [ ] Verify native widths, large fonts plus keyboard, TalkBack, pull-to-refresh, and gesture/three-button navigation insets. Full Library interaction acceptance remains open despite the successful APK build/install.
- [ ] On mobile web, verify sign-in, both search screens, browser confirmation/cancellation, external watch links, refresh failures, and Back. Web remains a development convenience.

## Pins and owner-only moves

- [ ] Pin two or three playlists from overview and details. Pinned entries appear first, in pin order, without duplicates. Search both sections; changing sort affects only the remaining playlists. Unpin and repin; no hard limit of three applies.
- [ ] Sign into the same account on another device, refresh and see the same pins. Sign out and into the second fixture account: no personal pins or move receipts leak. Check offline/failure feedback, recovery on focus/reconnect, and double taps.
- [ ] On the connection page, verify only the connected administrator can configure moves or request broader Google access. Decline the upgrade and confirm read-only sync still works. In the fixture, reject identical, missing, special, or another channel's playlists. Saving valid choices binds IDs; renaming retains their meaning.
- [ ] Only in the configured added playlist, tap **Move to watched**. The dialog names the video and both playlists. Cancel first: no provider write. Confirm deliberately: progress remains visible across navigation, then the exact source entry disappears after server confirmation. The watched playlist contains the video; other catalog occurrences remain and show **In watched playlist**.
- [ ] Check a video already in watched: no duplicate is added. Duplicate source entries remain separate; moving one removes only that chosen entry. Opening YouTube alone never changes a playlist.
- [ ] In the disposable fixture, lose the insert response or fail removal. Status must show unknown or **Saved to watched; still in added**. No automatic replay. Confirm **Finish removal from added** and verify it rechecks watched, removes only the source, and does not insert again.
- [ ] Test process death, a lost database lock, repeated request IDs, simultaneous sync, changed ownership/channel, expired grant and quota failure. Backend integration tests cover these; do not inject failures in production.
- [ ] Reload/relaunch after a move, fail a status read, and restore connectivity. Preserve the last confirmed result and recover it. Unknown receipts must not become retryable additions merely because a later status read fails. Offline mutations are not queued.
- [ ] Remove a watched membership in the fixture, complete a sync, and verify badges clear even though saved destination metadata is retained. Fail a fetch partway: the last confirmed membership remains. The legacy shared `watched` boolean does not create a badge.
- [ ] Repeat pins, move/cancel/partial recovery, long titles, sort layout, largest text plus keyboard, and screen-reader focus on iPhone and Android. Native build/export success alone does not close these checks.
- [ ] Live acceptance only after explicit Google consent and choosing the two intended playlists. Select a specific real video that you intend to move; verify its receipt and both YouTube playlists. No arbitrary live video should be used as a test item.

## Disposable local fixture

Run `poetry run python scripts/library-preview-fixture.py` in an environment synchronized with `poetry.lock`. It uses temporary SQLite storage, two disposable accounts, seven playlists, a 150-video playlist plus move examples, synthetic artwork, missing artwork, and a missing watch link. Account 1 is the connected administrator; account 2 is an ordinary viewer. It disables dotenv/cloud metadata and mocks imports and YouTube writes; it does not contact YouTube, OAuth, or S3. Stop the process to remove its database.

Use `EXPO_NO_DOTENV=1 EXPO_PUBLIC_API_URL=http://127.0.0.1:5057 npx expo start --dev-client --port 8089` in `mobile/`. Android needs `adb reverse tcp:5057 tcp:5057` and `adb reverse tcp:8089 tcp:8089`. Credentials are printed by the fixture. The watch link is a public sample video; opening it is the only intentional external video interaction.

Control local failure scenarios with a POST to `http://127.0.0.1:5057/fixture/state`:

```json
{"sync":"unavailable","reads":"failure","delay":0}
```

`sync` accepts `success`, `unavailable`, `upstream`, or `unexpected`; `reads` accepts `success`, `failure`, or `empty`; `delay` is seconds before the import completes. Use 35 seconds for timeout/status recovery. Restore `{"sync":"success","reads":"success","delay":0}` afterward. These controls exist only in this script, not in the application routes.

For moves, set `{"move_failure":"insert-unknown"}` to accept an addition but lose its response, or `{"move_failure":"removal"}` to leave the source in place. Restore `{"move_failure":"none","move_delay":0}` before deliberately retrying removal. `move_delay` delays the fake insertion; 35 seconds exercises HTTP timeout/status recovery. `/fixture/move-events` exposes only this disposable provider's calls for verification. Restart the fixture for a clean source entry.

## Recorded results

Automated checks and native findings are recorded in mobile validation. The checklist above is for the complete acceptance pass; simulator inspection does not mark physical-device items complete. Existing Grocery/Wishlist accessibility, Android interaction, cold-link, photo-renewal, production EAS configuration, and credential-retirement follow-ups remain open unless separately verified.

The v136 controlled import completed at **3:10:22 p.m. EDT on October 10** and its successful receipt was read from a fresh server process afterward. It checked 181 playlists / 10,755 entries, added no videos, populated 10,557 positions, and skipped 198 unavailable entries. The larger retained catalog stays at 186 playlists / 10,918 videos. The first import's changed count includes adding position metadata. On the new phone preview, verify this saved result appears before starting another deliberate import.

Keith's subsequent phone screenshot confirms the receipt and 186-playlist catalog were displayed in preview `b73edbc5`, and exposed clipped sort text. The repair reproduced and fixed that clipping in the iPhone 18 Pro / iOS 27 simulator against disposable data. Both menus, playlist reordering, 150-video YouTube ordering, and normal/largest text layouts passed. See the [sort repair evidence](mobile-ui-validation.md#library-sort-clipping-repair--october-10). Physical-device checklist items stay unchecked until the repaired preview is installed and tested.
