# Resolve Jobwizard Ownership Model (`resolve-jobwizard-ownership`)

Date: 2026-07-06
Todo ID: `resolve-jobwizard-ownership`

## Objective

Make jobwizard ownership semantics explicit — jobs are now private, per-user records — so the upcoming mobile API can implement meaningful auth and ownership checks.

## Scope Delivered

- Added `user_id` foreign key (non-nullable, indexed) and an `owner` relationship to the `Job` model in `project/models.py`.
- Rewrote `project/services/jobwizard_service.py` around owner-scoped functions: `list_jobs_for_user`, `get_job_for_user`, and `create_job_for_user`.
- Updated `project/jobwizard/views.py` so all web routes operate on `current_user.id`; users can no longer see or open other users' jobs.
- Added Alembic migration `migrations/versions/e5f6a7b8c9d0_add_job_ownership.py` with backfill for existing rows.
- Updated the legacy seed script `db_create.py` to assign an owner when seeding a job.
- Expanded `tests/test_jobwizard_service.py` with foreign-user access coverage (9 tests total).

## Prior Art / Context

- The ownership pattern mirrors `wishlist_service` (`project/services/wishlist_service.py`), where `Gift` rows carry `user_id` and lookups take `user_id` + record ID, returning not-found for foreign records.
- The migration backfill approach follows `b7f9c1d2e3f4_add_invite_only_signup.py`: add column with relaxed constraint, backfill via `op.execute`, then tighten with `batch_alter_table`.

## Architecture and Design Choices

### 1) Ownership decision: private per-user jobs

- Jobs were previously global — every logged-in user saw every job. The plan flagged that ownership must be explicit before exposing a mobile API.
- Chose private per-user ownership (rather than an intentional shared/admin model) because jobwizard is a personal job-hunt tracker; sharing has no use case here, and this matches every other user-owned domain in the app (gifts, lists, review progress).

### 2) Not-found instead of forbidden for foreign jobs

- `get_job_for_user` raises `NotFoundError` for both missing and foreign-owned jobs, so the web route returns 404 either way and job existence is not leaked. This matches `wishlist_service.get_gift_for_user` returning `None` for foreign gifts.

### 3) Migration backfill strategy

- New `jobs.user_id` is added nullable, backfilled to the earliest admin user (falling back to the earliest user), then made `NOT NULL` with an index and FK (`fk_jobs_user_id_user`).
- Rationale: all pre-existing jobs were created by the site owner before multi-user semantics existed, and the invite-only migration grandfathered the original users as admins, so "earliest admin" identifies the owner.
- If no users exist, orphaned job rows are deleted so the `NOT NULL` constraint can apply; a jobs table with no users has no meaningful owner.
- Uses `batch_alter_table` for SQLite compatibility, consistent with other migrations in the repo.

### 4) Service API rename

- Functions were renamed (`list_jobs` → `list_jobs_for_user`, etc.) rather than given optional `user_id` parameters, so ownership scoping is impossible to forget at call sites. No compatibility shims were kept; the only callers (web views and tests) were updated in the same change.

## Files Created

- `migrations/versions/e5f6a7b8c9d0_add_job_ownership.py` — migration adding `jobs.user_id` with backfill.
- `docs/notes/2026/2026-07-06__resolve-jobwizard-ownership.md` — this note.

## Files Modified

- `project/models.py` — `Job` gains `user_id` column, `owner` relationship, and a required `user_id` constructor argument.
- `project/services/jobwizard_service.py` — owner-scoped service functions replace global ones.
- `project/jobwizard/views.py` — routes pass `current_user.id` into the service.
- `tests/test_jobwizard_service.py` — updated to new service API; added foreign-user and per-user listing tests.
- `db_create.py` — seed script now resolves an owner (earliest admin, fallback earliest user) and exits with a message if no user exists.

## API Contract

Service layer (module `project.services.jobwizard_service`):

- `list_jobs_for_user(user_id: int) -> list[Job]`
- `get_job_for_user(*, user_id: int, job_id: int) -> Job` (raises `NotFoundError` for missing or foreign jobs)
- `create_job_for_user(*, user_id: int, title, company_name, listing_url, posted_date=None) -> Job` (raises `ValidationError` on blank fields)

No HTTP API endpoints yet; the jobwizard API is a later todo and will build on these functions.

## Validation and Verification

1. `PYTHONPATH=. poetry run pytest tests/test_jobwizard_service.py -q` — 9 passed, including foreign-user 404 and per-user listing tests.
2. Full suite (`--ignore=tests/test_card_builder.py`) — 65 passed; the one failure (`test_scheduler.py::test_rate_creates_log_and_intra_day_review`) and the `test_card_builder.py` collection error were confirmed pre-existing by stashing this change and re-running.
3. Lint check on all touched files — clean.

## Known Gaps / Follow-ups

- The migration has not been executed against the production database; run `flask db upgrade` at deploy time.
- Jobwizard API endpoints (`project/api/jobwizard.py`) remain a separate todo and should reuse the owner-scoped service functions.
- `Job.render_screenshot` still performs live ApiLeap/S3 calls inside `create_job_for_user`; tests mock it, but extracting it behind an injectable client is possible future cleanup.

## How to Run (Current)

1. `poetry install`
2. `flask db upgrade` (applies `e5f6a7b8c9d0` — adds `jobs.user_id` and backfills existing rows).
3. `PYTHONPATH=. poetry run pytest tests/test_jobwizard_service.py -q`
4. Run the app, log in as two different users, and confirm each only sees their own jobs at `/jobwizard`; opening another user's job URL returns 404.
