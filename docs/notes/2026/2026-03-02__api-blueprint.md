# API Blueprint for Auth and Lists (`api-blueprint`)

Date: 2026-03-02
Owner: AI coding agent
Todo ID: `api-blueprint`

## Objective

Create a new Flask API surface under `/api/v1/` for authentication and list management, while reusing the existing service-layer business logic so web and mobile clients can share behavior without duplicating core rules.

## Scope Delivered

- Added API package and root registration module in `project/api/__init__.py`.
- Added JSON auth endpoints in `project/api/auth.py` for login, signup by invite token, refresh, logout, forgot-password, and reset-password.
- Added JSON lists endpoints in `project/api/lists.py` for list CRUD-ish flows, categories, items, reorder operations, sharing, and settings updates.
- Registered the new API blueprint in `project/__init__.py` at `/api/v1`.
- Added JWT extension wiring (`JWTManager`) in `project/extensions.py` and initialized it in app setup.
- Added `JWT_SECRET_KEY` config fallback in `project/_config.py` (`JWT_SECRET_KEY` -> `SECRET_KEY`).
- Added API-scoped CORS setup in `project/__init__.py` with `CORS(app, resources={r"/api/v1/*": {"origins": "*"}})`.

## Legacy Behavior Ported

- Preserved service-layer behavior from `project/services/auth_service.py` and `project/services/lists_service.py` by delegating API route handlers to those functions.
- Preserved invitation and email workflows by reusing existing email templates and MailerSend integration used in Jinja views.
- Preserved permission and ownership rules (`ensure_list_access`, `ensure_list_owner`) and translated outcomes to JSON HTTP responses (`403`, `404`, `400`) instead of flash+redirect patterns.
- Preserved password reset token mechanism by using `project/account/tokens.py` in API flows.

## Architecture and Design Choices

### 1) API Composition via Nested Blueprints
- What was done: Introduced `api_blueprint` with `url_prefix="/api/v1"` and registered feature sub-blueprints (`/auth`, `/lists`).
- Why this approach was chosen: Keeps feature separation clear and mirrors the existing modular Flask structure.
- Trade-offs considered: Single-file API registration would be simpler short-term, but scales poorly as more features are added.
- Key implementation details: `project/api/__init__.py` registers `auth_api_blueprint` and `lists_api_blueprint`.

### 2) JWT for API Authentication, Session Auth Left Intact
- What was done: Added `JWTManager` extension and JWT-protected API endpoints with `@jwt_required()`.
- Why this approach was chosen: Mobile/API clients need stateless bearer token auth; web session auth already exists and remains unchanged.
- Trade-offs considered: JWT blocklisting for true logout was deferred; current logout endpoint is informational.
- Key implementation details: `project/extensions.py`, `project/_config.py` (`JWT_SECRET_KEY`), and identity stored as `str(user.id)`.

### 3) Service Layer Reuse as Source of Truth
- What was done: API routes call existing service functions for auth/list logic.
- Why this approach was chosen: Avoids diverging behavior between Jinja routes and API routes.
- Trade-offs considered: Some thin serialization/mapping code is duplicated in API route modules, but business rules remain centralized.
- Key implementation details: Calls to `auth_service.authenticate_user`, `lists_service.get_user_lists`, `lists_service.share_list_with_email`, etc.

### 4) API-Scoped CORS and JSON Error Semantics
- What was done: Scoped CORS to `/api/v1/*` and standardized JSON error payloads.
- Why this approach was chosen: Keeps existing web app behavior/security posture stable while enabling external/mobile clients.
- Trade-offs considered: Wildcard origins (`*`) are flexible but less restrictive than environment-specific allowlists.
- Key implementation details:

```python
from flask_cors import CORS
from .extensions import jwt

jwt.init_app(app)
CORS(app, resources={r"/api/v1/*": {"origins": "*"}})
```

## Files Created

