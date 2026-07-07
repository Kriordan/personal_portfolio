# Backend Verification Runbook

Operational entry point for verifying the Flask backend and its `/api/v1/` surface. Use this document to confirm the backend is ready for local development, review, or mobile-client work. The dated files under `docs/notes/` are historical implementation notes; this runbook supersedes them for day-to-day verification.

Last verified: 2026-07-07 (51 tests passing in the focused API/socket suite).

## 1. Local setup

Requirements:

- Python 3.13 (pinned in `.python-version`)
- [Poetry](https://python-poetry.org/) for dependency management
- A Postgres database (or any SQLAlchemy-compatible URL) reachable via `DATABASE_URL`

```bash
cd /path/to/personal_portfolio
poetry install
```

### Environment variables

Config is loaded from a `.env` file at the repo root (via `python-dotenv`) into `project/_config.py`. There is no `.env.example`; the variables below are the full set.

Required to boot:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Flask sessions and signed tokens |
| `DATABASE_URL` | SQLAlchemy database URL. `postgres://` is auto-rewritten to `postgresql+psycopg://`. The app crashes on boot if this is unset. |

Recommended:

| Variable | Purpose |
| --- | --- |
| `JWT_SECRET_KEY` | JWT signing key; falls back to `SECRET_KEY` if unset |
| `API_CORS_ORIGINS` | Restrict CORS for `/api/v1/*`; defaults to `*` |

Feature-specific (safe to omit for basic verification; see section 7):

| Variable | Feature |
| --- | --- |
| `MAILERSEND_API_KEY`, `CONTACT_EMAIL` | Email (signup verification, password reset, list-share invites, contact form) |
| `WISHLIST_S3_BUCKET` | Wishlist image uploads to S3 |
| `JOBWIZARD_S3_BUCKET`, `APILEAP_ACCESS_KEY` | Jobwizard listing screenshots (APILeap render + S3 upload) |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_PROJECT_ID` | YouTube OAuth for library sync |
| `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY` | Contact form CAPTCHA (web only) |
| `ENV=development` | Makes jobwizard S3 use the `personalportfolio` AWS profile |
| `PORT` | Port for `python run.py` (default 5001) |

### Database

Migrations are managed with Flask-Migrate/Alembic (`migrations/`):

```bash
flask --app project db upgrade
```

To reset from scratch (drops all data):

```bash
flask --app project reset-db
```

### Create a user

API signup is invite-token based, so for local verification create a user via CLI:

```bash
flask --app project create-user --email test@example.com --username testuser --password password123
```

Users are created verified by default (`--no-verified` to opt out). Unverified users get a 403 from API login.

### Run the server

```bash
flask --app project run --port 5001 --debug
```

Debug mode matters: Talisman redirects to HTTPS outside debug, which breaks plain-HTTP local requests (see README troubleshooting). `python run.py` is the production-style entry point (used by the `Procfile` after `db upgrade`).

## 2. Test commands

Tests use Python `unittest` and live in `tests/`. There is no shared `conftest.py`; each API test class builds an app via `create_app(test_config)` with an in-memory SQLite database, so no external services or database are needed.

Focused API/auth/socket regression suite (the standard pre-merge check):

```bash
poetry run python -m unittest \
  tests.test_api_auth \
  tests.test_api_feature_registration \
  tests.test_api_learning \
  tests.test_api_wishlist \
  tests.test_api_library \
  tests.test_api_jobwizard \
  tests.test_socket_auth
```

Expected: `Ran 51 tests ... OK`.

Other useful invocations:

```bash
# Everything in tests/ (note: plain `discover` from repo root finds 0 tests; use -s tests)
poetry run python -m unittest discover -s tests

# Single domain
poetry run python -m unittest tests.test_api_jobwizard

# Jobwizard service layer
poetry run python -m unittest tests.test_jobwizard_service
```

Known pre-existing failures in the full suite (not regressions):

- `tests/test_card_builder.py` — import error (`_build_cards` was removed)
- `tests/test_scheduler.py::test_rate_creates_log_and_intra_day_review` — expects 200, gets 302

What the API tests cover:

| File | Coverage |
| --- | --- |
| `tests/test_api_auth.py` | Login/refresh/signup/reset, CORS scoping |
| `tests/test_api_feature_registration.py` | Route registration smoke: protected routes return 401, not 404 |
| `tests/test_api_learning.py` | Notes, review queue, rating contracts |
| `tests/test_api_wishlist.py` | Gift CRUD, owner scoping, S3 mock |
| `tests/test_api_library.py` | Playlists/videos, sync trigger mock |
| `tests/test_api_jobwizard.py` | Job list/create/detail, ownership, screenshot mock |
| `tests/test_socket_auth.py` | Socket.IO JWT handshake and room join |

## 3. JWT login and refresh flow

Auth uses flask-jwt-extended with tokens in the `Authorization` header only (no cookies). Access tokens last 15 minutes; refresh tokens last 30 days. API login does not create a Flask-Login session — the web UI's session auth is entirely separate.

Endpoints under `/api/v1/auth`:

| Method | Path | Auth | Body |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/login` | none | `{"email", "password"}` |
| POST | `/api/v1/auth/refresh` | refresh token as Bearer | empty |
| POST | `/api/v1/auth/logout` | access token | — (stateless; no server-side revocation) |
| POST | `/api/v1/auth/signup/<invite_token>` | none | `{"username", "password", "email"?}` |
| POST | `/api/v1/auth/forgot-password` | none | `{"email"}` |
| POST | `/api/v1/auth/reset-password/<token>` | none | `{"password"}` |

Flow:

```bash
BASE=http://127.0.0.1:5001

# Login → 200 {access_token, refresh_token, user}
curl -s -X POST $BASE/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'

export ACCESS=...   # from response
export REFRESH=...  # from response

# Refresh → 200 {access_token} (new access token only)
curl -s -X POST $BASE/api/v1/auth/refresh \
  -H "Authorization: Bearer $REFRESH"
```

Login error cases: 400 missing fields, 401 bad credentials, 403 email not verified.

## 4. API smoke checks

All feature endpoints require an access token: `-H "Authorization: Bearer $ACCESS"`. A quick sanity check for each domain — an unauthenticated request should return 401 (proving the route is registered and protected), and an authenticated one should return 200.

### Lists — `/api/v1/lists`

```bash
curl -s $BASE/api/v1/lists/ -H "Authorization: Bearer $ACCESS"
curl -s -X POST $BASE/api/v1/lists/ -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" -d '{"title":"Smoke test list"}'
```

Also available: `GET /<list_id>`, `POST /<list_id>/items`, `POST /<list_id>/items/<item_id>/toggle`, `POST /<list_id>/items/reorder`, `POST /<list_id>/categories`, `POST /<list_id>/categories/reorder`, `POST /<list_id>/share` (sends a MailerSend invite), `PATCH /<list_id>/settings` (owner only).

### Learning — `/api/v1/learning`

```bash
curl -s $BASE/api/v1/learning/notes -H "Authorization: Bearer $ACCESS"
curl -s $BASE/api/v1/learning/review -H "Authorization: Bearer $ACCESS"
```

Also: `GET /notes/<note_id>`, `POST /rate` with `{"card_id", "rating", "response_ms"?, "session_id"?}`.

### Wishlist — `/api/v1/wishlist`

```bash
curl -s $BASE/api/v1/wishlist/gifts -H "Authorization: Bearer $ACCESS"
curl -s -X POST $BASE/api/v1/wishlist/gifts -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" -d '{"title":"Smoke gift","body":"testing"}'
```

Also: `GET/PUT/DELETE /gifts/<gift_id>`. Gifts are owner-scoped — another user's gift ID returns 404. Create accepts multipart with an `image` field when `WISHLIST_S3_BUCKET` is configured.

### Library — `/api/v1/library`

```bash
curl -s $BASE/api/v1/library/playlists -H "Authorization: Bearer $ACCESS"
```

Also: `GET /playlists/<playlist_id>`, `GET /videos/<video_id>`, `POST /sync` (triggers a real YouTube sync — see section 7 before using outside tests). Library content is shared across users, not owner-scoped.

### Jobwizard — `/api/v1/jobwizard`

```bash
curl -s $BASE/api/v1/jobwizard/jobs -H "Authorization: Bearer $ACCESS"
curl -s -X POST $BASE/api/v1/jobwizard/jobs -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"title":"Engineer","company_name":"Acme","listing_url":"https://example.com/job"}'
```

Also: `GET /jobs/<job_id>` (owner-scoped; foreign job returns 404). Job creation triggers screenshot rendering, which needs `APILEAP_ACCESS_KEY` and `JOBWIZARD_S3_BUCKET`; without them, expect the screenshot step to fail or be skipped while automated tests mock it.

### CORS

CORS is enabled only for `/api/v1/*` (origins from `API_CORS_ORIGINS`, default `*`). Web routes never get CORS headers. To verify:

```bash
curl -si -X OPTIONS $BASE/api/v1/auth/login \
  -H "Origin: http://localhost:19006" \
  -H "Access-Control-Request-Method: POST" | rg -i access-control
```

## 5. Socket.IO JWT smoke path

Socket.IO (`project/sockets.py`) accepts two auth methods on connect: an existing Flask-Login session (web) or a JWT access token in the connect `auth` payload (API/mobile clients). Refresh tokens are rejected; only `type == "access"` tokens are accepted.

The automated path is the primary check:

```bash
poetry run python -m unittest tests.test_socket_auth
```

Manual check with `python-socketio` against a running dev server:

```python
import socketio

sio = socketio.Client()
sio.connect("http://127.0.0.1:5001", auth={"token": ACCESS_TOKEN})
print(sio.call("join_list", {"list_id": 1}))  # {"success": True, "room": "list_1"} for a list you own
sio.disconnect()
```

List events broadcast to room `list_<id>`: `item_added`, `item_toggled`, `items_reordered`, `category_added`, `categories_reordered`, `settings_updated`, plus `user_joined`/`user_left`. Note that dev runs use Flask-SocketIO threading mode (`run.py` calls `app.run()`, not `socketio.run()`).

## 6. Mobile client verification

The Expo app lives under `mobile/` (see `mobile/README.md` for full setup). To verify it against this backend:

```bash
# Backend first (section 1); --debug avoids Talisman HTTPS redirects
flask --app project run --port 5001 --debug

# Then the app
cd mobile
npm install
npx tsc --noEmit && npx expo lint   # static checks
npm start                           # press i (iOS), a (Android), or w (web)
```

Base URL resolution is in `mobile/src/lib/config.ts`: `EXPO_PUBLIC_API_URL` if set (copy `mobile/.env.example` to `mobile/.env`), otherwise `http://127.0.0.1:5001` on iOS simulator/web and `http://10.0.2.2:5001` on the Android emulator. Physical devices need the machine's LAN IP.

Manual smoke in the app: sign in with the section-1 test user, confirm the home screen shows the username and API URL, then sign out. The client stores tokens with `expo-secure-store` and auto-refreshes on 401 (`mobile/src/lib/api-client.ts`), matching the JWT flow in section 3. Socket.IO integration (section 5) is not wired into the app yet — it arrives with the lists/realtime feature work.

## 7. External dependency notes

None of these are required for the automated test suite — tests mock all of them.

### S3 (boto3)

- Wishlist images upload to `WISHLIST_S3_BUCKET` via `project/services/wishlist_service.py`. If the bucket or AWS credentials are missing, upload silently returns `None` and the gift is created without an image. Tests patch `project.services.wishlist_service.upload_image_to_s3`.
- Jobwizard screenshots upload to `JOBWIZARD_S3_BUCKET` via `Job.render_screenshot` in `project/models.py`, using the APILeap API (`APILEAP_ACCESS_KEY`) to render the listing page. With `ENV=development`, boto3 uses the `personalportfolio` AWS profile. Tests patch `Job.render_screenshot`.

### YouTube sync

- Sync logic lives in `project/library/jobs.py` (`sync_playlists_and_videos`); playlist IDs come from `project/data/jsonfiles/youtube-ids.json`.
- Credentials: browser OAuth flow at `/oauth/authorize` (requires a logged-in web session and a gitignored `client_secret.json` plus `GOOGLE_*` env vars). The resulting token is saved to `project/data/youtube_token.json`, which the CLI path reuses.
- Triggers: `flask --app project sync-yt-subs` (CLI) or `POST /api/v1/library/sync` (API). Both make real YouTube API calls — do not use in automated checks. Tests patch `project.services.library_service.sync_playlists_and_videos`.

### MailerSend

- Requires `MAILERSEND_API_KEY`. Used by `project/api/auth.py` (verification and password-reset emails), `project/api/lists.py` (share invites), and the web account/foyer/lists views.
- Without the key, email-dependent flows (API signup verification, forgot-password, list sharing) will fail at the send step; login and all other endpoints work fine. Tests patch the send helpers (e.g. `project.api.auth._send_verification_email`).

## Quick full-verification sequence

```bash
# 1. Automated regression (no env vars or DB needed)
poetry run python -m unittest \
  tests.test_api_auth tests.test_api_feature_registration \
  tests.test_api_learning tests.test_api_wishlist tests.test_api_library \
  tests.test_api_jobwizard tests.test_socket_auth

# 2. Boot check (needs .env with SECRET_KEY + DATABASE_URL)
flask --app project db upgrade
flask --app project create-user --email test@example.com --username testuser --password password123
flask --app project run --port 5001 --debug

# 3. Manual smoke (separate shell)
BASE=http://127.0.0.1:5001
curl -s -X POST $BASE/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
# export ACCESS from the response, then:
curl -s $BASE/api/v1/lists/ -H "Authorization: Bearer $ACCESS"
curl -s $BASE/api/v1/learning/notes -H "Authorization: Bearer $ACCESS"
curl -s $BASE/api/v1/wishlist/gifts -H "Authorization: Bearer $ACCESS"
curl -s $BASE/api/v1/library/playlists -H "Authorization: Bearer $ACCESS"
curl -s $BASE/api/v1/jobwizard/jobs -H "Authorization: Bearer $ACCESS"
```

## Related historical notes

Deeper context on each subsystem, in `docs/notes/2026/`:

- `2026-03-02__api-blueprint.md` — original auth + lists API contract
- `2026-03-04__jwt-auth.md`, `2026-03-04__cors-config.md`, `2026-03-04__socket-jwt.md` — auth, CORS, and socket handshake design
- `2026-07-06__test-existing-feature-apis.md` — feature API test strategy and mocking approach
- `2026-07-06__extract-jobwizard-service.md`, `2026-07-06__resolve-jobwizard-ownership.md`, `2026-07-07__add-jobwizard-api.md` — jobwizard service, ownership model, and API
