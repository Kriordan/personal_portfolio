# Scaffold Expo App (`scaffold-expo-app`)

Date: 2026-07-07
Todo ID: `scaffold-expo-app`

## Objective

Add an isolated Expo mobile app scaffold under `mobile/` with router, query client, API client, environment config, and secure token storage, so feature screens (auth, lists, learning, wishlist, library, jobwizard) can be built against the existing `/api/v1/` Flask backend.

## Scope Delivered

- New `mobile/` directory (Expo SDK 57, React Native 0.86, TypeScript strict) generated from the `create-expo-app` default template and trimmed of demo content.
- Expo Router file-based navigation with a root `Stack` in `mobile/src/app/_layout.tsx` wiring `QueryClientProvider`, `AuthProvider`, and the theme provider.
- TanStack Query client (`mobile/src/lib/query-client.ts`) with sensible retry defaults (no retries on 4xx).
- Fetch-based API client (`mobile/src/lib/api-client.ts`) with JWT attachment, deduplicated 401 refresh-and-retry, typed `ApiError`, and `authApi.login`/`authApi.logout`.
- Environment config (`mobile/src/lib/config.ts`) resolving the API base URL from `EXPO_PUBLIC_API_URL` with platform-aware dev defaults; `mobile/.env.example` documents the variable.
- Secure token storage (`mobile/src/lib/token-storage.ts`) using `expo-secure-store` with a `localStorage` fallback on web.
- Minimal authenticated shell: `mobile/src/app/login.tsx` (sign-in form) and `mobile/src/app/index.tsx` (authed home with sign-out), gated by `mobile/src/lib/auth-context.tsx`.
- `mobile/README.md` covering setup, base URL configuration for simulator/device, project structure, and the auth flow.
- Updated `docs/verification-runbook.md` section 6 (mobile client verification) from "not applicable" to concrete commands.

## Prior Art / Context

- API contracts came from the existing backend: `POST /api/v1/auth/login` returns `access_token` (15 min), `refresh_token` (30 days), and a `user` object; `POST /api/v1/auth/refresh` takes the refresh token as Bearer and returns a new access token only; `POST /api/v1/auth/logout` is stateless. See `project/api/auth.py` and `./2026-03-04__jwt-auth.md`.
- The scaffold sits in `mobile/` as its own npm package, fully separate from the root Gulp/Sass asset pipeline (`package.json` at repo root is untouched apart from nothing — the app has its own lockfile).

## Architecture and Design Choices

### 1) Template-based scaffold, trimmed

- Used `create-expo-app` (default template, SDK 57) rather than hand-rolling, to get correct Metro/Babel/tsconfig and native config for free.
- Deleted demo screens/components (`explore.tsx`, animated icon, app tabs, hint rows, web badge, collapsible) and demo-only deps (`@expo/ui`, `expo-device`, `expo-glass-effect`, `expo-image`, `expo-symbols`, `expo-web-browser`), keeping the template's themed primitives (`themed-text`, `themed-view`, `constants/theme.ts`, `use-theme`) since feature screens will reuse them.
- Kept `experiments.typedRoutes` and the React Compiler flag from the template.

### 2) API base URL resolution (`src/lib/config.ts`)

- Order: `EXPO_PUBLIC_API_URL` env var, else platform default — `http://10.0.2.2:5001` on Android emulator (host loopback), `http://127.0.0.1:5001` elsewhere.
- `EXPO_PUBLIC_` prefix is required for Expo to inline env vars into the client bundle; `.env` is gitignored, `.env.example` is committed.
- Exposes `API_PREFIX = '/api/v1'` so callers pass short paths like `/auth/login`.

### 3) API client with single-flight refresh (`src/lib/api-client.ts`)

- Plain `fetch` wrapper rather than axios: no extra dependency, and interception needs are simple.
- On 401 (non-anonymous requests): refresh via `/auth/refresh` using the stored refresh token, persist the new access token, retry the original request once. A module-level `refreshPromise` deduplicates concurrent refreshes so parallel 401s trigger one network call.
- If the retry still 401s, a registered `onUnauthorized` listener fires; the auth provider uses it to clear tokens and redirect to login. This keeps the client free of React imports.
- `ApiError` carries `status` and the parsed body; the message is lifted from the backend's `{"error": "..."}` shape when present.

### 4) Secure token storage (`src/lib/token-storage.ts`)

- `expo-secure-store` (Keychain/Keystore) on native. Web falls back to `localStorage` — acceptable because web is a dev convenience target only; noted in a comment.
- Stores access and refresh tokens under `auth.access_token` / `auth.refresh_token`. `setTokens` accepts an optional refresh token so the refresh flow (which only rotates the access token) doesn't clobber it.

