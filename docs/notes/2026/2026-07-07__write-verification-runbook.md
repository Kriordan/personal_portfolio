# Backend Verification Runbook (`write-verification-runbook`)

Date: 2026-07-07
Todo ID: `write-verification-runbook`

## Objective

Consolidate the scattered setup, test, auth, smoke-check, and external-dependency knowledge into a single operational runbook so a new contributor can verify backend readiness from one document (plan phase 7).

## Scope Delivered

- Created `docs/verification-runbook.md` covering:
  - Local setup: Poetry install, full env var table (required vs. feature-specific), `db upgrade` / `reset-db`, `create-user`, and the debug-mode server command with the Talisman HTTPS caveat.
  - Test commands: the focused 51-test API/auth/socket regression suite, `discover -s tests` caveat, per-domain invocations, known pre-existing failures (`test_card_builder`, one scheduler test), and a table of what each API test file covers.
  - JWT login/refresh flow: all six `/api/v1/auth` endpoints, token lifetimes, header-only token location, curl examples, and login error cases.
  - API smoke checks per domain (lists, learning, wishlist, library, jobwizard) with curl examples, ownership-scoping notes, and a CORS preflight check.
  - Socket.IO JWT smoke path: automated test command plus a manual `python-socketio` snippet, event list, and the threading-mode note.
  - Mobile section: explicitly N/A until the Expo scaffold lands, with instructions for what to verify once it does.
  - External dependency notes for S3 (wishlist + jobwizard/APILeap), YouTube sync, and MailerSend, including how each is mocked in tests.
  - A copy-pasteable quick full-verification sequence and links to related historical notes.

## Prior Art / Context

- The closest existing docs were `docs/notes/2026/2026-07-06__test-existing-feature-apis.md` (test strategy) and `docs/notes/2026/2026-03-02__api-blueprint.md` (auth/lists contract); the runbook consolidates and supersedes them for operational use while linking back for design context.
- `README.md` retains the frontend/gulp and user-management CLI docs; the runbook references its troubleshooting guidance rather than duplicating it.

## Architecture and Design Choices

### 1) Single evergreen doc under `docs/`, not a dated note

- Placed at `docs/verification-runbook.md` rather than `docs/notes/2026/` because dated notes are historical records; the runbook is meant to be updated in place as the operational entry point (per the plan's acceptance criteria).

### 2) Automated-first verification

- The runbook leads with the unittest regression suite (no env vars, no DB, all external services mocked) and treats manual curl smoke checks as the second layer, since the automated path is the cheapest reliable signal.

### 3) Verified-against-code content, not transcribed docs

- Endpoint tables, env vars, CLI commands, and mocking claims were checked against `project/api/auth.py`, `project/api/jobwizard.py`, `project/_config.py`, `project/commands.py`, and `project/models.py` (`Job.render_screenshot`) rather than copied from older notes.

### 4) Mobile placeholder section

- The plan's phase 7 precedes the Expo scaffold (phase 8). The runbook includes a mobile verification section marked not-applicable-yet with concrete steps to fill in once `mobile/` exists, so the doc structure won't need rework.

## Files Created

- `docs/verification-runbook.md`
- `docs/notes/2026/2026-07-07__write-verification-runbook.md` (this note)

## Files Modified

N/A — documentation-only change.

## API Contract

N/A — no code changes; the runbook documents existing contracts.

## Validation and Verification

1. Ran the focused suite documented in the runbook: `poetry run python -m unittest tests.test_api_auth tests.test_api_feature_registration tests.test_api_learning tests.test_api_wishlist tests.test_api_library tests.test_api_jobwizard tests.test_socket_auth` — `Ran 51 tests ... OK`.
2. Cross-checked auth endpoint paths against route decorators in `project/api/auth.py` and jobwizard endpoints against `project/api/jobwizard.py`.
3. Confirmed env var names against `project/_config.py` and `os.getenv` calls in `project/models.py`.
4. Confirmed CLI commands and options against `project/commands.py`.

## Known Gaps / Follow-ups

- No `tests/test_api_lists.py` exists — the lists API relies on manual smoke checks; the runbook flags authenticated curl checks for it.
- The manual Socket.IO snippet (`python-socketio` client) was not executed against a live server; the automated `tests.test_socket_auth` path was.
- The mobile section must be updated when the Expo scaffold lands (plan phase 8).

## How to Run (Current)

1. Open `docs/verification-runbook.md`.
2. For a zero-setup check, run the automated suite from section 2 (`Ran 51 tests ... OK` expected).
3. For a full manual pass, follow the "Quick full-verification sequence" at the bottom: run tests, boot the server with `.env` configured, log in via curl, and hit one endpoint per domain with the access token.
