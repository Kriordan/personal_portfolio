# Clean Up Service-Backed Routes (`cleanup-service-backed-routes`)

Date: 2026-07-06
Todo ID: `cleanup-service-backed-routes`

## Objective

Do a focused cleanup pass on the learning, wishlist, and library service-backed web routes so no placeholder routes remain that imply CRUD behavior but return hard-coded strings, while keeping browser flows compatible.

## Scope Delivered

- Removed the three stubbed Jinja wishlist routes from `project/wishlist/views.py`:
  - `POST /wishlist/gifts` (`gift_create`) — returned `"Item added to wishlist"`
  - `GET /wishlist/gifts/<int:item_id>` (`gift_detail`) — returned `"Item read from wishlist"`
  - `PUT /wishlist/gifts/<int:item_id>` (`gift_update`) — returned `"Item updated in wishlist"`
- Fixed stale docstrings in `project/library/views.py` (`library_home` and `view_playlist` both claimed to render `library.html`; they render `playlists.html` and `playlist.html` respectively).
- Removed vestigial `# Python` header comments from `project/wishlist/views.py` and `project/library/views.py`.
- Confirmed `project/learning/views.py` needed no changes — all routes already delegate to `learning_service` and contain no placeholders.

## Legacy Behavior Ported

- All browser-facing wishlist behavior is preserved: `wishlist.wishlist_home` (list + create via `GiftForm`) and `wishlist.gift_delete` (confirm + delete) are the only endpoints the wishlist templates reference (`wishlist.html`, `gift_delete_confirm.html`), and both remain unchanged.
- Library `export_subscriptions` was intentionally left as-is, calling `project/library/jobs.export_subscriptions_to_json` directly, per the plan's guidance to keep that behavior separate absent a clear service boundary.

## Architecture and Design Choices

### 1) Remove wishlist stubs rather than implement them

- What was done: Deleted `gift_create`, `gift_detail`, and `gift_update` from the Jinja blueprint instead of wiring them through `wishlist_service`.
- Why this approach was chosen: A repo-wide search found no template, JS, or test references to these endpoints. Full gift CRUD already exists with real service-backed implementations in the JSON API (`project/api/wishlist.py`, registered under `/api/v1/wishlist/gifts` with GET/POST/PUT/DELETE). The browser flow only needs the form-based create on `wishlist_home` and the confirm-page delete, both of which already exist.
- Trade-offs considered: Implementing the stubs through `wishlist_service` would duplicate the API surface for clients that don't exist; the mobile client planned in the migration will use `/api/v1/wishlist/*` instead.
- Key implementation details: This resolves the open item recorded in `./2026-03-12__services-wishlist.md` ("Decide whether to implement the currently stubbed Jinja wishlist routes ... or remove them if obsolete").

### 2) Leave learning and library route logic untouched

- What was done: Verified both view modules are already thin wrappers around `learning_service` and `library_service`, then limited changes to docstring/comment corrections in library views.
- Why this approach was chosen: The plan's acceptance criterion is thin service-backed routes with no behavior change; introducing refactors here would widen the review boundary.
- Trade-offs considered: Extracting `export_subscriptions_to_json` into `library_service` was considered and rejected — the plan explicitly keeps export-subscriptions separate unless a clear service boundary emerges.

## Files Created

- `docs/notes/2026/2026-07-06__cleanup-service-backed-routes.md` — this implementation note.

## Files Modified

- `project/wishlist/views.py` — removed the three placeholder gift routes and a header comment.
- `project/library/views.py` — corrected two stale docstrings and removed a header comment.

## API Contract

- No API contract changes. The removed routes were Jinja-blueprint placeholders under `/wishlist/gifts` that returned plain strings; real gift CRUD remains at `/api/v1/wishlist/gifts` (unchanged).
- Remaining wishlist web routes: `GET|POST /wishlist/` and `GET|POST /wishlist/gifts/<int:item_id>/delete`.

## Validation and Verification

1. Searched the repo for references to `wishlist.gift_create`, `wishlist.gift_detail`, and `wishlist.gift_update` — none exist in templates, JS, or tests.
2. Ran `poetry run python -m unittest tests.test_api_feature_registration tests.test_api_auth tests.test_socket_auth` — 11 tests passed.
3. Booted the app via `create_app()` and dumped the URL map: the stub endpoints are gone; `wishlist.wishlist_home`, `wishlist.gift_delete`, all `/api/v1/wishlist|learning|library` routes, and all library/learning web routes remain registered.
4. Ran linter diagnostics on the edited files — no errors.
5. Grepped `project/` for `TODO`, `FIXME`, `placeholder`, and `stub` — no matches remain.

## Known Gaps / Follow-ups

- Detailed feature API behavior tests for learning, wishlist, and library are deferred to the dedicated API-tests todo (plan phase 3).
- Pre-existing full-suite failures noted in `./2026-07-01__register-existing-feature-apis.md` (`tests/test_card_builder.py` import of removed `_build_cards`, one `tests/test_scheduler.py` 302-vs-200 assertion) remain out of scope and unresolved.

## How to Run (Current)

1. Run the focused regression checks:

```bash
poetry run python -m unittest tests.test_api_feature_registration tests.test_api_auth tests.test_socket_auth
```

2. Exercise the surviving browser flow: log in, visit `/wishlist/`, add a gift via the form, then delete it via the `X` link (which routes through `/wishlist/gifts/<id>/delete`).
3. Confirm the removed stubs are gone (should 404/405 rather than return placeholder strings):

```bash
curl -i -X POST https://localhost/wishlist/gifts
```
