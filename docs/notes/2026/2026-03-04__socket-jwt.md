# Add JWT Socket Auth for Mobile (`socket-jwt`)

Date: 2026-03-04
Todo ID: `socket-jwt`

## Objective

Add JWT verification to the Socket.IO connection flow so mobile clients can authenticate without Flask session cookies. This enables Expo clients to establish real-time list collaboration connections using API-issued access tokens.

## Scope Delivered

- Updated `project/sockets.py` connection handling to accept either:
  - existing Flask-Login session auth (web clients), or
  - JWT access token passed via Socket.IO `auth.token` (mobile clients).
- Added JWT validation and identity resolution in the Socket.IO `connect` handler using `flask-jwt-extended`.
- Added socket-level user tracking keyed by `request.sid` so non-session clients remain identifiable for subsequent events.
- Updated all list collaboration event handlers in `project/sockets.py` to resolve the active user via session or socket JWT identity.
- Added cleanup of socket identity state on disconnect.
- Added new test module `tests/test_socket_auth.py` covering connection acceptance/rejection and JWT-authenticated list room join behavior.
- Replaced a legacy SQLAlchemy pattern (`Query.get`) with `db.session.get` in list room join authorization.

## Legacy Behavior Ported

- Preserved existing web socket behavior for browser clients using Flask-Login sessions (`current_user.is_authenticated` path still accepted first in `connect`).
- Preserved authorization semantics for list room access: users must still be list owners or explicitly shared collaborators.
- Preserved all existing event names and payload shape (`item_toggled`, `item_added`, `categories_reordered`, etc.), while changing only how actor identity is resolved.

## Architecture and Design Choices

### 1) Dual-authentication handshake for Socket.IO
- What was done: `handle_connect(auth=None)` now branches between session auth and JWT auth.
- Why this approach was chosen: web clients already rely on session cookies, while mobile clients rely on API JWTs; dual-path auth avoids regressions and duplicate socket namespaces.
- Trade-offs considered: a JWT-only socket policy would simplify auth logic but break existing browser behavior.
- Key implementation details:
  - File: `project/sockets.py`
  - JWT token source: Socket.IO connect payload `auth["token"]`
  - JWT check: `decode_token(token, allow_expired=False)`
  - Token type guard: only `type == "access"` accepted

### 2) Persisting identity for subsequent socket events
- What was done: introduced `_socket_user_ids: dict[str, int]` keyed by socket `sid` and helper `_resolve_authenticated_user()`.
- Why this approach was chosen: JWT is provided on connect only; event handlers need a repeatable way to resolve actor identity when no Flask session exists.
- Trade-offs considered: calling JWT decode on every event would increase overhead and require passing token repeatedly from client.
- Key implementation details:
  - File: `project/sockets.py`
  - Connect stores `sid -> user_id`
  - Disconnect removes `sid` entry
  - Event handlers call `_resolve_authenticated_user()` before acting

### 3) Consistent authorization + modern SQLAlchemy access
- What was done: switched list lookup from `CustomList.query.get(list_id)` to `db.session.get(CustomList, list_id)` and reused existing owner/shared access checks.
- Why this approach was chosen: remove legacy API warnings and keep auth checks centralized around resolved user identity.
- Trade-offs considered: no material trade-off; behavior remains the same with newer ORM access style.
- Key implementation details:
  - File: `project/sockets.py`
  - Access control condition unchanged in intent (`owner_id` or in `shared_with`)

## Files Created

- Tests
  - `tests/test_socket_auth.py` — new Socket.IO authentication coverage for JWT and unauthenticated clients.
- Notes
  - `docs/notes/2026/2026-03-04__socket-jwt.md` — implementation record for this todo.

## Files Modified

- `project/sockets.py` — added JWT socket connect verification, socket user-id mapping, identity resolver helper, disconnect cleanup, and event-level auth identity resolution updates.

## API Contract

- **Socket.IO connect auth input (newly supported)**
  - Client sends token in handshake payload:
    ```json
    {
      "token": "<jwt-access-token>"
    }
    ```
  - Accepted under Socket.IO `auth` field on connect (e.g. `io(url, { auth: { token } })`).
- **Authentication behavior**
  - Session-authenticated browser clients: accepted as before.
  - JWT-authenticated mobile clients: accepted when token is valid, unexpired, and token type is `access`.
  - Refresh tokens, malformed tokens, missing token (without session): rejected.

## Validation and Verification

1. Ran `poetry run python -m unittest tests.test_socket_auth`.
2. Verified all new socket auth tests pass (`Ran 4 tests ... OK`).
3. Ran `ReadLints` on edited files:
   - `project/sockets.py`
   - `tests/test_socket_auth.py`
   and confirmed no linter errors.
4. Confirmed SQLAlchemy legacy warning for `Query.get` in touched path is removed by using `db.session.get`.

## Known Gaps / Follow-ups

- Socket auth does not currently support token revocation/blocklist checks (same as current API logout model).
- `_socket_user_ids` is in-memory per process; if multi-process scaling is introduced, identity mapping would need process-aware/session-backed strategy.
- Existing socket event handlers still use `print`; structured logging can be introduced in a separate hardening pass.

## How to Run (Current)

1. Start the Flask app with Socket.IO enabled (normal app startup path).
2. Obtain an API access token from `POST /api/v1/auth/login`.
3. Connect from a Socket.IO client using:
   - `auth: { token: "<access-token>" }`
4. Emit `join_list` with a list ID owned/shared by that user:
   - `{ "list_id": <id> }`
5. Verify acknowledgment includes success and a room name (`list_<id>`), and collaboration events broadcast as expected.
