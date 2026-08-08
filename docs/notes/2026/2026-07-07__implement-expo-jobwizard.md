# Implement Mobile Jobwizard List/Create/Detail (`implement-expo-jobwizard`)

Date: 2026-07-07
Todo ID: `implement-expo-jobwizard`

## Objective

Add jobwizard job tracking to the Expo app — list, create, and detail flows — consuming the existing `/api/v1/jobwizard` endpoints. This is the last feature screen phase from the migration plan.

## Scope Delivered

- Typed jobwizard API client `mobile/src/lib/jobwizard-api.ts` covering `GET /jobwizard/jobs`, `POST /jobwizard/jobs`, and `GET /jobwizard/jobs/:id`, plus `jobwizardKeys` query keys and a `jobScreenshotUrl` helper.
- Job list screen `mobile/src/app/jobwizard/index.tsx`: job rows (title, company, posted date), pull-to-refresh, and a New Job button.
- Create screen `mobile/src/app/jobwizard/new.tsx`: title/company/listing-URL form with client-side required-field gating, duplicate-submit prevention, and a pending hint that screenshot capture can take a moment.
- Detail screen `mobile/src/app/jobwizard/[id].tsx`: job header, Open Original Listing button, and the S3 listing screenshot (tappable to open full-size).
- Navigation: `jobwizard/index`, `jobwizard/new`, and `jobwizard/[id]` registered in `mobile/src/app/_layout.tsx`; Jobwizard button added to the home hub in `mobile/src/app/index.tsx`.

## Prior Art / Context

- Screens follow the established feature pattern (`./2026-07-07__implement-expo-library.md`, `./2026-07-07__implement-expo-wishlist.md`): feature `*-api.ts` module with types mirroring the backend serializer, inline react-query in screens, auth redirect guard, and shared loading/error/empty conventions.
- The backend contract was already shipped and tested (`project/api/jobwizard.py`, `jobwizard_service.serialize_job`, `tests/test_api_jobwizard.py`); no backend changes were needed.

## Architecture and Design Choices

### 1) Inline form instead of a shared form component

- The wishlist create flow extracted `GiftForm` because it is reused by both create and edit screens and carries image-picker logic. Jobwizard has no edit endpoint and only three plain text fields, so the form lives directly in `new.tsx` — extracting a component would be premature abstraction.
- The submit button is disabled unless all three fields are non-empty and no mutation is in flight, mirroring the backend's `ValidationError` rule (`title, company_name, and listing_url are required`) and preventing duplicate submissions. Server-side validation errors still surface inline via the `ApiError` message.

### 2) Screenshot URL constructed client-side from the S3 bucket

- `serialize_job` returns `listing_image` as a bare S3 object key (e.g. `abc123.jpeg`), not a URL. The web template (`project/jobwizard/templates/job.html`) hardcodes `https://jobwizard-test.s3.amazonaws.com/<key>`, so `jobScreenshotUrl` replicates that same base URL. Jobs whose screenshot upload failed have an empty `listing_image` and the detail screen shows a "No screenshot available" note instead.
- A cleaner long-term fix is for the API to serialize a full `listing_image_url` derived from `JOBWIZARD_S3_BUCKET` (the bucket is currently hardcoded in two clients); noted as a follow-up rather than expanding this todo's scope to a backend contract change.

### 3) Create-then-return navigation with cache invalidation

- On successful create, the mutation invalidates `jobwizardKeys.jobs()` and pops back to the list (same flow as wishlist's new-gift screen). The screenshot render happens synchronously inside `POST /jobwizard/jobs` (ApiLeap capture + S3 upload before commit), so the create request can be slow — the form shows a "Capturing a screenshot…" hint while pending.

### 4) Numeric ID handling in the detail route

- Job IDs are integers (unlike library's string YouTube IDs). The detail screen converts the `[id]` route param with `Number(...)` and gates the query on `Number.isFinite`, keeping `jobwizardKeys.job(jobId)` numerically typed and consistent with the API module.

## Files Created

- `mobile/src/lib/jobwizard-api.ts`
- `mobile/src/app/jobwizard/index.tsx`
- `mobile/src/app/jobwizard/new.tsx`
- `mobile/src/app/jobwizard/[id].tsx`
- `docs/notes/2026/2026-07-07__implement-expo-jobwizard.md` (this note)

## Files Modified

- `mobile/src/app/_layout.tsx` — registered `jobwizard/index`, `jobwizard/new`, and `jobwizard/[id]` stack screens.
- `mobile/src/app/index.tsx` — added Jobwizard button to the home hub.

## API Contract

Consumed (all JWT Bearer, defined in `project/api/jobwizard.py`):

- `GET /api/v1/jobwizard/jobs` → `{"jobs": [{id, title, company_name, listing_url, listing_image, posted_date, user_id}]}`
- `POST /api/v1/jobwizard/jobs` with `{title, company_name, listing_url}` → 201 `{"job": {...}}`; 400 `{"error": "title, company_name, and listing_url are required"}`
- `GET /api/v1/jobwizard/jobs/<id>` → `{"job": {...}}`; 404 `{"error": "Job not found."}` (also for other users' jobs)

## Validation and Verification

1. `./node_modules/.bin/tsc --noEmit` in `mobile/` — clean (after `npx expo customize tsconfig.json` regenerated Expo Router typed routes to include the new `/jobwizard` routes).
2. `npx expo lint` in `mobile/` — clean.
3. No device/simulator end-to-end run in this pass; screens follow the same query/mutation patterns as the prior verified features against the tested API contract.

## Known Gaps / Follow-ups

- The S3 screenshot base URL (`jobwizard-test` bucket) is duplicated in the web template and the mobile client; the API should serialize a full screenshot URL from `JOBWIZARD_S3_BUCKET` instead.
- Creating a job blocks on the synchronous screenshot render server-side; without an `APILEAP_ACCESS_KEY`/S3 setup the create request fails or stores an empty `listing_image`.
- No edit or delete flows — the backend exposes no update/delete endpoints.
- Mobile unit tests remain deferred, consistent with prior feature phases.

## How to Run (Current)

1. Start the backend: `flask --app project run --port 5001 --debug`.
2. `cd mobile && npm install && npm start`, open a simulator, and sign in.
3. Tap Jobwizard on the home screen: jobs load from `GET /api/v1/jobwizard/jobs`.
4. Tap New Job, fill in title/company/listing URL, and submit; the job posts to `POST /api/v1/jobwizard/jobs` (screenshot capture requires `APILEAP_ACCESS_KEY` and `JOBWIZARD_S3_BUCKET` credentials) and appears in the list.
5. Tap a job to open its detail screen; Open Original Listing opens the URL, and the listing screenshot renders when one was captured.