- API blueprint package
  - `project/api/__init__.py`
  - `project/api/auth.py`
  - `project/api/lists.py`
- Implementation notes
  - `docs/notes/2026/2026-03-02__api-blueprint.md`

## Files Modified

- `project/__init__.py` - registered API blueprint, initialized JWT, and enabled API-scoped CORS.
- `project/_config.py` - added `JWT_SECRET_KEY` config fallback.
- `project/extensions.py` - added shared `jwt = JWTManager()` extension object.

## API Contract

- Base prefix: `/api/v1`

- Auth routes (`/api/v1/auth`)
  - `POST /login`
    - Request: `{ "email": string, "password": string }`
    - Success `200`: `{ "access_token": string, "refresh_token": string, "user": {...} }`
  - `POST /refresh` (refresh JWT required)
    - Success `200`: `{ "access_token": string }`
  - `POST /logout` (access JWT required)
    - Success `200`: `{ "message": "Logged out." }`
  - `POST /signup/<token>`
    - Request: `{ "username": string, "password": string, "email"?: string }`
    - Success `201`: `{ "message": string, "user": {...} }`
  - `POST /forgot-password`
    - Request: `{ "email": string }`
    - Success `200`: `{ "message": string }`
  - `POST /reset-password/<token>`
    - Request: `{ "password": string }`
    - Success `200`: `{ "message": "Password has been reset." }`

- Lists routes (`/api/v1/lists`, access JWT required)
  - `GET /` -> `{ "owned": [listSummary], "shared": [listSummary] }`
  - `POST /` with `{ "title": string }` -> `{ "list": listSummary }` (`201`)
  - `GET /<list_id>` -> `{ "list": listDetailWithCategoriesAndItems }`
  - `POST /<list_id>/items` with `{ "name": string, "category_id": number, "quantity"?: string, "notes"?: string }` -> `{ "item": item }`
  - `POST /<list_id>/items/<item_id>/toggle` -> `{ "completed": boolean }`
  - `POST /<list_id>/items/reorder` with `{ "items": [{ "id": number, "ordering"?: number, "category_id"?: number }] }`
  - `POST /<list_id>/categories` with `{ "name": string }` -> `{ "category": category }`
  - `POST /<list_id>/categories/reorder` with `{ "categories": [{ "id": number, "ordering"?: number }] }`
  - `POST /<list_id>/share` with `{ "email": string }` -> `{ "status": string, "email": string }`
  - `PATCH /<list_id>/settings` with `{ "completed_display_mode": "inline_bottom" | "category_section" | "global_section" }` -> `{ "list": listSummary }`

## Validation and Verification

1. Ran `git status --short`, `git diff HEAD`, `git diff --cached`, and `git diff --name-status` to verify scope and changed files.
2. Ran linter diagnostics on edited files (`project/api/*`, `project/__init__.py`, `project/extensions.py`, `project/_config.py`) with no reported lints.
3. Ran syntax compilation: `python -m compileall project/api project/__init__.py project/extensions.py project/_config.py` (passed).

## Known Gaps / Follow-ups

- JWT logout is currently stateless and does not revoke tokens (no blocklist/denylist storage yet).
- No dedicated API schema/validation layer (e.g., Marshmallow schemas) has been introduced yet.
- No API-specific automated test coverage added in this todo.
- CORS currently allows all origins for `/api/v1/*`; tighten per environment before production hardening.

## How to Run (Current)

1. Ensure environment variables are set (at minimum `SECRET_KEY`, `DATABASE_URL`, and optionally `JWT_SECRET_KEY`).
2. Start the Flask app with your normal run command (e.g., `python run.py`).
3. Authenticate via `POST /api/v1/auth/login` to get access/refresh tokens.
4. Call protected list endpoints with header: `Authorization: Bearer <access_token>`.
5. Use `POST /api/v1/auth/refresh` with a refresh token when access token expires.
