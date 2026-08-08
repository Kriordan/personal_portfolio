# Implement Mobile Lists and Realtime (`implement-expo-lists`)

Date: 2026-07-07
Todo ID: `implement-expo-lists`

## Objective

Build the mobile lists feature — overview, detail, and mutations against the existing `/api/v1/lists` contract — with Socket.IO realtime updates authenticated via JWT, so multiple clients (including the web UI) stay in sync live.

## Scope Delivered

- `mobile/src/lib/lists-api.ts` — typed API module (`ListSummary`, `ListDetail`, `ListCategory`, `ListItem`) covering `GET/POST /lists/`, `GET /lists/:id`, `POST /lists/:id/categories`, `POST /lists/:id/items`, and `POST /lists/:id/items/:itemId/toggle`, plus shared TanStack Query keys (`listsKeys`).
- `mobile/src/lib/list-socket.ts` — Socket.IO client layer: lazily-created shared socket with JWT connect auth, `useListRoom(listId, handlers, {enabled})` hook (room join/leave, typed event subscriptions, connection status), `emitListEvent` for post-mutation fan-out, and `disconnectListSocket` for sign-out teardown.
- `mobile/src/app/lists/index.tsx` — lists overview screen: owned + shared sections, create-list input, pull-to-refresh, loading/error/empty states, auth redirect guard.
- `mobile/src/app/lists/[id].tsx` — list detail screen: categories with pending/completed item grouping, item toggle, add item per category, add category, Live/Connecting…/Offline connection badge in the header, realtime cache updates, pull-to-refresh, auth redirect guard.
- Navigation wiring: `lists/index` and `lists/[id]` registered in `mobile/src/app/_layout.tsx`; "My Lists" button on the home screen.
- Sign-out and unrecoverable-401 paths now disconnect the socket (`mobile/src/lib/auth-context.tsx`).
- `socket.io-client@^4.8.3` added to `mobile/package.json`.
- `mobile/README.md` gains a "Lists and realtime" section documenting the protocol.

## Prior Art / Context

- The realtime protocol deliberately mirrors the existing web client (`project/static/js/lists.js`): REST call persists the change, then the client emits the matching socket event; the server (`project/sockets.py`) rebroadcasts to the `list_<id>` room with `include_self=False`.
- JWT socket auth was already implemented server-side (connect handler validates an access token from the Socket.IO `auth` payload) and covered by `tests/test_socket_auth.py`; the mobile client targets exactly that path.
- API payload types mirror the serializers in `project/api/lists.py` one-to-one. No backend changes were needed.
- Builds on the auth phase (`./2026-07-07__implement-expo-auth.md`): `apiRequest` refresh-and-retry, `tokenStorage`, and the unauthorized listener are reused as-is.

## Architecture and Design Choices

### 1) Shared singleton socket with per-attempt token refresh

- One module-level socket (`getListSocket`) serves all screens rather than a socket per component; rooms scope the traffic per list.
- The `auth` option is a callback that calls the exported `refreshAccessToken()` (newly exported from `api-client.ts`) before every connection attempt. Connects are infrequent, and a stale 15-minute access token would be rejected outright by the server's connect handler, so always refreshing is simpler and safer than tracking token expiry.
- Server-side connect rejection (returning `False` in Flask-SocketIO) does not trigger socket.io-client's automatic reconnection, so `connect_error` schedules a manual retry after 5s — each retry re-runs the auth callback and gets a fresh token.
- Sign-out and unrecoverable 401s call `disconnectListSocket()` so a subsequent login gets a connection authenticated as the new user.

### 2) `useListRoom` hook owns the room lifecycle

- The hook joins `list_<id>` on every `connect` (initial and reconnects), leaves on unmount, and returns a `SocketStatus` for the UI badge.
- Handlers are stored in a ref (updated in an effect, per `react-hooks/refs`) so callers can pass fresh closures each render without tearing down socket listeners.
- Every event handler filters on `event.list_id === listId`, matching the web client's guard.
- `onJoined` fires after a successful `join_list` ack and the detail screen uses it to invalidate the list query — this is the reconciliation mechanism for events missed while disconnected.
- An `enabled` option gates the connection so unauthenticated renders never attempt a doomed connect.

### 3) Targeted cache patches for granular events, refetch for bulk events

