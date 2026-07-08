# Final Integration Pass (`final-integration-pass`)

Date: 2026-07-07
Todo ID: `final-integration-pass`

## Objective

Close out the Flask API/Expo migration (plan phase 12): run all backend and mobile checks, bring the docs in line with the final implementation, and clean up stale artifacts left over from earlier phases.

## Scope Delivered

- Full backend test suite now passes (`Ran 77 tests ... OK`) — fixed the two documented pre-existing failures instead of carrying them forward.
- Mobile static checks pass: `tsc --noEmit` clean, `eslint .` clean (one warning in the generated `.expo/types/router.d.ts`, not project code).
- `docs/verification-runbook.md` updated to match reality: test counts (54 focused / 77 full), removed the "known pre-existing failures" section, updated the mobile smoke section (Socket.IO/lists is now wired in), and added the mobile-phase notes to the historical index.
- `mobile/README.md` project-structure table expanded to cover the learning, wishlist, library, and jobwizard screens and their typed API modules.
- Root `README.md` gained a short "Project layout" section pointing to `project/api/`, `mobile/`, and the verification runbook.
- Removed 14 unused Expo-template images from `mobile/assets/images/` and the empty untracked `mobile/src/components/ui/` directory.

## Prior Art / Context

This is the last phase of the migration plan. All feature work (API registration, service extraction, jobwizard ownership/API, runbook, Expo scaffold/auth/lists/learning/wishlist/library/jobwizard) landed in the preceding commits on `build-api-blueprint`; this pass only verifies, documents, and cleans up.

## Architecture and Design Choices

### 1) Fix the two pre-existing test failures rather than re-document them

- `tests/test_card_builder.py` imported `_build_cards` from `project.learning.views`, which no longer exists; the function moved to `project/services/learning_service.py` as `build_cards` during the service extraction (March). Updated the import — the test body needed no changes, confirming the behavior contract survived the move.
- `tests/test_scheduler.py::test_rate_creates_log_and_intra_day_review` failed twice over:
  - It POSTed to `/learning/rate` over plain HTTP, and Talisman 302-redirects to HTTPS in tests. Fixed with `base_url="https://localhost"`, the same convention every other integration test in the repo already uses.
  - The final assertion compared `progress.next_review` (naive, as SQLite deserializes timezone columns) against an aware datetime. Coerced to UTC in the test, mirroring the `_ensure_aware` approach in `learning_service`.
- Rationale: the runbook previously listed these as "known pre-existing failures (not regressions)". Fixing them makes `discover -s tests` a clean signal, which is worth more than the documentation workaround.

### 2) Docs updated in place, historical notes left alone

- The runbook is the operational entry point and is meant to be edited in place; the dated notes under `docs/notes/2026/` are historical records and were not rewritten even where they describe superseded states (e.g. the runbook note saying the mobile section is "not-applicable-yet").

### 3) Asset cleanup scoped to provably-unused files

- Only deleted images with zero references across `mobile/src`, `mobile/app.json`, and config files (react logos, expo badges/logo, tutorial image, tab icons, logo-glow). Everything referenced by `app.json` (icons, splash, favicon, adaptive-icon set, `assets/expo.icon/`) was kept.

## Files Created

- `docs/notes/2026/2026-07-07__final-integration-pass.md` (this note)

## Files Modified

- `tests/test_card_builder.py` — import `build_cards` from `learning_service` instead of the removed `views._build_cards`
- `tests/test_scheduler.py` — HTTPS `base_url` on the rate POST; naive→aware coercion before the `next_review` assertion
- `docs/verification-runbook.md` — test counts, removed stale known-failures list, mobile smoke section covers all feature screens, historical-notes index extended
- `mobile/README.md` — project-structure table covers all feature screens and API modules
- `README.md` — new "Project layout" section linking API, mobile app, and runbook

Deleted: `mobile/assets/images/{tutorial-web,react-logo,react-logo@2x,react-logo@3x,expo-badge,expo-badge-white,expo-logo,logo-glow}.png` and `mobile/assets/images/tabIcons/` (6 files).

## API Contract

N/A — no endpoint or interface changes; route inventory in the runbook was verified against `project/api/*.py` decorators and matches.

## Validation and Verification

1. Focused suite: `poetry run python -m unittest tests.test_api_auth ... tests.test_socket_auth` → `Ran 54 tests ... OK`.
2. Full suite: `poetry run python -m unittest discover -s tests` → `Ran 77 tests ... OK` (previously 1 failure + 1 error).
3. Mobile: `tsc --noEmit` exits 0; `eslint . --quiet` exits 0.
4. Runbook API paths cross-checked against blueprint route decorators in `project/api/` (auth, lists, learning, wishlist, library, jobwizard) — all match.
5. Grep for `TODO|FIXME|placeholder|stub` across `project/` found nothing; AST scan of all branch-touched Python files found no unused imports.

## Known Gaps / Follow-ups

- Manual end-to-end smoke (booting the Flask server + Expo app against it) was not run in this pass; the runbook's section 6 documents the steps.
- `tests/test_scheduler.py` still asserts against `LEARNING_STEPS[0]` timing with a 5-second buffer; fine today but could flake on a very slow machine.
- The eslint warning in `.expo/types/router.d.ts` is generated code and will regenerate; not actionable.

## How to Run (Current)

```bash
# Backend
poetry run python -m unittest discover -s tests   # expect: Ran 77 tests ... OK

# Mobile
cd mobile
./node_modules/.bin/tsc --noEmit
./node_modules/.bin/eslint .
```

Full manual verification: follow `docs/verification-runbook.md` sections 1–6.
