# iPhone smoke test: Grocery editing and duplicate warnings

This follow-up adds Edit controls beside the list title, category headings, and item rows. Open Edit to rename or delete; item editing also changes quantity, notes, and category. Only the owner can rename or delete a whole list. Shared members can edit and delete its items and categories.

**Ready for live testing:** install the [October 3 iPhone preview](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/5acf57e2-adcf-43ec-b48f-e22fb7894772), built from `0e603ea`. Its backend is deployed as **Heroku v124**, from `7f77799`, on October 3 at 18:08 UTC. Startup and read-only route checks passed; authenticated edit/delete testing is the next step. This change is in [PR #94](https://github.com/Kriordan/personal_portfolio/pull/94). The October 1 preview does not contain these controls.

Use a disposable list named **Editing smoke test**, with **Produce** and **Pantry** categories. Keep the same list open on the [website](https://keithriordan.herokuapp.com/lists), using the same account. Reload the website once after the backend release to load its new event listeners. This preview uses live data; only delete test entries you intend to remove.

## Checklist

- [ ] **Edit an item.** Add Apples under Produce. Tap its Edit button: the checkbox must not toggle. Change quantity to 6 and notes to For lunches. Save, reopen, and confirm all fields persisted. The website should update automatically.
- [ ] **Warn about duplicates.** Try adding ` apples `, then `Apple`, then `Appls`. Each should warn about Apples, including its category and completion state. Keep editing must preserve the draft. Choose Add anyway for Apple; two separate entries should exist. Unrelated names such as Apple juice should not warn.
- [ ] **Delete only the extra item.** Open Edit on Apple, choose Delete item, then Keep editing. Nothing should disappear. Repeat and confirm deletion: only Apple disappears; Apples and its quantity/notes remain. Confirm on the website.
- [ ] **Move a completed item.** Complete Apples, edit it, and move it to Pantry. It stays checked, appears under the correct category/completed section, and retains quantity/notes. Renaming another item to Apples should also warn; changing only quantity/notes on Apples should not.
- [ ] **Rename and delete a category.** Rename Pantry to Cupboard. Confirm both clients update. Delete Cupboard: the confirmation must explicitly say that all its items, including completed items, will be removed. Confirm only that category and its contents disappear; Produce remains.
- [ ] **Rename and delete a list.** Use Edit beside the list title to rename it. Confirm the title in the detail page and overview. Delete this disposable list after reviewing the confirmation. The app returns to Grocery; the website returns to Lists; the deleted list stays gone after reopening. Other lists remain.
- [ ] **Recover an offline draft.** Edit an item in another disposable list. Turn on airplane mode with Wi-Fi off, wait for disconnection, then save. The app should show a failure and retain the entered text. Reconnect: it must not save automatically. Retry once and confirm the result in both clients.
- [ ] **Shared access, if available.** As a shared member, item/category Edit controls work, but the list-title Edit control is absent. The owner remains able to rename/delete the list.
- [ ] **Readability and accessibility.** Check the Edit buttons and confirmation sheets in dark mode and with larger text/the software keyboard. With VoiceOver, Edit actions should name their item/category/list and remain distinct from completion checkboxes.

Duplicate warnings are advisory and use the currently loaded list, across all categories and including completed items. They account for capitalization, spacing/punctuation, accents, simple English plurals, and conservative spelling errors. They do not merge entries, understand synonyms, or prevent simultaneous additions from separate clients. Website additions do not yet show these warnings or new editing controls.

## Local verification — October 3, 2026

All 104 backend tests and 18 mobile tests passed. Coverage includes owner/shared/outsider permissions, cross-list IDs, validated partial edits, moving a completed item, deletion cascades with foreign keys enabled, room isolation, transport failure after persistence, cache invalidation, and duplicate matching.

The iPhone 18 Pro / iOS 27 simulator passed item editing, duplicate warning/override, canceled and confirmed item deletion, moving a completed item, category rename/deletion, and list rename/deletion. The existing website reflected those changes without manual refresh. The shared list had no list-title Edit control. These checks used an isolated temporary database, not the user's account or data.

Physical iPhone testing, Android interaction checks for these new controls, and a full screen-reader pass remain outstanding. Build and static-check results are recorded in [mobile-ui-validation.md](mobile-ui-validation.md).
