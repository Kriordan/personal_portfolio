# Implement Expo Learning/Review Screens (`implement-expo-learning`)

Date: 2026-07-07
Todo ID: `implement-expo-learning`

## Objective

Add learning/review screens to the Expo mobile app so an authenticated user can browse notes, inspect flashcards, and run a spaced-repetition review session against the existing `/api/v1/learning` endpoints.

## Scope Delivered

- `mobile/src/lib/learning-api.ts` — typed API module (`learningApi`) and query-key factory (`learningKeys`) covering all four learning endpoints.
- `mobile/src/app/learning/index.tsx` — notes overview: total-due "Start Review" button, per-note rows with card counts, tags, and due-count badges.
- `mobile/src/app/learning/[id].tsx` — note detail: tags, summary, and tap-to-reveal rendered cards; dedicated 404 "Note not found." state.
- `mobile/src/app/learning/review.tsx` — review session: show prompt → reveal answer → rate (Again/Hard/Good/Easy), progress counter, `next_review_display` feedback, session-complete and all-caught-up states.
- Route registration in `mobile/src/app/_layout.tsx` and a "Learning" entry button on the home screen (`mobile/src/app/index.tsx`).

## Prior Art / Context

Follows the conventions established by the lists feature (see `./2026-07-07__implement-expo-lists.md`):

- API module + query-key factory shape mirrors `mobile/src/lib/lists-api.ts`.
- Screen structure mirrors `mobile/src/app/lists/*`: `Redirect` guard on `isAuthenticated === false`, queries gated with `enabled: isAuthenticated === true`, centered `ActivityIndicator` pending state, error state with Retry button, `RefreshControl` pull-to-refresh, `MaxContentWidth` content column, ALL-CAPS section headers.
- Auth/refresh handling comes for free via `apiRequest` (`./2026-07-07__implement-expo-auth.md`).
- Unlike lists, learning is pure REST — no Socket.IO integration.

## Architecture and Design Choices

### 1) API module mirrors the backend contract exactly

- Types in `learning-api.ts` mirror `project/api/learning.py` / `project/services/learning_service.py`: `NoteSummary` (with server-computed `flashcard_count`/`due_count`), `NoteDetail` (whose `flashcards` are **rendered** `ReviewCard`s from `build_cards()`, not raw note JSON), `ReviewCard`, and `RateCardResponse`.
- `RATINGS` constant encodes the web UI's button mapping (Again=0, Hard=3, Good=4, Easy=5) so mobile and web rate identically.
- `getNote` URL-encodes the note ID since note IDs come from filenames.

### 2) Review queue is a per-session snapshot

- The queue query uses `staleTime: Infinity` + `refetchOnMount: 'always'` so the queue is fetched fresh when the screen opens but never refetched in the background — a mid-session refetch would reorder/reset cards under the user.
- The session itself lives in a child `ReviewSession` component keyed by `queueQuery.dataUpdatedAt`. A fresh fetch (retry or "Review more") remounts the session with clean state. This avoids syncing server data into local state via effects (an earlier `useEffect`-based version tripped `react-hooks/set-state-in-effect`).
- Index-based iteration through the snapshot; after the final rating the notes overview cache is invalidated so due counts refresh.

### 3) Rating flow and telemetry

- `response_ms` is measured from when the card is shown (`shownAt` reset after each rating), matching the web review page's semantics.
- A `session_id` (`mobile-<ts36>-<rand>`) is generated once per session for `ReviewLog` grouping.
- Rating buttons disable while the mutation is pending to prevent duplicate submissions; errors render inline and leave the card in place so the user can retry.

### 4) Note detail reveals answers lazily

- Each card row is a `Pressable` that toggles its answer, so the detail screen doubles as a lightweight self-quiz without touching review progress.
- A 404 from the API is detected via `ApiError.status` and rendered as a terminal "Note not found." state without a Retry button.

## Files Created

- `mobile/src/lib/learning-api.ts`
- `mobile/src/app/learning/index.tsx`
- `mobile/src/app/learning/[id].tsx`
- `mobile/src/app/learning/review.tsx`

## Files Modified

- `mobile/src/app/_layout.tsx` — registered `learning/index`, `learning/[id]`, and `learning/review` stack screens.
- `mobile/src/app/index.tsx` — added a "Learning" navigation button to the authed home screen (and fixed indentation of the surrounding buttons).

## API Contract

Consumes (does not change) the existing learning API:

- `GET /api/v1/learning/notes` → `{ notes: NoteSummary[], total_due: number }`
- `GET /api/v1/learning/notes/<note_id>` → `{ note: NoteDetail }` (404 `{ error: "Note not found." }`)
- `GET /api/v1/learning/review` → `{ cards: ReviewCard[] }` (due cards in queue order)
- `POST /api/v1/learning/rate` with `{ card_id, rating, response_ms?, session_id? }` → `{ card_id, learning_state, interval, repetitions, easiness, next_review, next_review_display, scheduler_version }`

## Validation and Verification

1. `./node_modules/.bin/tsc --noEmit` in `mobile/` passes (required regenerating Expo Router typed routes by briefly running `npx expo start`, since `.expo/types/router.d.ts` didn't know the new routes).
2. `npm run lint` (`expo lint`) passes; an initial `react-hooks/set-state-in-effect` violation in the review screen was resolved by the keyed-`ReviewSession` refactor described above.
3. IDE diagnostics clean on all created/modified files.
4. Not manually exercised against a running backend in this session (no simulator run).

## Known Gaps / Follow-ups

- No incident-card creation from mobile (the service supports it; there is no JSON API endpoint for it yet).
- Card `prompt`/`response` render as plain text; markdown/code formatting in card bodies is not styled.
- Admin `debug` payload from `/rate` is ignored.
- No end-to-end manual test against a device/simulator yet; worth doing alongside the next mobile feature.

## How to Run (Current)

1. Start the Flask API locally (port 5001 per mobile config defaults).
2. `cd mobile && npm install && npm start`, then open in a simulator or Expo Go.
3. Sign in, tap **Learning** on the home screen.
4. Browse notes, open one to tap-reveal its cards, or tap **Start Review (N due)** to rate cards; ratings persist to `ReviewProgress`/`ReviewLog` and due counts update on return.
