# Refactor Jinja Views To Service Layer (`refactor-views`)

Date: 2026-03-04
Todo ID: `refactor-views`

## Objective

Refactor existing Jinja routes into thinner HTTP wrappers by moving account and list business logic into the service layer. This keeps route handlers focused on request/response concerns and makes shared behavior reusable for API and future clients.

## Scope Delivered

- Moved account-domain decision logic out of `project/account/views.py` into `project/services/auth_service.py`.
- Added service functions for verification-token classification, password-reset preparation, resend-verification preparation, site invite creation, and admin invite listing.
- Updated account routes (`verify_email`, `resend_verification`, `admin_invites`, `forgot_password`, `reset_password`) to delegate business logic to `auth_service`.
- Added list service helpers in `project/services/lists_service.py` for invitation and list-item lookup.
- Updated list routes (`accept_invitation`, `toggle_item`) to call list service lookup helpers instead of querying ORM models directly in views.
- Removed now-unneeded direct model/query imports from refactored view modules.

## Legacy Behavior Ported

- Preserved existing flash-message behavior and route outcomes for invalid/expired/already-used verification and invitation flows.
- Preserved account invite safety checks (existing user, active invite) while relocating those checks into service functions.
- Preserved password-reset anti-enumeration behavior by still returning the same user-facing success message regardless of account existence.
- Preserved list access and invitation accept flow behavior while routing token/item lookups through services.

## Architecture and Design Choices

### 1) Service-first domain checks for account flows
- What was done: Introduced `get_verification_status`, `prepare_verification_resend`, `prepare_password_reset`, `create_site_invitation`, `get_admin_invites`, `get_user_from_reset_token`, and `reset_user_password` in `project/services/auth_service.py`.
- Why this approach was chosen: Account routes had mixed HTTP and domain logic; centralizing domain decisions makes behavior reusable and testable without Flask request context.
- Trade-offs considered: Returning simple status strings is lightweight and explicit, but less type-safe than richer result objects/exceptions.
- Key implementation details: `verify_email` now classifies token state via `auth_service.get_verification_status`; `admin_invites` calls `auth_service.create_site_invitation`; `forgot_password` calls `auth_service.prepare_password_reset`; `reset_password` calls `auth_service.get_user_from_reset_token` and `auth_service.reset_user_password`.

### 2) Keep HTTP-side responsibilities in views
- What was done: Left email sending (`MailerSendClient` usage), flash messaging, redirects, and template rendering in `project/account/views.py` and `project/lists/views.py`.
- Why this approach was chosen: These behaviors are HTTP/integration concerns and belong in route wrappers, while the service layer handles persistence and domain validation.
- Trade-offs considered: Some orchestration remains in views (status-to-flash mapping), but this keeps services decoupled from Flask request/response details.
- Key implementation details: `resend_verification` still catches send failures and logs via `current_app.logger`; `admin_invites` still constructs invite URLs and sends outbound invite emails.

### 3) Incremental list view extraction
- What was done: Added `get_invitation_or_404` and `get_list_item_or_404` in `project/services/lists_service.py`, then updated list routes to use those helpers.
- Why this approach was chosen: It reduces direct ORM usage in views without changing route behavior or introducing risky broad rewrites.
- Trade-offs considered: This is a narrow extraction step; deeper list orchestration can be moved later if needed.
- Key implementation details: `accept_invitation` no longer queries `ListInvitation` directly; `toggle_item` no longer queries `ListItem` directly.

## Files Created

- None in application code for this todo.
- `docs/notes/2026/2026-03-04__refactor-views.md` (this implementation note).

## Files Modified

- `project/account/views.py` - Refactored multiple account routes to delegate domain logic to `auth_service`.
- `project/services/auth_service.py` - Added account-domain helper/service functions used by Jinja views.
- `project/lists/views.py` - Replaced direct ORM lookups with list service helper calls in invitation/item handlers.
- `project/services/lists_service.py` - Added lookup helpers used by list views.

## API Contract

N/A - No external API endpoint contract changes were introduced; this todo refactors internal server-side route/service boundaries.

## Validation and Verification

1. Ran IDE lint diagnostics for modified files with `ReadLints`; no linter errors were reported.
2. Ran `python -m compileall` (via Poetry env) on all modified files to confirm syntax validity.
3. Attempted to run targeted tests (`tests/test_api_auth.py`, `tests/test_socket_auth.py`), but `pytest` is not currently installed in the environment (`No module named pytest`).

## Known Gaps / Follow-ups

- Add/enable `pytest` in the project environment and run account/list regression tests for auth + invite flows.
- Consider converting status-string returns to typed result objects/enums for stronger service contracts.
- Continue migrating remaining non-thin Jinja route logic in other blueprints once corresponding service modules exist.

## How to Run (Current)

1. Ensure dependencies are installed for the Flask app environment (`poetry install`).
2. Start the app (`poetry run python run.py` or project-standard command).
3. Exercise these flows in browser:
   - `/verify-email/<token>` verification outcomes.
   - `/resend-verification` from login flow with `pending_verification_email` in session.
   - `/admin/invites` as an admin user.
   - `/forgot-password` and `/reset-password/<token>`.
   - `/lists/invitation/<token>` and `/lists/<list_id>/toggle_item/<item_id>`.
