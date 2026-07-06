# Add Feature API Tests For Existing Domains (`test-existing-feature-apis`)

Date: 2026-07-06
Todo ID: `test-existing-feature-apis`

## Objective

Add focused behavior tests for the learning, wishlist, and library `/api/v1/` endpoints covering auth, validation, not-found, ownership, and JSON payload contracts, so the mobile client can rely on these contracts and regressions to 404/contract drift are caught.

## Scope Delivered

- `tests/test_api_learning.py` (13 tests): notes list/detail, review queue, and rate endpoints, including validation and per-user progress scoping.
- `tests/test_api_wishlist.py` (13 tests): gift CRUD, including owner-scoped access checks and a mocked S3 image upload path.
- `tests/test_api_library.py` (7 tests): playlist/video read endpoints and the sync trigger with the YouTube job mocked.
- Fixed a latent timezone bug in `project/services/learning_service.py` that the new tests exposed: naive `next_review` values loaded from SQLite crashed due-card comparisons and next-review display formatting.

## Prior Art / Context

- Follows the conventions of `tests/test_api_auth.py` and `tests/test_socket_auth.py`: plain `unittest`, in-memory SQLite via `create_app(test_config)`, requests issued with `base_url="https://localhost"` (Talisman forces HTTPS), and JWTs minted directly with `flask_jwt_extended.create_access_token` inside an app context.
- Builds on the route activation from [./2026-07-01__register-existing-feature-apis.md](./2026-07-01__register-existing-feature-apis.md); those smoke tests only proved routes existed, while these tests pin endpoint behavior.

## Architecture and Design Choices

### 1) Real DB fixtures, targeted mocks for external systems only

- What was done: Tests create `User`, `Gift`, `Playlist`, `Video`, `ReviewProgress`, and `ReviewLog` rows through the real SQLAlchemy models against in-memory SQLite. Only two things are mocked: `project.services.wishlist_service.upload_image_to_s3` (S3) and `project.services.library_service.sync_playlists_and_videos` (YouTube sync).
- Why: The plan explicitly warned against over-mocking services; exercising the real service layer means the tests protect actual behavior, not mock wiring.
- Trade-offs: Slightly slower tests and exposure to SQLite quirks (which surfaced a real bug — see decision 3).
- Key details: Sync tests assert both that the mocked job runs exactly once when authenticated and that it is never invoked on a 401.

### 2) Learning notes served from a temp directory

- What was done: Each learning test writes a note JSON fixture into a `tempfile.TemporaryDirectory` and patches `project.services.learning_service.notes_dir_for_root` to return it.
- Why: The API resolves notes from the repo-level `notes/` directory at request time; patching the resolver isolates tests from real notes content that changes over time.
- Trade-offs: Patching a service function couples tests to that seam, but it is the single choke point every learning endpoint already uses.
- Key details: The fixture note `flask-basics` has one `qa` flashcard, giving a stable card ID `flask-basics:q1` for review/rate assertions.

### 3) Normalize naive datetimes in the learning service

- What was done: Added `_ensure_aware()` to `project/services/learning_service.py` and applied it where persisted `next_review` values are compared or subtracted (`summarize_notes_for_user`, `review_cards_for_user`, `format_next_review_display`).
- Why: SQLite deserializes `DateTime(timezone=True)` columns as naive datetimes, so rating a card then computing its display or due status raised `TypeError: can't subtract offset-naive and offset-aware datetimes`. This mirrors the existing normalization pattern in `InvitationMixin.is_expired` in `project/models.py`.
- Trade-offs: Normalization at comparison sites rather than a global SQLAlchemy type decorator keeps the change minimal; a repo-wide UTC type could be a future refactor.
- Key details: Assumes stored values are UTC, consistent with all model defaults using `datetime.now(timezone.utc)`.

### 4) Ownership is asserted through indistinguishable 404s and data isolation

