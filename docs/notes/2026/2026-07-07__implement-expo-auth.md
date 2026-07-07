# Implement Mobile Auth (`implement-expo-auth`)

Date: 2026-07-07
Todo ID: `implement-expo-auth`

## Objective

Complete the mobile auth flow — login, token refresh, logout, authenticated request attachment, and full session restoration — so feature screens can rely on a stable, self-healing session.

## Scope Delivered

- New backend endpoint `GET /api/v1/auth/me` in `project/api/auth.py` returning the current user, plus three tests in `tests/test_api_auth.py` (happy path, missing token, deleted user).
- `authApi.me()` in `mobile/src/lib/api-client.ts` consuming the new endpoint.
- Real session restoration in `mobile/src/lib/auth-context.tsx`: on launch the app restores the session from the stored refresh token and then validates it and repopulates `user` via `/auth/me`, closing the gap noted in the scaffold phase where `user` stayed `null` after an app restart.
- Docs updated: `mobile/README.md` auth flow section and `docs/verification-runbook.md` auth endpoint table/curl flow now cover `/auth/me`.

## Prior Art / Context

- The scaffold phase (`./2026-07-07__scaffold-expo-app.md`) already delivered login, secure token storage, single-flight 401 refresh-and-retry, an unauthorized listener, logout, and redirect-based route gating. Its "Known Gaps" explicitly deferred user restoration because no `/auth/me` endpoint existed; this todo resolves that follow-up.
- `_current_user_from_jwt` mirrors the identical helper in `project/api/lists.py` for consistent JWT-identity-to-User resolution.

## Architecture and Design Choices

### 1) Add `GET /auth/me` rather than persisting the user object locally

- A locally cached user goes stale (username/admin changes) and cannot detect revoked accounts. `/auth/me` validates the session server-side and returns fresh data in one call.
- The endpoint is a thin `@jwt_required()` handler reusing the existing `_serialize_user` shape, so the mobile `ApiUser` type is unchanged. A missing user (deleted account with a still-valid token) returns 404.

### 2) Optimistic restore, then validate

- On mount, `AuthProvider` checks for a stored refresh token and immediately sets `isAuthenticated = true` so the authenticated shell renders without a network round-trip (same boot behavior as before).
- It then calls `authApi.me()`. Because that goes through `apiRequest`, an expired access token transparently triggers the refresh-and-retry path — so restoration also exercises and validates the refresh token.
- Failure handling is deliberate:
  - Unrecoverable 401 (refresh also failed): handled by the existing unauthorized listener, which clears tokens/cache and redirects to login. The listener registration effect was moved above the restore effect so it is guaranteed to be in place first.
  - 404 (account deleted): treated as an invalid session; tokens and query cache are cleared explicitly in the restore path.
  - Network/5xx errors: session is kept and `user` stays `null` until a later request succeeds — an offline launch should not log the user out.

### 3) No changes to login/logout/refresh mechanics

- Those flows were already correct from the scaffold (single-flight refresh dedup, stateless logout with local cleanup, query-cache clearing). This pass only filled the restoration gap rather than reworking working code.

## Files Created

- `docs/notes/2026/2026-07-07__implement-expo-auth.md` (this note)

## Files Modified

- `project/api/auth.py` — added `_current_user_from_jwt` helper and `GET /auth/me` endpoint.
- `tests/test_api_auth.py` — added `_get` helper and three `/auth/me` tests.
- `mobile/src/lib/api-client.ts` — added `authApi.me()`.
- `mobile/src/lib/auth-context.tsx` — reordered listener registration before restore; rewrote restoration to validate the session and populate `user` via `/auth/me` with 404/offline handling.
- `mobile/README.md` — auth flow section documents session restore via `/auth/me`.
- `docs/verification-runbook.md` — added `/auth/me` to the auth endpoint table and curl flow.

## API Contract

- `GET /api/v1/auth/me` — access token as Bearer.
  - 200: `{"user": {"id", "email", "username", "email_verified", "is_admin"}}`
  - 401: missing/expired/invalid token (standard flask-jwt-extended response)
  - 404: `{"error": "User not found."}` (token valid but account gone)

## Validation and Verification

1. `poetry run python -m unittest tests.test_api_auth -v` — 9 tests pass, including the three new `/auth/me` tests.
2. Full pre-merge regression suite (`tests.test_api_auth tests.test_api_feature_registration tests.test_api_learning tests.test_api_wishlist tests.test_api_library tests.test_api_jobwizard tests.test_socket_auth`) — 54 tests, OK.
3. `mobile`: `./node_modules/.bin/tsc --noEmit` clean; `npx expo lint` / `eslint src` clean.
4. No end-to-end device login was performed in this pass; the flow matches the curl-verified contract in the runbook.

## Known Gaps / Follow-ups

- Logout remains stateless server-side (no token blocklist), unchanged from before.
- If `/auth/me` fails due to a network error at launch, `user` stays `null` until another successful request; there is no automatic retry/backoff loop yet.
- Mobile unit tests still deferred until feature screens exist (per plan).

## How to Run (Current)

1. Start the backend: `flask --app project run --port 5001 --debug` (runbook section 1 covers `.env`/DB setup and `create-user`).
2. `cd mobile && npm install && npm start`, then open a simulator.
3. Sign in; the home screen shows the username. Kill and relaunch the app: you land on the home screen already signed in, and the username reappears once `/auth/me` resolves.
4. Verify the endpoint directly: `curl -s $BASE/api/v1/auth/me -H "Authorization: Bearer $ACCESS"`.
