# Add Jobwizard API (`add-jobwizard-api`)

Date: 2026-07-07
Todo ID: `add-jobwizard-api`

## Objective

Expose jobwizard through the `/api/v1/` JSON API so the planned Expo mobile client can list, create, and view jobs, reusing the extracted `jobwizard_service` and the ownership model added in the previous todo.

## Scope Delivered

- New API blueprint `project/api/jobwizard.py` with three JWT-protected endpoints:
  - `GET /api/v1/jobwizard/jobs` — list the authenticated user's jobs
  - `POST /api/v1/jobwizard/jobs` — create a job (renders listing screenshot via the service)
  - `GET /api/v1/jobwizard/jobs/<job_id>` — job detail, owner-scoped
- Registered the blueprint in `project/api/__init__.py` alongside the other feature APIs.
- Added `serialize_job()` to `project/services/jobwizard_service.py` for JSON-safe payloads.
- New test module `tests/test_api_jobwizard.py` (7 tests) covering auth, ownership, validation, payload shape, and screenshot mocking.
- Added `/api/v1/jobwizard/jobs` to the route-registration smoke test in `tests/test_api_feature_registration.py`.

## Prior Art / Context

- Endpoint structure, JWT identity resolution (`_current_user_from_jwt`), payload parsing, and error-shape conventions were copied from `project/api/wishlist.py` so all feature APIs behave identically.
- Ownership semantics come from `jobwizard_service` (see `./2026-07-06__resolve-jobwizard-ownership.md`): foreign jobs raise `NotFoundError`, which the API maps to 404 so job existence is not leaked.

## Architecture and Design Choices

### 1) Serialization lives in the service

- Added `serialize_job()` next to the query/create helpers in `jobwizard_service.py`, mirroring `wishlist_service.serialize_gift()`.
- Keeps the JSON contract in one place should the web layer or future consumers need it, and keeps API handlers limited to auth, parsing, and error mapping.
- Payload includes `listing_image` (the S3 screenshot URL) so the mobile detail screen can show it without an extra endpoint.

### 2) Error mapping via service exceptions

- `ValidationError` → 400 with `{"error": "<message>"}`; `NotFoundError` → 404 `{"error": "Job not found."}`.
- Unlike wishlist (whose service returns `None` for missing gifts), jobwizard's service raises exceptions, so the API uses try/except rather than None checks. No behavior difference for clients.

### 3) Endpoint surface kept minimal

- Only list/create/detail were implemented — the same surface the web UI offers. No update/delete endpoints were invented, matching the plan's scope for the mobile flow.
- `posted_date` is not accepted from clients; the service defaults it to now, same as the web form path.

## Files Created

- `project/api/jobwizard.py`
- `tests/test_api_jobwizard.py`
- `docs/notes/2026/2026-07-07__add-jobwizard-api.md` (this note)

## Files Modified

- `project/api/__init__.py` — import and register `jobwizard_api_blueprint`.
- `project/services/jobwizard_service.py` — added `serialize_job()`.
- `tests/test_api_feature_registration.py` — added jobwizard route to the JWT-protection smoke test.

## API Contract

All endpoints require `Authorization: Bearer <access_token>`.

- `GET /api/v1/jobwizard/jobs` → 200 `{"jobs": [<job>, ...]}`
- `POST /api/v1/jobwizard/jobs` with JSON or form body `{"title", "company_name", "listing_url"}` → 201 `{"job": <job>}`; 400 `{"error": "title, company_name, and listing_url are required"}` on blank/missing fields.
- `GET /api/v1/jobwizard/jobs/<int:job_id>` → 200 `{"job": <job>}`; 404 `{"error": "Job not found."}` for unknown or foreign jobs.

Job payload shape:

```json
{
  "id": 1,
  "title": "Engineer",
  "company_name": "Acme",
  "listing_url": "https://example.com/job",
  "listing_image": "",
  "posted_date": "2026-07-07T13:58:00+00:00",
  "user_id": 1
}
```

## Validation and Verification

1. `pytest tests/test_api_jobwizard.py tests/test_api_feature_registration.py tests/test_jobwizard_service.py` — 17 passed.
2. Full suite `pytest tests --ignore=tests/test_card_builder.py` — 72 passed, 1 pre-existing failure in `tests/test_scheduler.py::SchedulerIntegrationTests::test_rate_creates_log_and_intra_day_review` (302 vs 200, unrelated to this change).
3. `tests/test_card_builder.py` fails at collection on `from project.learning.views import _build_cards` — pre-existing breakage; the function moved to `learning_service.build_cards` in earlier refactoring.
4. No linter errors in any touched file.

## Known Gaps / Follow-ups

- `tests/test_card_builder.py` needs updating to import `build_cards` from `project.services.learning_service` (pre-existing, out of scope here).
- The scheduler test failure above predates this change and should be triaged separately.
- No update/delete API endpoints; add them if the mobile jobwizard flow grows beyond list/create/detail.

## How to Run (Current)

1. Activate the venv: `source .venv/bin/activate`.
2. Run the tests: `python -m pytest tests/test_api_jobwizard.py -q`.
3. To exercise manually: start the app, obtain a JWT via `POST /api/v1/auth/login`, then:
   - `curl -H "Authorization: Bearer $TOKEN" https://localhost/api/v1/jobwizard/jobs`
   - `curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"title":"Engineer","company_name":"Acme","listing_url":"https://example.com/job"}' https://localhost/api/v1/jobwizard/jobs`

   Note: real job creation calls the APILeap screenshot API and S3 (`Job.render_screenshot`), so manual creation needs those credentials configured.