- `item_toggled`, `item_added`, and `category_added` patch the TanStack Query cache in place via immutable helpers (`withItemToggled`, `withItemAdded`, `withCategoryAdded` in `lists/[id].tsx`); the add helpers are idempotent (skip if the id already exists) to tolerate duplicate delivery.
- `items_reordered`, `categories_reordered`, and `settings_updated` invalidate the query instead — replaying multi-row ordering payloads client-side is error-prone and the server is the source of truth.
- Local mutations follow the same pattern: on success, patch the cache with the server's response, then `emitListEvent` so other room members update (server rebroadcast excludes the sender).

### 4) Offline behavior degrades to plain REST

- The connection badge (Live / Connecting… / Offline) is informational; mutations are never blocked on socket state. While offline, REST writes still succeed and the rejoin refetch reconciles everyone once the socket returns.

### 5) Ordering and completed-item display kept minimal

- Items are sorted by `ordering` with completed items grouped after pending ones within each category (a simplification of the web UI's three `completed_display_mode` variants). Drag-and-drop reordering was deliberately deferred — the mobile client consumes reorder events but does not emit them.

## Files Created

- `mobile/src/lib/lists-api.ts`
- `mobile/src/lib/list-socket.ts`
- `mobile/src/app/lists/index.tsx`
- `mobile/src/app/lists/[id].tsx`
- `docs/notes/2026/2026-07-07__implement-expo-lists.md` (this note)

## Files Modified

- `mobile/src/lib/api-client.ts` — exported `refreshAccessToken` for the socket auth callback.
- `mobile/src/lib/auth-context.tsx` — `disconnectListSocket()` on sign-out and in the unauthorized listener.
- `mobile/src/app/_layout.tsx` — registered `lists/index` and `lists/[id]` stack screens.
- `mobile/src/app/index.tsx` — added "My Lists" navigation button (sign-out demoted to secondary style).
- `mobile/package.json` / `mobile/package-lock.json` — added `socket.io-client@^4.8.3`.
- `mobile/README.md` — project-structure rows for the new modules and a "Lists and realtime" section.

## API Contract

Consumed (no backend changes):

- `GET /api/v1/lists/` → `{owned: ListSummary[], shared: ListSummary[]}`
- `POST /api/v1/lists/` `{title}` → 201 `{list}`
- `GET /api/v1/lists/:id` → `{list}` with nested `categories[].items[]`
- `POST /api/v1/lists/:id/categories` `{name}` → 201 `{category}`
- `POST /api/v1/lists/:id/items` `{name, category_id, quantity?, notes?}` → 201 `{item}`
- `POST /api/v1/lists/:id/items/:itemId/toggle` → `{completed}`

Socket events — client emits: `join_list`, `leave_list`, `item_toggled`, `item_added`, `category_added`; client consumes: those three plus `items_reordered`, `categories_reordered`, `settings_updated`.

## Validation and Verification

1. `./node_modules/.bin/tsc --noEmit` — clean (required regenerating Expo typed routes for the new screens via a brief `expo start`).
2. `./node_modules/.bin/eslint src` — clean (one `react-hooks/refs` violation found and fixed: ref write moved out of render into an effect).
3. Backend regression: `poetry run python -m unittest tests.test_socket_auth tests.test_api_auth tests.test_api_feature_registration` — 14 tests, OK.
4. No end-to-end simulator run against a live backend in this pass; the socket protocol matches the server handlers and web client verbatim.

## Known Gaps / Follow-ups

- No drag-and-drop reordering or list-sharing UI on mobile (share endpoint exists server-side); reorder/settings events are consumed via refetch only.
- `completed_display_mode` is not honored; completed items always render at the bottom of their category.
- No optimistic updates — mutations wait for the server response before patching the cache (acceptable latency for local dev; revisit if needed).
- An accidental `npm install socket.io-client` in the repo root (shell cwd mixup) was reverted; root `package.json`/lock are untouched. Root `node_modules` legitimately contains socket.io-client as a transitive dep of `browser-sync`.
- Mobile unit tests still deferred (per plan) until the feature set stabilizes.

## How to Run (Current)

1. Start the backend: `flask --app project run --port 5001 --debug`.
2. `cd mobile && npm install && npm start`, open a simulator, sign in.
3. Tap "My Lists" → create a list → open it → add a category, add items, toggle them. The header badge should read "Live".
4. To see realtime sync: open the same list in a browser (`/lists/<id>` web UI) and toggle/add items on either side — the other client updates without refresh.