### 5) Auth state (`src/lib/auth-context.tsx`)

- React context with `isAuthenticated: boolean | null` (null = session restoration in progress), `user`, `signIn`, `signOut`.
- Session restoration checks for a stored refresh token at mount — no network call needed; the first authenticated request will refresh if the access token has expired. There is no `/auth/me` endpoint yet, so `user` is only populated after a fresh login (documented as a follow-up).
- `signOut` calls the (stateless) logout endpoint, clears secure storage, and clears the query cache.

### 6) Route gating

- Simple `<Redirect>`-based gating: `index.tsx` redirects to `/login` when unauthenticated; `login.tsx` redirects home when authenticated. With only two screens, expo-router route groups/protected routes would be premature; revisit when feature tabs land.

### 7) Lint fix in template code

- `src/hooks/use-color-scheme.web.ts` shipped with a `setState`-in-effect hydration pattern that fails `react-hooks/set-state-in-effect` under eslint-config-expo 57. Rewrote it with `useSyncExternalStore` (server snapshot `'light'`, client snapshot from `useColorScheme`), which is the hydration-safe equivalent without the cascading render.

## Files Created

- App scaffold (template-derived): `mobile/app.json`, `mobile/package.json`, `mobile/package-lock.json`, `mobile/tsconfig.json`, `mobile/eslint.config.js`, `mobile/.gitignore`, `mobile/AGENTS.md`, `mobile/assets/`, `mobile/src/global.css`, `mobile/src/constants/theme.ts`, `mobile/src/components/themed-text.tsx`, `mobile/src/components/themed-view.tsx`, `mobile/src/hooks/use-color-scheme.ts`, `mobile/src/hooks/use-color-scheme.web.ts`, `mobile/src/hooks/use-theme.ts`
- New library code: `mobile/src/lib/config.ts`, `mobile/src/lib/token-storage.ts`, `mobile/src/lib/api-client.ts`, `mobile/src/lib/query-client.ts`, `mobile/src/lib/auth-context.tsx`
- Screens: `mobile/src/app/_layout.tsx` (rewritten), `mobile/src/app/index.tsx` (rewritten), `mobile/src/app/login.tsx`
- Docs: `mobile/README.md`, `mobile/.env.example`

## Files Modified

- `docs/verification-runbook.md` — section 6 replaced with concrete mobile verification commands (backend + `npm install` + static checks + `npm start`, base URL notes, manual smoke steps).

## API Contract

No backend changes. The client consumes:

- `POST /api/v1/auth/login` `{email, password}` → `{access_token, refresh_token, user}`
- `POST /api/v1/auth/refresh` (refresh token as Bearer) → `{access_token}`
- `POST /api/v1/auth/logout` (access token as Bearer) → `{message}` (stateless)

## Validation and Verification

1. `npx tsc --noEmit` — clean (after Expo generated `.expo/types/router.d.ts` and `expo-env.d.ts` on first start).
2. `npx expo lint` — clean after the `use-color-scheme.web.ts` fix.
3. Metro boot smoke: `npx expo start` served the manifest (HTTP 200) and compiled the iOS dev bundle (HTTP 200, ~6.1 MB) including the login/auth modules.
4. No end-to-end login against a running backend was performed in this pass (no local `.env`/DB assumed); the JWT flow mirrors the curl-verified contract in the runbook.

## Known Gaps / Follow-ups

- No `/auth/me` endpoint exists, so the `user` object is only available after a fresh login, not after session restoration. Either persist the user object locally or add the endpoint (noted in the API exploration).
- Socket.IO client is not wired up yet — arrives with the lists/realtime phase.
- Web token storage falls back to `localStorage`; fine for dev, revisit if web becomes a real target.
- `npm audit` reports 11 moderate advisories in template/transitive deps; not addressed to avoid breaking pinned Expo versions.
- No mobile unit tests yet; the plan defers testing until feature screens exist.

## How to Run (Current)

1. Start the backend: `flask --app project run --port 5001 --debug` (see runbook section 1 for `.env`/DB setup and test-user creation).
2. `cd mobile && npm install && npm start`.
3. Press `i` (iOS simulator), `a` (Android emulator), or `w` (web). Physical device: copy `.env.example` to `.env`, set `EXPO_PUBLIC_API_URL` to the machine's LAN IP, restart Expo.
4. Sign in with the test user; the home screen shows the username and resolved API URL; sign out clears the session.
