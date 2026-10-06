# Wishlist smoke test — October 6, 2026

Use the Wishlist preview identified in [mobile validation](mobile-ui-validation.md), with the matching deployed backend. Older previews do not contain these controls. Use gifts named **Wishlist smoke test** and a nonpersonal photo; the standalone preview uses live storage. Photo removal/deletion clears the gift's reference, but does not erase the S3 object.

**Current gate:** preview `38115e8e-06bd-4e9e-844e-11cdbaef57c1` has built, but the matching backend deployment awaits approval and production has no `WISHLIST_S3_BUCKET`. Complete those steps before the full live photo checklist. The disposable fixture below can exercise the new contract independently of production.

## iPhone checklist

- [ ] Install the preview, cold-launch, restore/sign into your account, and open Wishlist through Home and Tools.
- [ ] Create **Wishlist smoke test** without a photo. Enter both fields rapidly and double-tap Add gift. Every character persists, the new detail opens, and Back shows the gift once.
- [ ] Create a second gift with a library JPEG/PNG/HEIC. Check correct orientation and proportions, then relaunch and verify its photo is still visible. A large photo is resized; an unsupported/unreadable photo produces a useful error while retaining text.
- [ ] Cancel the picker. The current photo and text stay unchanged. Choosing one photo should not require granting access to the whole library or microphone/camera.
- [ ] Search by title and description, try a query with no matches, then clear it. Verify newest-first ordering and a stable thumbnail/placeholder for each row.
- [ ] Open the three-dot options. Edit both fields, replace the photo, save, and reopen. Repeat with Remove photo and verify it stays removed after relaunch.
- [ ] Try Remove photo, then Undo photo change. Close a changed form, cancel Discard, and verify the draft remains intact. Repeat using a swipe dismissal and system Back where available.
- [ ] Enter 140 characters, then 141. Both title and description are required and limited to 140; over-limit text is visible rather than silently truncated.
- [ ] Turn on airplane mode with Wi-Fi off while editing. Save reports failure and retains the draft. Reconnect: no mutation runs automatically. Retry deliberately and verify the saved result. For an uncertain save, check Wishlist before repeating creation.
- [ ] Cancel Delete and verify the gift still exists. Delete only the labelled test gift; confirm it disappears and navigation returns to Wishlist.
- [ ] Reload the website's Wishlist and check the same data. Create/delete a test gift on the website while the app is backgrounded, then return within 30 seconds. Verify foreground recovery and manual pull-to-refresh. Wishlist has no realtime socket events.
- [ ] Try a deleted/invalid gift link. It shows an unavailable state with a route back, without an endless spinner. Test warm and terminated-app links to `personal-portfolio:///wishlist/ID`, both signed in and signed out.
- [ ] Check light/dark appearance, largest Dynamic Type with software keyboard, and a smaller phone. All form content—including its heading, errors, photo controls, and Save/Close—must remain reachable by scrolling.
- [ ] With VoiceOver, check focus order, field labels, gift rows, options, photo states, alerts, and confirmation buttons.
- [ ] Regression: Home counts/links, Tools search, Me sign-out, protected-route privacy, and Grocery create/edit/delete/completion/website synchronization.

## Android and web

- [ ] Install the rebuilt Android client on the ARM64/16 KB-page emulator. Repeat CRUD, picker cancellation/upload, removal/undo, failure recovery, and Back/discard checks.
- [ ] Verify native field widths, large fonts plus keyboard, TalkBack, pull-to-refresh, and gesture/three-button navigation insets.
- [ ] In mobile web, verify CRUD, browser photo selection/upload, deletion confirmation, refresh failures, and navigation/discard prompts. Web remains a development convenience.

## Disposable local fixture

`poetry run python scripts/wishlist-preview-fixture.py` creates a temporary SQLite database, three gifts, and a disposable account. It disables dotenv and cloud metadata access; photos use real image validation but temporary local storage. It never contacts S3. Use `EXPO_PUBLIC_API_URL=http://127.0.0.1:5057` for Metro. Android requires `adb reverse tcp:5057 tcp:5057` and a reverse mapping for Metro's port.

The fixture prints its disposable credentials. Native modules changed, so rebuild the development clients before opening the bundle. Local fixtures do not establish live S3 readiness.

## Results

Record device/OS, preview build ID, backend release, checked steps, and any expected-versus-actual result. A compiled native app or installable IPA alone is not a passed device test.
