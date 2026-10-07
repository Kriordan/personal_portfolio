# Library smoke test — October 7, 2026

Use the Library preview and backend release recorded in [mobile validation](mobile-ui-validation.md#library-modernization--october-7-2026). A successful native build is not a passed physical-device test. Record device/OS, source commit, build ID, backend release, and actual results for each checked step.

The [October 7 iPhone preview](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/fe2b446b-5742-4202-a0cc-0d91fb9d8228) contains source `44cbd1c` and is ready to install on the registered iPhone. Check mobile validation for the backend deployment status before evaluating the new sync-error responses.

Library is one shared catalog for all signed-in accounts. Pull-to-refresh reads saved data. **Sync from YouTube imports into that shared catalog using the server's connection**, and affects everyone. Do not use live sync for failure injection; use the fixture below. Opening YouTube never changes the shared watched flag.

## iPhone checklist

- [ ] Install the new preview, cold-launch, restore/sign in, and open Library from Tools. Verify Home, Tools filtering, Me, sign-out, and protected-route privacy.
- [ ] Browse playlists, including long titles and absent/broken artwork. Search title and description, mix case/whitespace, try no matches, and clear. Counts and newest-first ordering remain correct.
- [ ] Open a playlist, expand/collapse its description, search its videos, and scroll a long collection. Check the empty-playlist state. Missing watch links are disabled; shared watched badges are labelled as shared.
- [ ] Tap a video with YouTube installed and without it. The HTTPS watch link opens the app/browser. Return and verify search/scroll position. Exercise launch failure locally and retry. No watched status changes.
- [ ] Cancel the sync confirmation and verify no import runs. Confirm a deliberate import, tap repeatedly, and navigate away/back while pending. Only one request runs in this app session; browsing remains usable.
- [ ] In the fixture, test missing authorization (503), upstream failure (502), unexpected failure (500), and a delay over 30 seconds. Errors contain no provider details. Timeout reports completion unknown and offers saved-catalog refresh; it does not claim server cancellation or automatically repeat the import.
- [ ] Start offline and try syncing: immediate failure, no queue. Reconnect and verify no import starts until deliberately confirmed. Keep loaded content after a failed refresh; restore connectivity and retry.
- [ ] Verify a successful import followed by a failed read is described as a refresh failure, not a failed import.
- [ ] Use the website and another account to confirm the same catalog. Background the app, change fixture data, return within 30 seconds, and verify recovery. Repeat after reconnect and with manual pull-to-refresh.
- [ ] Open an invalid/deleted playlist link. Verify unavailable feedback and Back to Library. Test warm and terminated-preview links to `personal-portfolio:///library/PLAYLIST_ID`, signed in and signed out.
- [ ] Check light/dark mode, largest Dynamic Type with the software keyboard, and a smaller phone. Search, rows, errors, and actions remain reachable. Use VoiceOver to check focus order, labels, shared watched status, confirmation buttons, and announcements.
- [ ] Regression: Grocery create/edit/delete/completion and website creation events/reconnect; Wishlist CRUD, photo selection/removal/discard, private-photo renewal after 15 minutes, and foreground recovery. Preserve the existing checklists' unchecked items.

## Android and web

- [ ] On the rebuilt Android ARM64/16 KB-page client, repeat Library browsing/search, YouTube handoff/return, confirmation, sync failure, offline/reconnect, and invalid links.
- [ ] Verify native widths, large fonts plus keyboard, TalkBack, pull-to-refresh, and gesture/three-button navigation insets. Full Library interaction acceptance remains open despite the successful APK build/install.
- [ ] On mobile web, verify sign-in, both search screens, browser confirmation/cancellation, external watch links, refresh failures, and Back. Web remains a development convenience.

## Disposable local fixture

Run `poetry run python scripts/library-preview-fixture.py` in an environment synchronized with `poetry.lock`. It uses temporary SQLite storage, two disposable accounts, four playlists, 150 videos, synthetic artwork, missing artwork, and a missing watch link. It disables dotenv/cloud metadata and mocks imports; it does not contact YouTube, OAuth, or S3. Stop the process to remove its database.

Use `EXPO_NO_DOTENV=1 EXPO_PUBLIC_API_URL=http://127.0.0.1:5057 npx expo start --dev-client --port 8089` in `mobile/`. Android needs `adb reverse tcp:5057 tcp:5057` and `adb reverse tcp:8089 tcp:8089`. Credentials are printed by the fixture. The watch link is a public sample video; opening it is the only intentional external video interaction.

Control local failure scenarios with a POST to `http://127.0.0.1:5057/fixture/state`:

```json
{"sync":"unavailable","reads":"failure","delay":0}
```

`sync` accepts `success`, `unavailable`, `upstream`, or `unexpected`; `reads` accepts `success`, `failure`, or `empty`; `delay` is seconds before the import completes. Use 35 seconds for the uncertain-completion case. Restore `{"sync":"success","reads":"success","delay":0}` afterward. These controls exist only in this script, not in the application routes.

## Recorded results

Automated checks and native findings are recorded in mobile validation. The checklist above is for the complete acceptance pass; simulator inspection does not mark physical-device items complete. Existing Grocery/Wishlist accessibility, Android interaction, cold-link, photo-renewal, production EAS configuration, and credential-retirement follow-ups remain open unless separately verified.
