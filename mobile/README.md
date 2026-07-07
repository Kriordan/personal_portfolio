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
| `src/lib/config.ts` | Environment/API URL configuration |
| `src/lib/api-client.ts` | Fetch wrapper with JWT attachment, 401 refresh-and-retry, auth endpoints |
| `src/lib/token-storage.ts` | Secure token persistence (`expo-secure-store`, localStorage fallback on web) |
| `src/lib/query-client.ts` | Shared TanStack Query client |
| `src/lib/auth-context.tsx` | Auth state provider: sign-in, sign-out, session restoration |

## Auth flow

- `POST /api/v1/auth/login` returns `access_token` (15 min), `refresh_token` (30 days), and the `user` object; both tokens are stored in secure storage.
- Requests attach `Authorization: Bearer <access_token>`. On a 401 the client refreshes via `POST /api/v1/auth/refresh` (using the refresh token) and retries once; concurrent 401s share a single refresh.
- If refresh also fails, tokens are cleared and the app redirects to the login screen.
- Logout calls `POST /api/v1/auth/logout` (stateless server-side) and clears local tokens and the query cache.

## Dev login

Create a local user via the Flask CLI if you don't have one:

```bash
flask --app project create-user --email test@example.com --username testuser --password password123
```
