# Extract Library Domain Service (`services-library`)

Date: 2026-03-12
Todo ID: `services-library`

## Objective

Create a shared library service module that centralizes playlist/video read behavior and sync orchestration so both Jinja and API route layers rely on one domain surface. This keeps route handlers thin and reduces behavior drift between interfaces.

## Scope Delivered

- Added `project/services/library_service.py` with shared playlist/video serialization, read helpers, and sync orchestration.
- Added typed service error contract in the new module via `LibraryServiceError` and `NotFoundError`.
- Refactored `project/api/library.py` to delegate playlist/video reads and sync execution to `library_service`.
- Refactored `project/library/views.py` to delegate playlist/video reads and sync execution to `library_service`.
- Preserved existing route-level auth checks and API response structure while moving non-HTTP domain logic into services.

## Legacy Behavior Ported

- Preserved API unauthorized handling (`{"error": "Unauthorized."}`, 401) by keeping JWT/user resolution in route wrappers.
- Preserved API not-found semantics for playlist/video reads with the same `404` payloads.
- Preserved API response envelopes:
  - playlists list: `{"playlists": [...]}`
  - playlist detail: `{"playlist": {...}, "videos": [...]}`
  - video detail: `{"video": {...}}`
  - sync: `{"message": "Library sync completed."}`
- Preserved web route rendering targets (`playlists.html`, `playlist.html`, `video.html`) and sync redirect behavior to `foyer.utilities`.

## Architecture and Design Choices

### 1) Introduce a dedicated library service boundary
- What was done: Created `project/services/library_service.py` with `list_playlists()`, `get_playlist_with_videos()`, `get_video()`, `sync_library()`, `serialize_playlist()`, and `serialize_video()`.
- Why this approach was chosen: Playlist/video read and sync orchestration were embedded in route files; extracting them creates a reusable domain API shared by both web and API layers.
- Trade-offs considered: Added one new module and exceptions surface, but reduced duplicate ORM queries and payload shaping in multiple route modules.
- Key implementation details: `get_playlist_with_videos()` and `get_video()` raise `NotFoundError` for route-level mapping to HTTP/template responses; `sync_library()` wraps `sync_playlists_and_videos()`.

### 2) Keep route files as transport adapters
- What was done: `project/api/library.py` now performs auth/context checks and converts service results/errors to HTTP responses; `project/library/views.py` now handles template rendering and delegates domain fetch/sync work.
- Why this approach was chosen: This aligns with the existing service-oriented refactor pattern used in `learning` and `wishlist` domains.
- Trade-offs considered: Route files still contain auth/session concerns (intentionally), but no longer own playlist/video query orchestration.
- Key implementation details: API routes catch `library_service.NotFoundError`; web routes catch the same exception and return `404` template response.

### 3) Preserve API contract while changing internals
- What was done: Reused service-level serializers to keep payload fields and timestamp formatting unchanged.
- Why this approach was chosen: Avoids downstream client regressions while still moving logic out of route handlers.
- Trade-offs considered: Serializer ownership moved into services, which couples API shape to service functions; accepted for consistency with current architecture.
- Key implementation details: API routes now call `library_service.serialize_playlist()` and `library_service.serialize_video()` before `jsonify(...)`.

## Files Created

- `project/services/library_service.py` - new shared library domain module for playlist/video reads and sync orchestration.
- `docs/notes/2026/2026-03-12__services-library.md` - this implementation note.

## Files Modified

- `project/api/library.py` - refactored API handlers to delegate read/sync logic and serialization to `library_service`.
- `project/library/views.py` - refactored web handlers to delegate read/sync logic to `library_service`.

## API Contract

- No new library endpoint paths were introduced.
- Existing API paths under `/api/v1/library` remain:
  - `GET /playlists` -> `{"playlists": [...]}` (200) or unauthorized (401)
  - `GET /playlists/<playlist_id>` -> `{"playlist": {...}, "videos": [...]}` (200), not found (404), unauthorized (401)
  - `GET /videos/<video_id>` -> `{"video": {...}}` (200), not found (404), unauthorized (401)
  - `POST /sync` -> `{"message": "Library sync completed."}` (200) or unauthorized (401)

## Validation and Verification

1. Ran lint diagnostics with `ReadLints` on:
   - `project/services/library_service.py`
   - `project/api/library.py`
   - `project/library/views.py`
   Result: no linter errors.
2. Ran syntax verification:
   - `python -m compileall project/services/library_service.py project/api/library.py project/library/views.py`
   Result: success.
3. Captured change evidence using git inspection commands (`git status --short`, `git diff --name-status`, `git diff HEAD`, `git diff --cached`, `git log --oneline -20`) while documenting this todo.

## Known Gaps / Follow-ups

- Add automated API tests for `project/api/library.py` endpoint behavior (auth, not found, response payload shape).
- Add web route tests for `project/library/views.py` 404 behavior and sync redirect flow.
- Evaluate whether deeper sync internals from `project/library/jobs.py` should be progressively extracted into smaller pure service/domain helpers in a follow-up todo.

## How to Run (Current)

1. Start the Flask app in your local development setup.
2. Verify web flow:
   - Visit `/lib/` to view playlist listing.
   - Open `/lib/playlist/<playlist_id>` and `/lib/videos/<video_id>` for detail pages.
   - Trigger `/lib/sync_playlists` from the existing utilities flow and confirm redirect to utilities page.
3. Verify API flow with a valid JWT:
   - `GET /api/v1/library/playlists`
   - `GET /api/v1/library/playlists/<playlist_id>`
   - `GET /api/v1/library/videos/<video_id>`
   - `POST /api/v1/library/sync`
4. Confirm parity:
   - Payload fields for playlist/video responses are unchanged.
   - Not-found behavior remains `404` for missing playlist/video IDs.
