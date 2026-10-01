# iPhone smoke test: Home, Tools, Me, and Grocery

Use the [September 30 preview](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/2c5db3b7-ac92-4a66-befe-cd7af0186eba) and the same account on the [website's Lists page](https://keithriordan.herokuapp.com/lists). This build uses live data. Use a list named **iPhone smoke test** to keep the checks easy to recognize.

Allow about 15–20 minutes. Tick each box when its expected result holds. For a failure, note the step, what happened, and whether you were on Wi-Fi or cellular; a screenshot or short recording helps.

## Already confirmed by Keith

- [x] The preview installs and opens on the physical iPhone.
- [x] A list created on the phone appears on the website under the same account.
- [x] Initial visual inspection looks good.
- [x] Phone-created items reach the website without manual reload; completion changes work in both directions for visible items.

## Reported failures — September 30

The original preview fails **Website → phone, live** and **Background recovery** for newly created website items. Pull-to-refresh retrieves them; completion then works. These are recorded failures, not additional setup steps for the tester.

The fix is in PR #89: website form saves now broadcast creation events, and Grocery always refetches on foreground/network recovery. Local tests and the iOS simulator pass. Physical-device retesting is pending a website deployment and replacement preview; the original preview linked above is unchanged.

When both updates are available, retest:

1. With the list foregrounded on the phone, create an item with quantity/notes on the website. It should appear immediately, once, without pull-to-refresh.
2. Create a category on the website, then an item in it. Both should appear on the phone.
3. Check and uncheck the new item from each client; both stay synchronized.
4. Return to the iPhone Home Screen, add an item on the website, and reopen the app within 30 seconds. Repeat after a longer background interval. Both times the item should appear automatically.

## Main flow

- [ ] **Create and navigate.** From Home, open Grocery and create **iPhone smoke test**. The new list opens. Back returns to the overview, where the list appears once; Home also links to it.
- [ ] **Enter a complete item.** Add categories **Produce** and **Pantry**. Add **Apples**, quantity **6**, notes **For lunches — keep every character**, under Produce. Add **Olive oil** under Pantry. The keyboard leaves the save controls reachable; names, quantity, notes, and category are correct after saving. Reopening the item form starts with empty fields.
- [ ] **Avoid duplicate saves.** Create one more item, **Bread**, and tap Save twice quickly. Exactly one item is created. The save control is disabled while saving.
- [ ] **Complete and undo.** Check Apples, then uncheck it. Its checked appearance, placement, and remaining/completed counts update correctly. Taps do not toggle it twice.
- [x] **Phone → website, live.** Keep this list's detail page open in both clients. Add an item and check it on the phone. The website updates without a manual reload.
- [ ] **Website → phone, live.** Add **From the website** and toggle an item on the website. The phone updates without leaving the list. Leave its screen unlocked and foregrounded for this check.

## Recovery and navigation

- [ ] **Background recovery.** Go to the iPhone Home Screen. Add **While away** on the website, then return to the app. The new item appears and the live-updates indicator reconnects.
- [ ] **Offline draft recovery.** Open Add category and enter **Offline draft**. Turn on airplane mode and make sure Wi-Fi is also off; wait for disconnection, then save. The app reports a failure and preserves the text. Restore connectivity. The category must not save itself; retry once, then confirm it appears exactly once in both clients.
- [ ] **Cold launch.** Close the app from the app switcher, then open it again. Your session restores, Home loads, and reopening the list shows the saved items.
- [ ] **Tools and account.** Tools shows the five existing services. Filtering for **wish** shows Wishlist; clearing the filter restores the directory. Open another tool and return with Back. Me shows the correct account.
- [ ] **Sign out and return.** Sign out from Me. The login screen appears and Back does not reveal private screens. Sign in again; the same lists return. The website has its own login session and may remain signed in.

## Readability and accessibility

- [ ] **Light and dark.** Check Home, Grocery overview/detail, and an item form in both appearances. Text, completion controls, and error messages remain readable.
- [ ] **Larger text and keyboard.** Increase iOS text size, then open an item form and type in its last field. Labels remain readable; Save and Close remain reachable by scrolling. Restore your preferred text size afterward.
- [ ] **VoiceOver.** Navigate the tabs, list rows, item checkboxes, and a form. Controls have useful names, checkboxes announce checked/unchecked state, and focus can reach every action without getting trapped. Turn VoiceOver off afterward if you do not normally use it.

## Follow-up checks

- [ ] **Display settings.** On the website, change the list's completed-item display mode; reopen the list on the phone. Check each mode: inline, per-category completed sections, and one global completed section. The website currently does not broadcast settings changes, so reopening is expected.
- [ ] **Cold deep link (with Codex's help if useful).** Use this list's numeric ID from its website URL to open `personal-portfolio:///lists/ID` from a tappable link while the app is closed. Verify the intended list and usable Back navigation. Repeat while signed out: authentication must be required. Record where the app lands after login.

## Results to send back

Copy this and fill in only what is useful:

```text
iPhone model / iOS version:
Preview: September 30, 2026
Passed steps:
Failed or confusing steps:
Expected → actual:
Reproduction steps:
Screenshot / recording:
```

Android emulator coverage and automated results are recorded in [mobile-ui-validation.md](mobile-ui-validation.md). The remaining checks can use the installed preview without a running Mac; retesting the reported realtime/recovery failures requires the replacement preview and website deployment described above.
