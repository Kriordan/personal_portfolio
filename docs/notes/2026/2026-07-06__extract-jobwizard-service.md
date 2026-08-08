# Extract Jobwizard Service (`extract-jobwizard-service`)

Date: 2026-07-06
Todo ID: `extract-jobwizard-service`

## Objective

Move job listing, lookup, creation, and screenshot/persistence orchestration out of the jobwizard web routes into a dedicated service module, so the upcoming jobwizard API (plan phase 6) can reuse the same business logic.

## Scope Delivered

- New service module `project/services/jobwizard_service.py` with `list_jobs()`, `get_job(job_id)`, and `create_job(...)`.
- Service-level exceptions: `JobwizardServiceError` (base), `NotFoundError`, and `ValidationError`, matching the pattern used by `library_service` and `wishlist_service`.
- Refactored `project/jobwizard/views.py` so routes only handle forms, redirects, and template rendering; all DB and screenshot work goes through the service.
- New test module `tests/test_jobwizard_service.py` covering service behavior and the refactored web routes (6 tests).

## Legacy Behavior Ported

- `home` still renders `job_list.html` with all jobs and an `AddJobForm`.
- `create_job` still validates via `AddJobForm`, renders a listing screenshot via `Job.render_screenshot()`, persists the job, and redirects to the job list.
- `get_job` still renders `job.html` for an existing job. Behavior change: a missing or non-numeric job ID now returns a 404 page instead of rendering `job.html` with `job=None` (missing ID) or raising `ValueError` on `int(job_id)` (non-numeric ID). This satisfies the plan's "missing job IDs map to a clear 404" acceptance criterion.

## Architecture and Design Choices

### 1) Service module shape

- Followed the established convention: module-level functions, a base exception class, and `NotFoundError`/`ValidationError` subclasses (same structure as `project/services/library_service.py` and `wishlist_service.py`).
- `get_job` raises `NotFoundError` rather than returning `None`, matching `library_service.get_video`, so future API handlers can map it to a JSON 404 the same way `project/api/library.py` does.

### 2) Screenshot rendering stays inside `create_job`

- `create_job` calls `job.render_screenshot()` before `db.session.add`/`commit`, preserving the original ordering from the view.
- Tests mock `Job.render_screenshot` with `unittest.mock.patch.object`, keeping the external APILeap/S3 calls out of the test run while still asserting the workflow invokes rendering exactly once.

### 3) Input validation in the service

- `create_job` strips and requires `title`, `company_name`, and `listing_url`, raising `ValidationError` on blanks. The web route still relies on `AddJobForm` validation first, but the service now guards the contract independently so the future API cannot create blank jobs.
- `posted_date` defaults to `datetime.now(timezone.utc)` inside the service, removing that concern from the view.

### 4) Route converter for job detail

- Changed `/jobwizard/<job_id>` to `/jobwizard/<int:job_id>`, so non-numeric IDs 404 at the routing layer instead of crashing on `int(job_id)`.

## Files Created

- `project/services/jobwizard_service.py`
- `tests/test_jobwizard_service.py`
- `docs/notes/2026/2026-07-06__extract-jobwizard-service.md` (this note)

## Files Modified

- `project/jobwizard/views.py` — routes now delegate to `jobwizard_service`; direct `db`/`Job` imports removed; job detail route uses `<int:job_id>` and returns `404.html` on `NotFoundError`.

## API Contract

N/A — no HTTP API added in this phase. The service functions form the contract the phase-6 jobwizard API will consume:

- `list_jobs() -> list[Job]`
- `get_job(job_id: int) -> Job` (raises `NotFoundError`)
- `create_job(*, title, company_name, listing_url, posted_date=None) -> Job` (raises `ValidationError`)

## Validation and Verification

1. `pytest tests/test_jobwizard_service.py` — 6 passed (service CRUD, validation, not-found, web-route 404, and web-route create delegation with screenshot mocked).
2. Full suite `pytest tests --ignore=tests/test_card_builder.py` — 56 passed plus the 6 new tests; the single failure (`tests/test_scheduler.py::test_rate_creates_log_and_intra_day_review`, 302 vs 200) was confirmed pre-existing by stashing changes and re-running on the clean tree.
3. `tests/test_card_builder.py` has a pre-existing collection error (`_build_cards` no longer exists in `project.learning.views`); also confirmed on the clean tree.
4. Linter check on the new/modified files — no errors.

## Known Gaps / Follow-ups

- `tests/test_card_builder.py` is broken independently of this work and should be updated to import from `learning_service`.
- The pre-existing `test_scheduler.py` rate-endpoint failure (302 redirect) should be investigated separately.
- Jobwizard ownership (plan phase 5) is still open: `Job` has no `user_id`, so `list_jobs`/`get_job` are intentionally not user-scoped yet.
- `pytest` was installed ad hoc into `.venv`; it is still not declared as a dev dependency in `pyproject.toml`.

## How to Run (Current)

1. `cd /Users/keithriordan/dojo/personal_portfolio`
2. `.venv/bin/python -m pytest tests/test_jobwizard_service.py -q`
3. To exercise manually: run the app, log in, visit `/jobwizard` to list jobs, `/jobwizard/add/` to create one (renders a screenshot via APILeap/S3 when configured), and `/jobwizard/<id>` for detail; unknown IDs return the 404 page.