- What was done: Wishlist tests verify a second user gets 404 (not 403) for another user's gift on GET/PUT/DELETE and that the underlying row is untouched. Learning tests verify one user's rating does not consume another user's due queue.
- Why: The wishlist service intentionally hides foreign resources as not-found; the tests pin that contract so the mobile client can treat 404 uniformly. Library content is deliberately shared (no ownership), so its tests only cover auth.

## Files Created

- `tests/test_api_learning.py` — learning API behavior tests.
- `tests/test_api_wishlist.py` — wishlist API behavior and ownership tests.
- `tests/test_api_library.py` — library API behavior tests with mocked sync.
- `docs/notes/2026/2026-07-06__test-existing-feature-apis.md` — this note.

## Files Modified

- `project/services/learning_service.py` — added `_ensure_aware()` and used it in due-card comparisons and next-review display to tolerate naive datetimes from the DB layer.

## API Contract

Contracts pinned by tests (all under `/api/v1`, all requiring a Bearer access token):

- `GET /learning/notes` → `{"notes": [{id, title, summary, flashcard_count, due_count, ...}], "total_due": int}`.
- `GET /learning/notes/<id>` → `{"note": {..., "flashcards": [{card_id, note_id, note_title, type, tags, prompt, response}]}}`; unknown ID → 404 `{"error": "Note not found."}`.
- `GET /learning/review` → `{"cards": [...]}` scoped to the requesting user's progress.
- `POST /learning/rate` → 200 `{card_id, learning_state, interval, repetitions, easiness, next_review, next_review_display, scheduler_version}`; 400 for missing fields, non-integer rating, out-of-range rating (0–5), malformed `card_id`; 404 for unknown cards. Persists `ReviewProgress` and `ReviewLog` (including `response_ms`, `session_id`).
- `GET/POST /wishlist/gifts`, `GET/PUT/DELETE /wishlist/gifts/<id>` → gift payload `{id, title, body, image_url, timestamp, user_id}`; 201 on create, 400 `{"error": ...}` on blank title/body, 404 for unknown or foreign gifts.
- `GET /library/playlists` (newest first), `GET /library/playlists/<id>` (playlist plus its videos, newest first), `GET /library/videos/<id>`; 404 with `Playlist not found.` / `Video not found.`. `POST /library/sync` → 200 `{"message": "Library sync completed."}`.

## Validation and Verification

1. `poetry run python -m unittest tests.test_api_learning tests.test_api_wishlist tests.test_api_library` — 33 tests, all pass.
2. `poetry run python -m unittest tests.test_api_feature_registration tests.test_api_auth tests.test_socket_auth tests.test_scheduler tests.test_queue_builder tests.test_hlr_scheduler` — only pre-existing failure remains (`test_scheduler.SchedulerIntegrationTests.test_rate_creates_log_and_intra_day_review` expects 200 but gets 302), already documented in the 2026-07-01 note and unrelated to this change.
3. Linter diagnostics on the three new test files and `project/services/learning_service.py` — clean.

## Known Gaps / Follow-ups

- No tests for `POST /learning/notes`-style authoring flows (`create_incident_card`) because no API route exposes them yet.
- Wishlist image upload asserts the mocked S3 path only; real `upload_image_to_s3` behavior (bucket env var, credential fallback) is untested.
- The pre-existing `tests/test_card_builder.py` import failure (`project.learning.views._build_cards` was removed) and the `test_scheduler` 302 failure remain unresolved; both predate this todo.
- A repo-wide timezone-aware SQLAlchemy type could replace point normalizations like `_ensure_aware()`.

## How to Run (Current)

1. Run the new feature API tests:

```bash
poetry run python -m unittest tests.test_api_learning tests.test_api_wishlist tests.test_api_library
```

2. Or run the broader API/auth/socket set:

```bash
poetry run python -m unittest tests.test_api_feature_registration tests.test_api_auth tests.test_socket_auth tests.test_api_learning tests.test_api_wishlist tests.test_api_library
```
