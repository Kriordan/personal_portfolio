# Extract Learning Domain Service (`services-learning`)

Date: 2026-03-10
Todo ID: `services-learning`

## Objective

Create a reusable learning-domain service module and move non-HTTP business logic out of learning web/API routes. This keeps route handlers thin and ensures learning behavior is implemented once and reused consistently across interfaces.

## Scope Delivered

- Added `project/services/learning_service.py` with shared learning domain logic used by both web and API routes.
- Moved note file loading and normalization logic into service functions: `notes_dir_for_root()`, `load_note()`, and `load_notes()`.
- Moved flashcard transformation logic into `build_cards()`, including support for `incident`, `cloze`, `command`, `code_diff`, and default Q/A card types.
- Moved review queue and due-count logic into `summarize_notes_for_user()` and `review_cards_for_user()`.
- Moved rating/scheduler persistence workflow into `rate_card_for_user()`, including `ReviewProgress` updates, `ReviewLog` inserts, and admin debug payload generation.
- Moved incident-card creation logic into `create_incident_card()`, including validation, slug generation, uniqueness checks, and file persistence.
- Refactored `project/learning/views.py` to delegate learning logic to the service module and keep handlers HTTP-focused.
- Refactored `project/api/learning.py` to delegate learning logic to the same service module and keep handlers HTTP-focused.

## Legacy Behavior Ported

- Preserved existing note JSON loading behavior, including defaults for `id`, `title`, `summary`, and `flashcards`.
- Preserved existing card rendering behavior and type-specific prompt/response shaping.
- Preserved review due-card filtering rules, including suspended-card skipping and queue building via `build_review_queue`.
- Preserved scheduler integration behavior (`get_scheduler`, `ScheduleInput`, target recall handling, graduation transitions, and debug payload visibility for admins).
- Preserved existing incident creation constraints and response semantics (including duplicate card ID conflict handling and safe note path checks).
- Preserved route-level HTTP status behavior by mapping service exceptions to `400`/`404` in route layers.

## Architecture and Design Choices

### 1) Introduce explicit learning service boundary
- What was done: Created `project/services/learning_service.py` and centralized all non-HTTP learning logic there.
- Why this approach was chosen: Learning logic previously lived in two route modules, causing duplication and drift risk.
- Trade-offs considered: A large shared module can grow quickly; however, centralization now reduces divergence and simplifies future extraction into smaller domain submodules.
- Key implementation details: New service functions now back both `project/learning/views.py` and `project/api/learning.py`.

### 2) Keep route modules as HTTP adapters
- What was done: Route modules now parse request payloads, resolve auth user context, call service functions, and translate service exceptions into HTTP responses.
- Why this approach was chosen: Keeps concerns separated (transport/protocol in routes, business logic in services).
- Trade-offs considered: Some lightweight validation remains in routes (for payload presence and integer casting) to keep error messaging and request parsing explicit.
- Key implementation details: Both routes call shared functions like `summarize_notes_for_user()`, `review_cards_for_user()`, `note_with_cards()`, `rate_card_for_user()`, and `create_incident_card()`.

### 3) Use typed service exceptions for predictable error mapping
- What was done: Added `ValidationError`, `NotFoundError`, and `ConflictError`.
- Why this approach was chosen: Gives web and API wrappers a clear contract for response code mapping while keeping service code HTTP-agnostic.
- Trade-offs considered: Adds a small exception taxonomy to maintain; in return, error behavior is clearer and reusable.
- Key implementation details: `rate_card_for_user()` raises `ValidationError` for invalid rating/card format and `NotFoundError` for missing cards; `create_incident_card()` raises `ValidationError` and `ConflictError`.

## Files Created

- `project/services/learning_service.py` — new shared learning business logic module.
- `project/api/learning.py` — API learning endpoints implemented as wrappers around service calls.
- `docs/notes/2026/2026-03-10__services-learning.md` — this implementation note.

## Files Modified

- `project/learning/views.py` — removed duplicated learning business logic and converted handlers to service delegation.

## API Contract

- N/A — no new API endpoints were introduced in this todo. Existing learning endpoints continue to return the same payload shapes, now backed by the shared service.

## Validation and Verification

1. Ran lint diagnostics via `ReadLints` on:
   - `project/services/learning_service.py`
   - `project/learning/views.py`
   - `project/api/learning.py`
   Result: no linter errors.
2. Ran syntax validation with:
   - `python -m py_compile project/services/learning_service.py project/learning/views.py project/api/learning.py`
   Result: success.
3. Attempted to run targeted tests:
   - `pytest tests/test_card_builder.py tests/test_queue_builder.py`
   - `python -m pytest tests/test_card_builder.py tests/test_queue_builder.py`
   Result: blocked in this environment because `pytest` is not installed.

## Known Gaps / Follow-ups

- Add/extend API and view tests that assert service-level parity across web and API entry points for learning flows.
- Split `learning_service.py` into smaller focused modules if complexity grows (for example: note IO, card rendering, review scheduling, and incident authoring).
- Install test tooling (`pytest`) in the active environment to enable local automated verification commands.

## How to Run (Current)

1. Start the Flask app in your normal local development environment.
2. Authenticate in either web UI session or API JWT flow.
3. Exercise learning features:
   - Web: visit learning index, note view, review view, and submit ratings/incidents.
   - API: call existing learning routes under `/api/v1/learning` (`/notes`, `/notes/<id>`, `/review`, `/rate`).
4. Confirm parity:
   - Due counts and review card ordering match expected behavior.
   - Rating updates persist scheduler fields and review logs.
   - Incident creation writes/updates note JSON safely.
