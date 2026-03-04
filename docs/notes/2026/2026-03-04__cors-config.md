# Scope API CORS Configuration (`cors-config`)

Date: 2026-03-04
Owner: AI coding agent
Todo ID: `cors-config`

## Objective

Ensure CORS is enabled for API endpoints under `/api/v1/*` without affecting existing web/Jinja routes, and verify this behavior with automated tests.

## Scope Delivered

- Updated Flask app extension setup in `project/__init__.py` to keep CORS scoped to `/api/v1/*`.
- Made API CORS origins configurable via `API_CORS_ORIGINS` app config (default `*`).
- Added API auth test coverage in `tests/test_api_auth.py` to verify:
  - CORS headers are present for `/api/v1/auth/login`.
  - CORS headers are not added for `/login` (non-API route).
- Executed test validation using `poetry run python -m unittest tests.test_api_auth`.

## Prior Art / Context

The codebase already initialized `flask-cors` in `register_extensions`. This work preserves that established initialization point while tightening explicit configurability and adding regression coverage for route scoping behavior.

## Architecture and Design Choices

### 1) Route-Scoped CORS Enforcement
- What was done: Kept `CORS(app, resources={r"/api/v1/*": ...})` pattern in `project/__init__.py`.
- Why this approach was chosen: It aligns with the API blueprint prefix (`/api/v1`) and avoids exposing CORS on session-based web routes.
- Trade-offs considered: Global CORS would be simpler but risks unintentionally broadening cross-origin access.
- Key implementation details: `register_extensions()` now computes `api_cors_origins` from `app.config`.

### 2) Configurable Allowed Origins
- What was done: Added `api_cors_origins = app.config.get("API_CORS_ORIGINS", "*")`.
- Why this approach was chosen: Keeps local/dev ergonomics while allowing production hardening without code changes.
- Trade-offs considered: Default `*` is permissive; stricter deployments should set `API_CORS_ORIGINS`.
- Key implementation details: Configuration is consumed directly by Flask-CORS resource mapping for `/api/v1/*`.

### 3) Behavior Verification via Preflight Requests
- What was done: Added OPTIONS-based test assertions in `tests/test_api_auth.py`.
- Why this approach was chosen: CORS behavior is most directly validated via preflight request headers and avoids coupling to endpoint internals.
- Trade-offs considered: Unit-level header assertions are fast but do not replace end-to-end browser validation.
- Key implementation details: Added `_options()` test helper and `test_cors_headers_apply_to_api_routes_only`.

## Files Created

- `docs/notes/2026/2026-03-04__cors-config.md` - implementation note for this todo.

## Files Modified

- `project/__init__.py` - made API CORS origin list configurable while preserving `/api/v1/*` scoping.
- `tests/test_api_auth.py` - added CORS scope regression test and OPTIONS helper.

## API Contract

N/A — no endpoint shape or payload contract changed. Route access policy via CORS headers is now explicitly configurable through `API_CORS_ORIGINS`.

## Validation and Verification

1. Ran `poetry run python -m unittest tests.test_api_auth`.
2. Confirmed all tests passed (`Ran 6 tests ... OK`).
3. Checked lints for changed files with `ReadLints` and found no diagnostics.
4. Confirmed git diff includes only intended CORS config and related tests.

## Known Gaps / Follow-ups

- `API_CORS_ORIGINS` is not yet declared in `project/_config.py`; it currently relies on direct config lookup defaulting to `*`.
- No browser/device-level integration test yet for cross-origin requests from the Expo runtime.
- Socket.IO CORS remains separately configured and is outside this todo.

## How to Run (Current)

1. Start with app config containing `API_CORS_ORIGINS` if you want restricted origins; omit it to use default `*`.
2. Run tests: `poetry run python -m unittest tests.test_api_auth`.
3. To manually inspect behavior, issue OPTIONS requests:
   - API route: `/api/v1/auth/login` should include `Access-Control-Allow-Origin`.
   - Web route: `/login` should not include API CORS headers.
