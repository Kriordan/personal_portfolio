# Register Existing Feature APIs (`register-existing-feature-apis`)

Date: 2026-07-01
Todo ID: `register-existing-feature-apis`

## Objective

Expose the already-implemented learning, wishlist, and library JSON APIs through the shared `/api/v1/` blueprint so mobile/API clients can reach them, and add route smoke coverage that fails if those feature routes regress to missing endpoints.

## Scope Delivered

- Registered `learning_api_blueprint`, `wishlist_api_blueprint`, and `library_api_blueprint` in `project/api/__init__.py`.
- Preserved the existing `/api/v1/auth` and `/api/v1/lists` registrations unchanged.
- Added `tests/test_api_feature_registration.py` to smoke-test representative feature API routes without credentials.
- Verified unauthenticated requests to the new feature API paths return JWT auth failures (`401`) rather than route-not-found responses (`404`).

## Legacy Behavior Ported

- Preserved the existing feature API modules as the source of endpoint behavior:
  - `project/api/learning.py`
  - `project/api/wishlist.py`
  - `project/api/library.py`
- No route contracts, service calls, serializers, or auth decorators inside the feature API modules were changed.
- The update only activates these already-built blueprints beneath the existing aggregate API prefix.

## Architecture and Design Choices

### 1) Reuse the Existing Nested Blueprint Pattern
- What was done: Imported and registered the three feature API blueprints in `project/api/__init__.py`.
- Why this approach was chosen: The repo already composes API routes through a root `api_blueprint` with `url_prefix="/api/v1"` and child feature blueprints for `/auth` and `/lists`.
- Trade-offs considered: Registering feature blueprints directly on the Flask app would work, but it would bypass the established API grouping and make future API-wide behavior harder to reason about.
- Key implementation details: The activated paths are `/api/v1/learning/*`, `/api/v1/wishlist/*`, and `/api/v1/library/*`.

### 2) Smoke Test Route Activation Through Auth Behavior
- What was done: Added a single test that requests representative protected routes without an Authorization header.
- Why this approach was chosen: The acceptance criterion is specifically that the routes no longer 404 due to missing registration and instead fail at JWT authentication.
- Trade-offs considered: Full endpoint behavior tests are deferred to later feature API test work; this todo only needed registration/auth reachability coverage.
- Key implementation details: The smoke test checks `GET /api/v1/learning/notes`, `GET /api/v1/wishlist/gifts`, and `GET /api/v1/library/playlists`.

## Files Created

- `tests/test_api_feature_registration.py` - route-registration smoke tests for the existing learning, wishlist, and library API blueprints.
- `docs/notes/2026/2026-07-01__register-existing-feature-apis.md` - implementation note for this todo.

## Files Modified

- `project/api/__init__.py` - registered the existing feature API blueprints beneath `/api/v1`.

## API Contract

- Base prefix remains `/api/v1`.
- Learning API is now registered under `/api/v1/learning`.
  - Smoke-tested route: `GET /api/v1/learning/notes`
  - Auth behavior: missing JWT returns `401`.
- Wishlist API is now registered under `/api/v1/wishlist`.
  - Smoke-tested route: `GET /api/v1/wishlist/gifts`
  - Auth behavior: missing JWT returns `401`.
- Library API is now registered under `/api/v1/library`.
  - Smoke-tested route: `GET /api/v1/library/playlists`
  - Auth behavior: missing JWT returns `401`.

## Validation and Verification

1. Ran linter diagnostics on `project/api/__init__.py` and `tests/test_api_feature_registration.py`; no linter errors were reported.
2. Ran focused regression coverage: `poetry run python -m unittest tests.test_api_feature_registration tests.test_api_auth tests.test_socket_auth` (passed: 11 tests).
3. Attempted `poetry run python -m unittest discover`; from the repo root this discovered 0 tests.
4. Ran explicit discovery with `poetry run python -m unittest discover -s tests`; this surfaced pre-existing learning test failures unrelated to this todo:
   - `tests/test_card_builder.py` imports removed symbol `project.learning.views._build_cards`.
   - `tests/test_scheduler.py::SchedulerIntegrationTests.test_rate_creates_log_and_intra_day_review` expected `200` but received `302`.
5. Ran `git status --short`, `git diff HEAD`, `git diff --cached`, and `git diff --name-status` to verify the implementation scope.

## Known Gaps / Follow-ups

- This is route activation coverage only; detailed feature API behavior tests for learning, wishlist, and library remain part of the later feature API test todo.
- Existing full-suite learning test failures remain unresolved because they are outside the assigned registration task.

## How to Run (Current)

1. Run the focused API/auth/socket checks:

```bash
poetry run python -m unittest tests.test_api_feature_registration tests.test_api_auth tests.test_socket_auth
```

2. Manually smoke-check route/auth behavior if needed:

```bash
curl -i https://localhost/api/v1/learning/notes
curl -i https://localhost/api/v1/wishlist/gifts
curl -i https://localhost/api/v1/library/playlists
```

Each unauthenticated request should reach the registered route and return a JWT auth failure rather than a 404.
