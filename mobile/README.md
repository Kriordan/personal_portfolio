# Mobile (Expo)

Expo client for the Flask API in the repo root. Uses [Expo Router](https://docs.expo.dev/router/introduction/) for navigation, [TanStack Query](https://tanstack.com/query) for server state, and `expo-secure-store` for token storage.

## Prerequisites

- Node 20+
- The Flask API running locally (see `docs/verification-runbook.md` in the repo root):

```bash
flask --app project run --port 5001 --debug
```

`--debug` matters: outside debug mode Talisman redirects to HTTPS, which breaks plain-HTTP requests from simulators/devices.

## Setup

```bash
cd mobile
npm install
npm start
```

Then press `i` (iOS simulator), `a` (Android emulator), or `w` (web).

## API base URL

The API base URL is resolved in `src/lib/config.ts`:

1. `EXPO_PUBLIC_API_URL` if set (copy `.env.example` to `.env` and fill it in)
2. Otherwise a platform default: `http://127.0.0.1:5001` (iOS simulator/web) or `http://10.0.2.2:5001` (Android emulator)

For a physical device, set `EXPO_PUBLIC_API_URL` to your machine's LAN IP, e.g. `http://192.168.1.20:5001`, and make sure the device is on the same network.

## Project structure

| Path | Purpose |
|------|---------|
| `src/app/` | Expo Router screens (`_layout.tsx` wires providers, `index.tsx` authed home, `login.tsx` sign-in) |
| `src/app/lists/index.tsx` | Lists overview: owned + shared lists, create list |
| `src/app/lists/[id].tsx` | List detail: categories, items, toggle/add, live sync badge |
| `src/lib/config.ts` | Environment/API URL configuration |
| `src/lib/api-client.ts` | Fetch wrapper with JWT attachment, 401 refresh-and-retry, auth endpoints |
| `src/lib/lists-api.ts` | Typed list endpoints (`/api/v1/lists/...`) and TanStack Query keys |
| `src/lib/list-socket.ts` | Socket.IO client: JWT connect auth, `useListRoom` hook, post-mutation emits |
| `src/lib/token-storage.ts` | Secure token persistence (`expo-secure-store`, localStorage fallback on web) |
| `src/lib/query-client.ts` | Shared TanStack Query client |
| `src/lib/auth-context.tsx` | Auth state provider: sign-in, sign-out, session restoration |

## Auth flow

- `POST /api/v1/auth/login` returns `access_token` (15 min), `refresh_token` (30 days), and the `user` object; both tokens are stored in secure storage.
- On app launch, a stored refresh token restores the session immediately; `GET /api/v1/auth/me` then repopulates the `user` object and validates the session (an unrecoverable 401/404 signs the user out; network errors keep the session).
- Requests attach `Authorization: Bearer <access_token>`. On a 401 the client refreshes via `POST /api/v1/auth/refresh` (using the refresh token) and retries once; concurrent 401s share a single refresh.
- If refresh also fails, tokens are cleared and the app redirects to the login screen.
- Logout calls `POST /api/v1/auth/logout` (stateless server-side) and clears local tokens and the query cache.

## Lists and realtime

- The overview screen (`/lists`) shows owned and shared lists via `GET /api/v1/lists/` and creates lists via `POST /api/v1/lists/`.
- The detail screen (`/lists/[id]`) loads the full list (`GET /api/v1/lists/:id`), toggles items, and adds items/categories through the REST API.
- Realtime sync uses Socket.IO against the same base URL as the API:
  - The connection authenticates by passing a JWT access token in the Socket.IO `auth` payload; the server validates it in the connect handler (`project/sockets.py`). A fresh token is fetched before each connection attempt.
  - After connecting, the client joins the `list_<id>` room via `join_list` and re-joins automatically on reconnect (each rejoin also refetches the list to catch missed events).
  - Incoming `item_toggled`, `item_added`, and `category_added` events patch the cached list in place; `items_reordered`, `categories_reordered`, and `settings_updated` trigger a refetch.
  - After a successful local mutation the client emits the matching event so other clients (including the web UI) update live — same protocol as `project/static/js/lists.js`.
  - The list header shows a connection badge: Live / Connecting… / Offline. While offline, mutations still work over REST; the rejoin refetch reconciles state when the socket returns.
- Signing out disconnects the socket and clears the query cache.

## Dev login

Create a local user via the Flask CLI if you don't have one:

```bash
flask --app project create-user --email test@example.com --username testuser --password password123
```
