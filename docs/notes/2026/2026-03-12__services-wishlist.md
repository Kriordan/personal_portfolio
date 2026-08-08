# Extract Wishlist Domain Service (`services-wishlist`)

Date: 2026-03-12
Todo ID: `services-wishlist`

## Objective

Create a shared wishlist service module that centralizes gift CRUD rules and image-upload orchestration so both Jinja and API route layers reuse the same domain behavior. This reduces duplication and keeps transport logic separate from business logic.

## Scope Delivered

- Added `project/services/wishlist_service.py` with shared wishlist business logic and typed validation errors.
- Added shared gift serialization in `serialize_gift()` for API response payload reuse.
- Added shared S3 upload orchestration in `upload_image_to_s3()` using `WISHLIST_S3_BUCKET` and graceful credential fallback.
- Added shared CRUD helpers: `list_gifts_for_user()`, `get_gift_for_user()`, `create_gift_for_user()`, `update_gift()`, and `delete_gift()`.
- Refactored `project/api/wishlist.py` to delegate create/read/update/delete flow and validation semantics to service functions.
- Refactored `project/wishlist/views.py` wishlist home and delete handlers to use the same service layer instead of direct model/session/S3 logic.

## Legacy Behavior Ported

- Preserved title/body required semantics for gift creation (`title and body are required`).
- Preserved update validation semantics (`title cannot be empty`, `body cannot be empty`).
- Preserved optional image upload behavior: upload is attempted only when a file is present; `image_url` is updated only on successful upload.
- Preserved API unauthorized and not-found responses from route wrappers while moving ownership lookup logic into `get_gift_for_user()`.
- Preserved existing wishlist page flow: submit form, persist gift, redirect back to wishlist home, and render current-user gifts.

## Architecture and Design Choices

### 1) Centralize wishlist domain logic behind a service boundary
- What was done: Introduced `project/services/wishlist_service.py` and moved gift CRUD + upload orchestration out of route modules.
- Why this approach was chosen: API and web handlers previously duplicated persistence and upload behavior, increasing drift risk.
- Trade-offs considered: Adds another module and service API surface, but significantly improves reuse and consistency.
- Key implementation details: Shared entry points now include `create_gift_for_user()` and `update_gift()` (validation + persistence), with `WishlistServiceError` / `ValidationError` as route-consumable error contracts.

### 2) Keep route modules as HTTP/session adapters only
- What was done: `project/api/wishlist.py` now resolves auth context, parses payload, calls services, and maps service exceptions to status codes; `project/wishlist/views.py` now handles forms/templates and delegates DB logic.
- Why this approach was chosen: Route layers should remain responsible for protocol concerns, not domain internals.
- Trade-offs considered: Some payload extraction remains in route functions for clarity (`_request_payload()`), but business rules no longer live there.
- Key implementation details: API routes call `wishlist_service.serialize_gift()` for response shape consistency; web delete route now uses owner-scoped lookup and aborts on missing/foreign gifts.

### 3) Reuse a single image-upload workflow
- What was done: Migrated S3 file upload from wishlist views to `wishlist_service.upload_image_to_s3()`.
- Why this approach was chosen: Ensures one upload path is used regardless of API multipart upload or Jinja form upload.
- Trade-offs considered: Service remains coupled to boto3/S3 details; acceptable for now because upload behavior is part of wishlist domain workflow.
- Key implementation details: Reads `WISHLIST_S3_BUCKET`, uploads with `boto3.client("s3").upload_fileobj(...)`, and returns `None` when bucket config is missing or credentials are unavailable.

## Files Created

- `project/services/wishlist_service.py` - new shared wishlist business logic module.
- `project/api/wishlist.py` - API wishlist endpoints now implemented as service-backed wrappers.
- `docs/notes/2026/2026-03-12__services-wishlist.md` - this implementation note.

## Files Modified

- `project/wishlist/views.py` - removed direct S3/DB gift logic and delegated wishlist home/delete flows to `wishlist_service`.

## API Contract

- No new endpoint paths were introduced.
- Existing wishlist API routes under `/api/v1/wishlist` keep the same endpoint structure and status behavior:
  - `GET /gifts` -> `{"gifts": [...]}` (200)
  - `POST /gifts` -> `{"gift": {...}}` (201), `{"error": "<message>"}` (400)
  - `GET /gifts/<gift_id>` -> `{"gift": {...}}` (200), `{"error": "Gift not found."}` (404)
  - `PUT /gifts/<gift_id>` -> `{"gift": {...}}` (200), `{"error": "<message>"}` (400/404)
  - `DELETE /gifts/<gift_id>` -> `{"message": "Gift deleted."}` (200), `{"error": "Gift not found."}` (404)

## Validation and Verification

1. Ran lint diagnostics with `ReadLints` on:
   - `project/services/wishlist_service.py`
   - `project/api/wishlist.py`
   - `project/wishlist/views.py`
   Result: no linter errors.
2. Attempted test execution:
   - `pytest -q`
   - `python -m pytest -q`
   Result: blocked because `pytest` is not installed in the active environment.
3. Ran syntax verification:
   - `python -m compileall project/services/wishlist_service.py project/api/wishlist.py project/wishlist/views.py`
   Result: success.

## Known Gaps / Follow-ups

- Add dedicated wishlist API and web-route tests to verify ownership, validation errors, and upload behavior across both interfaces.
- Decide whether to implement the currently stubbed Jinja wishlist routes (`gift_create`, `gift_detail`, `gift_update`) or remove them if obsolete.
- Install `pytest` in the local environment so automated regression tests can be executed here.

## How to Run (Current)

1. Start the Flask app in your normal local development setup.
2. Ensure `WISHLIST_S3_BUCKET` is set if you want image upload enabled.
3. Verify web flow:
   - Log in and visit `/wishlist/`.
   - Create a gift (optionally attach an image) and confirm it appears in the list.
   - Delete a gift via `/wishlist/gifts/<id>/delete` and confirm it is removed.
4. Verify API flow (JWT required):
   - `GET /api/v1/wishlist/gifts`
   - `POST /api/v1/wishlist/gifts` with `title`, `body`, optional `image`
   - `PUT /api/v1/wishlist/gifts/<id>` with partial updates and optional `image`
   - `DELETE /api/v1/wishlist/gifts/<id>`
5. Confirm behavior parity:
   - Validation messages and ownership checks behave consistently.
   - Uploaded image URL population is handled through the shared service.
