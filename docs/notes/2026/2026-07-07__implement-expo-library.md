# Implement Mobile Library Browsing and Sync (`implement-expo-library`)

Date: 2026-07-07
Todo ID: `implement-expo-library`

## Objective

Add library browsing (YouTube playlists and their videos) and a manual sync trigger to the Expo app, consuming the existing `/api/v1/library` endpoints.

## Scope Delivered

- Typed library API client `mobile/src/lib/library-api.ts` covering `GET /library/playlists`, `GET /library/playlists/:id`, `GET /library/videos/:id`, and `POST /library/sync`, plus `libraryKeys` query keys.
- Playlist overview screen `mobile/src/app/library/index.tsx`: playlist list with thumbnails, pull-to-refresh, and a Sync Library button with pending/success/error feedback.
- Playlist detail screen `mobile/src/app/library/[id].tsx`: playlist header plus video rows (thumbnail, published date, watched marker); tapping a video opens it on YouTube.
- Navigation: `library/index` and `library/[id]` registered in `mobile/src/app/_layout.tsx`; Library button added to the home hub in `mobile/src/app/index.tsx`.

## Prior Art / Context

- Screens follow the wishlist/learning pattern established in `./2026-07-07__implement-expo-wishlist.md`: feature `*-api.ts` module with types and query keys, inline react-query in screens, auth redirect guard, and the shared loading/error/empty conventions.
- The backend contract was already shipped and tested (`project/api/library.py`, `tests/test_api_library.py`); no backend changes were needed.

## Architecture and Design Choices

### 1) String IDs throughout

- Playlist and video IDs are YouTube IDs (strings), unlike the numeric IDs in wishlist/learning. The API module and route params treat them as strings, and path segments are `encodeURIComponent`-escaped defensively since the IDs come from an external system.

### 2) Sync as a mutation that invalidates all library queries

- `POST /library/sync` takes no body and re-imports playlists/videos server-side. The sync button uses `useMutation` and on success invalidates `libraryKeys.all` (`['library']`), so both the playlist list and any cached playlist details refetch fresh data.
- The button is disabled while pending to avoid duplicate concurrent syncs (per the plan's "avoid duplicate submissions" criterion), and the server's success message or the `ApiError` message is shown inline.
- Note: the backend sync route has no try/except, so a failed sync (e.g. missing YouTube credentials) surfaces as a 500; the screen shows the generic error text in that case.

### 3) Videos open externally instead of an in-app player

- Tapping a video calls `Linking.openURL` with `https://www.youtube.com/watch?v=<video_url_id>`, which hands off to the YouTube app or browser. Embedding playback would require a WebView dependency (`react-native-webview`) that isn't in the project; external handoff matches the browse-oriented scope of this todo. The `GET /library/videos/:id` endpoint is included in the API module for completeness but no dedicated video screen was needed.

### 4) Read-only detail screen with dynamic title

- The detail screen sets the header title to the playlist name via `<Stack.Screen options>`, mirroring the wishlist detail screen. `watched` is displayed but not mutable — the backend exposes no watch-toggle endpoint.

## Files Created

- `mobile/src/lib/library-api.ts`
- `mobile/src/app/library/index.tsx`
- `mobile/src/app/library/[id].tsx`
- `docs/notes/2026/2026-07-07__implement-expo-library.md` (this note)

## Files Modified

- `mobile/src/app/_layout.tsx` — registered `library/index` and `library/[id]` stack screens.
- `mobile/src/app/index.tsx` — added Library button to the home hub.

## API Contract

Consumed (all JWT Bearer, defined in `project/api/library.py`):

- `GET /api/v1/library/playlists` → `{"playlists": [{id, title, description, published_at, updated_at, thumbnail_url}]}`
- `GET /api/v1/library/playlists/<id>` → `{"playlist": {...}, "videos": [{id, playlist_id, video_url_id, title, description, published_at, thumbnail_url, embed_url, watched, created_at, updated_at}]}`; 404 `{"error": "Playlist not found."}`
- `POST /api/v1/library/sync` → `{"message": "Library sync completed."}`

## Validation and Verification

1. `./node_modules/.bin/tsc --noEmit` in `mobile/` — clean (after regenerating Expo Router typed routes by briefly starting the dev server so the new `/library` routes type-check).
2. `npm run lint` (`expo lint`) in `mobile/` — clean.
3. No device/simulator end-to-end run in this pass; screens follow the same query/mutation patterns as the verified wishlist and learning features against the tested API contract.

## Known Gaps / Follow-ups

- No in-app video playback; videos open in the YouTube app/browser.
- `watched` state is display-only (no backend endpoint to toggle it).
- Sync errors from the backend arrive as unhandled 500s without a structured message; a backend try/except mapping credential errors to a 4xx/JSON error would improve the mobile error text.
- Mobile unit tests remain deferred, consistent with prior feature phases.

## How to Run (Current)

1. Start the backend: `flask --app project run --port 5001 --debug`.
2. `cd mobile && npm install && npm start`, open a simulator, and sign in.
3. Tap Library on the home screen: playlists load from `GET /api/v1/library/playlists`.
4. Tap Sync Library to trigger `POST /api/v1/library/sync` (requires YouTube credentials in `project/data/youtube_token.json`; without them the sync fails with an error message).
5. Tap a playlist to see its videos; tap a video to open it on YouTube.
